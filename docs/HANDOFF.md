# Bàn giao phần nền phân tích — handoff-v1

Gói handoff-v1 là đầu vào cố định cho kho PostgreSQL, Superset và kiểm chứng độc lập. Tài liệu mô tả cách tái tạo, cấu trúc bảng và kết quả đối soát.

## Bắt đầu trên máy khác

1. Mở bản sao của nhánh main tại thư mục gốc dự án.
2. Cài Python 3.12 và dựng môi trường Windows theo README:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe scripts/reproduce.py --download
```

`--download` chỉ tải ZIP AI4I chính thức nếu CSV chưa có và kiểm tra SHA-256 ZIP/CSV trước khi lưu. Không tải C-MAPSS, không upload dữ liệu. Nếu đã có đúng CSV, có thể bỏ `--download` để chạy hoàn toàn local sau khi thư viện đã sẵn. File nguồn sai hash làm dừng, không tự thay thế file đang có. Nhánh tải mạng không cần thiết cho máy hiện tại vì đã có CSV đúng phiên bản.

Lệnh reproduce tuần tự chạy quality → chuẩn hóa bảng → split → Isolation Forest/baseline → Logistic Regression → test cố định → đóng gói bàn giao → tests. Dừng ngay khi có lỗi. Nó tái tạo quyết định đã chốt, không cho phép tự đổi seed/feature/ngưỡng sau khi xem test. Test được tính lại để xác minh, không phải lần đánh giá độc lập mới.

Khi tái tạo mô hình, binary joblib có thể đổi hash; metadata được cập nhật theo file hiện tại, khóa quyết định test gốc vẫn được giữ. Không xóa evaluation-lock để chạy cấu hình mới qua; nếu code/config/split/score hoặc quyết định khác, cần báo lỗi và điều phối.

## Chỉ đóng gói/xác minh nếu đã chạy đủ bước

```powershell
.\.venv\Scripts\python.exe scripts/build_handoff.py
.\.venv\Scripts\python.exe scripts/build_handoff.py --verify-only
```

Bộ CSV nằm tại `data/processed/handoff-v1/`, được Git bỏ qua. [data/metadata/handoff.json](../data/metadata/handoff.json) là danh mục theo dõi trên Git: đường dẫn, số dòng, grain, cột/kiểu pandas/null và SHA-256 từng file; bản manifest cùng nội dung nằm ngay trong thư mục gói. Không cần nhận model nhị phân hoặc CSV qua tin nhắn nếu có thể tái tạo bằng code.

Đây là folder dữ liệu bàn giao, không phải một hệ thống PostgreSQL đã cài sẵn. Dựng venv và tải thư viện lần đầu cần kết nối; phân tích/huấn luyện/đánh giá chạy local. Không yêu cầu có Docker để tạo gói này, Docker dành cho phần kho/dashboard sau.

## Tám bảng đã xuất

| File trong gói | Dòng | Khóa duy nhất / grain | Mục đích |
|---|---:|---|---|
| readings.csv | 10.000 | dataset_version × reading_id | 14 cột nguồn chuẩn hóa + phiên bản, chứa nhãn để hậu kiểm |
| features.csv | 10.000 | dataset_version × reading_id | Sáu đầu vào và ba biến vật lý, không nhãn |
| quality_flags.csv | 10.000 | dataset_version × reading_id | Ba cờ hậu kiểm suy từ nhãn, không làm feature |
| split_membership.csv | 20.000 | split_id × dataset_version × reading_id | Hai giao thức, mỗi giao thức phủ đủ 10.000 dòng kể cả gap |
| model_runs.csv | 20 | model_run_id | Họ mô hình, seed, feature set, split_id và ngưỡng khóa |
| scores.csv | 78.000 | model_run_id × split × dataset_version × reading_id | Điểm/rank/dự đoán của validation/test; không nhãn thật |
| metrics.csv | 40 | model_run_id × split × population_scope | Một dòng validation/test cho mỗi run, chỉ phạm vi all |
| budget_metrics.csv | 120 | model_run_id × split × population_scope × budget_k | K=20/50/100 cho mỗi run/tập, kể cả dòng không áp dụng |

20 model runs gồm 10 ở mỗi giao thức: IF3 seed, random3 seed, always_normal3 seed và LR1 seed. Mỗi run có validation và test nên metrics có 40 dòng; 3 ngân sách cho mỗi dòng nên budget_metrics có 120 dòng. Test chính/validation chính đều 1.900 dòng, phụ đều 2.000, nên scores có 10×(1.900+1.900+2.000+2.000)=78.000 dòng. Không nhầm 78.000 điểm mô hình là 78.000 quan sát cảm biến độc lập.

## Tên cột, kiểu và đơn vị phải giữ

- Mã chuỗi: dataset_version, schema_version, split_id, model_run_id, model_family, feature_set, product_id, product_type, split, population_scope. Không đổi Product ID thành mã máy.
- Các khóa/số đếm/rank/seed/k là số nguyên. Khi CSV có null, pandas có thể ghi cột đếm dạng float; ở kho có thể dùng integer nullable sau kiểm tra phần thập phân bằng 0. Không biến null thành 0 để ép kiểu.
- Các số đo/score/threshold/chỉ số là double precision; temperature giữ K, speed rpm, torque N·m, wear min; power W. Dùng từ điển cột và manifest, không đổi đơn vị âm thầm.
- Cờ chất lượng/defined/applicable là boolean, CSV biểu diễn True/False. Nhãn và predicted_failure là 0/1 nguyên.
- metrics có precision/recall/f1 nullable và cờ *_defined. ROC-AUC/AP có thể null nếu không xác định theo quy tắc; không fill 0. Budget metrics có topk_applicable=false cho always_normal và tp/precision/recall null. Không gọi null là mô hình đạt 0 hay 100%.
- priority_score càng lớn càng ưu tiên. IF là âm score_samples, không phải xác suất; LR là predict_proba lớp1, chưa chứng minh hiệu chuẩn. Không so trực tiếp thang điểm hai model để xếp chung một danh sách.
- priority_rank được tính trong toàn population của một model_run_id × split; tie dùng reading_id tăng dần. predicted_failure dùng ngưỡng validation đã lưu, không phải tự động top50.
- model_runs.threshold giữ đủ độ chính xác, không làm tròn trước khi tính dự đoán. metadata JSON và CSV dùng UTF-8, dấu phẩy, dấu chấm thập phân, LF do exporter sinh. pydtype trong manifest là trạng thái thực tế pandas, không phải câu lệnh DDL đã triển khai.

Từ điển nền: [DATA_DICTIONARY.md](DATA_DICTIONARY.md), [DATA_CONTRACT.md](DATA_CONTRACT.md). Gói chỉ xuất CSV; mô hình fit lại vẫn phải dùng sáu đầu vào gốc qua select_inputs và pipeline, không dùng cả features.csv có khóa hoặc cờ/nhãn.

## Quy tắc nối và chống nhân số liệu

1. scores → model_runs: nối model_run_id, quan hệ nhiều–một. model_run chỉ thuộc một split_id; không suy split_id bằng cách cắt chuỗi ID.
2. scores → readings: nối dataset_version + reading_id, nhiều–một. Đây là chỗ lấy nhãn thật cho hậu kiểm; không đưa nhãn vào điểm trước khi xếp hạng.
3. scores → split_membership: nối thêm split_id cùng hai khóa nguồn; xác minh split trong mapping bằng split của score. Không nối readings với toàn bộ mappings chỉ bằng reading_id vì có hai giao thức.
4. metrics/budget_metrics là bảng tổng hợp riêng. Không nối ngân sách vào tất cả dòng score rồi SUM n_samples/TP/FP: chỉ số bị lặp theo bản ghi. Không SUM n_samples qua nhiều run để gọi đó là số máy/quan sát.
5. Lọc một run/partition cụ thể hoặc COUNT DISTINCT(dataset_version, reading_id) trong phạm vi rõ ràng trước khi báo số bản ghi. Không gộp validation và test hoặc hai giao thức thành một “đánh giá test chung”.

Ví dụ hậu kiểm SQL sau khi nạp ba bảng tương ứng vào PostgreSQL (chưa phải script kho đã chạy):

```sql
SELECT s.model_run_id, s.split,
       COUNT(*) AS n_readings,
       SUM(r.machine_failure) AS n_failures,
       SUM(CASE WHEN s.priority_rank <= 50 THEN r.machine_failure ELSE 0 END) AS tp_at_50
