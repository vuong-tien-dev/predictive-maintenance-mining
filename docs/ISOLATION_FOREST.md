# Baseline và Isolation Forest — kết quả validation v1

Ngày chạy: 29/10/2026. Bước 6, chưa chạy mô hình phân lớp hoặc đánh giá test. Hồ sơ kỹ thuật để thành viên rà soát; chưa phải báo cáo cuối.

## Thuật toán và ý nghĩa

Isolation Forest chia ngẫu nhiên các chiều/giá trị để cô lập điểm. Điểm dễ bị cô lập có đường đi ngắn hơn và được coi bất thường hơn. Không phải mọi điểm bất thường đều hỏng; cần đối chiếu nhãn thật sau khi có điểm.

Fit chỉ nhận sáu đầu vào của train, không truyền nhãn và không lọc train chỉ còn các dòng bình thường. Type được one-hot; công thức vật lý tính từ đầu vào. ID và nhãn không vào estimator. Điểm ưu tiên là `-pipeline.score_samples(X)`, đảo chiều đúng một lần để giá trị lớn hơn là bất thường hơn, không phải xác suất hỏng. Không dùng trực tiếp nhãn −1/+1 của predict để so với nhãn nguồn 0/1.

**Phân biệt:** fit Isolation Forest không dùng nhãn; chọn cấu hình và ngưỡng ở đây có dùng nhãn validation. Không gọi toàn bộ quy trình lựa chọn này là hoàn toàn không giám sát khi không có nhãn. Muốn kết luận hiệu quả trong điều kiện không có nhãn validation cần một giao thức khác.

## Thiết kế đặt trước khi chạy

[configs/isolation.json](../configs/isolation.json) quy định:

- Bốn cấu hình: base/physical × max_samples 256/1.024; mỗi cấu hình 200 cây, seed 42. Đây là lưới nhỏ có giới hạn, chưa chứng minh tối ưu toàn cục.
- Không scaling đầu vào số cho họ cây ở phiên bản này; vẫn dùng pipeline kiểm tra đầu vào và one-hot. Max samples là số bản ghi lấy cho mỗi cây, không phải kích thước train.
- `contamination="auto"` không lấy tỷ lệ hỏng từ test. Runner dùng score_samples và ngưỡng riêng, không dùng offset/predict của thư viện làm kết luận cuối.
- Chọn bằng validation Average Precision giảm dần; nếu bằng thì Precision@50 giảm dần, cuối cùng candidate_id tăng dần. Không chọn theo test.
- Chọn ngưỡng lớn nhất trong các ngưỡng đạt F1 cao nhất trên validation; cảnh báo khi score ≥ ngưỡng. Thử các điểm quan sát, giữ nguyên các nhóm đồng điểm; không chọn top-k bằng nhãn.
- Giữ cấu hình đã chọn, chạy thêm seed 43/44. Seed 42 là lần chạy chính, không chọn seed tốt nhất. Ngưỡng được chọn riêng trên validation của từng lần fit vì thang điểm có thể thay đổi. Chưa refit train+validation.
- Cả giao thức chính/phụ dùng [mapping đã chốt](SPLIT_PROTOCOL.md). Chưa mở test ở cả hai. Lựa chọn bằng validation là ước lượng có thiên lệch do lựa chọn; test sẽ kiểm chứng sau khi cả hai họ được khóa.

Average Precision là chỉ số xếp hạng tổng thể phù hợp để kiểm tra trong dữ liệu ít ca hỏng; không đồng nhất với diện tích hình thang dưới đường PR. Dùng thêm ROC-AUC, Precision/Recall/F1 và top-k, không kết luận chỉ bằng một chỉ số.

## Hai baseline

1. `random`: điểm sinh từ SHA-256(seed, dataset_version, reading_id). Không dùng feature/nhãn để tạo điểm, ổn định khi đổi thứ tự dòng. Đây là xếp hạng giả ngẫu nhiên, không phải quy luật vật lý từ ID. Đối chiếu ba seed và kỳ vọng lý thuyết của chọn đều: Precision@k kỳ vọng bằng tỷ lệ hỏng của tập, TP kỳ vọng bằng k × tỷ lệ hỏng. Một seed bắt được 0 ca không có nghĩa kỳ vọng bằng 0. Ngưỡng random cũng tối ưu bằng validation nên F1 của nó không phải kết quả ngoài mẫu.
2. `always_normal`: mọi điểm 0, ngưỡng 1 nên không cảnh báo. Recall/F1 = 0 khi tập có ca hỏng; Precision không xác định vì không có cảnh báo. ROC-AUC = 0,5 và AP bằng tỷ lệ hỏng trên tập đủ hai lớp. Không báo top-k cho baseline này vì không có xếp hạng phân biệt, tránh trình bày thứ tự ID tùy ý như một chính sách có ích.

