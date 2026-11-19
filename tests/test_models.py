"""Kiểm chứng chiều điểm, ngưỡng/đồng hạng, chỉ số và baseline không nhãn."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.evaluation import (binary_counts, choose_threshold, random_priority,
                                    ranking_order, score_metrics)
from maintenance.models import anomaly_score, make_isolation


class EvaluationTests(unittest.TestCase):
    def test_counts_and_auc_use_continuous_score(self):
        result = score_metrics([0, 1, 0, 1], [.1, .9, .8, .7], [4, 3, 2, 1], .75, [2, 5])
        self.assertEqual([result[k] for k in ['tn', 'fp', 'fn', 'tp']], [1, 1, 1, 1])
        self.assertEqual(result['precision'], .5)
        self.assertEqual(result['recall'], .5)
        self.assertEqual(result['f1'], .5)
        self.assertEqual(result['roc_auc'], .75)
        self.assertEqual(result['precision_at_2'], .5)
        self.assertIsNone(result['precision_at_5'])

    def test_tie_ranking_and_best_threshold(self):
        np.testing.assert_array_equal(ranking_order([.8, .8, .1], [9, 2, 1]), [1, 0, 2])
        y, scores = np.array([1, 0, 0, 1]), np.array([.9, .8, .2, .1])
        threshold = choose_threshold(y, scores)
        candidates = [(f1_score(y, scores >= t), t) for t in np.unique(scores)]
        self.assertEqual(threshold, max(candidates)[1])

    def test_undefined_metrics_and_invalid_inputs(self):
        result = score_metrics([0, 0], [.1, .2], [1, 2], 1., [1])
        for name in ['precision', 'recall', 'f1', 'roc_auc', 'average_precision']:
            self.assertIsNone(result[name])
        self.assertFalse(result['precision_defined'])
        with self.assertRaises(ValueError): choose_threshold([0, 0], [.1, .2])
        with self.assertRaises(ValueError): score_metrics([0, 2], [.1, .2], [1, 2], .1)
        with self.assertRaises(ValueError): ranking_order([.1, .2], [1, 1])
        with self.assertRaises(ValueError): binary_counts([0, 1], [0])

    def test_random_baseline_ignores_labels_and_row_order(self):
        keys = pd.DataFrame({'dataset_version': ['synthetic']*3, 'reading_id': [1, 2, 3]})
        a = random_priority(keys.assign(machine_failure=[0, 1, 0]), 42)
        np.testing.assert_array_equal(a, random_priority(keys.assign(machine_failure=[1, 0, 1]), 42))
        np.testing.assert_array_equal(a[::-1], random_priority(keys.iloc[::-1], 42))
        self.assertFalse(np.array_equal(a, random_priority(keys, 43)))

    def test_isolation_fits_without_y_and_sign_is_inverted_once(self):
        rng = np.random.default_rng(42)
        X = pd.DataFrame({'product_type': ['L']*200, 'air_temperature_k': rng.normal(300, 1, 200),
            'process_temperature_k': rng.normal(310, 1, 200), 'rotational_speed_rpm': rng.integers(1400, 1600, 200),
            'torque_nm': rng.normal(40, 2, 200), 'tool_wear_min': rng.integers(0, 50, 200)})
        model = make_isolation('base', 64, 42, n_estimators=30)
        model.fit(X)
        scores = anomaly_score(model, X)
        np.testing.assert_allclose(scores, -model.score_samples(X))
        second = make_isolation('base', 64, 42, n_estimators=30).fit(X)
        np.testing.assert_array_equal(scores, anomaly_score(second, X))
        self.assertEqual(model.named_steps['model'].n_features_in_, 8)


if __name__ == '__main__':
    unittest.main()
