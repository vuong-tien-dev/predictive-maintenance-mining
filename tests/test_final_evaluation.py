"""Kiểm tra khóa quyết định, phân tích nhóm và bootstrap tái lập."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.final_evaluation import block_bootstrap, decision_view, error_groups


class FinalEvaluationTests(unittest.TestCase):
    def test_threshold_locked_but_binary_hash_can_vary(self):
        lock = {"settings": {"budgets": [20, 50, 100]}, "selection_digests": {"a": "old"},
                "runs": [{"threshold": .5, "model_sha256": "old", "score_sha256": "same"}]}
        other = copy.deepcopy(lock)
        other["selection_digests"]["a"] = "new"
        other["runs"][0]["model_sha256"] = "new"
        self.assertEqual(decision_view(lock), decision_view(other))
        other["runs"][0]["threshold"] = .6
        self.assertNotEqual(decision_view(lock), decision_view(other))
        self.assertEqual(lock["runs"][0]["model_sha256"], "old")

    def test_paired_bootstrap_reproducible_and_zero_difference(self):
        y = np.tile([0, 1, 0, 0], 10)
        scores = np.linspace(.1, .9, len(y))
        kwargs = dict(repeats=30, block_rows=4, seed=42)
        first = block_bootstrap(y, {"isolation_forest": scores, "logistic_regression": scores}, **kwargs)
        second = block_bootstrap(y, {"isolation_forest": scores, "logistic_regression": scores}, **kwargs)
        pd.testing.assert_frame_equal(first, second)
        delta = first.loc[first.model_family.eq("LR_minus_IF")].iloc[0]
        self.assertEqual(delta.lower_percentile_2_5, 0)
        self.assertEqual(delta.upper_percentile_97_5, 0)

    def test_empty_positive_resamples_are_unavailable_not_zero(self):
        table = block_bootstrap(np.zeros(10), {"a": np.arange(10)}, repeats=10, block_rows=2)
        self.assertTrue(table.valid_resamples.eq(0).all())
        self.assertTrue(table.lower_percentile_2_5.isna().all())

    def test_group_top50_is_global_not_reranked(self):
        frame = pd.DataFrame({"product_type": ["L", "M", "H"], "twf": [1, 0, 0],
            "hdf": [0, 0, 0], "pwf": [0, 0, 0], "osf": [1, 0, 0], "rnf": [0, 0, 0]})
        result = pd.DataFrame(error_groups(frame, np.array([1, 1, 0]), np.array([0, 1, 0]), np.array([False, True, False]))).set_index("group")
        self.assertEqual(result.loc["Type=L", "global_top50_hits"], 0)
        self.assertEqual(result.loc["Type=M", "global_top50_hits"], 1)
        self.assertEqual(result.loc["mode=twf", "fn"], 1)
        self.assertTrue(pd.isna(result.loc["Type=H", "recall"]))


if __name__ == "__main__":
    unittest.main()
