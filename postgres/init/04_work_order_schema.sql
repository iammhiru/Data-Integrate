-- ============================================================================
--  WORK ORDER (MES) — 14/11/2026
--
--  Vong doi WO (theo Vinamilk FillingWorkOrderStatus):
--      DRAFT ──release──▶ RELEASED ──start──▶ IN_PROGRESS ⇄ PAUSED
--                                                  │
--                                              complete
--                                                  ▼
--                                             COMPLETED
--      DRAFT/RELEASED ──cancel──▶ CANCELLED
--
--  Quyet dinh da chot:
--    · PlannedTime cua OEE theo WO = actual_start_time -> (actual_end_time ?? now)
--      (dung y Vinamilk: A = run_sec / planned_sec cua lenh)
--    · San luong/Good/NG theo WO = BASELINE chuan Vinamilk:
--        WO_VALUE = max(0, raw_counter_now - baseline_luc_bam_dau_WO)
--      baseline luu trong DB (chiu duoc restart), co reset guard.
--    · Service so huu nghiep vu ghi WO: master-api (POST/PUT + work_order_log)
--    · NG tay (nhap thu cong): CHUA can trong dot nay -> Q chi tinh tu counter may.
--
--  Idempotent: chay lai nhieu lan deu an toan.
-- ============================================================================

-- ---------------------------------------------------------------- Mo rong work_order
--  Cac cot moi dung de mo phong "tao phieu -> phat hanh -> chay -> hoan thanh".
--  `seq` = so thu tu lenh trong chuyen (dung de "lenh tiep theo").
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS planned_end      TIMESTAMPTZ;
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS released_at      TIMESTAMPTZ;
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS released_by      VARCHAR(64);
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS operator_id      VARCHAR(64);
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS note              TEXT;
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS seq               INT NOT NULL DEFAULT 1;
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS paused_at         TIMESTAMPTZ;
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS pause_accum_sec   DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE work_order ADD COLUMN IF NOT EXISTS unit              VARCHAR(16);

--  Status moi: DRAFT | RELEASED | IN_PROGRESS | PAUSED | COMPLETED | CANCELLED
--  Migrate status cu (PLANNED -> DRAFT, RUNNING -> IN_PROGRESS, DONE -> COMPLETED).
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN SELECT DISTINCT status FROM work_order WHERE status IS NOT NULL LOOP
        IF r.status IN ('PLANNED', 'NEW') THEN
            UPDATE work_order SET status = 'DRAFT' WHERE status = r.status;
        ELSIF r.status IN ('RUNNING', 'STARTED', 'INPROGRESS') THEN
            UPDATE work_order SET status = 'IN_PROGRESS' WHERE status = r.status;
        ELSIF r.status IN ('DONE', 'FINISHED') THEN
            UPDATE work_order SET status = 'COMPLETED' WHERE status = r.status;
        ELSIF r.status IN ('CANCEL', 'CANCELED') THEN
            UPDATE work_order SET status = 'CANCELLED' WHERE status = r.status;
        END IF;
    END LOOP;
END $$;

--  Moi chuyen chi chay duoc MOT work order tai mot thoi diem.
--  Partial unique index: chi ap dung cho WO "dang chay" (IN_PROGRESS/PAUSED).

--  Seed cu tao 9 WO deu status=RUNNING voi cung 1 timestamp -> vi pham quy tac
--  "1 chuyen = 1 lenh dang chay". Chuan hoa: giu WO dau tien theo thu tu tao la
--  IN_PROGRESS, cac WO con lai -> RELEASED (da phat hanh, chua chay).
WITH ranked AS (
    SELECT wo_id, line_id,
           ROW_NUMBER() OVER (PARTITION BY line_id ORDER BY created_at, wo_id) AS rn
    FROM work_order
    WHERE status IN ('IN_PROGRESS', 'PAUSED')
)
UPDATE work_order w
SET status = CASE WHEN r.rn = 1 THEN 'IN_PROGRESS' ELSE 'RELEASED' END
FROM ranked r
WHERE w.wo_id = r.wo_id
  AND w.status IN ('IN_PROGRESS', 'PAUSED')
  AND w.status <> CASE WHEN r.rn = 1 THEN 'IN_PROGRESS' ELSE 'RELEASED' END;

--  WO "dang chay" tu truoc den hom nay > 1 ngay -> dang chua dong -> hoan thanh.
--  (Seed Phase 1 tao WO moc thoi 13/11 voi actual_start_time = created_at.)
--  Thoi gian chay = toi da 8 gio (mot ca) neu chua co actual_end_time.
UPDATE work_order
SET status = 'COMPLETED',
    actual_end_time = COALESCE(actual_end_time, actual_start_time + interval '8 hours')
WHERE status IN ('IN_PROGRESS', 'PAUSED')
  AND actual_start_time IS NOT NULL
  AND actual_start_time < now() - interval '1 day';

CREATE UNIQUE INDEX IF NOT EXISTS uq_work_order_active_line
    ON work_order (line_id)
    WHERE status IN ('IN_PROGRESS', 'PAUSED');

