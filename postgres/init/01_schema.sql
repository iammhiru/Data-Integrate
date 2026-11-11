-- Schema PostgreSQL theo docs/architecture.txt (muc 4.3).
-- Chay tu dong mot lan khi volume postgres-data con trong.

-- =========================================================== Master data
CREATE TABLE IF NOT EXISTS machine (
    machine_id      VARCHAR(16) PRIMARY KEY,
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
    machine_id      VARCHAR(16)  NOT NULL REFERENCES machine(machine_id),
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS product (
    product_id            VARCHAR(16) PRIMARY KEY,
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

-- =========================================================== Speed layer (Spark Streaming)
CREATE TABLE IF NOT EXISTS machine_status_current (
    machine_id       VARCHAR(16) PRIMARY KEY,
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
    machine_id       VARCHAR(16) NOT NULL,
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
    machine_id       VARCHAR(16) NOT NULL,
    product_id       VARCHAR(16) NOT NULL,
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
    machine_id       VARCHAR(16) NOT NULL,
    product_id       VARCHAR(16) NOT NULL,
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
    machine_id    VARCHAR(16) NOT NULL,
    status        VARCHAR(16) NOT NULL,       -- IDLE | STOPPED
    start_time    TIMESTAMPTZ NOT NULL,
    end_time      TIMESTAMPTZ,
    duration_sec  DOUBLE PRECISION,
    shift_id      VARCHAR(8),
    PRIMARY KEY (machine_id, start_time)
);

CREATE TABLE IF NOT EXISTS oee_metric (
    machine_id     VARCHAR(16) NOT NULL,
    product_id     VARCHAR(16) NOT NULL,
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
