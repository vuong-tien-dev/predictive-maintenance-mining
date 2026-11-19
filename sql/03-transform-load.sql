-- ============================================================================
-- 03-transform-load.sql
-- Mục đích: Chuyển đổi và nạp dữ liệu từ Staging vào mô hình Star Schema
-- Đảm bảo tính Idempotent: chạy nhiều lần không gây trùng lặp (ON CONFLICT DO NOTHING)
-- Tác giả: Quốc Việt (QV) - Đề tài 16: Bảo trì dự đoán thiết bị
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. NẠP CÁC BẢNG DIMENSION (Chiều phân tích)
-- ----------------------------------------------------------------------------

-- 1.1. Nạp dim_product_type
INSERT INTO dim_product_type (product_type, description, quality_tier)
VALUES
    ('L', 'Low variant - 50% sản lượng sản xuất', 'Tiêu chuẩn phổ thông'),
    ('M', 'Medium variant - 30% sản lượng sản xuất', 'Trung cấp'),
    ('H', 'High variant - 20% sản lượng sản xuất', 'Chất lượng cao')
ON CONFLICT (product_type) DO NOTHING;

-- 1.2. Nạp dim_dataset_version
INSERT INTO dim_dataset_version (dataset_version, schema_version, source_url, checksum_sha256)
SELECT DISTINCT
    dataset_version,
    schema_version,
    'https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset' AS source_url,
    'dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e' AS checksum_sha256
FROM stg_readings
ON CONFLICT (dataset_version) DO NOTHING;

-- 1.3. Nạp dim_failure_pattern
INSERT INTO dim_failure_pattern (
    failure_pattern_key,
    machine_failure,
    twf,
    hdf,
    pwf,
    osf,
    rnf,
    pattern_label,
    is_multilabel
)
SELECT DISTINCT
    CONCAT(
        'MF', machine_failure,
        '_TWF', twf,
        '_HDF', hdf,
        '_PWF', pwf,
        '_OSF', osf,
        '_RNF', rnf
    ) AS failure_pattern_key,
    machine_failure,
    twf,
    hdf,
    pwf,
    osf,
    rnf,
    CASE
        WHEN machine_failure = 0 AND (twf + hdf + pwf + osf + rnf) = 0 THEN 'Hoạt động bình thường'
        WHEN machine_failure = 1 AND (twf + hdf + pwf + osf + rnf) = 0 THEN 'Hỏng không rõ chế độ'
        WHEN machine_failure = 0 AND (twf + hdf + pwf + osf + rnf) > 0 THEN 'Cờ chế độ hỏng nhưng máy không dừng'
        WHEN (twf + hdf + pwf + osf + rnf) > 1 THEN 'Đa chế độ hỏng đồng thời'
        WHEN twf = 1 THEN 'Hỏng do mòn dụng cụ (TWF)'
        WHEN hdf = 1 THEN 'Hỏng do tản nhiệt (HDF)'
        WHEN pwf = 1 THEN 'Hỏng do công suất vượt ngưỡng (PWF)'
        WHEN osf = 1 THEN 'Hỏng do quá tải quá ứng suất (OSF)'
        WHEN rnf = 1 THEN 'Hỏng ngẫu nhiên (RNF)'
        ELSE 'Khác'
    END AS pattern_label,
    ((twf + hdf + pwf + osf + rnf) > 1) AS is_multilabel
FROM stg_readings
ON CONFLICT (failure_pattern_key) DO NOTHING;

-- 1.4. Nạp dim_model_run
INSERT INTO dim_model_run (
    model_run_id,
    split_id,
    model_family,
    feature_set,
    seed,
    threshold
)
SELECT DISTINCT
    model_run_id,
    split_id,
    model_family,
    feature_set,
    seed,
    threshold
FROM stg_model_runs
ON CONFLICT (model_run_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. NẠP CÁC BẢNG FACT (Bảng sự kiện đo lường)
-- ----------------------------------------------------------------------------

-- 2.1. Nạp fact_reading (10.000 dòng quan sát cảm biến)
INSERT INTO fact_reading (
    reading_id,
    dataset_version,
    product_id,
    product_type,
    failure_pattern_key,
    air_temperature_k,
    process_temperature_k,
    rotational_speed_rpm,
    torque_nm,
    tool_wear_min,
    temperature_difference_k,
    power_w,
    wear_torque_min_nm,
    is_suspect
)
SELECT
    r.reading_id,
    r.dataset_version,
    r.product_id,
    r.product_type,
    CONCAT(
        'MF', r.machine_failure,
        '_TWF', r.twf,
        '_HDF', r.hdf,
        '_PWF', r.pwf,
        '_OSF', r.osf,
        '_RNF', r.rnf
    ) AS failure_pattern_key,
    r.air_temperature_k,
    r.process_temperature_k,
    r.rotational_speed_rpm,
    r.torque_nm,
    r.tool_wear_min,
    f.temperature_difference_k,
    f.power_w,
    f.wear_torque_min_nm,
    (q.failure_without_mode OR q.mode_without_failure) AS is_suspect
FROM stg_readings r
JOIN stg_features f
    ON r.dataset_version = f.dataset_version AND r.reading_id = f.reading_id
JOIN stg_quality_flags q
    ON r.dataset_version = q.dataset_version AND r.reading_id = q.reading_id
ON CONFLICT (reading_id) DO NOTHING;

-- 2.2. Nạp fact_model_score (78.000 dòng chấm điểm của các mô hình)
INSERT INTO fact_model_score (
    model_run_id,
    reading_id,
    dataset_version,
    split_id,
    partition,
    priority_score,
    priority_rank,
    predicted_failure
)
SELECT
    model_run_id,
    reading_id,
    dataset_version,
    split_id,
    split AS partition,
    priority_score,
    priority_rank,
    predicted_failure
FROM stg_scores
ON CONFLICT (model_run_id, partition, dataset_version, reading_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. NẠP BẢNG TỔNG HỢP CHỈ SỐ THEO NGÂN SÁCH (120 dòng)
-- ----------------------------------------------------------------------------

INSERT INTO agg_budget_metrics (
    model_run_id,
    partition,
    population_scope,
    budget_k,
    n_samples,
    n_failures,
    topk_applicable,
    tp,
    precision,
    recall
)
SELECT
    model_run_id,
    split AS partition,
    population_scope,
    budget_k,
    n_samples,
    n_failures,
    topk_applicable,
    tp,
    precision,
    recall
FROM stg_budget_metrics
ON CONFLICT (model_run_id, partition, population_scope, budget_k) DO NOTHING;

