# Mã dùng chung

Đã triển khai `quality.py`: đọc/đối chiếu nguồn, audit, thống kê và xuất hình/bảng. Module không sửa dữ liệu hoặc học mô hình. Chạy từ `scripts/run_quality.py`; xem `docs/DATA_QUALITY.md`.

Đã triển khai thêm `preprocessing.py`: chuyển đổi theo dòng và xuất readings/features/labels/quality_flags; `features.py`: công thức vật lý, chọn sáu đầu vào và pipeline mã hóa/scaling chưa fit. Xem `docs/PREPROCESSING.md`.

Đã có `splits.py`: mapping chính/phụ, kiểm tra hash/khóa và loader train/validation/test theo giao thức. Không tự chia lại trong mô hình.

Đã có `models.py` và `evaluation.py` cho baseline/Isolation Forest, lựa chọn/metrics validation, điểm/rank và run metadata. Đã có `classification.py` cho Logistic Regression có scaling train và so sánh validation; đã có `final_evaluation.py` khóa lựa chọn, chấm test không fit/chọn lại, phân tích lỗi/dao động và xuất bảng/hình.

Đã có `handoff.py`: xuất 8 bảng có grain/schema/hash, kiểm tra score và đối chiếu metrics nguồn; dùng scripts/build_handoff.py. scripts/reproduce.py điều phối pipeline cố định, không đổi model/ngưỡng.

Các phần sau vẫn dự kiến, chưa triển khai:

- data.py: chưa tạo module riêng; chức năng nguồn/chuẩn hóa/split đã nằm trong quality.py, preprocessing.py và splits.py, tái sử dụng các module đó.
- models.py: họ chính đã có; họ phụ nằm riêng trong classification.py để giữ nguyên kết quả/provenance của việc 6.
- evaluation.py: đã có metrics/ngân sách/ngưỡng; phân tích lỗi/test được thực hiện trong final_evaluation.py, tái dùng các hàm metrics ở đây.
- warehouse.py: nạp đầu ra đã kiểm chứng vào PostgreSQL.

Notebook, script và tác vụ xuất kết quả gọi lại các hàm này. Không gắn đường dẫn tuyệt đối của máy hay thông tin cá nhân vào mã. Các giao diện tuân theo docs/DATA_CONTRACT.md.
