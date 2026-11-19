# Phân lớp hỏng/không hỏng — Logistic Regression v1

Ngày chạy: 29/10/2026. Việc 7 đã có kết quả train/validation cho hai giao thức; chưa mở test. Hồ sơ kỹ thuật phục vụ thành viên kiểm chứng, chưa phải báo cáo cuối.

## Mục tiêu và cách học

Họ phụ là phân lớp nhị phân Machine failure: 0 không hỏng, 1 hỏng. Không ép năm mode chồng lấp thành các lớp loại trừ nhau. Mục tiêu vẫn là xếp hạng ưu tiên các bản ghi và kiểm tra số ca hỏng tìm được trong ngân sách k.

Logistic Regression kết hợp tuyến tính các đầu vào đã biến đổi thành log-odds rồi qua sigmoid để tạo điểm lớp 1. Dù có chữ Regression, ở đây nó dùng cho phân lớp. So với mô hình phức tạp hơn, nó là đối chứng gọn, có hệ số để khảo sát và thích hợp làm bước đầu. Chưa khẳng định là bộ phân lớp tối ưu.

Fit dùng X_train và y_train; Type one-hot, số được StandardScaler fit trên train. Nhãn/ID/cờ chất lượng không vào X. Điểm lấy từ predict_proba ở cột tương ứng classes_==1, không mặc định chỉ số cột. Điểm cao nghĩa ưu tiên cao; chưa chứng minh xác suất đã hiệu chuẩn trên test hoặc ngoài dữ liệu mô phỏng.

## Lưới định trước

[configs/classification.json](../configs/classification.json) tạo 16 cấu hình mỗi giao thức:

- Feature set: base hoặc physical.
- C: 0,01 / 0,1 / 1 / 10. C là nghịch đảo sức mạnh điều chuẩn: C nhỏ phạt hệ số mạnh hơn. Không diễn giải C là tỷ lệ ca hỏng.
- class_weight: không trọng số hoặc balanced, thử cả hai vì dữ liệu mất cân bằng. Balanced tính trọng số từ y_train, tăng trọng lượng lớp ít; không tạo thêm bản ghi hoặc đổi nhãn/validation. Có thể làm thay đổi diễn giải điểm xác suất, không bảo đảm tốt hơn.
- Điều chuẩn L2, solver lbfgs, tol=0,0001, max_iter=2.000; triển khai bằng l1_ratio=0 theo phiên bản sklearn đã khóa. Không nâng thư viện. Cảnh báo chưa hội tụ được coi là lỗi thay vì im lặng nhận kết quả.
- Seed 42; lbfgs không dùng seed như ngẫu nhiên xây cây, nên không tạo ba lần chạy seed giống nhau rồi gọi đó là bằng chứng dao động độc lập.
- Chọn AP validation giảm dần, tie P@50 giảm dần rồi candidate_id tăng dần, cùng tiêu chí với Isolation Forest. Ngưỡng max F1 trên validation, tie ngưỡng lớn; không mặc định dùng 0,5.

Cả hai giao thức dùng train/validation qua loader đã có. Không fit lại trên train+validation, không gọi loader test, không chọn tham số từ test hoặc từ bảng so sánh test chưa tồn tại. Cấu hình chọn và ngưỡng đã lưu để dùng nguyên khi đánh giá cuối.

## Kết quả validation đã chạy

Mỗi tập có 6.000 mẫu train; tất cả 32 lần fit hội tụ, số vòng lặp tối đa quan sát được 38. Tập validation chính có 1.900 mẫu/43 ca hỏng; phụ có 2.000 mẫu/68 ca hỏng.

| Nội dung | Chính ordered-gap100-v1 | Phụ stratified-seed42-v1 |
|---|---:|---:|
| Cấu hình chọn | base, C=0,01, không trọng số | physical, C=1, không trọng số |
| Average Precision | 0,5011 | 0,4634 |
| ROC-AUC | 0,8297 | 0,8949 |
| Ca hỏng tìm được top 50 | 25 | 26 |
| Precision@50 | 50,00% | 52,00% |
| Recall@50 | 58,14% | 38,24% |
| TP/FP/FN/TN tại ngưỡng F1 | 24/13/19/1.844 | 27/24/41/1.908 |
| F1 tại ngưỡng chọn | 0,6000 | 0,4538 |

Top-50 và ngưỡng F1 là hai chính sách khác nhau. Ở tập chính, top-50 có 25 TP/25 FP; ngưỡng chọn tạo 37 cảnh báo, 24 TP/13 FP. Không lấy Precision/Recall của ngưỡng ghép vào kết quả top-50.

