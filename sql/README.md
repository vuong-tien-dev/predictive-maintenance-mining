# Kho dữ liệu và OLAP

1. [01-staging.sql](01-staging.sql) tạo bảng staging.
2. [02-star-schema.sql](02-star-schema.sql) tạo facts, dimensions và khóa.
3. [03-transform-load.sql](03-transform-load.sql) nạp dữ liệu từ staging.
4. [04-olap.sql](04-olap.sql) tạo các view phân tích dùng trong Superset.
5. [05-reconciliation.sql](05-reconciliation.sql) đối soát các bảng và chỉ số.

Xem [hướng dẫn nạp kho](../docs/WAREHOUSE.md) và [sơ đồ dữ liệu](../docs/diagrams/warehouse.mermaid).
