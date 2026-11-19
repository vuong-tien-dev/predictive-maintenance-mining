"""Kiểm tra các lỗi có thể làm sai bằng chứng chất lượng dữ liệu."""
from pathlib import Path
import json
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from maintenance.quality import audit_columns, label_diagnostics, typed_view


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "configs/ai4i-schema.json").read_text(encoding="utf-8"))
        self.frame = pd.DataFrame([{
            "reading_id": "1", "product_id": "M1", "product_type": "M",
            "air_temperature_k": "298.1", "process_temperature_k": "308.6",
            "rotational_speed_rpm": "1551", "torque_nm": "42.8", "tool_wear_min": "0",
            "machine_failure": "0", "twf": "0", "hdf": "0", "pwf": "0", "osf": "0", "rnf": "0"}])

    def test_corruption_is_reported_not_silently_fixed(self):
        self.frame.loc[0, ["air_temperature_k", "torque_nm", "rotational_speed_rpm",
                           "product_type", "machine_failure"]] = ["", "inf", "1.5", "X", "2"]
        report = audit_columns(self.frame, self.schema).set_index("column")
        self.assertEqual(report.loc["air_temperature_k", "missing"], 1)
        self.assertEqual(report.loc["torque_nm", "invalid_type"], 1)
        self.assertEqual(report.loc["rotational_speed_rpm", "invalid_type"], 1)
        self.assertEqual(report.loc["product_type", "invalid_domain"], 1)
        self.assertEqual(report.loc["machine_failure", "invalid_domain"], 1)
        with self.assertRaises(ValueError):
            typed_view(self.frame, self.schema)

    def test_valid_extreme_values_are_not_trimmed(self):
        self.frame.loc[0, "torque_nm"] = "1000000"
        before = self.frame.copy(deep=True)
        result = typed_view(self.frame, self.schema)
        self.assertEqual(result.loc[0, "torque_nm"], 1000000)
        pd.testing.assert_frame_equal(self.frame, before)

    def test_label_disagreement_and_overlap_are_distinct(self):
        data = pd.DataFrame({"reading_id": [1, 2, 3, 4], "machine_failure": [1, 0, 1, 0],
                             "twf": [0, 1, 1, 0], "hdf": [0, 0, 1, 0]})
        before = data.copy(deep=True)
        summary, flags = label_diagnostics(data, ["twf", "hdf"])
        self.assertEqual(summary, {"failure_without_mode": 1,
                                  "mode_without_failure": 1, "multiple_modes": 1})
        self.assertEqual(list(flags["reading_id"]), [1, 2, 3])
        pd.testing.assert_frame_equal(data, before)


if __name__ == "__main__":
    unittest.main()
