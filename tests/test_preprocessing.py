"""Kiểm tra đơn vị vật lý, tách nhãn và không học thống kê từ validation."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.base import clone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from maintenance.features import make_preprocessor, physical_features, select_inputs


class PreprocessingTests(unittest.TestCase):
    def setUp(self):
        self.inputs = pd.DataFrame({"product_type": ["L", "M"],
            "air_temperature_k": [300., 302.], "process_temperature_k": [310., 314.],
            "rotational_speed_rpm": [60, 120], "torque_nm": [2., 4.], "tool_wear_min": [3, 7]})

    def test_formulas_units_index_and_source_preserved(self):
        self.inputs.index = [20, 7]
        before = self.inputs.copy(deep=True)
        result = physical_features(self.inputs)
        np.testing.assert_allclose(result["power_w"], [4*np.pi, 16*np.pi])
        np.testing.assert_allclose(result["temperature_difference_k"], [10, 12])
        np.testing.assert_allclose(result["wear_torque_min_nm"], [6, 28])
        self.assertEqual(list(result.index), [20, 7])
        pd.testing.assert_frame_equal(self.inputs, before)

    def test_labels_and_ids_cannot_enter_transformer(self):
        extra = self.inputs.assign(machine_failure=[1, 0], reading_id=[1, 2])
        with self.assertRaises(ValueError):
            make_preprocessor().fit(extra)
        pd.testing.assert_frame_equal(select_inputs(extra), self.inputs)

    def test_scaler_is_train_only_and_categories_are_schema_defined(self):
        pipeline = make_preprocessor("base")
        pipeline.fit(self.inputs)
        scaler = pipeline.named_steps["encode"].named_transformers_["numeric"]
        before = scaler.mean_.copy()
        validation = self.inputs.iloc[[0]].copy()
        validation["product_type"] = "H"  # category absent in train, present in schema
        validation["air_temperature_k"] = 1000.
        result = pipeline.transform(validation)
        self.assertEqual(result.shape, (1, 8))
        self.assertAlmostEqual(result[0, 0], 699.)  # (1000 - train mean 301) / std 1
        np.testing.assert_array_equal(scaler.mean_, before)
        np.testing.assert_array_equal(result[0, -3:], [0, 0, 1])
        self.assertEqual(clone(pipeline).get_params()["features__feature_set"], "base")

    def test_missing_unknown_nonfinite_or_fractional_integer_fail(self):
        for col, value in [("product_type", "X"), ("torque_nm", np.nan),
                           ("process_temperature_k", np.inf), ("tool_wear_min", 1.5)]:
            with self.subTest(col=col):
                invalid = self.inputs.copy().astype({"tool_wear_min": "float64"})
                invalid.loc[0, col] = value
                with self.assertRaises(ValueError):
                    physical_features(invalid)

    def test_base_physical_and_scaling_disabled_shapes(self):
        for feature_set, size in [("base", 8), ("physical", 11)]:
            pipeline = make_preprocessor(feature_set, scale_numeric=False)
            values = pipeline.fit_transform(self.inputs)
            self.assertEqual(values.shape, (2, size))
            self.assertEqual(len(pipeline.get_feature_names_out()), size)
            self.assertEqual(values[0, 0], 300.)


if __name__ == "__main__":
    unittest.main()
