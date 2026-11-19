"""Script đối soát tự động toàn bộ số liệu Kho Dữ liệu PostgreSQL với tiêu chí nghiệm thu."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maintenance.warehouse import get_engine, run_reconciliation


def main():
    parser = argparse.ArgumentParser(description="Đối soát số liệu Kho PostgreSQL.")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/maintenance_dw"),
        help="Chuỗi kết nối SQLAlchemy tới PostgreSQL."
    )
    args = parser.parse_args()

    print(f"Connecting to database for reconciliation: {args.db_url}")
    engine = get_engine(args.db_url)

    res = run_reconciliation(engine)
    print("\n================== RECONCILIATION REPORT ==================")
    for check in res["checks"]:
        status = "[PASS]" if check["pass"] else "[FAIL]"
        print(f"{status} {check['name']:32s} | Actual: {check['actual']} | Expected: {check['expected']}")

    print("===========================================================")
    if res["all_passed"]:
        print("ALL RECONCILIATION CHECKS PASSED PERFECTLY (100% MATCH)!")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED! Please review the discrepancies above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

