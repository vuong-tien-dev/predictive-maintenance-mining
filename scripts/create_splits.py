"""Tạo ánh xạ split cố định và bảng đếm; không fit mô hình."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from maintenance.splits import export_splits

if __name__ == "__main__":
    print(json.dumps(export_splits(ROOT), ensure_ascii=True, indent=2))
