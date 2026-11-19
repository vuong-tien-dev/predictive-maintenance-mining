"""Tái tạo bảng chuẩn hóa và ba biến vật lý; không fit trên toàn dữ liệu."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from maintenance.preprocessing import export_prepared


if __name__ == "__main__":
    print(json.dumps(export_prepared(ROOT), ensure_ascii=True, indent=2))
