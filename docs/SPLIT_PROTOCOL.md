# Giao thức chia tập AI4I — v1

Chốt ngày 29/10/2026, trước khi huấn luyện mô hình. Chưa có điểm mô hình hoặc ngưỡng được chọn. Đây là thiết kế đánh giá của nhóm, không phải tỷ lệ/khoảng đệm bắt buộc do giảng viên quy định.

## Mục tiêu và lựa chọn

[EDA](DATA_QUALITY.md) ghi nhận phụ thuộc mạnh giữa thông số ở các dòng liền nhau. Vì vậy chọn `ordered-gap100-v1` làm giao thức chính: giữ thứ tự nguồn, chia ngân sách vị trí 60/20/20, rồi dành 100 dòng đầu mỗi đoạn validation/test làm khoảng đệm. Khoảng đệm 100 là lựa chọn thực dụng được đặt trước khi đo kết quả mô hình; chưa được chứng minh là chiều dài làm hết phụ thuộc. Không điều chỉnh để có test đẹp hơn.

`stratified-seed42-v1` là giao thức phụ: chia ngẫu nhiên phân tầng nhãn tổng, 60/20/20 với seed 42, để kiểm tra độ nhạy so với cách chia thông dụng. Các họ mô hình dùng cùng ánh xạ trong từng giao thức. Không chọn giao thức có điểm test cao hơn để làm kết luận chính; không dùng kết quả ở test phụ để tối ưu mô hình cho test chính vì các tập này chồng lấp giữa hai giao thức.

Thứ tự nguồn không phải timestamp. Không gọi đây là dự báo tương lai theo phút hoặc kiểm tra độc lập trên máy chưa từng thấy. Khoảng đệm chỉ tách các vị trí ở ranh giới; hai tập vẫn có thể phụ thuộc hoặc khác phân bố.

## Ánh xạ chính đã tạo

Vị trí là số thứ tự dòng dữ liệu trong CSV (không tính header), không phải phép suy diễn thời gian từ UDI.

| Vai trò | Vị trí nguồn | Số dòng | Nhãn hỏng |
|---|---|---:|---:|
| Train — học mô hình và fit biến đổi | 1–6.000 | 6.000 | 255 |
| Gap — không fit/chọn cấu hình/chấm điểm | 6.001–6.100 và 8.001–8.100 | 200 | 3 |
| Validation — chọn cấu hình/ngưỡng | 6.101–8.000 | 1.900 | 43 |
| Test — đánh giá cuối sau khi khóa cấu hình | 8.101–10.000 | 1.900 | 38 |

Không xóa các dòng gap khỏi nguồn hoặc bảng chuẩn hóa. Tỷ lệ thực dùng là 60%/19%/19% và 2% đệm. Với ngẫu nhiên phân tầng, train/validation/test có 6.000/2.000/2.000 dòng và 203/68/68 nhãn hỏng. Ranh giới/gap/seed không được thay sau khi xem các số đếm này. Xem [bảng đếm sinh từ code](../reports/tables/splits/summary.csv); min/max vị trí ở giao thức ngẫu nhiên không mô tả một đoạn liên tục.

## Bổ sung độ bao phủ mode, 30/10/2026

Đã xác minh toàn bộ 115 HDF nằm trong train chính; validation/test chính không có HDF. Vì vậy chọn cấu hình bằng validation và kết quả test chính không đánh giá được HDF. Phụ phân tầng có 67/22/26 HDF ở train/validation/test; đây là số đo, không phải bảo đảm stratify mọi mode. Giữ nguyên giao thức/seed/khoảng đệm, không chia lại sau khi xem test. Xem [bảng và hậu kiểm HDF](HDF_SUPPLEMENT_V1.md); không suy kết quả chung thành hiệu quả đầy đủ mọi loại hỏng.

## Tái tạo và bàn giao