--  Seq tang dan trong tung chuyen.
--  Seq = thu tu lenh trong chuyen. Seed cu co ca 3 WO cung seq=1 -> gan lai
--  theo thu tu tao truoc khi tao unique index.
WITH ranked AS (
    SELECT wo_id,
           ROW_NUMBER() OVER (PARTITION BY line_id ORDER BY created_at, wo_id) AS rn
    FROM work_order
)
UPDATE work_order w
SET seq = r.rn
FROM ranked r
WHERE w.wo_id = r.wo_id AND w.seq <> r.rn;

CREATE UNIQUE INDEX IF NOT EXISTS uq_work_order_line_seq
    ON work_order (line_id, seq);

CREATE INDEX IF NOT EXISTS idx_work_order_status   ON work_order (status);
CREATE INDEX IF NOT EXISTS idx_work_order_actual   ON work_order (actual_start_time, actual_end_time);

--  Constraint trang thai hop le (bo neu da ton tai tu lan chay truoc).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_work_order_status') THEN
        ALTER TABLE work_order ADD CONSTRAINT ck_work_order_status
            CHECK (status IN ('DRAFT', 'RELEASED', 'IN_PROGRESS', 'PAUSED', 'COMPLETED', 'CANCELLED'));
    END IF;
END $$;

