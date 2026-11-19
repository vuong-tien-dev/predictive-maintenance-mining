"""Kiểm tra mẫu số mode và top-k toàn quần thể trong hậu kiểm HDF."""
import importlib.util
from pathlib import Path
import unittest

import pandas as pd

SPEC = importlib.util.spec_from_file_location("audit_hdf_v1", Path(__file__).resolve().parents[1]/"scripts/audit_hdf_v1.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HdfSupplementTests(unittest.TestCase):
    def test_global_topk_not_topk_inside_hdf(self):
        frame = pd.DataFrame({"reading_id": [3, 2, 1], "priority_score": [.9, .8, .8], "hdf": [0, 1, 1]})
        result = MODULE.hdf_policy_counts(frame, .85, 1)
        self.assertEqual((result["n_hdf"], result["hdf_found"], result["hdf_missed"]), (2, 0, 2))
        self.assertEqual(MODULE.hdf_policy_counts(frame, .85, 2)["hdf_found"], 1)
        self.assertEqual(MODULE.hdf_policy_counts(frame, .8)["hdf_recall"], 1)

    def test_absent_mode_is_undefined_not_zero(self):
        frame = pd.DataFrame({"reading_id": [1], "priority_score": [.5], "hdf": [0]})
        result = MODULE.hdf_policy_counts(frame, .4)
        self.assertIsNone(result["hdf_recall"])
        self.assertFalse(result["hdf_recall_defined"])


if __name__ == "__main__":
    unittest.main()
