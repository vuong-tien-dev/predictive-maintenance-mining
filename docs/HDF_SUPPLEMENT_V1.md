# Bổ sung hậu kiểm HDF và phạm vi đánh giá v1

Ngày: 30/10/2026. Đã được chấp thuận bổ sung bốn phần: khảo sát mode, giới hạn split, phân tích HDF từ điểm đã có và tài liệu bàn giao. Không có huấn luyện/chấm model mới, không đổi split/model/ngưỡng/k/score/kết quả gốc. Không phải v2 hoặc một test độc lập mới.

## 1. Phân bố đã kiểm chứng

Nguồn vẫn 10.000 dòng, 339 nhãn hỏng tổng, 115 HDF. Bảng [blocks.csv](../reports/tables/hdf-supplement-v1/blocks.csv) ghi số nhãn mỗi khối 1.000 dòng: khối 3.001–4.000 có 7 HDF, khối 4.001–5.000 có 108, các khối còn lại không có. Trong khối 4.001–5.000 có 134 nhãn hỏng tổng.

[split-modes.csv](../reports/tables/hdf-supplement-v1/split-modes.csv) ghi đủ năm mode theo từng partition:

| Giao thức | Train HDF | Validation HDF | Test HDF |
|---|---:|---:|---:|
| Chính: ordered-gap100-v1 | 115 | 0 | 0 |
| Phụ: stratified-seed42-v1 | 67 | 22 | 26 |

Đây là số mode đo từ dữ liệu/mapping, không phải bảo đảm của stratify theo nhãn tổng. Không cộng mode chồng lấp thành số ca hỏng tổng.

## 2. Giới hạn và nguyên nhân

Cách chia chính giữ train ở vị trí 1–6.000 nên nhận toàn bộ vùng có HDF. Không có bước làm rơi/xóa nhãn và gap không loại HDF. Chia theo đoạn giúp tránh các dòng sát nhau qua ranh giới nhưng đồng thời làm các tập khác thành phần mode. Khoảng đệm 100 dòng chưa bảo đảm độc lập hoặc bao phủ mode.

Validation chính không kiểm chứng được việc chọn cấu hình cho HDF; test chính không đo được mức phát hiện HDF. Điểm chung của test chính vẫn đúng trên quần thể đó, nhưng không suy ra đủ hiệu quả mọi loại hỏng. Giữ giao thức chính và kết quả v1 nguyên trạng, không chuyển giao thức chính sang phương án có số đẹp hơn sau khi xem test.

## 3. Hậu kiểm bằng score v1 đã lưu, seed42

Mô hình dự đoán hỏng tổng. Bảng này đo **bao nhiêu trường hợp có nhãn HDF nằm trong danh sách/cảnh báo của mô hình**, không phải huấn luyện classifier HDF. Chọn top-k trên toàn validation/test trước khi đối chiếu nhãn mode, không lọc chỉ HDF rồi lấy top-k.

| Tập phân tầng | Chính sách | IF: HDF tìm được/tổng | LR: HDF tìm được/tổng |
|---|---|---:|---:|
| Validation | Top20 toàn tập | 0/22 | 4/22 |
| Validation | Top50 toàn tập | 5/22 | 8/22 |
| Validation | Top100 toàn tập | 6/22 | 11/22 |
| Validation | Ngưỡng validation cố định | 5/22 | 8/22 |
| Test | Top20 toàn tập | 0/26 | 2/26 |
| Test | Top50 toàn tập | 0/26 | 10/26 |
| Test | Top100 toàn tập | 2/26 | 14/26 |
| Test | Ngưỡng validation cố định | 0/26 | 10/26 |

Test phân tầng top50: IF bỏ sót 26/26 HDF ở ngân sách này, LR bỏ sót 16/26 (recall mode ≈38,46%). Ngưỡng IF phát 54 cảnh báo, ngưỡng LR phát 41; top50 luôn chọn 50, nên hai chính sách không đồng nhất dù một số đếm trùng nhau. IF tìm 2 HDF ở top100 không cho phép kết luận “hoàn toàn không thể nhận ra HDF”; kết luận phải gắn với chính sách/ngân sách.

Với validation/test chính, HDF recall là không xác định vì mẫu số 0, không ghi 0% hay 100%. Kết quả trong [hdf-coverage.csv](../reports/tables/hdf-supplement-v1/hdf-coverage.csv) giữ ô trống và cờ hdf_recall_defined=false ở các nhóm đó.

## 4. Tái tạo, kiểm tra và bàn giao

```powershell
.\.venv\Scripts\python.exe scripts/audit_hdf_v1.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Script độc lập [audit_hdf_v1.py](../scripts/audit_hdf_v1.py) đọc nguồn, mapping và score theo manifest, xác minh hash/quần thể rồi đếm; không import model, gọi fit, predict hoặc chọn lại ngưỡng. Các module đã nằm trong hash huấn luyện không bị sửa. [manifest](../reports/tables/hdf-supplement-v1/manifest.json) ghi hash nguồn/khóa, score đầu vào và ba bảng tổng hợp mới.

Gói tám bảng handoff-v1 và các kết quả v1 không đổi. Bổ sung này là tài liệu/bảng tổng hợp đi kèm, để phần kho/dashboard/báo cáo nêu đúng mức bao phủ HDF. Không tự đổi scope hoặc trạng thái task của hai thành viên; nếu tích hợp chart mới ngoài scope cần điều phối riêng.

Các kết luận này là phân tích hậu kiểm, dùng nhãn đã xem để hiểu giới hạn chứ không chọn cấu hình mới. Hai giao thức có dữ liệu chồng lấp giữa nhau, nên không coi phân tầng là dữ liệu kiểm chứng ngoài hoàn toàn mới. Không tuyên bố hiệu quả thời gian báo trước hoặc nhà máy thực. Cải tiến từ các phát hiện này cần thiết kế v2 và kiểm chứng phù hợp mới trước khi thực hiện.
