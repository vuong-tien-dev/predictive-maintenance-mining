# Bài toán và phạm vi đã thống nhất

Ngày chốt: 29/10/2026. Phụ trách: Vương Tiễn.
Kết quả chạy được trình bày trong [đánh giá test v1](TEST_EVALUATION.md).

## Hệ thống làm gì?

Nhận thông số vận hành từ AI4I, chấm mức độ bất thường cho từng bản ghi và xếp hạng các trường hợp cần ưu tiên kiểm tra. Sau đó đối chiếu với nhãn hỏng có sẵn để đo phát hiện đúng, cảnh báo sai và bỏ sót.

Ví dụ minh họa: người dùng đặt ngân sách kiểm tra 20 trường hợp. Hệ thống chọn 20 bản ghi đứng đầu theo điểm ưu tiên; phần đánh giá mới đối chiếu nhãn thật. Số 20 chỉ là ví dụ, không phải giới hạn bắt buộc hoặc kết quả đã chạy.

## Câu hỏi và người sử dụng

**Với ngân sách kiểm tra k bản ghi trạng thái vận hành, phương pháp xếp hạng nào phát hiện được nhiều bản ghi mang nhãn hỏng hơn, đồng thời thể hiện rõ số cảnh báo giả và ca hỏng bị bỏ sót?**

Người sử dụng giả định là người phụ trách bảo trì: xem danh sách ưu tiên và đánh đổi giữa phát hiện đúng với cảnh báo sai. Nhóm kiểm chứng trên dữ liệu mô phỏng, chưa triển khai quyết định bảo trì ở nhà máy thật.

## Đầu vào

- AI4I 2020 của UCI, file đã kiểm tra có 10.000 dòng × 14 cột; xem [nguồn và cấu trúc](../datasets/README.md).
- Một dòng là một bản ghi trạng thái vận hành; không mặc nhiên là một máy riêng hoặc một phút đo.
- Sáu đầu vào: loại sản phẩm, nhiệt độ không khí, nhiệt độ quá trình, tốc độ quay, mô-men xoắn và độ mòn dụng cụ.
- UDI và Product ID chỉ dùng truy vết, không làm feature.
- Machine failure và các nhãn loại hỏng dùng cho đánh giá/phân lớp; không đưa vào feature của Isolation Forest hoặc đầu vào khi dự đoán.
- Đặc trưng vật lý được tính từ đầu vào với công thức/đơn vị rõ ràng. Xem [quy ước dữ liệu](DATA_CONTRACT.md).

## Sản phẩm cần xây và nộp

| Thành phần | Kết quả cần có | Vị trí |
|---|---|---|
| Phân tích dữ liệu | Kiểm tra chất lượng, quyết định xử lý, dữ liệu chuẩn hóa tái tạo được | `notebooks/`, `src/maintenance/`, `docs/DECISIONS.md` |
| Mô hình và đánh giá | Isolation Forest, phân lớp đối chiếu, baseline, điểm ưu tiên, top-k, bảng chỉ số và phân tích sai sót | `src/maintenance/`, `notebooks/`, `artifacts/` |
| Kho dữ liệu | PostgreSQL, ít nhất 1 fact + 3 dimension có ý nghĩa, 3 script SQL và truy vấn OLAP | `sql/`, `infra/`, `docs/diagrams/` |
| Dashboard | Superset với 4–6 biểu đồ thật, bộ lọc và bản xuất để khôi phục | `dashboards/`, `infra/superset/` |
| Gói bàn giao | Mã nguồn/cấu hình chạy lại, báo cáo 10–15 trang, slide và hướng dẫn demo | `reports/`, `slides/`, `README.md` |

Xem [README](../README.md) để mở các sản phẩm và tái tạo dữ liệu hoặc kết quả cấp bản ghi.

## Cách kiểm chứng

- Chia tập dùng chung; học mô hình và chọn cấu hình/ngưỡng đúng giao thức, giữ tập kiểm tra cho đánh giá cuối.
- So sánh với baseline trên cùng tập và cùng ngân sách kiểm tra.
- Báo ma trận nhầm lẫn, Precision, Recall, F1, ROC-AUC từ điểm liên tục; thêm Precision@k/Recall@k, độ dao động và phân tích cảnh báo sai/bỏ sót phù hợp.
- Báo kết quả chạy thật, kể cả khi mô hình chưa cải thiện so với baseline.

Xem [giao thức chọn cấu hình và đánh giá test](TEST_EVALUATION.md). Split, ngân sách20/50/100, model và ngưỡng v1 đã khóa; kết quả test và audit trong TEST_EVALUATION.md/REPRODUCIBILITY_REVIEW.md. Không coi hậu kiểm là quyền chọn lại cấu hình theo test.

## Giới hạn và phạm vi

Đề bài gợi ý tìm dấu hiệu báo trước hỏng đủ sớm. AI4I không có lịch sử thời gian và mã thiết bị phù hợp để đo thời gian báo trước từng máy. Dự án chỉ kiểm chứng phát hiện trạng thái và ưu tiên kiểm tra; chưa trả lời được máy sẽ hỏng sau bao nhiêu phút/ngày. Không dùng UDI làm timestamp hoặc Product ID làm mã máy.

Luồng triển khai: Python/Jupyter → PostgreSQL → Superset, chạy local. Chưa đưa vào phạm vi chính: cảm biến thật, streaming, web/API riêng, tự động dừng máy, adapter đa nguồn hoặc dự báo thời gian tới hỏng.
