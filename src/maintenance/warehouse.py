"""Quản lý kho PostgreSQL và quy trình nạp dữ liệu từ gói CSV."""
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/maintenance_dw"
)

STAGING_TABLE_MAP = {
    "readings.csv": "stg_readings",
    "features.csv": "stg_features",
    "quality_flags.csv": "stg_quality_flags",
    "split_membership.csv": "stg_split_membership",
    "model_runs.csv": "stg_model_runs",
    "scores.csv": "stg_scores",
    "metrics.csv": "stg_metrics",
    "budget_metrics.csv": "stg_budget_metrics",
}


def get_engine(db_url: str = None):
    """Tạo SQLAlchemy engine từ db_url hoặc biến môi trường."""
    url = db_url or DEFAULT_DB_URL
    return create_engine(url, isolation_level="AUTOCOMMIT")


def execute_sql_file(engine, file_path: Path):
    """Đọc và thực thi toàn bộ script SQL từ file."""
    content = Path(file_path).read_text(encoding="utf-8")
    statements = [stmt.strip() for stmt in content.split(";") if stmt.strip()]
    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def load_csv_to_staging(engine, csv_path: Path, table_name: str):
    """Nạp file CSV vào bảng staging bằng PostgreSQL COPY để tối ưu tốc độ."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file CSV: {csv_path}")

    # Ưu tiên sử dụng lệnh COPY của PostgreSQL nếu là connection psycopg2
    try:
        raw_conn = engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            with open(csv_path, "r", encoding="utf-8") as f:
                cursor.copy_expert(f"COPY {table_name} FROM STDIN WITH CSV HEADER", f)
            raw_conn.commit()
            return
        finally:
            raw_conn.close()
    except Exception:
        # Fallback bằng pandas nếu không dùng được COPY trực tiếp
        df = pd.read_csv(csv_path)
        df.to_sql(name=table_name, con=engine, if_exists="append", index=False)


def load_all_staging(engine, handoff_dir: Path):
    """Nạp lần lượt 8 bảng CSV từ handoff_dir vào 8 bảng staging."""
    handoff_dir = Path(handoff_dir)
    results = {}
    for filename, table_name in STAGING_TABLE_MAP.items():
        csv_file = handoff_dir / filename
        load_csv_to_staging(engine, csv_file, table_name)
        with engine.connect() as conn:
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            results[table_name] = row_count
    return results


def run_full_etl(engine, sql_dir: Path, handoff_dir: Path):
    """Quy trình ETL hoàn chỉnh: Tạo staging -> Tạo Star Schema -> Nạp Staging -> Transform Load."""
    sql_dir = Path(sql_dir)
    handoff_dir = Path(handoff_dir)

    # 1. Tạo bảng Staging
    execute_sql_file(engine, sql_dir / "01-staging.sql")

    # 2. Tạo mô hình Star Schema
    execute_sql_file(engine, sql_dir / "02-star-schema.sql")

    # 3. Nạp dữ liệu vào Staging
    staging_counts = load_all_staging(engine, handoff_dir)

    # 4. Chuyển đổi và nạp vào Star Schema
    execute_sql_file(engine, sql_dir / "03-transform-load.sql")

    return staging_counts


def run_reconciliation(engine):
    """Chạy các kiểm tra đối soát và trả về kết quả chi tiết."""
    results = {"checks": [], "all_passed": True}
    with engine.connect() as conn:
        # Kiểm tra 1: Tổng số dòng các bảng chính
        r_readings = conn.execute(text("SELECT COUNT(*) FROM fact_reading")).scalar()
        r_scores = conn.execute(text("SELECT COUNT(*) FROM fact_model_score")).scalar()
        r_runs = conn.execute(text("SELECT COUNT(*) FROM dim_model_run")).scalar()
        r_budgets = conn.execute(text("SELECT COUNT(*) FROM agg_budget_metrics")).scalar()
        r_failures = conn.execute(text("""
            SELECT SUM(fp.machine_failure)
            FROM fact_reading r
            JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key
        """)).scalar()

        results["checks"].append({
            "name": "fact_reading count", "actual": r_readings, "expected": 10000, "pass": r_readings == 10000
        })
        results["checks"].append({
            "name": "fact_model_score count", "actual": r_scores, "expected": 78000, "pass": r_scores == 78000
        })
        results["checks"].append({
            "name": "dim_model_run count", "actual": r_runs, "expected": 20, "pass": r_runs == 20
        })
        results["checks"].append({
            "name": "agg_budget_metrics count", "actual": r_budgets, "expected": 120, "pass": r_budgets == 120
        })
        results["checks"].append({
            "name": "total machine failures", "actual": r_failures, "expected": 339, "pass": r_failures == 339
        })

        # Kiểm tra 2: Tập Test chính seed 42 Top-50
        q_top50 = conn.execute(text("""
            SELECT m.model_family,
                   SUM(CASE WHEN s.priority_rank <= 50 THEN fp.machine_failure ELSE 0 END) AS tp_50
            FROM fact_model_score s
            JOIN dim_model_run m ON s.model_run_id = m.model_run_id
            JOIN fact_reading r ON s.reading_id = r.reading_id
            JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key
            WHERE s.split_id = 'ordered-gap100-v1'
              AND s.partition = 'test'
              AND m.seed = 42
              AND m.model_family IN ('logistic_regression', 'isolation_forest')
            GROUP BY m.model_family
        """)).fetchall()

        for row in q_top50:
            family, tp_50 = row[0], row[1]
            exp = 21 if family == "logistic_regression" else 13
            results["checks"].append({
                "name": f"top50_tp_{family}", "actual": tp_50, "expected": exp, "pass": tp_50 == exp
            })

        # Kiểm tra 3: Ngưỡng validation cố định
        q_matrix = conn.execute(text("""
            SELECT m.model_family,
                   SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) AS tp,
                   SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) AS fp,
                   SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) AS fn,
                   SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) AS tn
            FROM fact_model_score s
            JOIN dim_model_run m ON s.model_run_id = m.model_run_id
            JOIN fact_reading r ON s.reading_id = r.reading_id
            JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key
            WHERE s.split_id = 'ordered-gap100-v1'
              AND s.partition = 'test'
              AND m.seed = 42
              AND m.model_family IN ('logistic_regression', 'isolation_forest')
            GROUP BY m.model_family
        """)).fetchall()

        for row in q_matrix:
            family, tp, fp, fn, tn = row[0], row[1], row[2], row[3], row[4]
            if family == "logistic_regression":
                is_ok = (tp == 10 and fp == 1 and fn == 28 and tn == 1861)
                results["checks"].append({
                    "name": "matrix_logistic_regression",
                    "actual": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
                    "expected": {"tp": 10, "fp": 1, "fn": 28, "tn": 1861},
                    "pass": is_ok
                })
            elif family == "isolation_forest":
                is_ok = (tp == 13 and fp == 25 and fn == 25 and tn == 1837)
                results["checks"].append({
                    "name": "matrix_isolation_forest",
                    "actual": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
                    "expected": {"tp": 13, "fp": 25, "fn": 25, "tn": 1837},
                    "pass": is_ok
                })

    results["all_passed"] = all(c["pass"] for c in results["checks"])
    return results

