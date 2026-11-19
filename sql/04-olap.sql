-- ============================================================================
-- 04-olap.sql
-- Mục đích: 4 truy vấn OLAP có ý nghĩa nghiệp vụ phục vụ ra quyết định bảo trì
-- Tác giả: Quốc Việt (QV) - Đề tài 16: Bảo trì dự đoán thiết bị
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TRUY VẤN OLAP 1: So sánh hai họ mô hình và baseline theo ngân sách kiểm tra k
-- Câu hỏi nghiệp vụ: "Ở các mức ngân sách kiểm tra k = 20, 50, 100 trên tập Test chính,
--                    mô hình nào bắt được nhiều ca hỏng nhất với tỷ lệ cảnh báo giả thấp nhất?"
-- ----------------------------------------------------------------------------
SELECT
    m.model_family,
    b.budget_k,
    b.n_samples,
    b.n_failures AS total_actual_failures,
    b.tp AS true_positives_detected,
    (b.budget_k - b.tp) AS false_alarms,
    ROUND((b.precision * 100)::numeric, 2) AS precision_pct,
    ROUND((b.recall * 100)::numeric, 2) AS recall_pct
FROM agg_budget_metrics b
JOIN dim_model_run m ON b.model_run_id = m.model_run_id
WHERE b.partition = 'test'
  AND m.split_id = 'ordered-gap100-v1'
  AND m.seed = 42
  AND b.topk_applicable = TRUE
ORDER BY b.budget_k ASC, b.tp DESC;


-- ----------------------------------------------------------------------------
-- TRUY VẤN OLAP 2: Roll-up / Drill-down theo Loại sản phẩm (Type L/M/H) & Họ mô hình
-- Câu hỏi nghiệp vụ: "Trong danh sách ưu tiên Top-50, hiệu quả phát hiện hỏng hóc
--                    phân bổ thế nào giữa các phân khúc sản phẩm L, M và H?"
-- ----------------------------------------------------------------------------
SELECT
    m.model_family,
    r.product_type,
    p.description AS type_description,
    COUNT(s.reading_id) AS items_in_top50,
    SUM(fp.machine_failure) AS actual_failures_found,
    ROUND((SUM(fp.machine_failure)::numeric / COUNT(s.reading_id) * 100), 2) AS precision_in_type_pct
FROM fact_model_score s
JOIN dim_model_run m ON s.model_run_id = m.model_run_id
JOIN fact_reading r ON s.reading_id = r.reading_id
JOIN dim_product_type p ON r.product_type = p.product_type
JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key
WHERE s.partition = 'test'
  AND m.split_id = 'ordered-gap100-v1'
  AND m.seed = 42
  AND s.priority_rank <= 50
  AND m.model_family IN ('isolation_forest', 'logistic_regression')
GROUP BY m.model_family, r.product_type, p.description
ORDER BY m.model_family, r.product_type;


-- ----------------------------------------------------------------------------
-- TRUY VẤN OLAP 3: Slice & Dice theo Giao thức Chia tập & Tập Phân hoạch (Val vs Test)
-- Câu hỏi nghiệp vụ: "Phân phối điểm bất thường (priority_score) có giữ được
--                    tính ổn định giữa tập Validation và Test qua 2 giao thức split?"
-- ----------------------------------------------------------------------------
SELECT
    s.split_id,
    s.partition,
    m.model_family,
    COUNT(*) AS total_scored_readings,
    ROUND(AVG(s.priority_score)::numeric, 4) AS avg_priority_score,
    ROUND(STDDEV(s.priority_score)::numeric, 4) AS std_priority_score,
    ROUND(MIN(s.priority_score)::numeric, 4) AS min_score,
    ROUND(MAX(s.priority_score)::numeric, 4) AS max_score
FROM fact_model_score s
JOIN dim_model_run m ON s.model_run_id = m.model_run_id
WHERE m.model_family IN ('isolation_forest', 'logistic_regression')
  AND m.seed = 42
GROUP BY s.split_id, s.partition, m.model_family
ORDER BY s.split_id, m.model_family, s.partition;


-- ----------------------------------------------------------------------------
-- TRUY VẤN OLAP 4: Phân tích Cơ cấu Chế độ Hỏng (Failure Modes) trong Top-50 Cảnh báo
-- Câu hỏi nghiệp vụ: "Mô hình phát hiện được những dạng hư hỏng nào (TWF, HDF, PWF, OSF, RNF)
--                    trong số 50 bản ghi được ưu tiên cao nhất, có trường hợp đa nhãn không?"
-- ----------------------------------------------------------------------------
SELECT
    m.model_family,
    fp.pattern_label,
    fp.is_multilabel,
    COUNT(s.reading_id) AS n_records_in_top50,
    SUM(fp.machine_failure) AS total_failures
FROM fact_model_score s
JOIN dim_model_run m ON s.model_run_id = m.model_run_id
JOIN fact_reading r ON s.reading_id = r.reading_id
JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key
WHERE s.partition = 'test'
  AND m.split_id = 'ordered-gap100-v1'
  AND m.seed = 42
  AND s.priority_rank <= 50
  AND m.model_family IN ('isolation_forest', 'logistic_regression')
GROUP BY m.model_family, fp.pattern_label, fp.is_multilabel
ORDER BY m.model_family, total_failures DESC, n_records_in_top50 DESC;

