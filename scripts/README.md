# Lệnh tái lập và kiểm chứng

- reproduce.py chạy pipeline AI4I từ kiểm tra nguồn đến gói CSV cho kho. Thêm --download khi chưa có CSV nguồn.
- build_handoff.py --verify-only kiểm tra gói CSV hiện có theo manifest.
- audit_results.py đối chiếu độc lập các chỉ số, ngân sách kiểm tra và lỗi theo nhóm.
- audit_hdf_v1.py tạo các bảng hậu kiểm độ bao phủ HDF.
- load_warehouse.py và check_warehouse.py nạp và đối soát kho PostgreSQL.

Xem [cách chạy pipeline](../README.md), [quy ước gói CSV](../docs/HANDOFF.md) và [cách nạp kho](../docs/WAREHOUSE.md).
