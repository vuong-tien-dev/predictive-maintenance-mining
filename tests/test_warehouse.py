"""Bộ kiểm thử đơn vị cho module kho dữ liệu và các script SQL."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
HANDOFF_METADATA = ROOT / "data/metadata/handoff.json"

from maintenance.warehouse import STAGING_TABLE_MAP


class WarehouseTests(unittest.TestCase):
    def test_sql_files_exist_and_not_empty(self):
        """Tất cả 5 file SQL phải tồn tại và có dung lượng hợp lệ."""
        expected_files = [
            "01-staging.sql",
            "02-star-schema.sql",
            "03-transform-load.sql",
            "04-olap.sql",
            "05-reconciliation.sql",
        ]
        for name in expected_files:
            file_path = SQL_DIR / name
            self.assertTrue(file_path.exists(), f"Thiếu file SQL: {name}")
            content = file_path.read_text(encoding="utf-8")
            self.assertGreater(len(content.strip()), 100, f"File {name} quá ngắn hoặc rỗng.")

    def test_staging_map_completeness(self):
        """Bản đồ staging phải bao phủ đủ 8 file CSV trong manifest handoff."""
        self.assertTrue(HANDOFF_METADATA.exists())
        manifest = json.loads(HANDOFF_METADATA.read_text(encoding="utf-8"))
        csv_tables = {Path(f["path"]).name for f in manifest["files"]}
        self.assertEqual(len(csv_tables), 8)
        for csv_name in csv_tables:
            self.assertIn(csv_name, STAGING_TABLE_MAP, f"Thiếu ánh xạ staging cho {csv_name}")

    def test_staging_ddl_matches_manifest_columns(self):
        """Các cột khai báo trong 01-staging.sql phải chứa đủ tên cột trong manifest."""
        manifest = json.loads(HANDOFF_METADATA.read_text(encoding="utf-8"))
        staging_sql = (SQL_DIR / "01-staging.sql").read_text(encoding="utf-8").lower()
        for f in manifest["files"]:
            for col in f["columns"]:
                self.assertIn(
                    col["name"].lower(),
                    staging_sql,
                    f"Cột {col['name']} của bảng {f['table']} không xuất hiện trong 01-staging.sql"
                )

    def test_star_schema_tables_present(self):
        """Star schema phải chứa đủ 4 Dimensions, 2 Facts và 1 Agg Table."""
        star_sql = (SQL_DIR / "02-star-schema.sql").read_text(encoding="utf-8").lower()
        required_tables = [
            "dim_product_type",
            "dim_dataset_version",
            "dim_failure_pattern",
            "dim_model_run",
            "fact_reading",
            "fact_model_score",
            "agg_budget_metrics",
        ]
        for tbl in required_tables:
            self.assertIn(f"create table {tbl}", star_sql, f"Thiếu DDL CREATE TABLE cho {tbl}")

    def test_olap_queries_contain_all_four_scenarios(self):
        """04-olap.sql phải chứa đủ 4 kịch bản phân tích nghiệp vụ."""
        olap_sql = (SQL_DIR / "04-olap.sql").read_text(encoding="utf-8").lower()
        self.assertIn("agg_budget_metrics", olap_sql)  # OLAP 1
        self.assertIn("dim_product_type", olap_sql)    # OLAP 2
        self.assertIn("avg(s.priority_score)", olap_sql)  # OLAP 3
        self.assertIn("dim_failure_pattern", olap_sql) # OLAP 4


if __name__ == "__main__":
    unittest.main()

