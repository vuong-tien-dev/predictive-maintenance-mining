# Quy ước dữ liệu dùng chung

Cập nhật 29/10/2026: đã chốt schema nguồn `ai4i-v1` và đối chiếu CSV thực tế. Đọc [từ điển dữ liệu](DATA_DICTIONARY.md) và [cấu hình schema](../configs/ai4i-schema.json) để lấy ánh xạ đủ 14 cột, kiểu, đơn vị và vai trò. Đã có bộ đọc kiểm tra nguồn phục vụ chất lượng/EDA trong `src/maintenance/quality.py`, đã có chuyển đổi theo dòng và pipeline tiền xử lý chưa fit tại [PREPROCESSING.md](PREPROCESSING.md); đã có ánh xạ split tại [SPLIT_PROTOCOL.md](SPLIT_PROTOCOL.md); các phần giao diện kết quả bên dưới vẫn là thiết kế, không phải file đã sinh. Metadata nguồn nằm trong datasets/manifest.json; đã có kết quả Isolation Forest/baseline trên validation ở [việc 6](ISOLATION_FOREST.md), đã có [Logistic Regression](CLASSIFICATION.md) fit có nhãn trên train và lựa chọn validation; đã có [test v1](TEST_EVALUATION.md) với model/ngưỡng đã khóa, không fit/chọn lại.

Đã chọn cấu trúc AI4I làm schema tham chiếu theo yêu cầu ngày 27/10/2026: 14 cột gốc, gồm 2 ID, 6 đầu vào và 6 nhãn. Các adapter tương lai phải giữ đúng ý nghĩa vật lý, đơn vị và vai trò từng cột. Chưa triển khai adapter hoặc tự áp đặt rằng mọi nhãn đều bắt buộc khi chấm điểm dữ liệu mới; điều kiện nhận dataset bên ngoài cần được xác định riêng theo tác vụ.

## Bản ghi vận hành

- Grain: một dòng dữ liệu nguồn là một trạng thái vận hành, không mặc nhiên là một máy hoặc một phút đo.
- `reading_id`: ánh xạ ổn định từ cột **UDI** trong CSV thực tế (mô tả UCI ghi UID); không dùng làm đầu vào dự đoán.
- `product_id`: ID sản phẩm nguồn, chỉ dùng truy nguyên.
- `product_type`: Type L/M/H, là thuộc tính đầu vào có thể sử dụng sau khi kiểm chứng ý nghĩa.
- `air_temperature_k`, `process_temperature_k`, `rotational_speed_rpm`, `torque_nm`, `tool_wear_min`: đầu vào đo lường, đơn vị nằm trong tên và data dictionary.
- `machine_failure`: nhãn đánh giá/phân lớp.
- `twf`, `hdf`, `pwf`, `osf`, `rnf`: nhãn chế độ hỏng; một dòng có thể có nhiều nhãn, không ép chọn một nhãn đại diện.
- `dataset_version`: `sha256:` nối toàn bộ SHA-256 của CSV nguồn; không phải thời điểm vận hành. `schema_version = ai4i-v1` là phiên bản quy ước cột, ghi riêng trong metadata.
- Khóa bản ghi chuẩn hóa: `dataset_version × reading_id`. Đọc CSV bằng `utf-8-sig` để bỏ BOM; không thay đổi bytes của file nguồn.

## Biến vật lý

- `temperature_difference_k = process_temperature_k - air_temperature_k`.
- `power_w = torque_nm * rotational_speed_rpm * 2π / 60`.
- `wear_torque_min_nm = tool_wear_min * torque_nm`.
- Không thêm nhãn vào feature list; danh sách feature tách rõ theo cấu hình thí nghiệm.

## Bảng chuẩn hóa và đầu vào mô hình

Xem [manifest tiền xử lý](../data/metadata/preprocessing.json). Bảng readings có 14 cột nguồn đã đổi tên/kiểu + dataset_version/schema_version; bảng features có hai khóa và 9 feature (6 gốc + 3 dẫn xuất); bảng labels có hai khóa và 6 nhãn; bảng quality_flags có hai khóa và 3 cờ. Các file cấp bản ghi trong data/interim/ và data/processed/ chỉ giữ local. Cờ được tính từ nhãn nên tuyệt đối không làm feature.

