# Khai báo phạm vi sử dụng AI

Nhóm sử dụng AI để hỗ trợ khảo sát dữ liệu, soạn và rà mã Python/SQL, notebook, cấu hình kho và dashboard, kiểm thử, tổng hợp báo cáo và chuẩn bị slide. Phần này được trình bày trong Phụ lục A của báo cáo.

| Hạng mục | Phạm vi hỗ trợ | Bằng chứng kiểm tra |
|---|---|---|
| Dữ liệu và tiền xử lý | Khảo sát schema, viết kiểm tra chất lượng, triển khai tiền xử lý và tạo bảng/hình | [Chất lượng dữ liệu](DATA_QUALITY.md), [tiền xử lý](PREPROCESSING.md) |
| Mô hình và đánh giá | Thiết kế giao thức, viết mã huấn luyện và đánh giá, kiểm thử và hậu kiểm HDF | [Đánh giá test](TEST_EVALUATION.md), [hậu kiểm HDF](HDF_SUPPLEMENT_V1.md), [bộ kiểm thử](../tests/) |
| Kho và dashboard | Hỗ trợ viết SQL, ETL, cấu hình Docker Compose và Superset | [Kho dữ liệu](WAREHOUSE.md), [dashboard](DASHBOARD.md), [phạm vi kiểm chứng runtime](REPRODUCIBILITY_REVIEW.md) |
| Kiểm chứng và trình bày | Hỗ trợ viết audit và notebook kiểm chứng, biên tập nội dung, bảng, hình và slide | [Kết quả kiểm chứng](REPRODUCIBILITY_REVIEW.md), [báo cáo](../reports/final/), [slide](../slides/final/) |

Các số liệu thực nghiệm được đối chiếu với đầu ra pipeline và bảng kiểm chứng. Mức kiểm chứng cụ thể và giới hạn được ghi trong các tài liệu tương ứng. Nhóm chịu trách nhiệm về nội dung và kết quả nộp.
