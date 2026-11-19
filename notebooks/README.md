# Thứ tự chạy notebook

1. 01-data-quality.ipynb: kiểm tra nguồn, schema, kiểu, số đếm, chất lượng và nhãn.
2. 02-eda-features.ipynb: phân phối, quan hệ, đặc trưng vật lý và quyết định tiền xử lý.
3. 02b-preprocessing.ipynb: chuyển đổi theo dòng, xuất bảng và khai báo pipeline chưa fit.
4. 02c-splits.ipynb: tạo mapping chung và kiểm tra loader, chưa fit mô hình.
5. 03-models.ipynb: đã chạy baseline/Isolation Forest và lựa chọn trên validation.
6. 03b-classification.ipynb: Logistic Regression và so sánh validation của hai họ.
7. 04-evaluation.ipynb: đánh giá test, ngân sách và phân tích sai sót.
8. 05-independent-review.ipynb: kiểm chứng độc lập các chỉ số và phân tích lỗi từ gói CSV. Chạy sau khi tạo gói theo hướng dẫn ở README gốc.

Notebook 01, 02, 02b và 02c đã chạy từ kernel mới cho chất lượng/EDA/tiền xử lý; notebook 03 đã chạy baseline/Isolation Forest; notebook 03b đã chạy Logistic Regression; notebook 04 đã chấm test bằng model/ngưỡng đã khóa và chạy thành công từ kernel mới. Xem ../docs/DATA_QUALITY.md để biết lệnh chạy, bằng chứng và giới hạn. Notebook 02 hiện khảo sát đầu vào gốc, chưa tạo feature vật lý hoặc chọn feature dựa trên nhãn. Hàm tính toán đặt tại src/maintenance/ và được gọi lại; đầu ra nằm trong data/ hoặc artifacts/, hình/bảng dùng trong báo cáo nằm ở reports/.
