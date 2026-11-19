# Phân tích lỗi từ điểm v1 đã khóa

Nguồn: reports/tables/review/metrics.csv, budgets.csv, group-errors.csv; notebook05. Không fit hoặc tối ưu thêm. Test đã được xem.

## Chính sách và ngân sách

Test chính có1.900bản ghi/38ca hỏng. Top50 toàn tập: IF13TP/37FP/25FN; LR21TP/29FP/17FN; random seed42 không tìm ca hỏng. Khi tăng lên100lượt, IF tìm15ca, LR25ca, nghĩa là50lượt tăng thêm chỉ tìm thêm2/4ca. Seed42 là một lần xếp ngẫu nhiên, không phải kỳ vọng của mọi seed.

Ngưỡng validation đã khóa cho IF13TP/25FP/25FN/1.837TN; LR10TP/1FP/28FN/1.861TN. LR precision90,91% tại ngưỡng chỉ đi kèm11cảnh báo và recall26,32%, không phải precision42% của50lượt. So sánh phải cùng quần thể và chính sách.

## Nhóm và mode

- TypeH test chính có210dòng,0ca nhãn tổng hỏng: recall không xác định. FP vẫn đo được; không suy công bằng chỉ từ tỷ lệ chung.
- TWF test chính có10ca nhãn tổng1; top50 của LR tìm1. Có thể liên quan chữ ký hỏng khác nhau nhưng chưa xác định nguyên nhân. Không gọi các loại hỏng là lớp loại trừ nhau.
- HDF/RNF vắng ở test chính, không ước lượng được recall tại đây. Test phụ có26HDF; top50 IF0,LR10. Đây là giao top50 toàn tập với các dòng có cờ HDF, không phải mô hình HDF riêng.
-9dòng hỏng không mode và18dòng mode có nhãn tổng0 ở toàn nguồn được giữ nguyên. Audit nhóm hậu kiểm tách rõ các trường hợp này, không thay nhãn tổng bằng phép OR.

## Biến vật lý và độ nhạy

Chỉ dùng candidates validation đã có. Với IF, AP tốt nhất base/physical là0,1615/0,3202ở giao thức chính và0,1406/0,2585ở phụ. LR chính base0,5011cao hơn physical0,3992; LR phụ physical0,4634cao hơn base0,4321. Vì vậy không kết luận biến dẫn xuất luôn giúp mọi mô hình. Xem validation-feature-comparison.csv.

IF primary test qua seed42/43/44 có AP0,1554±0,0234, P@50=25,33%±1,15điểm phần trăm. LR không có ba lần fit ngẫu nhiên độc lập để báo std giả. Bootstrap500lần/khối100trên19khối là thăm dò; chưa chứng minh độ độc lập/coverage. Chênh lệch hai thuật toán không cô lập tác động nhân quả của nhãn.

## Khuyến nghị có điều kiện

Nếu đủ nhãn và chỉ kiểm tra50trường hợp, thử danh sách LR có người giám sát; vẫn còn29lượt báo giả và17ca bỏ sót. Duy trì bảo trì định kỳ, ghi phản hồi. Không gọi điểm IF là xác suất hoặc hứa thời gian báo trước, vì AI4I không có lịch sử từng máy. Không dùng phân tích test này để chọn mô hình/ngưỡng mới.
