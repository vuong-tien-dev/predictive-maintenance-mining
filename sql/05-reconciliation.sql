-- ============================================================================
-- 05-reconciliation.sql
-- Mục đích: Truy vấn đối soát tự động toàn bộ số liệu kho với tiêu chí nghiệm thu
-- Tác giả: Quốc Việt (QV) - Đề tài 16: Bảo trì dự đoán thiết bị
-- ============================================================================

-- ----------------------------------------------------------------------------
-- KIỂM TRA 1: ĐỐI SOÁT TỔNG SỐ LƯỢNG BẢN GHI (ROW COUNTS)
-- ----------------------------------------------------------------------------
SELECT 'fact_reading' AS table_name, COUNT(*) AS actual_rows, 10000 AS expected_rows,
       (COUNT(*) = 10000) AS is_pass FROM fact_reading
UNION ALL
SELECT 'fact_model_score', COUNT(*), 78000, (COUNT(*) = 78000) FROM fact_model_score
UNION ALL
SELECT 'dim_model_run', COUNT(*), 20, (COUNT(*) = 20) FROM dim_model_run
UNION ALL
SELECT 'agg_budget_metrics', COUNT(*), 120, (COUNT(*) = 120) FROM agg_budget_metrics
UNION ALL
SELECT 'total_machine_failures', SUM(fp.machine_failure), 339, (SUM(fp.machine_failure) = 339)
FROM fact_reading r
JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key;


-- ----------------------------------------------------------------------------
-- KIỂM TRA 2: ĐỐI SOÁT TẬP TEST CHÍNH (ordered-gap100-v1), SEED 42
-- KỲ VỌNG: 1.900 quan sát, 38 ca hỏng thực tế
--          LR Top-50 bắt đúng 21 TP, IF Top-50 bắt đúng 13 TP
-- ----------------------------------------------------------------------------
SELECT
    m.model_family,
    s.partition,
    COUNT(DISTINCT s.reading_id) AS total_readings,
    SUM(fp.machine_failure) AS total_failures,
    SUM(CASE WHEN s.priority_rank <= 50 THEN fp.machine_failure ELSE 0 END) AS tp_at_50,
    CASE
        WHEN m.model_family = 'logistic_regression' THEN (SUM(CASE WHEN s.priority_rank <= 50 THEN fp.machine_failure ELSE 0 END) = 21)
        WHEN m.model_family = 'isolation_forest' THEN (SUM(CASE WHEN s.priority_rank <= 50 THEN fp.machine_failure ELSE 0 END) = 13)
        ELSE TRUE
    END AS is_pass
FROM fact_model_score s
JOIN dim_model_run m ON s.model_run_id = m.model_run_id
JOIN fact_reading r ON s.reading_id = r.reading_id
JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key
WHERE s.split_id = 'ordered-gap100-v1'
  AND s.partition = 'test'
  AND m.seed = 42
  AND m.model_family IN ('logistic_regression', 'isolation_forest')
GROUP BY m.model_family, s.partition;


-- ----------------------------------------------------------------------------
-- KIỂM TRA 3: MA TRẬN NHẦM LẪN TẠI NGƯỠNG VALIDATION ĐÃ KHÓA
-- KỲ VỌNG TEST CHÍNH:
--   LR: TP=10, FP=1, FN=28, TN=1861
--   IF: TP=13, FP=25, FN=25, TN=1837
-- ----------------------------------------------------------------------------
SELECT
    m.model_family,
    m.threshold AS locked_threshold,
    SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) AS tp,
    SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) AS fp,
    SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) AS fn,
    SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) AS tn,
    CASE
        WHEN m.model_family = 'logistic_regression' THEN
            (SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) = 10 AND
             SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) = 1 AND
             SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) = 28 AND
             SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) = 1861)
        WHEN m.model_family = 'isolation_forest' THEN
            (SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) = 13 AND
             SUM(CASE WHEN s.predicted_failure = 1 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) = 25 AND
             SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 1 THEN 1 ELSE 0 END) = 25 AND
             SUM(CASE WHEN s.predicted_failure = 0 AND fp.machine_failure = 0 THEN 1 ELSE 0 END) = 1837)
        ELSE TRUE
    END AS is_pass
FROM fact_model_score s
JOIN dim_model_run m ON s.model_run_id = m.model_run_id
JOIN fact_reading r ON s.reading_id = r.reading_id
JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key
WHERE s.split_id = 'ordered-gap100-v1'
  AND s.partition = 'test'
  AND m.seed = 42
  AND m.model_family IN ('logistic_regression', 'isolation_forest')
GROUP BY m.model_family, m.threshold;