`make_preprocessor` nhận đúng sáu đầu vào gốc và tự tính biến dẫn xuất nếu cấu hình physical. Dùng `select_inputs` để tách khỏi ID/nhãn/cờ và feature đã tính sẵn. CSV lưu đơn vị vật lý; chưa fit scaler hoặc one-hot trên AI4I.

## Chia tập và kết quả mô hình

- Ánh xạ cố định dùng chung theo từng `split_id`, xem [SPLIT_PROTOCOL.md](SPLIT_PROTOCOL.md). Chính: ordered-gap100-v1, giữ 6.000 train/1.900 validation/1.900 test và 200 gap. Phụ: stratified-seed42-v1, 6.000/2.000/2.000, seed 42. Hai giao thức không phải các test độc lập.
- File ánh xạ split có `dataset_version`, `reading_id`, `split_id`, `source_position`, `split`; một ánh xạ cho mỗi giao thức. Không tự chia lại trong từng notebook. `gap` không dùng học/chọn/chấm. Hash config chuẩn hóa JSON và hash mapping nằm trong data/metadata/splits.json.
- Một dòng điểm mô hình: `model_run_id × dataset_version × reading_id`; mỗi run phải khai báo rõ phiên bản dữ liệu và `split_id`. Không trộn kết quả các giao thức.
- Trường tối thiểu: `model_run_id`, `dataset_version`, `reading_id`, `split`, `model_family`, `feature_set`, `priority_score`, `split_id`.
- `priority_score`: giá trị lớn hơn có nghĩa ưu tiên kiểm tra cao hơn. Đảo chiều score của thư viện nếu cần và ghi lại quyết định.
- Xếp hạng khi bằng điểm dùng `reading_id` làm khóa phụ ổn định. Không mặc định mọi model có cùng thang điểm hay score là xác suất.
- Nhãn thật chỉ dùng cho đánh giá/hậu kiểm; tách khỏi giao diện chấm điểm đầu vào. Bước 6 đã lưu score validation có thêm predicted_failure và priority_rank; rank theo score giảm dần/reading_id tăng dần. Isolation Forest fit không nhãn, Logistic Regression fit với y_train; cả hai lựa chọn cấu hình/ngưỡng bằng validation. Họ phụ đã xuất cùng giao diện score, giá trị lớn hơn là ưu tiên lớp 1 hơn nhưng chưa chứng nhận hiệu chuẩn; đã lưu test score local tại artifacts/scores/test/ theo cùng schema, bảng hậu kiểm nhãn/lỗi tách riêng tại artifacts/metrics/test-errors/. Manifest khóa và kết quả đánh giá ở data/metadata/evaluation-lock.json và reports/tables/test/manifest.json.

## Chỉ số theo ngân sách

- Grain: một dòng cho mỗi `model_run_id × split × population_scope × budget_k`.
- Ghi rõ số mẫu và số ca hỏng trong phạm vi trước khi tính Precision@k, Recall@k, TP/FP/FN.
- Chỉ nhận k trong phạm vi số mẫu; xử lý rõ phạm vi không có ca hỏng, không âm thầm biến chỉ số không xác định thành 0.
- Bộ lọc Type phải chọn đúng metrics của phạm vi hoặc tính lại xếp hạng trong phạm vi đó. Nhãn thật không dùng làm bộ lọc tạo danh sách ưu tiên.
- Nhiều model hoặc nhiều ngân sách không được làm nhân số reading trong thống kê kho.

## Bộ giao diện bàn giao v1

[HANDOFF.md](HANDOFF.md) chốt 8 bảng local tại data/processed/handoff-v1, [manifest](../data/metadata/handoff.json) chứa cột/kiểu/null/grain/số dòng/hash. scores gộp validation/test có 78.000 dòng, model_runs20, metrics40 và budget_metrics120; đây là nhiều kết quả trên cùng quan sát, không phải số bản ghi nguồn mới. Quy tắc join/không cộng lặp và bộ lọc Type được mô tả trong hồ sơ. Chưa có PostgreSQL/Superset thực thi.

## Manifest và metadata

Ghi URL nguồn, DOI, giấy phép, ngày tải, SHA-256 của file gốc, số dòng/cột thực đo, phiên bản schema, số mẫu sau xử lý và cấu hình split. Ngày tải/huấn luyện không được trình bày thành ngày đo cảm biến.
