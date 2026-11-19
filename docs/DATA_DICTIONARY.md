# Từ điển dữ liệu AI4I — phiên bản ai4i-v1

Chốt ngày 29/10/2026. Phụ trách: Vương Tiễn. Đã đối chiếu 14 cột với CSV local; bộ đọc kiểm tra nguồn đã triển khai trong `src/maintenance/quality.py` ở việc 3, đã có tiền xử lý theo dòng và pipeline chưa fit ở [việc 4](PREPROCESSING.md).

Bản cho chương trình đọc: [configs/ai4i-schema.json](../configs/ai4i-schema.json). Cấu hình đã được bộ kiểm tra nguồn trong `quality.py` sử dụng; chưa phải adapter chấm điểm dữ liệu mới. Quy ước đầu ra/split: [DATA_CONTRACT.md](DATA_CONTRACT.md).

## Bảng ánh xạ

Kiểu dưới đây là kiểu quy ước sau khi đọc, không phải kiểu nhị phân được lưu trong CSV. Vai trò feature là đầu vào; target/failure_mode là đáp án để học có giám sát hoặc hậu kiểm.

| Cột CSV gốc | Tên thống nhất | Kiểu | Vai trò | Đơn vị | Ý nghĩa |
|---|---|---|---|---|---|
| `UDI` | `reading_id` | integer | identifier | — | ID bản ghi; không phải thời gian hoặc mã máy |
| `Product ID` | `product_id` | string | identifier | — | Mã sản phẩm; giữ nguyên để truy vết |
| `Type` | `product_type` | string | feature | — | Loại chất lượng sản phẩm L/M/H; không phải mức độ hỏng |
| `Air temperature [K]` | `air_temperature_k` | float | feature | K | Nhiệt độ không khí xung quanh |
| `Process temperature [K]` | `process_temperature_k` | float | feature | K | Nhiệt độ quá trình vận hành |
| `Rotational speed [rpm]` | `rotational_speed_rpm` | integer | feature | rpm | Số vòng quay mỗi phút |
| `Torque [Nm]` | `torque_nm` | float | feature | N m | Mô-men xoắn: tác dụng làm quay trục |
| `Tool wear [min]` | `tool_wear_min` | integer | feature | min | Độ mòn dụng cụ biểu diễn bằng phút sử dụng; không phải thời gian tới hỏng |
| `Machine failure` | `machine_failure` | integer | target | — | Nhãn hỏng tổng: 1 hỏng, 0 không hỏng theo dữ liệu |
| `TWF` | `twf` | integer | failure_mode | — | Tool wear failure: hỏng do mòn dụng cụ |
| `HDF` | `hdf` | integer | failure_mode | — | Heat dissipation failure: hỏng do tản nhiệt |
| `PWF` | `pwf` | integer | failure_mode | — | Power failure: hỏng liên quan công suất |
| `OSF` | `osf` | integer | failure_mode | — | Overstrain failure: hỏng do quá tải |
| `RNF` | `rnf` | integer | failure_mode | — | Random failure: hỏng ngẫu nhiên |

## Kết quả đối chiếu file ngày 29/10/2026

- 10.000 dòng; 2 cột định danh, 6 đầu vào và 6 nhãn; không có ô trống.
- CSV có UTF-8 BOM: dùng `utf-8-sig`, dấu phẩy và header. Tên thật là `UDI`; không tự đổi file nguồn thành `UID`.
- UDI duy nhất trong file này, từ 1 tới 10.000. Product ID cũng có 10.000 giá trị khác nhau; tính duy nhất không biến nó thành mã thiết bị.
- Type: L = 6.000, M = 2.997, H = 1.003. Các tỷ lệ/số đếm trong báo cáo phải lấy từ file, không sao chép tỷ lệ mô tả nguồn.

SHA-256 file CSV: `dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e`. `dataset_version` quy ước là `sha256:` nối toàn bộ chuỗi này. Khóa bản ghi là cặp `dataset_version × reading_id`; phiên bản schema `ai4i-v1` được ghi riêng.

| Cột đo | Nhỏ nhất | Lớn nhất |
|---|---:|---:|
| `air_temperature_k` | 295.3 | 304.5 |
| `process_temperature_k` | 305.7 | 313.8 |
| `rotational_speed_rpm` | 1168 | 2886 |
| `torque_nm` | 3.8 | 76.6 |
| `tool_wear_min` | 0 | 253 |

Đây là khoảng quan sát của file hiện tại, không phải ngưỡng loại dữ liệu mới. Không xóa các trạng thái cực đoan chỉ vì chúng bất thường: đó có thể chính là đối tượng cần phát hiện.

## Quy tắc sử dụng

1. Bản nguồn phục vụ huấn luyện/đánh giá cần đủ 14 cột, đối chiếu bằng tên cột; thiếu/thừa/trùng header phải báo lỗi. Không phụ thuộc thứ tự cột khi triển khai bộ đọc.
2. Đầu vào chấm điểm cần sáu feature; nhãn không bắt buộc và không được dùng để xếp hạng. Khi lưu kết quả theo lô phải có ID bản ghi và phiên bản để truy vết. Chưa xây API/adapter trong việc này.
3. Type chỉ nhận L/M/H; nhãn chỉ nhận số nguyên 0/1; số đo phải parse đúng kiểu và hữu hạn. Null, sai kiểu hoặc giá trị ngoài miền phân loại phải được báo; chưa có chính sách tự điền/xóa/ép kiểu để bỏ qua lỗi.
4. Không mã hóa L/M/H thành mức rủi ro 1/2/3. Cách mã hóa category và scaling sẽ chốt trong tiền xử lý.
5. Giữ riêng sáu nhãn gốc. Các mode có thể đồng thời bằng 1 và có bất nhất với nhãn tổng; ghi nhận để phân tích, không tự sửa Machine failure bằng phép OR các mode.
6. Không tạo timestamp hoặc machine_id từ UDI/Product ID. Tool wear không phải tuổi thọ còn lại.
7. Dataset ngoài phải có ý nghĩa vật lý và đơn vị tương đương của sáu đầu vào, cùng điều kiện đánh giá riêng; không nhận chỉ vì trùng tên cột hoặc tự lấp cột thiếu. Adapter đa nguồn chưa thuộc phạm vi triển khai chính.

## Đặc trưng dẫn xuất đã định nghĩa

- `temperature_difference_k = process_temperature_k - air_temperature_k`, đơn vị K.
- `power_w = torque_nm × rotational_speed_rpm × 2π / 60`, đơn vị W.
- `wear_torque_min_nm = tool_wear_min × torque_nm`, đơn vị min·N·m.

Ba biến được tính từ đầu vào, không từ nhãn; việc 4 đã tái tạo chúng trong bảng features local, xem [tiền xử lý](PREPROCESSING.md). Mỗi thí nghiệm phải ghi feature set gốc hoặc gốc + dẫn xuất, không mặc định thêm biến chắc chắn cải thiện kết quả.

## Nguồn và giới hạn

Ý nghĩa/đơn vị tham chiếu [UCI AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset), DOI 10.24432/C5HS5C, CC BY 4.0. Tên header và các thống kê trên đo trực tiếp từ file có checksum ghi ở trên; không dùng mô tả nguồn để thay số đếm thực tế.

Việc 2 chốt cấu trúc dữ liệu; kiểm tra chất lượng/EDA đã có ở [việc 3](DATA_QUALITY.md). Đã có [split/giao thức](SPLIT_PROTOCOL.md); mô hình, kho và dashboard chưa triển khai.
