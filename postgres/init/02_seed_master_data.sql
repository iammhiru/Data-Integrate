-- ============================================================================
--  MASTER DATA — seed tu `config/master_data.json`.
--  SINH TU DONG: `python tools/gen_seed_sql.py` (KHONG sua tay file nay).
--
--  Nguon du lieu:
--    · 26 may  <- IndustrialTelemetry.Middleware/metadata/catalog.json
--                 (dung voi middleware, dong doi day len)
--    · SKU     <- khai bao trong tools/gen_master_data.py
--    · Ideal Cycle Time <- DesignSpeed thuc te doc tu state-api
--  Moi truong: CHAY LAI khi doi master data:
--    docker compose -f docker-compose.server.yml exec -T postgres \
--        psql -U sf_user -d smart_factory \
--        -f /docker-entrypoint-initdb.d/02_seed_master_data.sql
-- ============================================================================


-- San pham (SKU) + Ideal Cycle Time (giay/san pham).

INSERT INTO product (product_id, product_name, ideal_cycle_time_sec) VALUES
    ('PET-500-COKE', 'Nước có ga 500ml', 0.4234),
    ('PET-500-WATER', 'Nước khoáng 500ml', 0.5047),
    ('CAN-330-SUGAR', 'Nước giải khát lon 330ml', 0.5877)
ON CONFLICT (product_id) DO UPDATE SET
    product_name = EXCLUDED.product_name,
    ideal_cycle_time_sec = EXCLUDED.ideal_cycle_time_sec;


-- Ca san xuat. Planned Production Time = planned_minutes - planned_break_minutes.

INSERT INTO shift (shift_id, shift_name, start_time, end_time, planned_minutes, planned_break_minutes) VALUES
    ('A', 'Ca A', '06:00', '14:00', 480, 30),
    ('B', 'Ca B', '14:00', '22:00', 480, 30),
    ('C', 'Ca C', '22:00', '06:00', 480, 30)
ON CONFLICT (shift_id) DO UPDATE SET
    shift_name = EXCLUDED.shift_name,
    start_time = EXCLUDED.start_time,
    end_time = EXCLUDED.end_time,
    planned_minutes = EXCLUDED.planned_minutes,
    planned_break_minutes = EXCLUDED.planned_break_minutes;


-- Dong chay san xuat. `reference_process` = cong doan CHIET (ra san pham chinh).

INSERT INTO line (line_id, line_name, channel, reference_process, product_id, unit) VALUES
    ('LINE_01', 'Chai PET — có ga', 'LINE_01', 'FILLING', 'PET-500-COKE', 'bottles'),
    ('LINE_02', 'Chai PET — không ga', 'LINE_02', 'FILLING', 'PET-500-WATER', 'bottles'),
    ('LINE_03', 'Lon nhôm', 'LINE_03', 'FILLING', 'CAN-330-SUGAR', 'cans')
ON CONFLICT (line_id) DO UPDATE SET
    line_name = EXCLUDED.line_name,
    channel = EXCLUDED.channel,
    reference_process = EXCLUDED.reference_process,
    product_id = EXCLUDED.product_id,
    unit = EXCLUDED.unit;


-- 26 may that (catalog.json). `ideal_speed` = DesignSpeed thuc te.

