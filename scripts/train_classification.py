"""Huấn luyện/chọn Logistic Regression trên validation, không nạp test."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.classification import run_classification

if __name__ == "__main__":
    manifest = run_classification(ROOT)
    for choice in manifest["selections"]:
        print(choice["split_id"], choice["candidate_id"])
    print("Classification validation complete; test_evaluated=False")
