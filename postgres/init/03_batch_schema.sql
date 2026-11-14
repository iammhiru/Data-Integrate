-- ============================================================================
-- BATCH LAYER (spark/apps/batch_kpi.py ghi) - 14/11/2026
--
-- Nguyen tac: moi cot so lieu deu CONG DUOC (sum/count/min/max/giay/delta).
-- KHONG luu ty le (OEE, A, P, Q, avg, %) -> API SUM theo cua so bat ky roi moi chia:
--     A = run_sec / planned_sec      P = ideal_time_sec / run_sec
--     Q = good_count / total_count   OEE = A * P * Q
-- Moi ts la TIMESTAMPTZ (UTC). shift_id / shift_date tinh theo gio dia phuong (Asia/Ho_Chi_Minh).
-- Ghi theo kieu: DELETE khoang [from, to) + INSERT trong 1 transaction -> chay lai idempotent.
-- ============================================================================

-- ---------------------------------------------------------------- KPI may theo phut
CREATE TABLE IF NOT EXISTS machine_kpi_1m (
    machine_id      VARCHAR(32)  NOT NULL,
    ts_minute       TIMESTAMPTZ  NOT NULL,
    line_id         VARCHAR(32),
    product_id      VARCHAR(32),
    shift_id        VARCHAR(8),
    shift_date      DATE,
    -- so giay o tung trang thai trong phut (tong = 60)
    run_sec         REAL NOT NULL DEFAULT 0,      -- RUNNING
    starting_sec    REAL NOT NULL DEFAULT 0,      -- STARTING
    stopped_sec     REAL NOT NULL DEFAULT 0,      -- STOPPED
    faulted_sec     REAL NOT NULL DEFAULT 0,      -- FAULTED
    maint_sec       REAL NOT NULL DEFAULT 0,      -- MAINTENANCE
    off_sec         REAL NOT NULL DEFAULT 0,      -- OFF
    nodata_sec      REAL NOT NULL DEFAULT 0,      -- chua biet trang thai
    stop_events     INT  NOT NULL DEFAULT 0,      -- so lan chuyen sang STOPPED/FAULTED
    -- san luong (delta bo dem tich luy)
    total_count     BIGINT NOT NULL DEFAULT 0,
    good_count      BIGINT NOT NULL DEFAULT 0,
    defect_count    BIGINT NOT NULL DEFAULT 0,
    ideal_time_sec  DOUBLE PRECISION NOT NULL DEFAULT 0,   -- total_count * 60 / design_speed
    counter_reset   BOOLEAN NOT NULL DEFAULT FALSE,
    -- snapshot cuoi phut: diem bat dau cho lan chay sau (KHONG cong, chi doc)
    design_speed    DOUBLE PRECISION,
    state_end       SMALLINT,
    state_since     TIMESTAMPTZ,
    total_end       DOUBLE PRECISION,
    good_end        DOUBLE PRECISION,
    defect_end      DOUBLE PRECISION,
    PRIMARY KEY (machine_id, ts_minute)
) PARTITION BY RANGE (ts_minute);
CREATE INDEX IF NOT EXISTS idx_machine_kpi_1m_ts ON machine_kpi_1m (ts_minute);
CREATE INDEX IF NOT EXISTS idx_machine_kpi_1m_shift ON machine_kpi_1m (shift_date, shift_id);

-- ---------------------------------------------------------------- KPI may theo gio (rollup tu 1m)
CREATE TABLE IF NOT EXISTS machine_kpi_1h (
    machine_id      VARCHAR(32)  NOT NULL,
    ts_hour         TIMESTAMPTZ  NOT NULL,
    line_id         VARCHAR(32),
    product_id      VARCHAR(32),
    shift_id        VARCHAR(8),
    shift_date      DATE,
    minutes         INT  NOT NULL,
    run_sec         REAL NOT NULL, starting_sec REAL NOT NULL, stopped_sec REAL NOT NULL,
    faulted_sec     REAL NOT NULL, maint_sec    REAL NOT NULL, off_sec     REAL NOT NULL,
    nodata_sec      REAL NOT NULL,
    stop_events     INT  NOT NULL,
    total_count     BIGINT NOT NULL, good_count BIGINT NOT NULL, defect_count BIGINT NOT NULL,
    ideal_time_sec  DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (machine_id, ts_hour)
);
CREATE INDEX IF NOT EXISTS idx_machine_kpi_1h_ts ON machine_kpi_1h (ts_hour);

