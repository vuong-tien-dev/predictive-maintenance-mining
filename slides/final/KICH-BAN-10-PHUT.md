# Kịch bản thuyết trình 10 phút và vấn đáp 5 phút

Các mốc là ngân sách tập nói, không phải thời lượng đã bấm giờ thực tế. Speaker notes trong PPTX có gợi ý và nguồn cho từng trang. Tất cả thành viên cần hiểu toàn pipeline.

| Slide | Người trình bày | Giây | Nội dung cần nói |
|---|---|---:|---|
|1|Vương Tiễn|30|Đề tài16, nhóm8, phạm vi batch local|
|2|Vương Tiễn|45|Ai quyết định k, hệ thống xếp bản ghi nào; không có mã máy thực|
|3|Phạm Thị Tường Vi|55|Nguồn UCI/CC BY4,3 vấn đề chất lượng có số liệu|
|4|Vương Tiễn|50|Biến vật lý, one-hot/scaling train-only, tránh leakage|
|5|Quốc Việt|55|2fact/4dimension, grain10k và78k, SQL→views|
|6|Vương Tiễn|50|IF không dùng y khi fit; LR dùng nhãn; chọn bằng validation|
|7|Vương Tiễn|65|So k20/50/100 cùng quần thể,13/21TP@50|
|8|Phạm Thị Tường Vi|60|Ngưỡng không phải top-k; P90,91% đi cùng11cảnh báo|
|9|Phạm Thị Tường Vi|55|HDF/RNF vắng chính, HDF phụ0/26và10/26; TWF; dao động|
|10|Quốc Việt|60|Demo một model/lần, test chính/seed42; chỉ ra nguồn dashboard|
|11|Phạm Thị Tường Vi|45|Audit40metrics/120budget,8hash; rủi ro báo giả/bỏ sót|
|12|Cả nhóm|30|Khuyến nghị có điều kiện và dữ liệu cần thêm|
|Tổng||600|10phút, sau đó5phút hỏi đáp|

## Demo 60 giây

Trước buổi nói phải mở sẵn Docker, PostgreSQL đã nạp và Superset đã import bundle. Mở docs/DASHBOARD.md để làm đúng lệnh. Bản runtime chưa được kiểm chứng trên máy tích hợp; không nhận đã chạy khi chưa demo thực tế. Không tự reset volume để chuẩn bị.

1. Chọn logistic_regression / ordered-gap100-v1 / test /42; Apply filters. Chỉ k50:21TP và P42%; ngưỡng10TP/1FP/28FN/1861TN.
2. Chuyển isolation_forest, giữ các bộ lọc khác. Chỉ k50:13TP và P26%; ngưỡng13TP/25FP/25FN/1837TN.
3. Bảng ưu tiên là trạng thái, không gọi mãProductID là máy thật. Chỉ chọn một model khi đọc ma trận/boxplot; hai model có thể bị cộng gộp.
4. Nếu dịch vụ không chạy, nói rõ dùng ảnh từ bản bàn giao; không gọi đó là demo trực tiếp hoặc chứng minh filter vừa chạy.

## Câu hỏi chéo cho mọi thành viên

| Câu hỏi | Ý trả lời kiểm chứng được |
|---|---|
|Ai chọn20/50/100?|Ngân sách kiểm tra được quy định trước; model xếp hạng và chọn top-k. Không chọn k theo kết quả test đẹp.|
|Vì sao accuracy98% vẫn không tốt?|Always-normal không bắt được ca nào trong38ca hỏng.|
|Có dùng nhãn cho IF không?|Không dùng khi fit; nhãn validation dùng chọn cấu hình/ngưỡng, nhãn test dùng đánh giá.|
|Vì sao LR90,91% mà top50chỉ42%?|10/11cảnh báo tại ngưỡng khác với21/50lượt top-k.|
|Vì sao thiếu HDF ở testchính?|Mode tập trung theo thứ tự nguồn;108/115HDF ởkhối4001–5000, nằmtrain; không phải bị xóa.|
|HDF0ởtestchính có recall0%?|Không, recall không xác định khi không có ca;testphụcó26ca nên0/26củaIF mới là0%.|
|Có dự đoán hỏng trước1giờ không?|Không có timestamp/lịch sử máy để chứng minh lead time/RUL.|
|CóAI không?|Có hỗ trợ viết code/tài liệu; khai đúng phạm vi, tự đọc và chịu trách nhiệm. Không khai chỉ sửa lỗi nếu thực tế rộng hơn.|
|8bảnghashkhớp nghĩa gì?|Tái lập byte giống trên checkout riêng cùng môi trường; không chứng minh khái quát hóa hoặc máy khác chạy chắc chắn.|
|Vì sao không sửa split bây giờ?|Testv1đã xem; thay đổi để cải thiện cần thiết kế kiểm chứng mới.|
|Một factscorecó78k nghĩa có78kmáy?|Không; một trạng thái được nhiều run/partition chấm, grain khác với10kreadings.|
|Nhóm đã làmOLAPnângcao chưa?|Bộ QVhiện dùngGROUPBYthường; chưa tuyên bố ROLLUP/window đã chạy.|

Thành viên tự tập nói và mở code/SQL trả lời. Chưa có xác nhận đã diễn tập hoặc tất cả đã hiểu, không tick thay.
