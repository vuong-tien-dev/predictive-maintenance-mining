"""Kiểm tra hợp đồng điểm, khóa/rank và phát hiện thay đổi file bàn giao."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.handoff import validate_scores, verify_handoff


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.readings = pd.DataFrame({"dataset_version": ["v"]*4, "reading_id": [1, 2, 3, 4]})
        self.runs = pd.DataFrame([{"model_run_id": "r", "split_id": "s", "model_family": "example",
                                   "feature_set": "base", "threshold": .5}])
        self.mapping = self.readings.assign(split_id="s", split=["validation", "validation", "test", "test"])
        self.scores = self.readings.assign(model_run_id="r", split_id="s",
            split=["validation", "validation", "test", "test"], model_family="example", feature_set="base",
            priority_score=[.7, .2, .8, .1], predicted_failure=[1, 0, 1, 0], priority_rank=[1, 2, 1, 2])

    def test_valid_coverage_and_corruptions(self):
        validate_scores(self.scores, self.readings, self.runs, self.mapping)
        for column, value in [("priority_rank", 2), ("predicted_failure", 0), ("split_id", "wrong")]:
            with self.subTest(column=column):
                bad = self.scores.copy()
                bad.loc[0, column] = value
                with self.assertRaises(ValueError): validate_scores(bad, self.readings, self.runs, self.mapping)
        with self.assertRaises(ValueError): validate_scores(self.scores.iloc[:-1], self.readings, self.runs, self.mapping)

    def test_changed_csv_is_not_accepted(self):
        with tempfile.TemporaryDirectory(dir=ROOT/".tmp") as folder:
            root = Path(folder)
            (root/"data/metadata").mkdir(parents=True)
            data = root/"sample.csv"
            data.write_bytes(b"id,value\n1,3\n")
            manifest = {"files": [{"table": "example", "path": "sample.csv", "rows": 1,
                "primary_key": ["id"], "sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
                "columns": [{"name": "id"}, {"name": "value"}]}]}
            (root/"data/metadata/handoff.json").write_text(json.dumps(manifest), encoding="utf-8")
            verify_handoff(root)
            data.write_bytes(b"id,value\n1,4\n")
            with self.assertRaises(ValueError): verify_handoff(root)


if __name__ == "__main__":
    unittest.main()
