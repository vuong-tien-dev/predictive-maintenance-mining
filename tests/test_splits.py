"""Split phải tái tạo được, không chồng lấp và không tự mở test."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.splits import assign_split, export_splits, load_partition, validate_mapping


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.readings = pd.DataFrame({"dataset_version": ["sha256:synthetic"]*100,
            "reading_id": np.arange(101, 201), "machine_failure": np.arange(100) % 2,
            "product_type": ["L"]*100, "air_temperature_k": [300.]*100,
            "process_temperature_k": [310.]*100, "rotational_speed_rpm": [1500]*100,
            "torque_nm": [40.]*100, "tool_wear_min": [10]*100})
        self.spec = {"split_id": "test-ordered", "method": "source_order", "gap_rows": 2}

    def test_source_order_boundaries_and_label_invariance(self):
        mapping = assign_split(self.readings, self.spec)
        validate_mapping(mapping, self.readings)
        self.assertEqual(mapping.split.value_counts().to_dict(), {"train": 60, "validation": 18, "test": 18, "gap": 4})
        self.assertEqual(mapping.loc[mapping.split.eq("validation"), "source_position"].min(), 63)
        self.assertEqual(mapping.loc[mapping.split.eq("test"), "source_position"].min(), 83)
        changed = self.readings.copy()
        changed.machine_failure = 1-changed.machine_failure
        pd.testing.assert_frame_equal(mapping, assign_split(changed, self.spec))

    def test_random_is_reproducible_and_covers_all_rows_once(self):
        spec = {"split_id": "test-random", "method": "stratified_random", "gap_rows": 0}
        first = assign_split(self.readings, spec)
        pd.testing.assert_frame_equal(first, assign_split(self.readings, spec))
        self.assertFalse(first.equals(assign_split(self.readings, spec, seed=43)))
        validate_mapping(first, self.readings)
        self.assertEqual(first.split.value_counts().to_dict(), {"train": 60, "validation": 20, "test": 20})

    def test_duplicate_keys_missing_rows_and_wrong_version_fail(self):
        bad = self.readings.copy()
        bad.loc[1, "reading_id"] = bad.loc[0, "reading_id"]
        with self.assertRaises(ValueError): assign_split(bad, self.spec)
        mapping = assign_split(self.readings, self.spec)
        with self.assertRaises(ValueError): validate_mapping(mapping.iloc[:-1], self.readings)
        mapping.loc[0, "dataset_version"] = "wrong"
        with self.assertRaises(ValueError): validate_mapping(mapping, self.readings)
        with self.assertRaises(ValueError): assign_split(self.readings, {**self.spec, "gap_rows": 20})

    def test_export_load_and_hash_protection(self):
        config = {"version": "synthetic", "primary": self.spec["split_id"], "seed": 42,
                  "ratios": [.6, .2, .2], "protocols": [self.spec]}
        with tempfile.TemporaryDirectory(dir=ROOT/".tmp") as folder:
            root = Path(folder)
            (root/"configs").mkdir()
            (root/"configs/splits.json").write_text(json.dumps(config), encoding="utf-8")
            with patch("maintenance.splits.prepare_tables", return_value=({"readings": self.readings}, {})):
                first = export_splits(root)
                self.assertEqual(first, export_splits(root))
                (root/"configs/splits.json").write_bytes(json.dumps(config, indent=2).replace("\n", "\r\n").encode())
                train = load_partition(root, self.spec["split_id"], "train")
                self.assertEqual(train["X"].shape, (60, 6))
                self.assertNotIn("machine_failure", train["X"])
                with self.assertRaises(ValueError): load_partition(root, self.spec["split_id"], "test")
                test = load_partition(root, self.spec["split_id"], "test", allow_test=True)
                self.assertEqual(len(test["y"]), 18)
                path = root/first["files"][0]["path"]
                path.write_text("corrupted", encoding="utf-8")
                with self.assertRaises(ValueError): load_partition(root, self.spec["split_id"], "train")
                with self.assertRaises(ValueError): export_splits(root)


if __name__ == "__main__":
    unittest.main()