INSERT INTO machine (machine_id, machine_name, line, machine_type, location, ideal_speed, installed_at) VALUES
    ('L01_PREFEED_01', 'L01_PREFEED_01', 'LINE_01', 'PREFORM_FEEDER', 'PLANT_01', 132.731, DATE '2026-01-01'),
    ('L01_BLOWER_01', 'L01_BLOWER_01', 'LINE_01', 'STRETCH_BLOW_MOULDER', 'PLANT_01', 147.8, DATE '2026-01-01'),
    ('L01_AIRCONV_01', 'L01_AIRCONV_01', 'LINE_01', 'AIR_CONVEYOR', 'PLANT_01', 111.11, DATE '2026-01-01'),
    ('L01_RINSER_01', 'L01_RINSER_01', 'LINE_01', 'BOTTLE_RINSER', 'PLANT_01', 83.0, DATE '2026-01-01'),
    ('L01_FILLER_01', 'L01_FILLER_01', 'LINE_01', 'CARBONATED_FILLER', 'PLANT_01', 141.694, DATE '2026-01-01'),
    ('L01_CAPPER_01', 'L01_CAPPER_01', 'LINE_01', 'SCREW_CAPPER', 'PLANT_01', 104.178, DATE '2026-01-01'),
    ('L01_LABELER_01', 'L01_LABELER_01', 'LINE_01', 'BOTTLE_LABELER', 'PLANT_01', 87.738, DATE '2026-01-01'),
    ('L01_CODER_01', 'L01_CODER_01', 'LINE_01', 'DATE_CODER', 'PLANT_01', 136.083, DATE '2026-01-01'),
    ('L01_CASEPACKER_01', 'L01_CASEPACKER_01', 'LINE_01', 'CASE_PACKER', 'PLANT_01', 112.079, DATE '2026-01-01'),
    ('L02_PREFEED_01', 'L02_PREFEED_01', 'LINE_02', 'PREFORM_FEEDER', 'PLANT_01', 93.943, DATE '2026-01-01'),
    ('L02_BLOWER_01', 'L02_BLOWER_01', 'LINE_02', 'STRETCH_BLOW_MOULDER', 'PLANT_01', 89.905, DATE '2026-01-01'),
    ('L02_AIRCONV_01', 'L02_AIRCONV_01', 'LINE_02', 'AIR_CONVEYOR', 'PLANT_01', 113.435, DATE '2026-01-01'),
    ('L02_RINSER_01', 'L02_RINSER_01', 'LINE_02', 'BOTTLE_RINSER', 'PLANT_01', 85.665, DATE '2026-01-01'),
    ('L02_FILLER_01', 'L02_FILLER_01', 'LINE_02', 'STILL_FILLER', 'PLANT_01', 118.872, DATE '2026-01-01'),
    ('L02_CAPPER_01', 'L02_CAPPER_01', 'LINE_02', 'SCREW_CAPPER', 'PLANT_01', 100.128, DATE '2026-01-01'),
    ('L02_LABELER_01', 'L02_LABELER_01', 'LINE_02', 'BOTTLE_LABELER', 'PLANT_01', 85.293, DATE '2026-01-01'),
    ('L02_CODER_01', 'L02_CODER_01', 'LINE_02', 'DATE_CODER', 'PLANT_01', 122.879, DATE '2026-01-01'),
    ('L02_CASEPACKER_01', 'L02_CASEPACKER_01', 'LINE_02', 'CASE_PACKER', 'PLANT_01', 88.191, DATE '2026-01-01'),
    ('L03_CANDEPAL_01', 'L03_CANDEPAL_01', 'LINE_03', 'CAN_DEPALLETIZER', 'PLANT_01', 124.492, DATE '2026-01-01'),
    ('L03_CANRINSER_01', 'L03_CANRINSER_01', 'LINE_03', 'CAN_RINSER', 'PLANT_01', 148.43, DATE '2026-01-01'),
    ('L03_CANFILLER_01', 'L03_CANFILLER_01', 'LINE_03', 'CAN_FILLER', 'PLANT_01', 102.085, DATE '2026-01-01'),
    ('L03_SEAMER_01', 'L03_SEAMER_01', 'LINE_03', 'CAN_SEAMER', 'PLANT_01', 123.88, DATE '2026-01-01'),
    ('L03_CANCODER_01', 'L03_CANCODER_01', 'LINE_03', 'DATE_CODER', 'PLANT_01', 112.949, DATE '2026-01-01'),
    ('L03_CANINSPECT_01', 'L03_CANINSPECT_01', 'LINE_03', 'CAN_INSPECTION', 'PLANT_01', 138.507, DATE '2026-01-01'),
    ('L03_CASEPACKER_01', 'L03_CASEPACKER_01', 'LINE_03', 'CASE_PACKER', 'PLANT_01', 109.75, DATE '2026-01-01'),
    ('CIP_SKID_01', 'CIP_SKID_01', 'SHARED', 'CIP_SKID', 'PLANT_01', NULL, DATE '2026-01-01')
ON CONFLICT (machine_id) DO UPDATE SET
    machine_name = EXCLUDED.machine_name,
    line = EXCLUDED.line,
    machine_type = EXCLUDED.machine_type,
    location = EXCLUDED.location,
    ideal_speed = EXCLUDED.ideal_speed;


-- Chu hoa ID tu cac nguon khac nhau -> machineId.

