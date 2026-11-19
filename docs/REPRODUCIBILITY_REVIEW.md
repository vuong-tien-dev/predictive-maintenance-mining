# Kiểm chứng tái lập và audit độc lập v1

Kiểm chứng ngày 16/11/2026.

## Phạm vi và môi trường

Dùng bản mã nguồn tại 3a9d9e7 trong một checkout sạch, chép CSV AI4I chính thức và chạy scripts/reproduce.py bằng môi trường Python của dự án. Runner tự kiểm tra checksum nguồn. Windows11, Python3.12.8, pandas3.1.0, numpy2.5.4, scikit-learn1.9.1. Đây là checkout sạch cùng môi trường đã cài, không phải thử nghiệm trên máy/OS mới.

## Lệnh và kết quả thực tế

```powershell
.\.venv\Scripts\python.exe scripts/build_handoff.py --verify-only
.\.venv\Scripts\python.exe scripts/audit_results.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute notebooks/05-independent-review.ipynb --inplace
```

Trong checkout riêng: scripts/reproduce.py hoàn tất toàn bộ quality → preprocessing → split → IF → LR → test cố định → handoff,34tests bản nền đạt. Tám bảng tái tạo trùng100% SHA256 gói gốc; xem [reproduction-check.json](../reports/tables/review/reproduction-check.json). Không thay metadata/score của workspace chính để khớp kết quả. Hash nhị phân joblib có thể khác dù quyết định/điểm giống; không thay khóa v1 vì khác serialization.

Audit mới tự đếm ma trận và top-k, dùng API sklearn cho AUC/AP từ điểm liên tục, không import hàm metrics v1. Tám file được kiểm tra theo manifest Git,40nhóm run/partition và120ngân sách khớp. Xem [audit-summary.json](../reports/tables/review/audit-summary.json), [package-checks.csv](../reports/tables/review/package-checks.csv). Tests có số tính tay, đồng điểm, null, k vượt n, số liệu/bytes hỏng có chủ đích; không sửa dữ liệu thật.

## Giới hạn còn lại

- Chưa chạy nhánh tải mạng vì CSV đã có; chưa cài mới toàn bộ thư viện trên máy khác.
- Docker daemon trên máy tích hợp không chạy ở thời điểm kiểm tra; chưa nghiệm thu runtime PostgreSQL, import bundle hoặc thao tác UI tại đây. Ảnh trong báo cáo là ảnh thành viên cung cấp, không coi là kết quả vừa chạy lại.
- Đối soát kho trên Docker và OLAP nâng cao vẫn là giới hạn kiểm chứng. Kho nạp lại bằng dựng lại bảng; cần sao lưu nếu có dữ liệu bổ sung. Chọn riêng từng model khi xem ma trận. Các truy vấn hiện có được liệt kê trong tài liệu kho.
- Notebook05 là kiểm chứng hậu kiểm, không test độc lập mới. Tự đọc bảng/hình và kiểm tra các lệnh trước bảo vệ.
