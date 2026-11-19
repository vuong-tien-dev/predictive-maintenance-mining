# Tiền xử lý AI4I — phiên bản v1

Cập nhật 29/10/2026. Đã chạy chuyển đổi theo từng dòng trên 10.000 bản ghi; phần này không chia tập hoặc fit scaler trên AI4I/học mô hình. Ánh xạ chia tập đã được bổ sung riêng ở [việc 5](SPLIT_PROTOCOL.md). Tài liệu kỹ thuật phục vụ nhóm rà soát, chưa phải nội dung báo cáo cuối.

## Chạy lại và sản phẩm

```powershell
.\.venv\Scripts\python.exe scripts/prepare_data.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Hoặc chạy [02b-preprocessing.ipynb](../notebooks/02b-preprocessing.ipynb) từ kernel mới. Hàm dùng chung ở [preprocessing.py](../src/maintenance/preprocessing.py) và [features.py](../src/maintenance/features.py); nguồn được đọc và kiểm tra bởi module quality đã có.

| File tái tạo local | Nội dung | Số dòng × cột |
|---|---|---|
| `data/interim/ai4i-readings.csv` | 14 cột nguồn đổi tên/kiểu + dataset_version/schema_version | 10.000 × 16 |
| `data/processed/ai4i-features.csv` | Hai khóa + sáu đầu vào gốc + ba biến vật lý | 10.000 × 11 |
| `data/processed/ai4i-labels.csv` | Hai khóa + sáu nhãn nguồn | 10.000 × 8 |
| `data/processed/ai4i-quality_flags.csv` | Hai khóa + ba cờ chất lượng | 10.000 × 5 |

Hai khóa là `dataset_version × reading_id`. Các bảng giữ thứ tự nguồn để nối với split sau này, không diễn giải thành thời gian đo. Dữ liệu cấp bản ghi không lên Git; [manifest tiền xử lý](../data/metadata/preprocessing.json) được đưa lên Git, ghi tên cột, số dòng, hash nguồn và hash từng đầu ra. CSV giữ đơn vị vật lý, chưa scaling/one-hot; kiểu quy ước theo schema, cần chỉ định lại khi nạp vào cơ sở dữ liệu. Tập feature đã lưu không chứa nhãn, Product ID hoặc cờ chất lượng; khóa truy vết phải được tách trước khi vào mô hình.

## Quyết định xử lý

| Vấn đề | Lựa chọn | Lý do và giới hạn |
|---|---|---|
| Thiếu/sai kiểu/miền | Dừng và báo khi gặp, không tự điền/xóa | Nguồn hiện không có các lỗi này; chưa có căn cứ chọn chiến lược imputation |
| Dòng/ID trùng | Dừng nếu trùng reading_id | Nguồn hiện không có ID trùng; không âm thầm bỏ bản ghi |
| Ngoại lệ IQR/giá trị cực đoan hữu hạn | Giữ nguyên, không clipping/winsorization | Cực đoan có thể chính là đối tượng cần phát hiện; không dùng min/max quan sát làm ngưỡng loại |
| Nhãn tổng và mode bất nhất | Giữ nguyên cả sáu nhãn, tách cờ | Vẫn 9 dòng hỏng không mode, 18 dòng có mode nhưng tổng không hỏng; chưa biết nhãn nào sai |
| Nhiều mode | Giữ multi-label và cờ | 24 dòng có nhiều mode; không ép thành một lớp |
| ID/nhãn/cờ chất lượng | Không dùng làm feature | Các cờ được suy từ nhãn cũng gây rò rỉ; tách ở bảng riêng |
| Type L/M/H | One-hot theo miền schema, lỗi khi gặp loại khác | Không gán thứ bậc rủi ro L=1/M=2/H=3. Không cần học miền category từ test |
| Thang đo số | StandardScaler tùy cấu hình, fit trên train | Phục vụ phương pháp nhạy thang đo; không khẳng định scaler cần thiết hoặc cải thiện Isolation Forest |
| Giảm chiều/chọn biến | Chưa áp dụng PCA hoặc lọc theo nhãn/tương quan | Chỉ có sáu đầu vào; giữ diễn giải vật lý và thiết kế so sánh gốc/dẫn xuất, chưa có bằng chứng cần giảm chiều |

Không kiểm chứng được mọi số đo hợp lý vật lý chỉ nhờ hữu hạn/đúng kiểu. Bộ này phục vụ nguồn AI4I đã xác minh hash, chưa phải cơ chế chấp nhận dataset ngoài.

## Ba biến bổ sung

- `temperature_difference_k = process_temperature_k − air_temperature_k`: chênh nhiệt, đơn vị K.
- `power_w = torque_nm × rotational_speed_rpm × 2π / 60`: công suất cơ học, đơn vị W, có chuyển vòng/phút sang rad/giây.
- `wear_torque_min_nm = tool_wear_min × torque_nm`: tương tác độ mòn và tải, đơn vị min·N·m, không phải xác suất hoặc thời gian tới hỏng.

Các phép tính không học thống kê và chỉ dùng sáu đầu vào, có thể thực hiện trước split. Không tạo nhãn hỏng từ ngưỡng vật lý của nguồn rồi dùng nó làm feature. Kiểm tra đơn vị dùng dữ liệu nhân tạo: 60 rpm và 2 N·m cho 4π W; đây là test công thức, không phải kết quả mô hình AI4I.

## Dùng pipeline sau khi chia tập

`make_preprocessor(feature_set="base" | "physical", scale_numeric=True | False)` tạo pipeline chưa fit. Nó nhận đúng sáu cột đầu vào có tên chuẩn, từ chối cột nhãn/ID/thừa/thiếu, giá trị thiếu/không hữu hạn và Type ngoài miền. `select_inputs(readings)` tách whitelist từ bảng đầy đủ. Không truyền trực tiếp CSV feature có hai khóa hoặc chín feature đã tính vào pipeline: pipeline tự tính dẫn xuất từ sáu đầu vào để tránh dùng nhầm công thức.

Sau one-hot, `base` có 8 cột (5 số + 3 Type), `physical` có 11 cột (8 số + 3 Type). Đây là lựa chọn thiết kế, chưa có kết quả chứng minh cấu hình nào tốt hơn. Nhãn tổng dùng làm y cho phân lớp sau này; Isolation Forest không nhận nhãn để fit. Các cờ chất lượng không tham gia đầu vào hoặc lọc train dựa trên nhãn.

Scaling là bước học tham số: caller chỉ fit trên train, rồi dùng nguyên transformer cho validation/test. Pipeline hỗ trợ ghép vào Pipeline mô hình để fit lại đúng từng fold; không tự nhận biết tập nào là train nếu caller truyền sai. Bước này chỉ fit dữ liệu nhân tạo trong unit test để xác minh hành vi; chưa fit bất kỳ scaler nào lên AI4I.

Tham khảo nguyên tắc chống rò rỉ và nhất quán biến đổi của [scikit-learn](https://scikit-learn.org/stable/common_pitfalls.html), cấu hình category của [OneHotEncoder](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html). Môi trường chạy theo requirements.lock.txt của dự án; không nâng thư viện trong bước này.

## Kiểm chứng và việc còn lại

Đã kiểm tra công thức, không sửa đầu vào, tách nhãn/ID, miền category và dữ liệu không hữu hạn; test train/validation nhân tạo xác nhận mean của scaler không thay đổi sau transform validation. Đối chiếu toàn nguồn và file xuất xác nhận giữ 10.000 dòng, sáu nhãn không thay đổi, khóa và thứ tự khớp nhau. Hash đầu ra tái tạo được khi chạy lại cùng môi trường.

Đã có split/giao thức riêng tại [việc 5](SPLIT_PROTOCOL.md). Chưa có xử lý mất cân bằng bằng lấy mẫu, scaler AI4I đã fit, estimator, metrics hoặc kết quả ưu tiên. Chỉ fit các bước học tham số trên train theo mapping đã lưu khi triển khai mô hình.