INSERT INTO machine_id_mapping (source, source_id, machine_id) VALUES
    ('kepware', 'PREF-L01-01', 'L01_PREFEED_01'),
    ('kepware', 'BLOW-L01-01', 'L01_BLOWER_01'),
    ('kepware', 'ACONV-L01-01', 'L01_AIRCONV_01'),
    ('kepware', 'RINSE-L01-01', 'L01_RINSER_01'),
    ('kepware', 'FILL-L01-01', 'L01_FILLER_01'),
    ('kepware', 'CAPP-L01-01', 'L01_CAPPER_01'),
    ('kepware', 'LABL-L01-01', 'L01_LABELER_01'),
    ('kepware', 'CODE-L01-01', 'L01_CODER_01'),
    ('kepware', 'CASE-L01-01', 'L01_CASEPACKER_01'),
    ('kepware', 'PREF-L02-01', 'L02_PREFEED_01'),
    ('kepware', 'BLOW-L02-01', 'L02_BLOWER_01'),
    ('kepware', 'ACONV-L02-01', 'L02_AIRCONV_01'),
    ('kepware', 'RINSE-L02-01', 'L02_RINSER_01'),
    ('kepware', 'FILL-L02-01', 'L02_FILLER_01'),
    ('kepware', 'CAPP-L02-01', 'L02_CAPPER_01'),
    ('kepware', 'LABL-L02-01', 'L02_LABELER_01'),
    ('kepware', 'CODE-L02-01', 'L02_CODER_01'),
    ('kepware', 'CASE-L02-01', 'L02_CASEPACKER_01'),
    ('kepware', 'DEPL-L03-01', 'L03_CANDEPAL_01'),
    ('kepware', 'RINSE-L03-01', 'L03_CANRINSER_01'),
    ('kepware', 'FILL-L03-01', 'L03_CANFILLER_01'),
    ('kepware', 'SEAM-L03-01', 'L03_SEAMER_01'),
    ('kepware', 'CODE-L03-01', 'L03_CANCODER_01'),
    ('kepware', 'INSP-L03-01', 'L03_CANINSPECT_01'),
    ('kepware', 'CASE-L03-01', 'L03_CASEPACKER_01'),
    ('kepware', 'CIP-SHARED-01', 'CIP_SKID_01')
ON CONFLICT (source, source_id) DO UPDATE SET
    machine_id = EXCLUDED.machine_id;


-- Work order (don hang san xuat). Trang thai RUNNING = dang chay.

INSERT INTO work_order (wo_id, wo_code, line_id, product_id, shift_id, planned_qty, status, actual_start_time) VALUES
    ('WO-2026-11-13-LINE_01-A', 'WO-2611-1301-A', 'LINE_01', 'PET-500-COKE', 'A', 57400, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_01-B', 'WO-2611-1301-B', 'LINE_01', 'PET-500-COKE', 'B', 57400, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_01-C', 'WO-2611-1301-C', 'LINE_01', 'PET-500-COKE', 'C', 57400, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_02-A', 'WO-2611-1302-A', 'LINE_02', 'PET-500-WATER', 'A', 52600, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_02-B', 'WO-2611-1302-B', 'LINE_02', 'PET-500-WATER', 'B', 52600, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_02-C', 'WO-2611-1302-C', 'LINE_02', 'PET-500-WATER', 'C', 52600, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_03-A', 'WO-2611-1303-A', 'LINE_03', 'CAN-330-SUGAR', 'A', 44000, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_03-B', 'WO-2611-1303-B', 'LINE_03', 'CAN-330-SUGAR', 'B', 44000, 'RUNNING', now()),
    ('WO-2026-11-13-LINE_03-C', 'WO-2611-1303-C', 'LINE_03', 'CAN-330-SUGAR', 'C', 44000, 'RUNNING', now())
ON CONFLICT (wo_id) DO UPDATE SET
    wo_code = EXCLUDED.wo_code,
    line_id = EXCLUDED.line_id,
    product_id = EXCLUDED.product_id,
    shift_id = EXCLUDED.shift_id,
    planned_qty = EXCLUDED.planned_qty,
    status = EXCLUDED.status;


-- Ke hoach san luong theo line + ca.

INSERT INTO production_plan (line_id, shift_id, product_id, plan_date, planned_qty, theoretical_qty) VALUES
    ('LINE_01', 'A', 'PET-500-COKE', CURRENT_DATE, 57400, 63769),
    ('LINE_01', 'B', 'PET-500-COKE', CURRENT_DATE, 57400, 63769),
    ('LINE_01', 'C', 'PET-500-COKE', CURRENT_DATE, 57400, 63769),
    ('LINE_02', 'A', 'PET-500-WATER', CURRENT_DATE, 52600, 53497),
    ('LINE_02', 'B', 'PET-500-WATER', CURRENT_DATE, 52600, 53497),
    ('LINE_02', 'C', 'PET-500-WATER', CURRENT_DATE, 52600, 53497),
    ('LINE_03', 'A', 'CAN-330-SUGAR', CURRENT_DATE, 44000, 45942),
    ('LINE_03', 'B', 'CAN-330-SUGAR', CURRENT_DATE, 44000, 45942),
    ('LINE_03', 'C', 'CAN-330-SUGAR', CURRENT_DATE, 44000, 45942)
ON CONFLICT (line_id, shift_id, plan_date) DO UPDATE SET
    product_id = EXCLUDED.product_id,
    planned_qty = EXCLUDED.planned_qty,
    theoretical_qty = EXCLUDED.theoretical_qty;


-- GHI CHU:
--   counter_baseline KHONG seed — no duoc GHI RUNTIME khi work order bat dau
--   (bo dem may tich luy tu lan bat nguon, khong reset theo ca/WO).
--   Phase 2 se chen moc nay tu dong khi nhan su kien WO_START.
