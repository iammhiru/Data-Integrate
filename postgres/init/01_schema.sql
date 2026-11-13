-- Schema PostgreSQL theo docs/architecture.txt (muc 4.3).
-- Chay tu dong mot lan khi volume postgres-data con trong.
--
-- PHASE 1 (13/11/2026) — bo sung master data cho OEE:
--   · machine_id VARCHAR(16) -> VARCHAR(32)  (machineId thuc te toi 18 ky tu:
--     L03_CANINSPECT_01, CIP_SKID_01 ...)
--   · work_order       : don hang san xuat (WO) — lien ket SKU + line
--   · counter_baseline : moc bo dem khi WO bat dau (bo dem may TICH LUY tu lan
--     bat nguon, khong reset theo ca/WO -> can moc de tinh san luong theo WO)
--   · production_plan  : ke hoach san luong theo line/shift
--   · line             : bang master duong chay (frontend lay tu day)
--
-- Ghi chu khoa: cac bang duoi day la MASTER DATA (nhap tu ERP/MES), KHONG
-- phai du lieu do pipeline ghi vao. Pipeline chi DOC master de enrich.

-- =========================================================== Master data
CREATE TABLE IF NOT EXISTS machine (
    machine_id      VARCHAR(32) PRIMARY KEY,
    machine_name    VARCHAR(100) NOT NULL,
    line            VARCHAR(32),
    machine_type    VARCHAR(32),
    location        VARCHAR(64),
    ideal_speed     DOUBLE PRECISION,
    installed_at    DATE
);

