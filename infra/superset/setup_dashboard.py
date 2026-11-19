"""Script thiết lập toàn bộ Datasets, Charts và Dashboard trong Apache Superset.

Lưu ý môi trường thực thi:
- Thư viện `superset` chỉ tồn tại bên trong Docker container `pm_superset`.
- Khi chạy trực tiếp từ máy host (Windows: `python infra/superset/setup_dashboard.py`),
  script sẽ tự động phát hiện và chuyển tiếp lệnh thực thi vào Docker container `pm_superset`.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

# Đảm bảo mã hóa console UTF-8 trên Windows để tránh lỗi UnicodeEncodeError
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Kiểm tra xem đang chạy bên trong Docker container (có superset) hay máy host
try:
    import superset  # type: ignore
    IS_INSIDE_CONTAINER = True
except ModuleNotFoundError:
    IS_INSIDE_CONTAINER = False

if not IS_INSIDE_CONTAINER:
    # Đang chạy từ máy host (Windows / ngoài container)
    # Tự động chuyển tiếp thực thi vào bên trong container pm_superset
    print("[INFO] Phat hien dang chay tu may host. Dang chuyen tiep thuc thi vao Docker container 'pm_superset'...")
    script_path = Path(__file__).resolve()
    infra_dir = script_path.parent.parent  # infra/
    
    # Đảm bảo PATH có docker binary trên Windows
    docker_extra_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin")
    env = os.environ.copy()
    if docker_extra_path not in env.get("PATH", ""):
        env["PATH"] = f"{env.get('PATH', '')};{docker_extra_path}"

    cmd = ["docker", "compose", "exec", "-T", "superset", "python", "-"]
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
        res = subprocess.run(
            cmd,
            input=script_content.encode("utf-8"),
            cwd=str(infra_dir),
            env=env
        )
        sys.exit(res.returncode)
    except Exception as e:
        print(f"[ERROR] Khong the chuyen tiep lenh vao Docker container: {e}")
        print("Goi y: Hay dam bao Docker Desktop dang bat va container 'pm_superset' dang Up.")
        sys.exit(1)


# ============================================================================
# LOGIC THIẾT LẬP BÊN TRONG CONTAINER APACHE SUPERSET
# ============================================================================
from superset.app import create_app  # type: ignore

app = create_app()
with app.app_context():
    # Phải import các model SAU KHI đã khởi tạo app_context để tránh RuntimeError
    from superset.extensions import db  # type: ignore
    from superset.models.core import Database  # type: ignore
    from superset.connectors.sqla.models import SqlaTable, TableColumn  # type: ignore
    from superset.models.slice import Slice  # type: ignore
    from superset.models.dashboard import Dashboard  # type: ignore

    print("Connecting to Superset metadata session...")
    dw_db = db.session.query(Database).filter_by(database_name="Maintenance Data Warehouse").first()
    if not dw_db:
        raise RuntimeError("Chưa tìm thấy database 'Maintenance Data Warehouse'.")

    # ------------------------------------------------------------------------
    # 1. TẠO / CẬP NHẬT DATASETS
    # ------------------------------------------------------------------------
    print("1. Creating Datasets...")
    
    # Dataset 1: view_budget_metrics (Hoặc agg_budget_metrics được chuyển thành view)
    ds_budget = (
        db.session.query(SqlaTable).filter_by(table_name="view_budget_metrics", database_id=dw_db.id).first()
        or db.session.query(SqlaTable).filter_by(table_name="agg_budget_metrics", database_id=dw_db.id).first()
    )
    if not ds_budget:
        ds_budget = SqlaTable(
            table_name="view_budget_metrics",
            database=dw_db,
            schema="public",
        )
        db.session.add(ds_budget)
        db.session.commit()
    else:
        ds_budget.table_name = "view_budget_metrics"
        ds_budget.sql = None
        db.session.commit()
    ds_budget.fetch_metadata()
    db.session.commit()

    # Dataset 2: view_priority_inspection
    ds_inspection = db.session.query(SqlaTable).filter_by(table_name="view_priority_inspection", database_id=dw_db.id).first()
    if not ds_inspection:
        ds_inspection = SqlaTable(
            table_name="view_priority_inspection",
            database=dw_db,
            schema="public",
        )
        db.session.add(ds_inspection)
        db.session.commit()
    else:
        ds_inspection.table_name = "view_priority_inspection"
        ds_inspection.sql = None
        db.session.commit()
    ds_inspection.fetch_metadata()
    db.session.commit()

    # ------------------------------------------------------------------------
    # 2. TẠO 5 CHARTS + 1 TABLE VIEW
    # ------------------------------------------------------------------------
    print("2. Creating Charts...")
    charts = []

    # Chart 1: Line Chart - Precision@k vs Budget k
    p1 = {
        "datasource": f"{ds_budget.id}__table",
        "viz_type": "echarts_timeseries_line",
        "slice_name": "Đánh đổi Ngân sách: Precision@k theo Ngân sách k",
        "x_axis": "budget_k",
        "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "precision"}, "aggregate": "AVG", "label": "Precision"}],
        "groupby": ["model_family"],
        "row_limit": 1000,
        "adhoc_filters": [
            {"clause": "WHERE", "expressionType": "SIMPLE", "operator": "==", "comparator": True, "subject": "topk_applicable"}
        ]
    }
    s1 = db.session.query(Slice).filter_by(slice_name=p1["slice_name"]).first() or Slice(slice_name=p1["slice_name"])
    s1.datasource_id, s1.datasource_type = ds_budget.id, "table"
    s1.viz_type = p1["viz_type"]
    s1.params = json.dumps(p1)
    db.session.add(s1)
    charts.append(s1)

    # Chart 2: Bar Chart - Recall / True Positives Detected
    p2 = {
        "datasource": f"{ds_budget.id}__table",
        "viz_type": "echarts_timeseries_bar",
        "slice_name": "Số ca hỏng bắt được (True Positives) theo Ngân sách",
        "x_axis": "budget_label",
        "xAxisLabelRotation": 0,
        "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "tp"}, "aggregate": "SUM", "label": "Ca hỏng bắt đúng (TP)"}],
        "groupby": ["model_family"],
        "row_limit": 1000,
        "adhoc_filters": []
    }
    s2 = db.session.query(Slice).filter_by(slice_name=p2["slice_name"]).first() or Slice(slice_name=p2["slice_name"])
    s2.datasource_id, s2.datasource_type = ds_budget.id, "table"
    s2.viz_type = p2["viz_type"]
    s2.params = json.dumps(p2)
    db.session.add(s2)
    charts.append(s2)

    # Chart 3: Confusion Matrix breakdown at locked threshold
    p3 = {
        "datasource": f"{ds_inspection.id}__table",
        "viz_type": "pivot_table_v2",
        "slice_name": "Ma trận Nhầm lẫn tại Ngưỡng Cố định (Validation & Test)",
        "groupbyRows": ["actual_failure"],
        "groupbyColumns": ["predicted_failure"],
        "metrics": [{"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": "Số bản ghi"}],
        "adhoc_filters": []
    }
    s3 = db.session.query(Slice).filter_by(slice_name=p3["slice_name"]).first() or Slice(slice_name=p3["slice_name"])
    s3.datasource_id, s3.datasource_type = ds_inspection.id, "table"
    s3.viz_type = p3["viz_type"]
    s3.params = json.dumps(p3)
    db.session.add(s3)
    charts.append(s3)

    # Chart 4: Failure Modes Distribution in Top-50
    p4 = {
        "datasource": f"{ds_inspection.id}__table",
        "viz_type": "pie",
        "slice_name": "Cơ cấu Chế độ Hỏng hóc trong Cảnh báo Top-50",
        "groupby": ["failure_mode"],
        "metric": {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": "Số thiết bị"},
        "adhoc_filters": [
            {"clause": "WHERE", "expressionType": "SIMPLE", "operator": "<=", "comparator": 50, "subject": "priority_rank"}
        ]
    }
    s4 = db.session.query(Slice).filter_by(slice_name=p4["slice_name"]).first() or Slice(slice_name=p4["slice_name"])
    s4.datasource_id, s4.datasource_type = ds_inspection.id, "table"
    s4.viz_type = p4["viz_type"]
    s4.params = json.dumps(p4)
    db.session.add(s4)
    charts.append(s4)

    # Chart 5: Priority Score Distribution across Product Types
    p5 = {
        "datasource": f"{ds_inspection.id}__table",
        "viz_type": "box_plot",
        "slice_name": "Phân phối Điểm Bất thường theo Loại Sản phẩm",
        "columns": ["product_type"],
        "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "priority_score"}, "aggregate": "AVG", "label": "Điểm ưu tiên"}],
        "adhoc_filters": []
    }
    s5 = db.session.query(Slice).filter_by(slice_name=p5["slice_name"]).first() or Slice(slice_name=p5["slice_name"])
    s5.datasource_id, s5.datasource_type = ds_inspection.id, "table"
    s5.viz_type = p5["viz_type"]
    s5.params = json.dumps(p5)
    db.session.add(s5)
    charts.append(s5)

    # Chart 6: Table View - Top-k Priority Inspection List
    p6 = {
        "datasource": f"{ds_inspection.id}__table",
        "viz_type": "table",
        "slice_name": "Danh sách Ưu tiên Kiểm tra Hàng đầu (Top-k Priority Inspection)",
        "all_columns": [
            "priority_rank",
            "reading_id",
            "product_id",
            "product_type",
            "priority_score",
            "predicted_failure",
            "actual_failure",
            "failure_mode",
            "air_temperature_k",
            "process_temperature_k",
            "rotational_speed_rpm",
            "torque_nm",
            "tool_wear_min",
            "power_w"
        ],
        "order_by_cols": ['["priority_rank", true]'],
        "server_page_length": 25,
        "row_limit": 100,
        "adhoc_filters": []
    }
    s6 = db.session.query(Slice).filter_by(slice_name=p6["slice_name"]).first() or Slice(slice_name=p6["slice_name"])
    s6.datasource_id, s6.datasource_type = ds_inspection.id, "table"
    s6.viz_type = p6["viz_type"]
    s6.params = json.dumps(p6)
    db.session.add(s6)
    charts.append(s6)

    db.session.commit()
    print("All 6 charts created / updated successfully!")

    # ------------------------------------------------------------------------
    # 3. TẠO DASHBOARD & NATIVE FILTERS
    # ------------------------------------------------------------------------
    print("3. Building Dashboard...")
    DASH_TITLE = "Đề tài 16 — Bảo trì Dự đoán Thiết bị (Predictive Maintenance Mining)"
    DASH_SLUG = "de-tai-16-bao-tri-du-doan"
    dash = db.session.query(Dashboard).filter_by(slug=DASH_SLUG).first() or Dashboard(slug=DASH_SLUG)
    dash.dashboard_title = DASH_TITLE
    dash.published = True
    dash.slices = charts

    chart_ids = [s1.id, s2.id, s3.id, s4.id, s5.id, s6.id]

    # Cấu trúc layout position_json liên kết ROOT_ID, GRID_ID và từng chart ID
    # Cần thiết để ECharts Native Filter định vị đúng scope của tất cả 6 charts
    position_data = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {
            "children": ["GRID_ID"],
            "id": "ROOT_ID",
            "type": "ROOT"
        },
        "GRID_ID": {
            "children": ["ROW-TOP", "ROW-BOTTOM"],
            "id": "GRID_ID",
            "parents": ["ROOT_ID"],
            "type": "GRID"
        },
        "HEADER_ID": {
            "id": "HEADER_ID",
            "meta": {"text": DASH_TITLE},
            "type": "HEADER"
        },
        "ROW-TOP": {
            "children": [f"CHART-{s1.id}", f"CHART-{s2.id}", f"CHART-{s3.id}"],
            "id": "ROW-TOP",
            "meta": {"0": "ROOT_ID", "background": "BACKGROUND_TRANSPARENT"},
            "parents": ["ROOT_ID", "GRID_ID"],
            "type": "ROW"
        },
        "ROW-BOTTOM": {
            "children": [f"CHART-{s4.id}", f"CHART-{s5.id}", f"CHART-{s6.id}"],
            "id": "ROW-BOTTOM",
            "meta": {"0": "ROOT_ID", "background": "BACKGROUND_TRANSPARENT"},
            "parents": ["ROOT_ID", "GRID_ID"],
            "type": "ROW"
        },
        f"CHART-{s1.id}": {
            "children": [],
            "id": f"CHART-{s1.id}",
            "meta": {"chartId": s1.id, "height": 50, "sliceName": s1.slice_name, "uuid": str(s1.uuid), "width": 4},
            "parents": ["ROOT_ID", "GRID_ID", "ROW-TOP"],
            "type": "CHART"
        },
        f"CHART-{s2.id}": {
            "children": [],
            "id": f"CHART-{s2.id}",
            "meta": {"chartId": s2.id, "height": 50, "sliceName": s2.slice_name, "uuid": str(s2.uuid), "width": 4},
            "parents": ["ROOT_ID", "GRID_ID", "ROW-TOP"],
            "type": "CHART"
        },
        f"CHART-{s3.id}": {
            "children": [],
            "id": f"CHART-{s3.id}",
            "meta": {"chartId": s3.id, "height": 50, "sliceName": s3.slice_name, "uuid": str(s3.uuid), "width": 4},
            "parents": ["ROOT_ID", "GRID_ID", "ROW-TOP"],
            "type": "CHART"
        },
        f"CHART-{s4.id}": {
            "children": [],
            "id": f"CHART-{s4.id}",
            "meta": {"chartId": s4.id, "height": 50, "sliceName": s4.slice_name, "uuid": str(s4.uuid), "width": 4},
            "parents": ["ROOT_ID", "GRID_ID", "ROW-BOTTOM"],
            "type": "CHART"
        },
        f"CHART-{s5.id}": {
            "children": [],
            "id": f"CHART-{s5.id}",
            "meta": {"chartId": s5.id, "height": 50, "sliceName": s5.slice_name, "uuid": str(s5.uuid), "width": 4},
            "parents": ["ROOT_ID", "GRID_ID", "ROW-BOTTOM"],
            "type": "CHART"
        },
        f"CHART-{s6.id}": {
            "children": [],
            "id": f"CHART-{s6.id}",
            "meta": {"chartId": s6.id, "height": 50, "sliceName": s6.slice_name, "uuid": str(s6.uuid), "width": 4},
            "parents": ["ROOT_ID", "GRID_ID", "ROW-BOTTOM"],
            "type": "CHART"
        }
    }
    dash.position_json = json.dumps(position_data)

    # Cấu hình Native Filters trong JSON metadata
    # Bắt buộc tiền tố id phải là 'NATIVE_FILTER-' (dấu gạch nối) theo quy chuẩn Redux selector Superset 4.0
    filter_config = [
        {
            "id": "NATIVE_FILTER-model",
            "name": "Họ mô hình (Model Family)",
            "type": "NATIVE_FILTER",
            "filterType": "filter_select",
            "targets": [
                {"datasetId": ds_budget.id, "column": {"name": "model_family"}},
                {"datasetId": ds_inspection.id, "column": {"name": "model_family"}}
            ],
            "defaultDataMask": {
                "id": "NATIVE_FILTER-model",
                "extraFormData": {
                    "filters": [{"col": "model_family", "op": "IN", "val": ["logistic_regression", "isolation_forest"]}]
                },
                "filterState": {"value": ["logistic_regression", "isolation_forest"]}
            },
            "controlValues": {"enableEmptyFilter": False, "multiSelect": True, "defaultToFirstItem": False},
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "isInstant": False,
            "chartsInScope": chart_ids,
            "tabsInScope": []
        },
        {
            "id": "NATIVE_FILTER-split",
            "name": "Giao thức chia tập (Split ID)",
            "type": "NATIVE_FILTER",
            "filterType": "filter_select",
            "targets": [
                {"datasetId": ds_budget.id, "column": {"name": "split_id"}},
                {"datasetId": ds_inspection.id, "column": {"name": "split_id"}}
            ],
            "defaultDataMask": {
                "id": "NATIVE_FILTER-split",
                "extraFormData": {
                    "filters": [{"col": "split_id", "op": "IN", "val": ["ordered-gap100-v1"]}]
                },
                "filterState": {"value": ["ordered-gap100-v1"]}
            },
            "controlValues": {"enableEmptyFilter": False, "multiSelect": False, "defaultToFirstItem": False},
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "isInstant": False,
            "chartsInScope": chart_ids,
            "tabsInScope": []
        },
        {
            "id": "NATIVE_FILTER-partition",
            "name": "Tập phân hoạch (Partition)",
            "type": "NATIVE_FILTER",
            "filterType": "filter_select",
            "targets": [
                {"datasetId": ds_budget.id, "column": {"name": "partition"}},
                {"datasetId": ds_inspection.id, "column": {"name": "partition"}}
            ],
            "defaultDataMask": {
                "id": "NATIVE_FILTER-partition",
                "extraFormData": {
                    "filters": [{"col": "partition", "op": "IN", "val": ["test"]}]
                },
                "filterState": {"value": ["test"]}
            },
            "controlValues": {"enableEmptyFilter": False, "multiSelect": False, "defaultToFirstItem": False},
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "isInstant": False,
            "chartsInScope": chart_ids,
            "tabsInScope": []
        },
        {
            "id": "NATIVE_FILTER-seed",
            "name": "Seed Ngẫu nhiên",
            "type": "NATIVE_FILTER",
            "filterType": "filter_select",
            "targets": [
                {"datasetId": ds_budget.id, "column": {"name": "seed"}},
                {"datasetId": ds_inspection.id, "column": {"name": "seed"}}
            ],
            "defaultDataMask": {
                "id": "NATIVE_FILTER-seed",
                "extraFormData": {
                    "filters": [{"col": "seed", "op": "IN", "val": [42]}]
                },
                "filterState": {"value": [42]}
            },
            "controlValues": {"enableEmptyFilter": False, "multiSelect": False, "defaultToFirstItem": False},
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "isInstant": False,
            "chartsInScope": chart_ids,
            "tabsInScope": []
        }
    ]

    dash.json_metadata = json.dumps({
        "native_filter_configuration": filter_config,
        "chart_configuration": {
            str(cid): {
                "id": cid,
                "crossFilters": {
                    "scope": "global",
                    "chartsInScope": [c for c in chart_ids if c != cid]
                }
            } for cid in chart_ids
        },
        "global_chart_configuration": {
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids
        },
        "color_scheme": "supersetColors",
        "refresh_frequency": 0,
        "cross_filters_enabled": True
    })

    db.session.add(dash)
    db.session.commit()
    print(f"Dashboard '{DASH_TITLE}' (ID: {dash.id}, Slug: {DASH_SLUG}) setup complete!")

