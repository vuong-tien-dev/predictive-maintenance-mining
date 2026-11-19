"""Chấm test bằng model/ngưỡng đã khóa; không huấn luyện hoặc chọn lại."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from maintenance.final_evaluation import run_final_evaluation

if __name__ == "__main__":
    result = run_final_evaluation(ROOT)
    print("Test runs:", result["runs_evaluated"], "refit:", result["refit"])
