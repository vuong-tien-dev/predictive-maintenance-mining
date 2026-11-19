"""Script thực thi toàn bộ quy trình ETL nạp Kho Dữ liệu PostgreSQL."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maintenance.warehouse import get_engine, run_full_etl


def main():
    parser = argparse.ArgumentParser(description="ETL nạp dữ liệu handoff-v1 vào Kho PostgreSQL.")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/maintenance_dw"),
        help="Chuỗi kết nối SQLAlchemy tới PostgreSQL."
    )
    parser.add_argument(
        "--handoff-dir",
        default=str(ROOT / "data/processed/handoff-v1"),
        help="Thư mục chứa 8 bảng CSV handoff-v1."
    )
    parser.add_argument(
        "--sql-dir",
        default=str(ROOT / "sql"),
        help="Thư mục chứa các script SQL."
    )
    args = parser.parse_args()

    print(f"Connecting to database: {args.db_url}")
    engine = get_engine(args.db_url)

    print("Running Full ETL Pipeline...")
    counts = run_full_etl(engine, Path(args.sql_dir), Path(args.handoff_dir))

    print("\n--- Staging Row Counts Loaded ---")
    for table, count in counts.items():
        print(f"  {table:24s}: {count:6d} rows")

    print("\nStar Schema transformation & load completed successfully!")


if __name__ == "__main__":
    main()

