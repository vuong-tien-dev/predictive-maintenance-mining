"""Xuất hoặc xác minh bộ CSV bàn giao; không sửa model hoặc chọn lại test."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.handoff import export_handoff, verify_handoff

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = verify_handoff(ROOT) if args.verify_only else export_handoff(ROOT)
    for entry in manifest["files"]:
        print(entry["table"], entry["rows"])
    print("Handoff verified:", manifest["version"])
