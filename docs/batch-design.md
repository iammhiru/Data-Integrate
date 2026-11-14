# Luồng batch — Kafka → MinIO (raw) → Spark Batch → PostgreSQL → API

Luồng streaming (`stream-machine-state` → `state-api` → WebSocket) giữ nguyên, phục vụ **trạng thái hiện tại**.
Luồng batch phục vụ **lịch sử / phân tích**: sản lượng, downtime, chất lượng, OEE, data quality.

```
industrial.telemetry ─► raw-ingest (Spark Streaming, 1 phút) ─► MinIO raw/telemetry/ingest_date=/ingest_hour=/*.parquet
                                                                 raw/_invalid/...  (message hỏng + lý do)
                         batch-scheduler (mỗi 5 phút) ─► batch_kpi.py --mode auto
                               incremental: [data_until − 30′, now − 3′)
                               daily 00:30: tính lại trọn ngày hôm qua (bắt event trễ)
                         ─► PostgreSQL: fact CỘNG ĐƯỢC, độ mịn 1 phút ─► API SUM theo cửa sổ bất kỳ ─► UI
```

## Chạy

```bash
docker compose --profile telemetry --profile batch up -d          # toàn bộ
docker logs -f batch-scheduler                                     # log từng lần chạy (JSON)
# tính lại / nạp lịch sử theo ngày địa phương (tuần tự, ngày sau dùng snapshot cuối ngày trước)
docker compose --profile batch run --rm --no-deps batch-scheduler \
    /opt/batch/submit.sh --mode backfill --from 2026-11-12 --to 2026-11-13
```

Schema: `postgres/init/03_batch_schema.sql` (tự chạy khi volume Postgres trống; với DB đang chạy thì `psql < 03_batch_schema.sql`).

## Bảng

| Bảng | Khoá | Nội dung |
|---|---|---|
| `machine_kpi_1m` | machine_id, ts_minute | giây theo trạng thái (`run/starting/stopped/faulted/maint/off/nodata_sec`, tổng = 60), `stop_events`, `total/good/defect_count`, `ideal_time_sec`, line/product/shift. Partition theo ngày (UTC) |
| `machine_kpi_1h` | machine_id, ts_hour | rollup của bảng trên — dùng cho khoảng dài (> 2 ngày) |
| `machine_state_interval` | machine_id, start_ts | khoảng trạng thái liên tục (downtime, MTTR, top máy dừng). `is_open` = đang diễn ra |
| `tag_metric_1m` | machine_id, tag_name, ts_minute | `n, sum, min, max, last` của tag số (trend nhiệt độ, tốc độ…) |
| `data_quality_1m` | machine_id, ts_minute | `received, invalid, duplicate, missing_value, late, bad_quality, valid` |
| `batch_run` / view `batch_freshness` | | nhật ký chạy; `data_until` để UI ghi "dữ liệu tính đến …" |

## Quy ước tính

* **Trạng thái**: `MachineState` chỉ gửi khi đổi → mỗi giá trị kéo dài tới event kế tiếp. Đầu khoảng lấy
  snapshot cuối phút trước (`state_end/state_since`). Máy **im lặng > 120 s** (không tag nào) → `NO_DATA`
  (`nodata_sec`), không kéo dài trạng thái cũ khi mất kết nối / pipeline dừng.
* **Sản lượng**: bộ đếm tích luỹ → delta = cuối − đầu; giá trị giảm = reset (`delta = giá trị mới`, `counter_reset`).
  Máy không có `GoodCounter` (CODER): good = total − defect.
* **Ideal time** = total_count × 60 / DesignSpeed (sp/phút; thiếu tag → `machine.ideal_speed`).
* **Ca**: theo giờ Asia/Ho_Chi_Minh, ca C (22:00–06:00) thuộc ngày bắt đầu ca (`shift_date`).
* **Late** = kafka_ts − event_ts > 30 s. **Duplicate** = số message − số eventId khác nhau.

## Analytics API (đã dựng) — `state-api` FastAPI, Swagger: http://localhost:8000/docs