-- ---------------------------------------------------------------- Khoang trang thai (downtime)
CREATE TABLE IF NOT EXISTS machine_state_interval (
    machine_id      VARCHAR(32)  NOT NULL,
    start_ts        TIMESTAMPTZ  NOT NULL,
    end_ts          TIMESTAMPTZ  NOT NULL,
    state           SMALLINT     NOT NULL,
    state_name      VARCHAR(16)  NOT NULL,
    duration_sec    DOUBLE PRECISION NOT NULL,
    is_open         BOOLEAN NOT NULL DEFAULT FALSE,   -- chua ket thuc tai thoi diem batch chay
    line_id         VARCHAR(32),
    shift_id        VARCHAR(8),                       -- ca luc bat dau
    shift_date      DATE,
    PRIMARY KEY (machine_id, start_ts)
);
CREATE INDEX IF NOT EXISTS idx_msi_end ON machine_state_interval (end_ts);
CREATE INDEX IF NOT EXISTS idx_msi_state ON machine_state_interval (state, start_ts);

-- ---------------------------------------------------------------- Tong hop tag so theo phut
-- Trung binh = sum / n (trung binh mau, khong trong so thoi gian: middleware chi gui khi doi gia tri)
CREATE TABLE IF NOT EXISTS tag_metric_1m (
    machine_id      VARCHAR(32)  NOT NULL,
    tag_name        VARCHAR(64)  NOT NULL,
    ts_minute       TIMESTAMPTZ  NOT NULL,
    n               INT NOT NULL,
    sum             DOUBLE PRECISION NOT NULL,
    min             DOUBLE PRECISION,
    max             DOUBLE PRECISION,
    last            DOUBLE PRECISION,
    PRIMARY KEY (machine_id, tag_name, ts_minute)
) PARTITION BY RANGE (ts_minute);
CREATE INDEX IF NOT EXISTS idx_tag_metric_1m_ts ON tag_metric_1m (ts_minute);

-- ---------------------------------------------------------------- Chat luong du lieu theo phut
-- received = so message nhan (ke ca trung, ke ca invalid); cac cot con lai dem tren event da dedup.
-- Data Quality Rate = valid / received.  machine_id = 'UNKNOWN' cho message khong doc duoc may.
CREATE TABLE IF NOT EXISTS data_quality_1m (
    machine_id      VARCHAR(32)  NOT NULL,
    ts_minute       TIMESTAMPTZ  NOT NULL,
    received        BIGINT NOT NULL DEFAULT 0,
    invalid         BIGINT NOT NULL DEFAULT 0,
    duplicate       BIGINT NOT NULL DEFAULT 0,
    missing_value   BIGINT NOT NULL DEFAULT 0,
    late            BIGINT NOT NULL DEFAULT 0,    -- kafka_ts - event_ts > late threshold
    bad_quality     BIGINT NOT NULL DEFAULT 0,    -- quality.isGood = false
    valid           BIGINT NOT NULL DEFAULT 0,    -- dedup, co gia tri, dung format
    PRIMARY KEY (machine_id, ts_minute)
);
CREATE INDEX IF NOT EXISTS idx_dq_1m_ts ON data_quality_1m (ts_minute);

-- ---------------------------------------------------------------- Nhat ky chay batch
CREATE TABLE IF NOT EXISTS batch_run (
    run_id          BIGSERIAL PRIMARY KEY,
    job             VARCHAR(32) NOT NULL,          -- incremental | daily | backfill
    range_start     TIMESTAMPTZ NOT NULL,
    range_end       TIMESTAMPTZ NOT NULL,          -- = "data_until" cho API
    status          VARCHAR(16) NOT NULL,          -- RUNNING | SUCCESS | FAILED
    stats           JSONB,
    error           TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_batch_run_job ON batch_run (job, status, range_end DESC);

-- ---------------------------------------------------------------- Partition theo ngay (UTC)
CREATE OR REPLACE FUNCTION batch_ensure_partitions(p_from DATE, p_to DATE) RETURNS void AS $$
DECLARE d DATE; t TEXT;
BEGIN
    d := p_from;
    WHILE d <= p_to LOOP
        FOREACH t IN ARRAY ARRAY['machine_kpi_1m', 'tag_metric_1m'] LOOP
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                t || '_' || to_char(d, 'YYYYMMDD'), t,
                (d::timestamp AT TIME ZONE 'UTC'), ((d + 1)::timestamp AT TIME ZONE 'UTC'));
        END LOOP;
        d := d + 1;
    END LOOP;
END $$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------- Do tuoi du lieu cho API
CREATE OR REPLACE VIEW batch_freshness AS
SELECT max(range_end) AS data_until, max(finished_at) AS last_success_at
FROM batch_run WHERE status = 'SUCCESS' AND job IN ('incremental', 'daily', 'backfill');