```powershell
.\.venv\Scripts\python.exe scripts/create_splits.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Hoặc chạy [notebook 02c](../notebooks/02c-splits.ipynb) từ kernel mới. Lệnh đọc nguồn đã xác minh checksum và dùng cùng hàm chuyển đổi theo dòng; không yêu cầu fit scaler hoặc model trước.

- [configs/splits.json](../configs/splits.json): tỷ lệ, seed, giao thức chính/phụ, khoảng đệm và phiên bản.
- `data/processed/splits/<split_id>.csv`: ánh xạ local gồm dataset_version, reading_id, split_id, source_position, split; mỗi khóa nguồn xuất hiện đúng một lần trong một giao thức.
- [data/metadata/splits.json](../data/metadata/splits.json): SHA-256 nội dung JSON config chuẩn hóa (không phụ thuộc LF/CRLF) và bytes từng ánh xạ, phiên bản nguồn/thư viện. Được đưa lên Git, còn ánh xạ cấp bản ghi được tái tạo local.
- [splits.py](../src/maintenance/splits.py): tạo/kiểm tra/nạp tập. Tái chạy cùng cấu hình cho cùng hash; nếu file ánh xạ đã có khác nội dung thì dừng, cần quyết định và split_id mới. Không tự ghi đè để thử seed khác.

Các mô hình phải nạp ánh xạ đã lưu, không tự train_test_split trong notebook riêng. Không join chỉ theo reading_id khi có nhiều dataset_version.

## Quy tắc dùng trong mô hình

`load_partition(root, split_id, "train" | "validation")` trả `keys`, `X` chỉ có sáu đầu vào, `y` nhãn tổng và metadata vai trò. Hàm kiểm tra hash config/ánh xạ, phủ đủ khóa và đúng thứ tự nguồn. Cờ chất lượng và loại hỏng không có trong X. `test` cần `allow_test=True`; `gap` không được nạp qua hàm này. Đây là rào chắn thao tác, không phải cơ chế bảo mật: bảng nguồn còn trên máy và kiểm tra hash không ngăn người có quyền sửa cả manifest.

1. Fit transformer và estimator trên train. Isolation Forest fit không dùng y, không lọc train chỉ còn các dòng không hỏng theo nhãn. Phân lớp dùng y_train. Không fit scaler trên toàn bảng feature hoặc validation/test.
2. Dùng validation để chọn cấu hình, feature set, ngưỡng; pipeline phải fit lại trên train cho từng cấu hình. Chưa refit bằng train+validation ở phiên bản đầu để tránh phải hiệu chỉnh ngưỡng theo thang điểm mới.
3. Trước khi mở test, lưu cấu hình đã khóa, tiêu chí chọn và seed mô hình. Cả giao thức chính/phụ khóa bằng validation của chính nó trước mọi so sánh test.
4. Sau khóa, đánh giá baseline và hai họ trên cùng test của từng giao thức, cùng ngân sách. Không thay cấu hình từ kết quả test. Kết quả test phụ chỉ là độ nhạy; hai giao thức không phải hai lần thử độc lập trên dữ liệu mới.
5. Mất cân bằng được giữ nguyên trong validation/test. Không SMOTE hoặc lọc mode dựa trên nhãn trước chia tập. Nếu áp dụng cân bằng ở bước mô hình sau này phải chỉ trong train và ghi quyết định.

## Quy tắc đánh giá đã định trước

Ngân sách báo cáo dự kiến cố định k = 20, 50, 100 trên tập đầy đủ; chỉ tính k không vượt số mẫu khi lọc phạm vi, ghi không khả dụng nếu không đủ. Không chọn k đẹp nhất sau khi xem test. Ngưỡng cho ma trận nhầm lẫn/Precision/Recall/F1 được chọn trên validation; quy tắc tối ưu và lưới mô hình phải ghi trước khi chạy tìm kiếm ở bước mô hình. ROC-AUC dùng điểm liên tục; thêm Average Precision và top-k. Không thay số ca hỏng ít bằng giả định tỷ lệ toàn nguồn. Xem [giao thức đánh giá test](TEST_EVALUATION.md).

Độ dao động cần phân biệt seed mô hình với thay đổi split. Seed split được cố định 42; các seed mô hình và phương pháp ước lượng độ dao động sẽ được đặc tả trước khi chạy mô hình. Không đổi split nhiều lần để lấy test tốt nhất hoặc báo seed mô hình như nhiều tập kiểm tra độc lập.

## Giới hạn cần ghi trong báo cáo

Nhóm đã xem audit và thống kê tổng hợp toàn nguồn trước split, gồm số đếm nhãn và tương quan đầu vào. Vì vậy test không phải nguồn hoàn toàn chưa được tiếp cận ở mọi mức. Bước này công khai số ca hỏng theo tập để kiểm tra khả năng tính chỉ số, không tối ưu theo điểm dự đoán. Chưa có đánh giá mô hình nào; test không dùng chọn feature/ngưỡng/thuật toán. Sau bước này không mở thêm phân tích chi tiết dựa trên nhãn test trước khi khóa mô hình.

Test chính chỉ có 38 ca hỏng, nên các chỉ số recall có thể dao động đáng kể; không suy ra hiệu quả nhà máy. Chia theo thứ tự nguồn kiểm tra khả năng chuyển giữa các đoạn điều kiện mô phỏng, không chứng minh mô hình đủ dùng ngoài thực tế, theo máy mới hoặc theo thời gian thật.

Tham khảo nguyên tắc chọn giao thức cho dữ liệu phụ thuộc và giữ test cho đánh giá cuối từ [scikit-learn cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html), API phân tầng của [train_test_split](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html). Không nâng thư viện ở bước này.
