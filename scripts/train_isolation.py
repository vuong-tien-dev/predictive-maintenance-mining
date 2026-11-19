"""Tái lập lựa chọn Isolation Forest và baseline trên validation; không mở test."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.models import run_isolation

if __name__ == "__main__":
    manifest = run_isolation(ROOT)
    for selection in manifest["selections"]:
        print(selection["split_id"], selection["candidate_id"])
    print("Validation complete; test_evaluated=False")
