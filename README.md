# Đề tài 16 — Bảo trì dự đoán thiết bị

Nhóm 8 đánh giá cách xếp hạng các trạng thái vận hành cần ưu tiên kiểm tra trên bộ dữ liệu AI4I 2020. Isolation Forest phát hiện bất thường, Logistic Regression là mô hình phân lớp đối chiếu. Kết quả được nạp vào PostgreSQL và trình bày bằng Apache Superset trên máy cục bộ.

## Sản phẩm

- [Báo cáo Word](reports/final/Bao-cao-De-tai-16-hoan-thien.docx)
- [Slide thuyết trình](slides/final/De-tai-16-Nhom-8.pptx) và [kịch bản 10 phút](slides/final/KICH-BAN-10-PHUT.md)
- [Notebook phân tích và đánh giá](notebooks/) cùng [mã nguồn Python](src/maintenance/)
- [Script SQL](sql/), [hạ tầng Docker Compose](infra/) và [bản xuất dashboard Superset](dashboards/exports/dashboard_export.zip)
- [Bảng số liệu](reports/tables/), [hình phân tích](reports/figures/) và [nhật ký quyết định kỹ thuật](docs/DECISIONS.md)

## Chạy lại trên Windows

Từ thư mục gốc, dùng Python 3.12 trong PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe scripts/reproduce.py --download
.\.venv\Scripts\python.exe scripts/build_handoff.py --verify-only
.\.venv\Scripts\python.exe scripts/audit_results.py
```

Lệnh tái lập tải AI4I chính thức nếu thiếu và kiểm tra checksum. Khi đã có đúng CSV trong [vị trí dữ liệu nguồn](docs/HANDOFF.md), bỏ cờ --download để chạy với dữ liệu cục bộ. Tám bảng CSV cấp bản ghi được tạo tại data/processed/handoff-v1/. Thứ tự chạy tương tác được ghi trong [hướng dẫn notebook](notebooks/README.md).

Để nạp các bảng vào PostgreSQL và khôi phục Superset, xem [hướng dẫn kho](docs/WAREHOUSE.md) và [hướng dẫn dashboard](docs/DASHBOARD.md). Phạm vi chạy lại và các kiểm tra Docker/OLAP còn hạn chế được ghi trong [kết quả kiểm chứng](docs/REPRODUCIBILITY_REVIEW.md).

## Đọc kết quả

- [Câu hỏi nghiệp vụ và phạm vi](docs/PROBLEM_SCOPE.md)
- [Nguồn dữ liệu](datasets/README.md), [chất lượng dữ liệu](docs/DATA_QUALITY.md) và [tiền xử lý](docs/PREPROCESSING.md)
- [Phân chia tập](docs/SPLIT_PROTOCOL.md), [Isolation Forest](docs/ISOLATION_FOREST.md) và [Logistic Regression](docs/CLASSIFICATION.md)
- [Kết quả test v1](docs/TEST_EVALUATION.md), [phân tích lỗi](docs/ERROR_ANALYSIS.md) và [hậu kiểm độ bao phủ HDF](docs/HDF_SUPPLEMENT_V1.md)
- [Khai báo phạm vi sử dụng AI](docs/AI_USAGE.md)
