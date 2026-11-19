-- ============================================================================
-- 01-staging.sql
-- Mục đích: DDL tạo các bảng Staging tương ứng với 8 file CSV trong gói handoff-v1
-- Tác giả: Quốc Việt (QV) - Đề tài 16: Bảo trì dự đoán thiết bị
-- ============================================================================

-- Bảng 1: stg_readings (10.000 dòng từ readings.csv)
DROP TABLE IF EXISTS stg_readings CASCADE;
CREATE TABLE stg_readings (
    dataset_version        VARCHAR(128) NOT NULL,
    schema_version         VARCHAR(32) NOT NULL,
    reading_id             INTEGER NOT NULL,
    product_id             VARCHAR(32) NOT NULL,
    product_type           VARCHAR(10) NOT NULL,
    air_temperature_k      DOUBLE PRECISION NOT NULL,
    process_temperature_k  DOUBLE PRECISION NOT NULL,
    rotational_speed_rpm   INTEGER NOT NULL,
    torque_nm              DOUBLE PRECISION NOT NULL,
    tool_wear_min          INTEGER NOT NULL,
    machine_failure        INTEGER NOT NULL,
    twf                    INTEGER NOT NULL,
    hdf                    INTEGER NOT NULL,
    pwf                    INTEGER NOT NULL,
    osf                    INTEGER NOT NULL,
    rnf                    INTEGER NOT NULL
);

-- Bảng 2: stg_features (10.000 dòng từ features.csv)
DROP TABLE IF EXISTS stg_features CASCADE;
CREATE TABLE stg_features (
    dataset_version           VARCHAR(128) NOT NULL,
    reading_id                INTEGER NOT NULL,
    product_type              VARCHAR(10) NOT NULL,
    air_temperature_k         DOUBLE PRECISION NOT NULL,
    process_temperature_k     DOUBLE PRECISION NOT NULL,
    rotational_speed_rpm      INTEGER NOT NULL,
    torque_nm                 DOUBLE PRECISION NOT NULL,
    tool_wear_min             INTEGER NOT NULL,
    temperature_difference_k  DOUBLE PRECISION NOT NULL,
    power_w                   DOUBLE PRECISION NOT NULL,
    wear_torque_min_nm        DOUBLE PRECISION NOT NULL
);

-- Bảng 3: stg_quality_flags (10.000 dòng từ quality_flags.csv)
DROP TABLE IF EXISTS stg_quality_flags CASCADE;
CREATE TABLE stg_quality_flags (
    dataset_version       VARCHAR(128) NOT NULL,
    reading_id            INTEGER NOT NULL,
    failure_without_mode  BOOLEAN NOT NULL,
    mode_without_failure  BOOLEAN NOT NULL,
    multiple_modes        BOOLEAN NOT NULL
);

-- Bảng 4: stg_split_membership (20.000 dòng từ split_membership.csv)
DROP TABLE IF EXISTS stg_split_membership CASCADE;
CREATE TABLE stg_split_membership (
    dataset_version  VARCHAR(128) NOT NULL,
    reading_id       INTEGER NOT NULL,
    split_id         VARCHAR(64) NOT NULL,
    source_position  INTEGER NOT NULL,
    split            VARCHAR(32) NOT NULL
);

-- Bảng 5: stg_model_runs (20 dòng từ model_runs.csv)
DROP TABLE IF EXISTS stg_model_runs CASCADE;
CREATE TABLE stg_model_runs (
    model_run_id  VARCHAR(128) NOT NULL,
    split_id      VARCHAR(64) NOT NULL,
    model_family  VARCHAR(64) NOT NULL,
    feature_set   VARCHAR(32) NOT NULL,
    seed          INTEGER NOT NULL,
    threshold     DOUBLE PRECISION NOT NULL
);

-- Bảng 6: stg_scores (78.000 dòng từ scores.csv)
DROP TABLE IF EXISTS stg_scores CASCADE;
CREATE TABLE stg_scores (
    dataset_version    VARCHAR(128) NOT NULL,
    reading_id         INTEGER NOT NULL,
    model_run_id       VARCHAR(128) NOT NULL,
    split_id           VARCHAR(64) NOT NULL,
    split              VARCHAR(32) NOT NULL,
    model_family       VARCHAR(64) NOT NULL,
    feature_set        VARCHAR(32) NOT NULL,
    priority_score     DOUBLE PRECISION NOT NULL,
    predicted_failure  INTEGER NOT NULL,
    priority_rank      INTEGER NOT NULL
);

-- Bảng 7: stg_metrics (40 dòng từ metrics.csv)
DROP TABLE IF EXISTS stg_metrics CASCADE;
CREATE TABLE stg_metrics (
    model_run_id        VARCHAR(128) NOT NULL,
    split               VARCHAR(32) NOT NULL,
    population_scope    VARCHAR(32) NOT NULL,
    split_id            VARCHAR(64) NOT NULL,
    model_family        VARCHAR(64) NOT NULL,
    seed                INTEGER NOT NULL,
    n_samples           INTEGER NOT NULL,
    n_failures          INTEGER NOT NULL,
    threshold           DOUBLE PRECISION NOT NULL,
    tp                  INTEGER,
    fp                  INTEGER,
    fn                  INTEGER,
    tn                  INTEGER,
    precision           DOUBLE PRECISION,
    recall              DOUBLE PRECISION,
    f1                  DOUBLE PRECISION,
    precision_defined   BOOLEAN,
    recall_defined      BOOLEAN,
    f1_defined          BOOLEAN,
    roc_auc             DOUBLE PRECISION,
    average_precision   DOUBLE PRECISION
);

-- Bảng 8: stg_budget_metrics (120 dòng từ budget_metrics.csv)
DROP TABLE IF EXISTS stg_budget_metrics CASCADE;
CREATE TABLE stg_budget_metrics (
    model_run_id      VARCHAR(128) NOT NULL,
    split             VARCHAR(32) NOT NULL,
    population_scope  VARCHAR(32) NOT NULL,
    budget_k          INTEGER NOT NULL,
    n_samples         INTEGER NOT NULL,
    n_failures        INTEGER NOT NULL,
    topk_applicable   BOOLEAN NOT NULL,
    tp                INTEGER,
    precision         DOUBLE PRECISION,
    recall            DOUBLE PRECISION
);