Các mẫu số không xác định giữ null/ô trống và cờ `*_defined`, không âm thầm đổi thành 0. Khi đồng điểm top-k của mô hình xếp hạng, đọc ID tăng dần làm khóa phụ, không dùng nhãn. Khi k vượt số mẫu thì đánh dấu không khả dụng.

## Kết quả thực tế trên validation, seed 42

Cả hai giao thức chọn `if-physical-m1024`. Kết quả dưới đây lấy từ [candidates.csv](../reports/tables/isolation/candidates.csv) và [validation.csv](../reports/tables/isolation/validation.csv).

| Chỉ số | Chính: ordered-gap100-v1 | Phụ: stratified-seed42-v1 |
|---|---:|---:|
| Số mẫu / ca hỏng validation | 1.900 / 43 | 2.000 / 68 |
| Average Precision | 0,3202 | 0,2585 |
| ROC-AUC | 0,8593 | 0,8423 |
| Tìm đúng trong top 20 | 9 / 20 | 8 / 20 |
| Tìm đúng trong top 50 | 15 / 50 | 20 / 50 |
| Precision@50 | 30,00% | 40,00% |
| Recall@50 | 34,88% | 29,41% |
| TP / FP / FN / TN tại ngưỡng chọn | 15 / 31 / 28 / 1.826 | 20 / 25 / 48 / 1.907 |
| F1 tại ngưỡng chọn trên cùng validation | 0,3371 | 0,3540 |

Top-50 và ngưỡng F1 là hai chính sách khác nhau. Ví dụ ở giao thức chính, ngưỡng F1 tạo 46 cảnh báo, không phải 50; số TP trùng nhau ở lần chạy này không biến hai chính sách thành tương đương.

Tỷ lệ hỏng validation chính là 43/1.900 ≈ 2,26%; chọn đều 50 trường hợp kỳ vọng tìm khoảng 1,13 ca. Isolation Forest tìm 15 ca trên validation; đây chỉ là so sánh trên dữ liệu chọn cấu hình. Không suy ra tỷ lệ tương tự trên test/nhà máy. Giao thức phụ khác thành phần/tỷ lệ hỏng, không dùng bảng này để kết luận giao thức nào hoặc mô hình nào tốt hơn ngoài mẫu.

Các cấu hình base/physical trên cùng validation là thí nghiệm ban đầu về biến dẫn xuất, chưa phải kiểm chứng độc lập. [seed_summary.csv](../reports/tables/isolation/seed_summary.csv) ghi mean/std mẫu (ddof=1) của ba seed. Đây là dao động do ngẫu nhiên thuật toán trên cùng split, không phải khoảng tin cậy trên dân số hoặc ba test độc lập. Baseline luôn bình thường không thay đổi giữa seed.

## Chạy lại và đầu ra

```powershell
.\.venv\Scripts\python.exe scripts/create_splits.py
.\.venv\Scripts\python.exe scripts/train_isolation.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Hoặc Restart & Run All [03-models.ipynb](../notebooks/03-models.ipynb) trong môi trường `.venv`. Mã dùng chung: [models.py](../src/maintenance/models.py), [evaluation.py](../src/maintenance/evaluation.py). Notebook hiện chỉ có baseline/Isolation Forest; họ phụ thực hiện ở việc 7.

- `artifacts/models/<run_id>.joblib`: pipeline đã fit local. Chỉ nạp file do quy trình dự án tạo và kiểm tra hash; không nạp joblib không rõ nguồn.
- `artifacts/scores/<run_id>.csv`: điểm/rank và dự đoán validation, không chứa nhãn thật. Có khóa, split_id, run ID, feature_set và chiều điểm theo quy ước. Nhãn hậu kiểm join riêng bằng hai khóa.
- [selection.json](../reports/tables/isolation/selection.json): cấu hình chọn theo từng giao thức, seed/ngưỡng, nguồn dữ liệu, hash cấu hình/split/mã nguồn chuẩn hóa newline, hash mô hình và score để truy vết.
- Bảng tổng hợp và notebook được đưa lên Git; mô hình và dữ liệu cấp bản ghi giữ local. Mỗi seed lưu ngưỡng validation tương ứng để bước đánh giá sau dùng nguyên trạng.

File joblib có thể khác bytes/hash giữa các lần fit lại dù cùng cấu hình/seed cho cùng điểm và metrics. Hash mô hình dùng xác minh đúng file hiện tại, không phải cam kết bytes nhị phân tái tạo y hệt; kiểm tra tái lập tập trung vào cấu hình, score/rank, ngưỡng và chỉ số. Đã ghi nhận sai khác hash này trong kiểm tra và không đổi seed để che sai khác.

Chưa có score test. Không dùng các kết quả ở đây làm bằng chứng đánh giá độc lập, chưa kết luận hữu ích trong vận hành. Bước tiếp: phân lớp có giám sát trên cùng split; sau khi chốt cấu hình của cả hai họ mới đánh giá cuối.

Tài liệu thuật toán/chiều điểm: [scikit-learn IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html). Định nghĩa AP: [average_precision_score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html).
