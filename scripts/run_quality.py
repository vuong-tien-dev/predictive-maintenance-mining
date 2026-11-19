"""Chạy kiểm tra/EDA từ gốc repository bằng môi trường Python dự án."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maintenance.quality import analyze, export_analysis, plot_analysis


if __name__ == "__main__":
    result = analyze(ROOT)
    export_analysis(result, ROOT)
    plot_analysis(result, ROOT)
    print(json.dumps(result["summary"], ensure_ascii=True, indent=2))