Cùng backend với luồng realtime (WebSocket `/ws/machines`), router riêng `services/state-api/analytics.py`.
UI gọi qua gateway: `/state-api/api/analytics/...`.

| Endpoint | Dùng cho |
|---|---|
| `GET /api/analytics/overview` | thẻ KPI Overview: OEE nhà máy + từng line, sản lượng, downtime, top 5 máy dừng, data quality (mặc định ca hiện tại) |
| `GET /api/analytics/oee` | OEE/A/P/Q + phân rã thời gian; `groupBy=machine\|line\|plant\|product\|shift`, `bucket=1m..1d\|shift` cho trend |
| `GET /api/analytics/production` | tổng / đạt / loại / reject rate / sp mỗi giờ chạy |
| `GET /api/analytics/downtime` | tổng thời gian dừng, số lần, MTTR theo máy/line, top N, `states=` |
| `GET /api/analytics/downtime/events` | danh sách khoảng dừng (timeline, bảng sự kiện) |
| `GET /api/analytics/tags`, `/tags/trend` | trend avg/min/max/last của tag số |
| `GET /api/analytics/data-quality` | received/invalid/duplicate/missing/late/bad + tỷ lệ |
| `GET /api/analytics/freshness` | `dataUntil`, độ trễ batch, các lần chạy gần nhất |

Cửa sổ: `last=15m|3h|7d` (mặc định 1h) · `preset=today|yesterday|current_shift|previous_shift` ·
`from`/`to` ISO 8601 có múi giờ. Tối đa 31 ngày; > 2 ngày đọc `machine_kpi_1h`. Mọi response có
`window.dataUntil` và `window.partial` (cửa sổ vượt quá phần batch đã tính).
OEE line/plant chỉ tính trên máy tham chiếu (`REF_MACHINE_PATTERN=%FILLER%`), `referenceOnly=false` để cộng tất cả.

## SQL gốc — luôn SUM rồi mới chia (không lấy trung bình của tỷ lệ)

```sql
-- OEE từng máy, cửa sổ bất kỳ (:from, :to). Đổi GROUP BY để lấy theo giờ / ca / ngày / line.
SELECT machine_id,
       sum(run_sec)                                   AS run_sec,
       sum(60 - off_sec - maint_sec - nodata_sec)     AS scheduled_sec,   -- OFF/MAINTENANCE = dừng có kế hoạch
       sum(ideal_time_sec)                            AS ideal_sec,
       sum(total_count) AS total, sum(good_count) AS good, sum(stop_events) AS stops
FROM machine_kpi_1m
WHERE ts_minute >= :from AND ts_minute < :to
GROUP BY machine_id;
-- planned = scheduled_sec × 450/480 (30′ nghỉ/ca)   A = run/planned   P = ideal/run   Q = good/total
-- OEE line: lấy máy có process = line.reference_process (FILLING)
-- theo ca: GROUP BY shift_date, shift_id     theo giờ: date_trunc('hour', ts_minute) hoặc machine_kpi_1h
-- trend tag: SELECT ts_minute, sum/n AS avg, min, max FROM tag_metric_1m WHERE machine_id=… AND tag_name='…'
-- data quality rate = sum(valid) / sum(received)
```

## Giới hạn đã biết

* Simulator tăng `TotalCounter`, `GoodCounter`, `DefectCounter` **cùng +1 mỗi nhịp** → defect ≈ total và
  good ≈ total (Q ≈ 100 %, defect vô nghĩa). Cần sửa simulator (vd defect = total × tỉ lệ lỗi, good = total − defect).
* `CIP_SKID_01` không có DesignSpeed / ideal_speed → P = 0; loại khỏi OEE.
* Trung bình tag là trung bình mẫu (middleware gửi khi đổi), không trọng số theo thời gian.
* Raw giữ `raw_json` → ~160 B/message (~3 GB/ngày ở 211 msg/s). Có thể bỏ cột này nếu thiếu dung lượng.
