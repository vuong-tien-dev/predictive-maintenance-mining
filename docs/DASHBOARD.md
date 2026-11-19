# TÀI LIỆU HƯỚNG DẪN & VẬN HÀNH DASHBOARD APACHE SUPERSET
## Đề tài 16: Khai thác Dữ liệu Bảo trì Dự đoán Thiết bị

* **Người phụ trách:** Quốc Việt (Vai trò: `QV`)
* **Ngày cập nhật:** 02/11/2026
* **Trạng thái:** Đã triển khai và đóng gói bundle xuất bản hoàn chỉnh.

---

## 1. Thông tin Truy cập & Khởi động Nhanh

* **Địa chỉ Dashboard:** [http://localhost:8088/superset/dashboard/de-tai-16-bao-tri-du-doan/](http://localhost:8088/superset/dashboard/de-tai-16-bao-tri-du-doan/)
* **Tài khoản quản trị viên mặc định:**
  * **Tên đăng nhập:** `admin`
  * **Mật khẩu:** `admin123`
* **Lệnh khởi động hạ tầng (nếu chưa chạy):**
  ```powershell
  cd infra
  docker compose up -d
  ```

---

## 2. Danh mục 5 Biểu đồ Thực tế & 1 Bảng Danh sách Ưu tiên

Dashboard được thiết kế trực tiếp phục vụ câu hỏi cốt lõi của người quản lý bảo trì:
*"Với ngân sách kiểm tra $k$ bản ghi trạng thái vận hành, phương pháp xếp hạng nào phát hiện nhiều ca hỏng nhất, đồng thời kiểm soát cảnh báo giả và ca bỏ sót?"*

### Biểu đồ 1: Đánh đổi Ngân sách — Precision@k theo Ngân sách $k$ (Line Chart)
* **Mục đích:** Thể hiện tỷ lệ chính xác (Precision@k) khi mở rộng ngân sách kiểm tra từ $k=20 \rightarrow 50 \rightarrow 100$.
* **Nguồn dữ liệu:** `agg_budget_metrics`.
* **Ý nghĩa thực tế:** Cho thấy rõ sự đánh đổi: ở ngân sách nhỏ ($k=20$), mô hình Logistic Regression đạt độ chính xác lên tới 75.00%, nhưng khi nới lỏng ngân sách lên $k=100$, độ chính xác giảm xuống 24.00% do xuất hiện thêm cảnh báo giả. Isolation Forest duy trì mức Precision 26.00%–40.00%, vượt trội hoàn toàn so với Random baseline (khoảng 2.00%).

### Biểu đồ 2: Số ca hỏng bắt được (Recall@k / True Positives) theo Ngân sách (Bar Chart)
* **Mục đích:** Đo lường số lượng ca hỏng hóc thực tế được phát hiện ứng với từng mức ngân sách $k$.
* **Nguồn dữ liệu:** `agg_budget_metrics`.
* **Ý nghĩa thực tế:** Với tổng số 38 ca hỏng trên tập Test chính, tại $k=50$, Logistic Regression phát hiện được **21 ca hỏng** (Recall = 55.26%), Isolation Forest phát hiện được **13 ca hỏng** (Recall = 34.21%), trong khi ngẫu nhiên chỉ bắt được 0–1 ca.

### Biểu đồ 3: Ma trận Nhầm lẫn tại Ngưỡng Cố định (Pivot Matrix Table)
* **Mục đích:** Đánh giá hiệu năng của mô hình theo chính sách **Ngưỡng phân loại cố định** (được khóa từ tập Validation), tách bạch với chính sách Top-k.
* **Nguồn dữ liệu:** `view_priority_inspection`.
* **Số liệu chuẩn đối soát:**
  * Logistic Regression (ngưỡng 0.1439): $\mathbf{TP = 10,\ FP = 1,\ FN = 28,\ TN = 1861}$. Độ đặc hiệu (*Specificity*) cực cao, hầu như không có báo động giả ($FP=1$).
  * Isolation Forest (ngưỡng 0.1447): $\mathbf{TP = 13,\ FP = 25,\ FN = 25,\ TN = 1837}$.

### Biểu đồ 4: Cơ cấu Chế độ Hỏng hóc trong Cảnh báo Top-50 (Pie / Donut Chart)
* **Mục đích:** Thống kê các dạng sự cố (TWF, HDF, PWF, OSF, RNF) xuất hiện trong Top-50 bản ghi được cảnh báo nguy hiểm nhất.
* **Nguồn dữ liệu:** `view_priority_inspection`.
* **Ý nghĩa thực tế:** Giúp đội bảo trì biết rõ dạng hỏng hóc phổ biến nhất cần mang dụng cụ thay thế (hỏng do mòn dụng cụ TWF, quá tải OSF hay sự cố công suất PWF). Có chú thích rõ các trường hợp thiết bị gặp đa sự cố đồng thời (*Multilabel*).

### Biểu đồ 5: Phân phối Điểm Bất thường theo Loại Sản phẩm Type L/M/H (Box Plot)
* **Mục đích:** Quan sát phân phối điểm ưu tiên/bất thường (`priority_score`) theo từng phân khúc sản phẩm (L: Tiêu chuẩn, M: Trung cấp, H: Cao cấp).
* **Nguồn dữ liệu:** `view_priority_inspection`.
* **Ý nghĩa thực tế:** Đảm bảo điểm số không bị lệch pha bất thường giữa các dòng sản phẩm, hỗ trợ đánh giá tính công bằng kỹ thuật.

### Bảng Thành phần 6: Danh sách Ưu tiên Kiểm tra Hàng đầu (Top-k Priority Inspection Table)
* **Mục đích:** Bảng danh sách hành động thực tế cho kỹ thuật viên bảo trì.
* **Các trường hiển thị:** `priority_rank` (thứ tự ưu tiên từ 1 đến $k$), `reading_id`, `product_id`, `product_type`, `priority_score`, các thông số cảm biến (`air_temperature_k`, `rotational_speed_rpm`, `torque_nm`, `tool_wear_min`, `power_w`), và nhãn thực tế (`actual_failure`, `failure_mode`) dùng để đối soát hậu kiểm.
* **Nguyên tắc:** Thứ hạng sắp xếp giảm dần theo điểm số `priority_score`, nếu bằng điểm thì dùng `reading_id` tăng dần làm khóa phụ ổn định.

---

## 3. Cấu hình Native Filters Tương tác

Dashboard tích hợp sẵn 4 bộ lọc tương tác trực quan (không làm reload trang web và không gây sai lệch mẫu số):

1. **Bộ lọc Họ mô hình (`model_family`):** Lựa chọn xem kết quả của `logistic_regression`, `isolation_forest`, hoặc `random`.
2. **Bộ lọc Giao thức chia tập (`split_id`):** Mặc định: `ordered-gap100-v1` (giao thức chính có vùng đệm 100 dòng cách ly).
3. **Bộ lọc Phân hoạch (`partition`):** Mặc định: `test` (đánh giá độc lập) hoặc chọn `validation`.
4. **Bộ lọc Seed Ngẫu nhiên (`seed`):** Mặc định: `42`.

---

## 4. Gói Xuất bản & Hướng dẫn Khôi phục Độc lập

Toàn bộ cấu hình Dashboard, Charts, Datasets và Database Connection đã được xuất bản thành file ZIP tiêu chuẩn tại:
`dashboards/exports/dashboard_export.zip`

### Hướng dẫn Khôi phục trên một Máy Chủ Superset Sạch:
Nếu triển khai trên một máy khác hoặc khôi phục sau khi xóa volume:

```powershell
# 1. Sao chép file export vào container Superset
docker cp dashboards/exports/dashboard_export.zip pm_superset:/tmp/dashboard_export.zip

# 2. Thực thi lệnh import tự động
docker exec pm_superset superset import-dashboards -p /tmp/dashboard_export.zip -u admin

# 3. Truy cập vào giao diện web Superset để xem Dashboard đã được phục hồi 100%
```

---

## 5. Kịch bản Thuyết trình / Demo 2–3 Phút khi Bảo vệ Đề tài

* **0:00 – 0:30 (Mở đầu & Bài toán):** 
  "Kính thưa Thầy/Cô và Hội đồng, đây là Dashboard hỗ trợ ra quyết định bảo trì dự đoán cho Đề tài 16. Bài toán đặt ra cho tổ bảo trì là: với nguồn lực giới hạn chỉ kiểm tra được 20, 50 hoặc 100 thiết bị, làm sao phát hiện được nhiều ca hỏng nhất với số lần cảnh báo sai ít nhất?"
* **0:30 – 1:15 (Đánh đổi Ngân sách & So sánh 2 Họ mô hình):**
  "Quan sát Biểu đồ 1 và Biểu đồ 2: Ở ngân sách $k=50$, nếu dùng mô hình phân lớp có giám sát Logistic Regression, ta bắt được 21 ca hỏng với độ chính xác 42%. Nếu dùng mô hình học không giám sát Isolation Forest, ta bắt được 13 ca hỏng. Cả hai phương pháp đều vượt trội hoàn toàn so với việc chọn ngẫu nhiên (chỉ bắt được 0 ca)."
* **1:15 – 1:50 (So sánh 2 Chính sách & Cơ cấu Hỏng hóc):**
  "Tại Biểu đồ 3, chúng em thể hiện chính sách Ngưỡng cố định: mô hình Logistic Regression đạt độ đặc hiệu cực cao khi chỉ có duy nhất 1 ca cảnh báo giả ($FP=1$). Tại Biểu đồ 4 và 5, hệ thống bóc tách cơ cấu các dạng hỏng hóc trong Top-50 cảnh báo và phân phối điểm số trên 3 dòng sản phẩm L, M, H."
* **1:50 – 2:30 (Danh sách Ưu tiên Thực thi):**
  "Cuối cùng, Bảng danh sách ưu tiên cung cấp danh sách hành động cụ thể cho kỹ sư bảo trì: thiết bị nào cần đến kiểm tra ngay hôm nay, thông số đo lường nhiệt độ, tốc độ quay, mô-men và độ mòn tại thời điểm đó là bao nhiêu. Toàn bộ dashboard chạy cục bộ trên PostgreSQL và Superset, đã được đóng gói xuất bản sẵn sàng bàn giao."

---

## 6. Giới hạn Nghiệp vụ Cần Nêu Rõ
1. **Phân tích Offline:** Dashboard phản ánh kết quả phân tích dữ liệu lô (batch mining) trên dữ liệu AI4I 2020, không phải hệ thống streaming giám sát thời gian thực từ cảm biến IoT đang chạy.
2. **Không dự báo Lead Time / RUL:** Do dữ liệu AI4I không có chuỗi thời gian liên tục cho từng máy cụ thể, dashboard chỉ xếp hạng mức độ bất thường của trạng thái vận hành, không dự báo máy sẽ hỏng sau bao nhiêu giờ/ngày.

