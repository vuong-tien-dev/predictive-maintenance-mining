# Hai bộ dữ liệu tham khảo của đề tài 16

Đã tải và kiểm tra file thực tế ngày 27/10/2026. Đây là bước khảo sát để so sánh hai lựa chọn; chưa chốt thay đổi nguồn dữ liệu của pipeline và chưa huấn luyện mô hình.

## Vị trí và nguồn

```text
datasets/
├── README.md
├── manifest.json                 Nguồn, checksum và thống kê thực đo
├── ai4i/                         Local, không commit
│   ├── ai4i2020.zip
│   └── ai4i2020.csv
└── cmapss/                       Local, không commit
    ├── CMAPSSData.zip
    ├── readme.txt
    ├── Damage Propagation Modeling.pdf
    ├── train_FD001.txt ... train_FD004.txt
    ├── test_FD001.txt  ... test_FD004.txt
    └── RUL_FD001.txt   ... RUL_FD004.txt
```

- AI4I: [trang UCI](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset), [ZIP chính thức](https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip), DOI 10.24432/C5HS5C; giấy phép công bố CC BY 4.0, cần ghi nguồn.
- C-MAPSS: [trang NASA](https://data.nasa.gov/dataset/cmapss-jet-engine-simulated-data), [ZIP chính thức](https://data.nasa.gov/docs/legacy/CMAPSSData.zip). Mục resource của NASA ghi License not specified; chưa xác minh đủ điều khoản sử dụng cho lớp học. Không tự gán CC BY hoặc kết luận public domain chỉ vì tải được.

File tải về giữ nguyên và không đưa lên Git. Chỉ README và manifest chứa metadata/thống kê được theo dõi. Môi trường khác phải tải dữ liệu riêng từ nguồn trên. data/raw/ vẫn dành cho nguồn được chọn khi triển khai pipeline; không sao chép hai bộ sang đó ở bước khảo sát này.

## 1. AI4I 2020 — bảng trạng thái vận hành

File ai4i2020.csv có **10.000 dòng × 14 cột**, header có sẵn. Một dòng là một bản ghi trạng thái vận hành mô phỏng; không có ID máy và timestamp đủ để dựng lịch sử từng máy một cách chắc chắn.

| Nhóm | Cột gốc | Ý nghĩa |
|---|---|---|
| Định danh | UDI | Số thứ tự/ID bản ghi, tên thật trong CSV là UDI |
| Định danh | Product ID | Mã sản phẩm, không mặc nhiên là mã thiết bị |
| Đầu vào | Type | Loại chất lượng sản phẩm L/M/H |
| Đầu vào | Air temperature [K] | Nhiệt độ không khí |
| Đầu vào | Process temperature [K] | Nhiệt độ quá trình |
| Đầu vào | Rotational speed [rpm] | Tốc độ quay |
| Đầu vào | Torque [Nm] | Mô-men xoắn |
| Đầu vào | Tool wear [min] | Độ mòn theo số phút sử dụng dụng cụ |
| Nhãn | Machine failure | Nhãn hỏng tổng: 0/1 |
| Nhãn | TWF, HDF, PWF, OSF, RNF | Các chế độ hỏng: mòn dụng cụ, tản nhiệt, công suất, quá tải và ngẫu nhiên |

Có **6 cột đầu vào**, **2 ID**, **6 nhãn**. Không dùng nhãn hoặc ID làm feature. Nhãn chế độ hỏng có thể đồng thời bằng 1, không phải các lớp loại trừ nhau.

Kết quả kiểm tra thực đo:

- Không có ô thiếu và không trùng UDI trong file tải về.
- Machine failure = 1 ở 339 dòng, tương đương 3,39%.
- Số nhãn chế độ hỏng: TWF 46, HDF 115, PWF 95, OSF 98, RNF 19; 24 dòng có nhiều chế độ cùng bằng 1.
- Có 9 dòng Machine failure = 1 nhưng mọi cột chế độ đều 0; 18 dòng Machine failure = 0 nhưng có ít nhất một cột chế độ bằng 1. Đây là kiểm tra tính nhất quán, chưa kết luận cột nào sai hoặc tự sửa nhãn.
- Tài liệu nguồn dùng tên UID trong mô tả nhưng CSV dùng UDI; bộ đọc phải ánh xạ tên thực tế.

Phù hợp câu hỏi: trạng thái nào đáng ưu tiên kiểm tra, điểm bất thường liên hệ với nhãn hỏng thế nào. Không có cơ sở quy đổi thứ tự bản ghi thành thời gian báo trước hỏng theo phút.

## 2. NASA C-MAPSS — lịch sử vận hành theo động cơ

Bốn bộ con FD001–FD004, mỗi bộ có ba file text phân cách bằng khoảng trắng và không có header. train/test đều có **26 cột**, phân tách bằng whitespace để tránh tạo cột rỗng vì khoảng trắng cuối dòng.

| Vị trí cột, đếm từ 1 | Tên quy ước | Ý nghĩa |
|---|---|---|
| 1 | unit_number | ID động cơ trong một subset và split |
| 2 | cycle | Số chu kỳ vận hành của động cơ |
| 3–5 | setting_1 ... setting_3 | Ba điều kiện/cấu hình vận hành |
| 6–26 | sensor_1 ... sensor_21 | 21 giá trị cảm biến |

Một dòng là **một động cơ ở một chu kỳ**. Các dòng cùng unit_number theo cycle tạo thành một chuỗi. Không ghép động cơ số 1 ở train và test thành một máy, hoặc ghép ID bằng nhau ở các bộ con khác nhau. Khóa khảo sát là subset × split × unit_number × cycle.

| Bộ con | Dòng train | Động cơ train | Dòng test | Động cơ test | Dòng RUL |
|---|---:|---:|---:|---:|---:|
| FD001 | 20.631 | 100 | 13.096 | 100 | 100 |
| FD002 | 53.759 | 260 | 33.991 | 259 | 259 |
| FD003 | 24.720 | 100 | 16.596 | 100 | 100 |
| FD004 | 61.249 | 249 | 41.214 | 248 | 248 |

Các số trên đo từ file, không sao chép từ phần giới thiệu. Tám file train/test đều có 26 cột, không có ô thiếu sau parse và không trùng cặp unit/cycle trong mỗi file. Số dòng RUL khớp số động cơ test ở cả bốn bộ con.

### Vai trò ba loại file

- train: chuỗi vận hành đi đến hỏng. Có thể tạo RUL tại mỗi dòng bằng chu kỳ cuối của động cơ trừ cycle hiện tại.
- test: chuỗi dừng trước khi động cơ hỏng, không chứa toàn bộ đoạn cuối.
- RUL: một cột, một dòng cho mỗi động cơ test theo thứ tự unit, cho biết số chu kỳ còn lại tại bản ghi cuối cùng của động cơ đó. Đây là đáp án đánh giá, không phải đầu vào lúc dự đoán.

Ví dụ đã đọc từ FD001: động cơ 1 của train có 192 chu kỳ; tại cycle 190, khoảng cách tới điểm cuối là 2 chu kỳ. Động cơ 1 của test chỉ quan sát đến cycle 31; dòng RUL đầu tiên là 112, tức còn 112 chu kỳ tại điểm dừng quan sát. Hai động cơ có cùng ID này thuộc hai split khác nhau.

Chu kỳ không mặc nhiên là phút/ngày. Dữ liệu không có nhãn hỏng 0/1 theo từng dòng như AI4I; nếu cần định nghĩa gần hỏng hoặc bất thường phải công khai quy tắc và không coi đó là nhãn fault onset chính thức.

### Khác biệt và lỗi tài liệu cần ghi nhận

- FD001/FD003 có một điều kiện vận hành; FD002/FD004 có sáu. FD001/FD002 có một chế độ suy giảm; FD003/FD004 có hai theo readme nguồn. Không có cột nhãn loại hỏng riêng trong 26 cột.
- Readme ghi FD004 có 248 train/249 test; file thực tế có 249 train/248 test. Giữ nguyên dữ liệu và ghi nhận chênh lệch.
- Readme kết thúc bằng sensor measurement 26 mặc dù tổng chỉ 26 cột. File thực tế gồm 2 cột định danh/thứ tự + 3 setting + 21 sensor, không phải 26 cảm biến.

## So sánh để lựa chọn

| Câu hỏi | AI4I | C-MAPSS |
|---|---|---|
| Có nhãn hỏng tổng và loại hỏng theo dòng? | Có, cần kiểm tra nhất quán | Không có trực tiếp |
| Có lịch sử cùng một động cơ? | Không được xác định chắc chắn bằng các cột hiện có | Có unit_number và cycle |
| Xếp ưu tiên trạng thái bất thường? | Trực tiếp, dễ đối chiếu nhãn | Làm được nhưng cần giao thức theo động cơ và chu kỳ |
| Đo khoảng cách tới hỏng? | Không đủ dữ liệu | Theo chu kỳ; không tự đổi sang phút |
| Độ phức tạp triển khai | Nhỏ, một CSV | Cần xử lý chuỗi, tách động cơ và các chế độ vận hành |

Tải cả hai để xem không đồng nghĩa phải ghép hoặc dùng cả hai trong đồ án. Chưa thay đổi lựa chọn dữ liệu chính và chưa triển khai mô hình ở tác vụ này.