CREATE TABLE IF NOT EXISTS machine_id_mapping (
    source          VARCHAR(32)  NOT NULL,   -- kepware-opcua | production-sim | quality-sim
    source_id       VARCHAR(64)  NOT NULL,   -- id goc o nguon
    machine_id      VARCHAR(32)  NOT NULL REFERENCES machine(machine_id),
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS product (
    product_id            VARCHAR(32) PRIMARY KEY,
    product_name          VARCHAR(100) NOT NULL,
    ideal_cycle_time_sec  DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS shift (
    shift_id               VARCHAR(8) PRIMARY KEY,
    shift_name             VARCHAR(32) NOT NULL,
    start_time             TIME NOT NULL,
    end_time               TIME NOT NULL,
    planned_minutes        INT  NOT NULL,
    planned_break_minutes  INT  NOT NULL DEFAULT 0
);

-- Dong chay san xuat. `reference_process` = cong doan CHIET (ra san pham
-- chinh, don vi pcs) -> dung bo dem cu may nay cho Performance/Quality.
CREATE TABLE IF NOT EXISTS line (
    line_id             VARCHAR(32) PRIMARY KEY,
    line_name           VARCHAR(100) NOT NULL,
    channel             VARCHAR(32),
    reference_process   VARCHAR(32),
    product_id          VARCHAR(32) REFERENCES product(product_id),
    unit                VARCHAR(16)
);

-- Work order — don hang san xuat. Can cho: san luong theo WO, OEE theo SKU,
-- va moc bo dem (counter_baseline) khi WO bat dau.
CREATE TABLE IF NOT EXISTS work_order (
    wo_id             VARCHAR(64) PRIMARY KEY,
    wo_code           VARCHAR(64) NOT NULL,
    line_id           VARCHAR(32) NOT NULL REFERENCES line(line_id),
    product_id        VARCHAR(32) NOT NULL REFERENCES product(product_id),
    shift_id          VARCHAR(8)  REFERENCES shift(shift_id),
    planned_qty       BIGINT,
    status            VARCHAR(16) NOT NULL DEFAULT 'PLANNED',  -- PLANNED|RUNNING|DONE|CANCELLED
    planned_start     TIMESTAMPTZ,
    actual_start_time TIMESTAMPTZ,
    actual_end_time   TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_work_order_line_status ON work_order(line_id, status);

-- Moc bo dem theo work order.
--
-- BO DEM MAY (TotalCounter/GoodCounter/DefectCounter) la BO DEM TICH LUY tu lan
-- bat nguon may — KHONG reset theo ca hay theo WO. Muon biet "san luong cua WO
-- nay la bao nhieu" thi phai luu gia tri bo dem tai thoi diem WO bat dau:
--     WO_VALUE = max(0, raw_now - baseline_value)
-- Tuong duong bang VNK_DL_COUNTER_WO_BASELINE cua he Vinamilk.
CREATE TABLE IF NOT EXISTS counter_baseline (
    node_id          VARCHAR(64) NOT NULL,     -- machineId + tagCode (may 1 dong)
    machine_id       VARCHAR(32) NOT NULL REFERENCES machine(machine_id),
    tag_code         VARCHAR(64) NOT NULL,
    work_order_id    VARCHAR(64) REFERENCES work_order(wo_id),
    baseline_value   DOUBLE PRECISION NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (node_id, work_order_id, recorded_at)
);
CREATE INDEX IF NOT EXISTS idx_counter_baseline_wo ON counter_baseline(work_order_id);

-- Ke hoach san luong theo line + shift (cho "con bao nhieu pcs").
CREATE TABLE IF NOT EXISTS production_plan (
    line_id           VARCHAR(32) NOT NULL REFERENCES line(line_id),
    shift_id          VARCHAR(8)  NOT NULL REFERENCES shift(shift_id),
    product_id        VARCHAR(32) NOT NULL REFERENCES product(product_id),
    plan_date         DATE        NOT NULL,
    planned_qty       BIGINT      NOT NULL,
    theoretical_qty   BIGINT,               -- san luong theo cong suat thiet ke
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (line_id, shift_id, plan_date)
);

-- =========================================================== Speed layer (Spark Streaming)
CREATE TABLE IF NOT EXISTS machine_status_current (
    machine_id       VARCHAR(32) PRIMARY KEY,
    status           VARCHAR(16),
    temperature      DOUBLE PRECISION,
    pressure         DOUBLE PRECISION,
    speed            DOUBLE PRECISION,
    energy           DOUBLE PRECISION,
    production_rate  DOUBLE PRECISION,
    event_time       TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS machine_metric_1m (
    machine_id       VARCHAR(32) NOT NULL,
    window_start     TIMESTAMPTZ NOT NULL,
    window_end       TIMESTAMPTZ NOT NULL,
    avg_temperature  DOUBLE PRECISION,
    max_temperature  DOUBLE PRECISION,
    avg_pressure     DOUBLE PRECISION,
    avg_speed        DOUBLE PRECISION,
    sum_energy       DOUBLE PRECISION,
    sample_count     BIGINT,
    missing_count    BIGINT,
    PRIMARY KEY (machine_id, window_start)
) PARTITION BY RANGE (window_start);
CREATE TABLE IF NOT EXISTS machine_metric_1m_default PARTITION OF machine_metric_1m DEFAULT;

-- =========================================================== Batch layer (Spark Batch)
CREATE TABLE IF NOT EXISTS production_metric (
    machine_id       VARCHAR(32) NOT NULL,
    product_id       VARCHAR(32) NOT NULL,
    shift_id         VARCHAR(8)  NOT NULL,
    date             DATE        NOT NULL,
    hour             SMALLINT    NOT NULL,
    total_qty        BIGINT,
    good_qty         BIGINT,
    reject_qty       BIGINT,
    reject_rate      DOUBLE PRECISION,
    production_rate  DOUBLE PRECISION,          -- san pham / phut
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (machine_id, product_id, shift_id, date, hour)
) PARTITION BY RANGE (date);
CREATE TABLE IF NOT EXISTS production_metric_default PARTITION OF production_metric DEFAULT;

CREATE TABLE IF NOT EXISTS quality_metric (
    machine_id       VARCHAR(32) NOT NULL,
    product_id       VARCHAR(32) NOT NULL,
    shift_id         VARCHAR(8)  NOT NULL,
    date             DATE        NOT NULL,
    hour             SMALLINT    NOT NULL,
    defect_type      VARCHAR(32) NOT NULL,
    inspected_qty    BIGINT,
    reject_qty       BIGINT,
    defect_rate      DOUBLE PRECISION,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (machine_id, product_id, shift_id, date, hour, defect_type)
) PARTITION BY RANGE (date);
CREATE TABLE IF NOT EXISTS quality_metric_default PARTITION OF quality_metric DEFAULT;

CREATE TABLE IF NOT EXISTS downtime_event (
    machine_id    VARCHAR(32) NOT NULL,
    status        VARCHAR(16) NOT NULL,       -- IDLE | STOPPED
    start_time    TIMESTAMPTZ NOT NULL,
    end_time      TIMESTAMPTZ,
    duration_sec  DOUBLE PRECISION,
    shift_id      VARCHAR(8),
    PRIMARY KEY (machine_id, start_time)
);

CREATE TABLE IF NOT EXISTS oee_metric (
    machine_id     VARCHAR(32) NOT NULL,
    product_id     VARCHAR(32) NOT NULL,
    shift_id       VARCHAR(8)  NOT NULL,
    date           DATE        NOT NULL,
    planned_time   DOUBLE PRECISION,          -- giay
    run_time       DOUBLE PRECISION,
    downtime       DOUBLE PRECISION,
    idle_time      DOUBLE PRECISION,
    total_count    BIGINT,
    good_count     BIGINT,
    reject_count   BIGINT,
    availability   DOUBLE PRECISION,
    performance    DOUBLE PRECISION,
    quality        DOUBLE PRECISION,
    oee            DOUBLE PRECISION,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (machine_id, product_id, shift_id, date)
);

CREATE TABLE IF NOT EXISTS data_quality_metric (
    event_type            VARCHAR(32) NOT NULL,
    date                  DATE        NOT NULL,
    hour                  SMALLINT    NOT NULL,
    total_events          BIGINT,
    valid_events          BIGINT,
    invalid_events        BIGINT,
    duplicate_events      BIGINT,
    missing_field_events  BIGINT,
    late_events           BIGINT,
    data_quality_rate     DOUBLE PRECISION,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (event_type, date, hour)
);

CREATE TABLE IF NOT EXISTS pipeline_latency_metric (
    window_start  TIMESTAMPTZ NOT NULL,
    stage         VARCHAR(32) NOT NULL,       -- source->kafka | kafka->spark | spark->ui
    avg_ms        DOUBLE PRECISION,
    p95_ms        DOUBLE PRECISION,
    max_ms        DOUBLE PRECISION,
    PRIMARY KEY (window_start, stage)
);
