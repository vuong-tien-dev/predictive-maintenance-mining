-- ============================================================================
-- 02-star-schema.sql
-- Mục đích: DDL tạo mô hình Star Schema (Dimensions, Facts, Agg Tables & Indexes)
-- Tác giả: Quốc Việt (QV) - Đề tài 16: Bảo trì dự đoán thiết bị
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. DIMENSION TABLES (Chiều phân tích)
-- ----------------------------------------------------------------------------

-- Chiều 1: dim_product_type (Phân loại sản phẩm L/M/H)
DROP TABLE IF EXISTS dim_product_type CASCADE;
CREATE TABLE dim_product_type (
    product_type  VARCHAR(10) PRIMARY KEY,
    description   VARCHAR(64) NOT NULL,
    quality_tier  VARCHAR(32) NOT NULL
);

-- Chiều 2: dim_dataset_version (Xuất xứ và phiên bản dữ liệu nguồn)
DROP TABLE IF EXISTS dim_dataset_version CASCADE;
CREATE TABLE dim_dataset_version (
    dataset_version   VARCHAR(128) PRIMARY KEY,
    schema_version    VARCHAR(32) NOT NULL,
    source_url        TEXT NOT NULL,
    checksum_sha256   VARCHAR(64) NOT NULL
);

-- Chiều 3: dim_failure_pattern (Tổ hợp các chế độ hỏng hóc và cờ đa nhãn)
DROP TABLE IF EXISTS dim_failure_pattern CASCADE;
CREATE TABLE dim_failure_pattern (
    failure_pattern_key  VARCHAR(64) PRIMARY KEY,
    machine_failure      INTEGER NOT NULL CHECK (machine_failure IN (0, 1)),
    twf                  INTEGER NOT NULL CHECK (twf IN (0, 1)),
    hdf                  INTEGER NOT NULL CHECK (hdf IN (0, 1)),
    pwf                  INTEGER NOT NULL CHECK (pwf IN (0, 1)),
    osf                  INTEGER NOT NULL CHECK (osf IN (0, 1)),
    rnf                  INTEGER NOT NULL CHECK (rnf IN (0, 1)),
    pattern_label        VARCHAR(64) NOT NULL,
    is_multilabel        BOOLEAN NOT NULL
);

-- Chiều 4: dim_model_run (Metadata 20 lần chạy mô hình và ngưỡng phân loại đã khóa)
DROP TABLE IF EXISTS dim_model_run CASCADE;
CREATE TABLE dim_model_run (
    model_run_id  VARCHAR(128) PRIMARY KEY,
    split_id      VARCHAR(64) NOT NULL,
    model_family  VARCHAR(64) NOT NULL,
    feature_set   VARCHAR(32) NOT NULL,
    seed          INTEGER NOT NULL,
    threshold     DOUBLE PRECISION NOT NULL
);

-- ----------------------------------------------------------------------------
-- 2. FACT TABLES (Bảng sự kiện đo lường)
-- ----------------------------------------------------------------------------

-- Fact 1: fact_reading (Grain: 1 quan sát cảm biến thực tế - đúng 10.000 dòng)
DROP TABLE IF EXISTS fact_reading CASCADE;
CREATE TABLE fact_reading (
    reading_id                INTEGER PRIMARY KEY,
    dataset_version           VARCHAR(128) NOT NULL REFERENCES dim_dataset_version(dataset_version),
    product_id                VARCHAR(32) NOT NULL,
    product_type              VARCHAR(10) NOT NULL REFERENCES dim_product_type(product_type),
    failure_pattern_key       VARCHAR(64) NOT NULL REFERENCES dim_failure_pattern(failure_pattern_key),
    air_temperature_k         DOUBLE PRECISION NOT NULL,
    process_temperature_k     DOUBLE PRECISION NOT NULL,
    rotational_speed_rpm      INTEGER NOT NULL,
    torque_nm                 DOUBLE PRECISION NOT NULL,
    tool_wear_min             INTEGER NOT NULL,
    temperature_difference_k  DOUBLE PRECISION NOT NULL,
    power_w                   DOUBLE PRECISION NOT NULL,
    wear_torque_min_nm        DOUBLE PRECISION NOT NULL,
    is_suspect                BOOLEAN NOT NULL DEFAULT FALSE
);