-- ---------------------------------------------------------------- Nhat ky hanh dong WO
-- Tuong duong VNK_MES_FILLING_WORK_ORDER_LOG cua Vinamilk.
CREATE TABLE IF NOT EXISTS work_order_log (
    log_id       BIGSERIAL PRIMARY KEY,
    wo_id       VARCHAR(64) NOT NULL REFERENCES work_order (wo_id) ON DELETE CASCADE,
    action      VARCHAR(16) NOT NULL,   -- CREATE | UPDATE | RELEASE | START | PAUSE | RESUME | COMPLETE | CANCEL
    old_status  VARCHAR(16),
    new_status  VARCHAR(16),
    action_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    action_by   VARCHAR(64),
    category    VARCHAR(32) NOT NULL DEFAULT 'VAN_HANH',
    message     TEXT,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_wo_log_wo ON work_order_log (wo_id, action_at DESC);

-- ---------------------------------------------------------------- Baseline bo dem theo WO
-- Chup gia tri bo dem tai thoi diem WO bat dau.
--   WO_VALUE = max(0, raw_now - baseline_value)
-- Reset guard: neu raw < baseline (may reset bo dem) -> ha baseline xuong raw.
--
-- Bang cu (Phase 1) co PK (node_id, work_order_id, recorded_at) -> khong phu hop
-- vi baseline phai la "moc hien tai" cua (machine, tag, wo) de ghi de duoc.
-- Bang rong -> drop va tao lai.
DROP TABLE IF EXISTS counter_baseline;
CREATE TABLE IF NOT EXISTS counter_baseline (
    node_id        VARCHAR(128),
    machine_id     VARCHAR(32) NOT NULL REFERENCES machine (machine_id),
    tag_code       VARCHAR(64) NOT NULL,
    work_order_id  VARCHAR(64) NOT NULL REFERENCES work_order (wo_id) ON DELETE CASCADE,
    baseline_value DOUBLE PRECISION NOT NULL,
    last_raw_value DOUBLE PRECISION,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (machine_id, tag_code, work_order_id)
);
CREATE INDEX IF NOT EXISTS idx_cb_wo ON counter_baseline (work_order_id);

-- ---------------------------------------------------------------- Fact: gan WO vao du lieu
-- machine_kpi_1m / machine_kpi_1h: them wo_id + wo_code + product_id theo WO.
ALTER TABLE machine_kpi_1m ADD COLUMN IF NOT EXISTS wo_id   VARCHAR(64);
ALTER TABLE machine_kpi_1m ADD COLUMN IF NOT EXISTS wo_code VARCHAR(64);
ALTER TABLE machine_kpi_1h ADD COLUMN IF NOT EXISTS wo_id   VARCHAR(64);
ALTER TABLE machine_kpi_1h ADD COLUMN IF NOT EXISTS wo_code VARCHAR(64);

-- machine_state_interval: downtime cung cat theo WO.
ALTER TABLE machine_state_interval ADD COLUMN IF NOT EXISTS wo_id   VARCHAR(64);
ALTER TABLE machine_state_interval ADD COLUMN IF NOT EXISTS wo_code VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_kpi_1m_wo ON machine_kpi_1m (wo_id, ts_minute);
CREATE INDEX IF NOT EXISTS idx_kpi_1h_wo ON machine_kpi_1h (wo_id, ts_hour);
CREATE INDEX IF NOT EXISTS idx_msi_wo    ON machine_state_interval (wo_id, start_ts);

-- ---------------------------------------------------------------- View WO + tien do
-- Tien do san luong: so sanh san luong thuc te cua WO voi ke hoach.
--   actual_qty  = SUM(total_count) trong [actual_start_time, actual_end_time ?? now)
--   Trong khi WO chay, actual_end_time = NULL -> dung now().
--  View da ton tai voi shape cu -> phai DROP truoc khi CREATE OR REPLACE
--  (PostgreSQL khong cho doi ten/them cot khi replace).
DROP VIEW IF EXISTS work_order_progress;
CREATE VIEW work_order_progress AS
SELECT
    w.wo_id,
    w.wo_code,
    w.line_id,
    w.product_id,
    w.shift_id,
    w.status,
    w.seq,
    w.planned_qty,
    w.unit,
    w.actual_start_time,
    w.actual_end_time,
    w.planned_start,
    w.planned_end,
    EXTRACT(EPOCH FROM (COALESCE(w.actual_end_time, now()) - w.actual_start_time))::BIGINT AS elapsed_sec,
    w.pause_accum_sec,
    COALESCE(k.total_count, 0)    AS actual_qty,
    COALESCE(k.good_count, 0)     AS good_qty,
    COALESCE(k.defect_count, 0)   AS defect_qty,
    COALESCE(k.run_sec, 0)        AS run_sec,
    COALESCE(k.stopped_sec, 0)    AS stopped_sec,
    COALESCE(k.faulted_sec, 0)    AS faulted_sec,
    CASE WHEN COALESCE(k.total_count, 0) > 0
         THEN COALESCE(k.good_count, 0)::float8 / k.total_count
         ELSE NULL END AS quality,
    CASE WHEN w.planned_qty > 0
         THEN COALESCE(k.total_count, 0)::float8 / w.planned_qty
         ELSE NULL END AS progress_ratio
FROM work_order w
LEFT JOIN (
    -- Tong fact theo TUNG LENH (nhom theo wo_id, khong theo chuyen) —
    -- moi WO chi giu so lieu cua chinh no.
    -- Chi dem cac dong da gan dung wo_id (batch_kpi gan khi enrich).
    SELECT k.wo_id,
           SUM(k.total_count)  AS total_count,
           SUM(k.good_count)   AS good_count,
           SUM(k.defect_count) AS defect_count,
           SUM(k.run_sec)      AS run_sec,
           SUM(k.stopped_sec)  AS stopped_sec,
           SUM(k.faulted_sec)  AS faulted_sec
    FROM machine_kpi_1m k
    WHERE k.wo_id IS NOT NULL
      AND k.ts_minute >= (SELECT actual_start_time FROM work_order w2 WHERE w2.wo_id = k.wo_id)
      AND k.ts_minute <  COALESCE((SELECT actual_end_time FROM work_order w2 WHERE w2.wo_id = k.wo_id), now())
    GROUP BY k.wo_id
) k ON k.wo_id = w.wo_id;

-- ---------------------------------------------------------------- Ham tinh tien do WO
-- Tinh theo WO ma may nao thuoc chuyen -> lay tong fact cua cac may do trong
-- khoang [actual_start_time, actual_end_time ?? now).
CREATE OR REPLACE FUNCTION work_order_metrics(p_wo_id VARCHAR) RETURNS TABLE (
    machine_id     VARCHAR,
    total_count    BIGINT,
    good_count     BIGINT,
    defect_count   BIGINT,
    run_sec        DOUBLE PRECISION,
    stopped_sec    DOUBLE PRECISION,
    faulted_sec    DOUBLE PRECISION,
    maint_sec      DOUBLE PRECISION,
    off_sec        DOUBLE PRECISION,
    nodata_sec     DOUBLE PRECISION,
    stop_events    INT,
    ideal_time_sec DOUBLE PRECISION
) AS $$
    SELECT k.machine_id,
           SUM(k.total_count), SUM(k.good_count), SUM(k.defect_count),
           SUM(k.run_sec), SUM(k.stopped_sec), SUM(k.faulted_sec),
           SUM(k.maint_sec), SUM(k.off_sec), SUM(k.nodata_sec),
           SUM(k.stop_events), SUM(k.ideal_time_sec)
    FROM machine_kpi_1m k
    JOIN machine m ON m.machine_id = k.machine_id
    JOIN work_order w ON w.wo_id = p_wo_id
    WHERE m.line = w.line_id
      AND k.ts_minute >= w.actual_start_time
      AND k.ts_minute <  COALESCE(w.actual_end_time, now())
    GROUP BY k.machine_id
    ORDER BY k.machine_id;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------- Helper: WO dang chay
CREATE OR REPLACE VIEW work_order_running AS
SELECT DISTINCT ON (line_id) wo_id, wo_code, line_id, product_id, shift_id,
       actual_start_time, actual_end_time, status
FROM work_order
WHERE status IN ('IN_PROGRESS', 'PAUSED')
ORDER BY line_id, actual_start_time DESC NULLS LAST;

-- ---------------------------------------------------------------- Triggers: dong bo updated_at
CREATE OR REPLACE FUNCTION work_order_touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_work_order_touch ON work_order;
CREATE TRIGGER trg_work_order_touch
    BEFORE UPDATE ON work_order
    FOR EACH ROW EXECUTE FUNCTION work_order_touch_updated_at();
