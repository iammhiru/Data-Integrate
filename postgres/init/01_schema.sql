-- Schema PostgreSQL theo docs/architecture.txt (muc 4.3).
-- Chay tu dong mot lan khi volume postgres-data con trong.
--
-- PHASE 1 (13/11/2026) — bo sung master data cho OEE:
--   · machine_id VARCHAR(16) -> VARCHAR(32)  (machineId thuc te toi 18 ky tu:
--     L03_CANINSPECT_01, CIP_SKID_01 ...)
--   · work_order       : don hang san xuat (WO) — lien ket SKU + line
--   · (counter_baseline da bo 14/11: san luong theo WO = SUM(total_count) cua
--     machine_kpi_1m trong [actual_start_time, actual_end_time) — xem 03_batch_schema.sql)
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
-- va xac dinh khoang thoi gian cua WO (actual_start_time .. actual_end_time).
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


-- =========================================================== Bang phan tich
-- 14/11/2026: cac bang speed/batch cu (machine_status_current, machine_metric_1m,
-- production_metric, quality_metric, downtime_event, oee_metric, data_quality_metric,
-- pipeline_latency_metric) DA BO — khong co job nao ghi. Trang thai hien tai do state-api
-- (Kafka compacted) phuc vu; lich su/phan tich nam o 03_batch_schema.sql (fact cong duoc 1 phut).
