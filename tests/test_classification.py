"""Kiểm chứng nhãn lớp dương, fit có nhãn và scaling không học validation."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.classification import make_classifier, positive_score


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        n = 100
        self.X = pd.DataFrame({"product_type": np.where(np.arange(n)%2, "M", "L"),
            "air_temperature_k": np.linspace(298, 302, n), "process_temperature_k": np.linspace(308, 312, n),
            "rotational_speed_rpm": np.arange(1400, 1500), "torque_nm": np.linspace(20, 60, n),
            "tool_wear_min": np.arange(n)})
        self.y = (np.arange(n) >= 70).astype(int)

    def test_positive_class_column_is_not_assumed(self):
        fake = SimpleNamespace(classes_=np.array([1, 0]), predict_proba=lambda X: np.array([[.8, .2]]))
        np.testing.assert_array_equal(positive_score(fake, self.X.iloc[:1]), [.8])
        fake.classes_ = np.array([0, 2])
        with self.assertRaises(ValueError): positive_score(fake, self.X.iloc[:1])

    def test_labels_affect_fit_and_seed_is_reproducible(self):
        first = make_classifier("base", .1, None).fit(self.X, self.y)
        second = make_classifier("base", .1, None).fit(self.X, self.y)
        opposite = make_classifier("base", .1, None).fit(self.X, 1-self.y)
        a = positive_score(first, self.X)
        np.testing.assert_allclose(a, positive_score(second, self.X), rtol=1e-12)
        np.testing.assert_allclose(a, 1-positive_score(opposite, self.X), atol=1e-10)
        self.assertTrue(np.isfinite(a).all() and ((a >= 0) & (a <= 1)).all())

    def test_scaler_fit_only_train_and_no_labels_as_features(self):
        model = make_classifier("physical", 1., "balanced").fit(self.X, self.y)
        encoder = model.named_steps["preprocess"].named_steps["encode"]
        scaler = encoder.named_transformers_["numeric"]
        before = scaler.mean_.copy()
        self.assertAlmostEqual(before[0], self.X.air_temperature_k.mean())
        validation = self.X.iloc[:2].copy()
        validation.air_temperature_k = 1000.
        positive_score(model, validation)
        np.testing.assert_array_equal(before, scaler.mean_)
        self.assertEqual(model.named_steps["model"].n_features_in_, 11)
        with self.assertRaises(ValueError):
            model.predict_proba(validation.assign(machine_failure=[1, 0]))

    def test_one_class_train_is_rejected(self):
        with self.assertRaises(ValueError):
            make_classifier("base", 1., None).fit(self.X, np.zeros(len(self.X)))


if __name__ == "__main__":
    unittest.main()