So với Isolation Forest seed 42 trên cùng validation chính: AP 0,5011 so với 0,3202; top-50 tìm 25 so với 15 ca hỏng; ROC-AUC lại thấp hơn (0,8297 so với 0,8593). Các chỉ số phản ánh vùng xếp hạng/đánh đổi khác nhau, không phải một lỗi tính toán. Chưa suy rằng phân lớp thắng ở mọi chỉ số hoặc ngoài mẫu.

Thêm biến vật lý không luôn tốt hơn: cấu hình thắng của Logistic Regression ở giao thức chính là base, nhưng ở giao thức phụ là physical. Không thay kết quả bằng câu chuyện “thêm biến chắc chắn cải thiện”. class_weight=balanced cũng không thắng ở cấu hình được chọn; mất cân bằng không có nghĩa phải bật balanced bất kể kiểm chứng.

## Giới hạn so sánh

- Kết quả trên chính validation dùng chọn trong 16 cấu hình nên lạc quan hơn đánh giá độc lập. Isolation Forest chọn trong 4 cấu hình, Logistic Regression chọn trong 16; ngân sách tìm kiếm khác nhau là giới hạn cần công khai.
- Hai họ khác cả thuật toán, cách học và khả năng biểu diễn; chênh lệch không phải tác động nhân quả thuần của riêng việc cung cấp nhãn. Chỉ có thể nói đây là so sánh hai cách tiếp cận có/không nhãn trong bước fit với thiết kế hiện tại.
- Cả hai đã dùng nhãn validation chọn cấu hình/ngưỡng. Không gọi toàn bộ nhánh Isolation Forest là hoàn toàn không có nhãn xuyên suốt.
- Giao thức chính/phụ khác thành phần và tỷ lệ hỏng, có chồng lấp giữa các giao thức. Không suy khác biệt chỉ số giữa hai giao thức thành kết luận trên hai bộ dữ liệu độc lập.
- Hệ số tại [coefficients.csv](../reports/tables/classification/coefficients.csv) là hệ số trong không gian đầu vào đã biến đổi. Có tương quan giữa biến và one-hot Type đầy đủ; không dùng độ lớn hệ số để khẳng định nguyên nhân hỏng hoặc xếp hạng tầm quan trọng tuyệt đối. Không có kiểm định nhân quả.
- Chưa có khoảng tin cậy hoặc thí nghiệm độ nhạy toàn diện của phân lớp; sẽ xử lý trong đánh giá mở rộng thay vì tạo dao động giả bằng seed không tác động solver.

## Chạy lại, kiểm chứng và bàn giao

```powershell
.\.venv\Scripts\python.exe scripts/train_classification.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Cần nguồn, split đã tái tạo và kết quả baseline/Isolation Forest trước đó; xem README để dựng môi trường. Hoặc chạy [03b-classification.ipynb](../notebooks/03b-classification.ipynb) từ kernel mới. Module [classification.py](../src/maintenance/classification.py) tái sử dụng features/evaluation/splits, không tự chia dữ liệu hoặc dùng định nghĩa metrics khác.

- [candidates.csv](../reports/tables/classification/candidates.csv): 32 dòng cấu hình/validation, có n_iter.
- [validation.csv](../reports/tables/classification/validation.csv): hai cấu hình được chọn.
- [comparison.csv](../reports/tables/classification/comparison.csv): baseline/Isolation Forest seed 42 và phân lớp trên cùng quần thể từng giao thức.
- [selection.json](../reports/tables/classification/selection.json): nguồn, hash config/split/mã nguồn, tham chiếu lựa chọn Isolation Forest, cấu hình/ngưỡng, model/score paths và hashes.
- artifacts/models và artifacts/scores: model và điểm từng bản ghi giữ local, có run ID, split_id, khóa phiên bản/bản ghi, score, dự đoán và thứ hạng; không chứa nhãn thật trong score CSV.

Đã kiểm tra lớp dương đúng cột ngay cả khi thứ tự classes_ đảo, y thực sự tác động fit, tái lập, scaler không học validation, nhãn/ID không vào đầu vào, train một lớp phải lỗi. Notebook chạy từ kernel mới. File nhị phân joblib không được cam kết cùng hash sau fit lại; hash xác minh file hiện tại, còn tái lập kiểm tra cấu hình/điểm/ngưỡng/chỉ số. Chỉ nạp model do quy trình dự án tạo.

Tham khảo API/ý nghĩa tham số tại [scikit-learn LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html). Bước tiếp theo là khóa các cấu hình và thực hiện đánh giá cuối theo giao thức, chưa thực hiện test trong việc 7.