-- Fact 2: fact_model_score (Grain: 1 lần chấm điểm 1 quan sát - đúng 78.000 dòng)
DROP TABLE IF EXISTS fact_model_score CASCADE;
CREATE TABLE fact_model_score (
    model_run_id       VARCHAR(128) NOT NULL REFERENCES dim_model_run(model_run_id),
    reading_id         INTEGER NOT NULL REFERENCES fact_reading(reading_id),
    dataset_version    VARCHAR(128) NOT NULL REFERENCES dim_dataset_version(dataset_version),
    split_id           VARCHAR(64) NOT NULL,
    partition          VARCHAR(32) NOT NULL,
    priority_score     DOUBLE PRECISION NOT NULL,
    priority_rank      INTEGER NOT NULL,
    predicted_failure  INTEGER NOT NULL CHECK (predicted_failure IN (0, 1)),
    PRIMARY KEY (model_run_id, partition, dataset_version, reading_id)
);

-- ----------------------------------------------------------------------------
-- 3. AGGREGATED METRICS TABLE (Bảng tổng hợp chỉ số ngân sách)
-- ----------------------------------------------------------------------------

-- Bảng tổng hợp: agg_budget_metrics (120 dòng phục vụ trực quan hóa siêu tốc)
DROP TABLE IF EXISTS agg_budget_metrics CASCADE;
CREATE TABLE agg_budget_metrics (
    model_run_id      VARCHAR(128) NOT NULL REFERENCES dim_model_run(model_run_id),
    partition         VARCHAR(32) NOT NULL,
    population_scope  VARCHAR(32) NOT NULL,
    budget_k          INTEGER NOT NULL,
    n_samples         INTEGER NOT NULL,
    n_failures        INTEGER NOT NULL,
    topk_applicable   BOOLEAN NOT NULL,
    tp                INTEGER,
    precision         DOUBLE PRECISION,
    recall            DOUBLE PRECISION,
    PRIMARY KEY (model_run_id, partition, population_scope, budget_k)
);

-- ----------------------------------------------------------------------------
-- 4. PERFORMANCE INDEXES (Chỉ mục tối ưu hóa truy vấn)
-- ----------------------------------------------------------------------------

CREATE INDEX idx_reading_type ON fact_reading (product_type);
CREATE INDEX idx_reading_pattern ON fact_reading (failure_pattern_key);

CREATE INDEX idx_score_reading ON fact_model_score (reading_id);
CREATE INDEX idx_score_run_part ON fact_model_score (model_run_id, partition);
CREATE INDEX idx_score_rank ON fact_model_score (priority_rank);
CREATE INDEX idx_score_split ON fact_model_score (split_id);

CREATE INDEX idx_budget_run ON agg_budget_metrics (model_run_id, partition, budget_k);

-- ----------------------------------------------------------------------------
-- 5. BUSINESS VIEWS (Góc nhìn nghiệp vụ phục vụ trực quan hóa BI & Dashboard)
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW view_budget_metrics AS
SELECT
    b.model_run_id,
    m.model_family,
    m.split_id,
    m.seed,
    b.partition,
    b.population_scope,
    b.budget_k,
    CASE b.budget_k
        WHEN 20 THEN '1. k=20'
        WHEN 50 THEN '2. k=50'
        WHEN 100 THEN '3. k=100'
        ELSE CONCAT('k=', b.budget_k)
    END AS budget_label,
    b.n_samples,
    b.n_failures,
    b.topk_applicable,
    b.tp,
    b.precision,
    b.recall
FROM agg_budget_metrics b
JOIN dim_model_run m ON b.model_run_id = m.model_run_id;

CREATE OR REPLACE VIEW view_priority_inspection AS
SELECT
    s.model_run_id,
    m.model_family,
    m.split_id,
    m.seed,
    s.partition,
    s.priority_rank,
    s.priority_score,
    s.predicted_failure,
    r.reading_id,
    r.product_id,
    r.product_type,
    p.description AS type_description,
    r.air_temperature_k,
    r.process_temperature_k,
    r.rotational_speed_rpm,
    r.torque_nm,
    r.tool_wear_min,
    r.temperature_difference_k,
    r.power_w,
    r.wear_torque_min_nm,
    fp.machine_failure AS actual_failure,
    fp.pattern_label AS failure_mode,
    fp.is_multilabel
FROM fact_model_score s
JOIN dim_model_run m ON s.model_run_id = m.model_run_id
JOIN fact_reading r ON s.reading_id = r.reading_id
JOIN dim_product_type p ON r.product_type = p.product_type
JOIN dim_failure_pattern fp ON r.failure_pattern_key = fp.failure_pattern_key;