FROM scores s
JOIN model_runs m ON m.model_run_id = s.model_run_id
JOIN readings r ON r.dataset_version = s.dataset_version AND r.reading_id = s.reading_id
WHERE m.split_id = 'ordered-gap100-v1'
  AND m.model_family = 'logistic_regression'
  AND m.seed = 42 AND s.split = 'test'
GROUP BY s.model_run_id, s.split;
```

Kết quả đối soát mong đợi của truy vấn trên: 1.900 dòng, 38 ca hỏng, 21 TP trong top50. Đây là kỳ vọng từ kết quả Python đã chạy; SQL minh họa chưa được nghiệm thu trên PostgreSQL.

## Bộ lọc/dashboard và warehouse cần lưu ý

Góc nhìn mặc định nên chỉ rõ split_id chính, seed42, test và model được chọn; cho đổi model/giao thức nhưng phải giữ label về phạm vi. Điểm/rank chỉ được tính cho validation/test; train/gap vẫn có trong readings/mapping, không có score và không được gán score0 thành “khỏe mạnh”.

Nếu lọc Type, phải quyết định chart đang mô tả giao của nhóm với top50 toàn tập hay tính lại top50 trong nhóm. Gói v1 chỉ có metrics population_scope=all; không áp bộ lọc Type vào mẫu số all rồi trình bày như chỉ số trong nhóm. groups.csv của bước 8 chỉ là hậu kiểm global_top50, không phải quota 50 mới cho từng nhóm. Không dùng nhãn thật làm bộ lọc tạo danh sách kiểm tra.

Từ các bảng này có thể thiết kế fact readings và fact scores/metrics với dimension phiên bản dữ liệu, loại sản phẩm, model run/giao thức. Thiết kế star schema/ERD cuối thuộc phần kho, phải có ít nhất fact và số dimension đúng yêu cầu học phần, grain rõ. Không tự tạo Dim_Date theo thời gian đo hoặc Dim_Machine từ Product ID khi dữ liệu không có. Ngày chạy/tải là metadata, không phải ngày đo.

Kho và dashboard phải dùng kết quả thật đã khóa; không huấn luyện lại hoặc thay ngưỡng để chart đẹp. Cần phân biệt hai chính sách: top-k với ngưỡng validation. Các bảng/hình báo cáo tham chiếu tại [TEST_EVALUATION.md](TEST_EVALUATION.md), [CLASSIFICATION.md](CLASSIFICATION.md) và [ISOLATION_FOREST.md](ISOLATION_FOREST.md).

## Bổ sung hậu kiểm HDF, không đổi gói v1

Đọc [HDF_SUPPLEMENT_V1.md](HDF_SUPPLEMENT_V1.md) và ba bảng tại reports/tables/hdf-supplement-v1/. Test/validation chính không có HDF, không báo recall mode là 0%; phân tầng có 22/26 HDF ở validation/test. Trên test phân tầng top50, IF chọn 0/26 HDF, LR 10/26, tính trên danh sách ưu tiên toàn tập. Giữ tám bảng handoff và số liệu gốc nguyên vẹn; các bảng mới là hồ sơ bổ sung. Không thay split/ngưỡng hoặc tự tạo classifier mode từ phân tích này.

## Điểm kiểm tra để tiếp nhận

| Nội dung kiểm chứng | Kỳ vọng |
|---|---|
| Số quan sát gốc | 10.000, 339 nhãn hỏng |
| Bảng scores | 78.000, khóa duy nhất, chỉ validation/test |
| Tập test chính mỗi run | 1.900 dòng / 38 hỏng |
| LR seed42 test chính top50 | 21 TP, 29 FP, 17 FN |
| IF seed42 test chính top50 | 13 TP, 37 FP, 25 FN |
| LR ngưỡng validation trên test chính | 10 TP, 1 FP, 28 FN, 1.861 TN |
| IF ngưỡng validation trên test chính | 13 TP, 25 FP, 25 FN, 1.837 TN |
| Tái tạo gói | Hash/rowcount/grain đúng metadata; kiểm tra score/rank/ngưỡng và metrics nguồn đạt |

Chạy verify-only xác minh bytes, cột, số dòng và khóa; export_handoff còn kiểm tra đủ run/partition, metadata, rank, ngưỡng, hash nguồn score và tính metrics lại để đối chiếu báo cáo. Không coi hash đúng thay cho mọi kiểm tra ý nghĩa. Môi trường thư viện có thể ảnh hưởng sai khác số thực; nếu có sai khác phải ghi lại, không sửa số liệu tham chiếu để bỏ qua.

## Sử dụng gói CSV

- [Kho PostgreSQL](WAREHOUSE.md) và [dashboard Superset](DASHBOARD.md) đọc dữ liệu theo cấu trúc ở trên.
- [Hồ sơ kiểm chứng tái lập](REPRODUCIBILITY_REVIEW.md) ghi kết quả kiểm tra hash, chỉ số và phạm vi kiểm chứng Docker.

Nguồn được ghi công theo [UCI AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset), DOI 10.24432/C5HS5C, CC BY 4.0. Không phát biểu dữ liệu mô phỏng đã chứng minh hiệu quả trên máy thật. Test v1 đã được xem, nên mọi cải tiến sau đây phải được công khai và có đánh giá phù hợp mới, không dùng test cũ để tối ưu rồi gọi độc lập.
