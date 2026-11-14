# Smart Manufacturing - Realtime + Batch Analytics (Nhóm 18)

Phiên bản hệ thống: **0.4.0** (xem [Phiên bản](#phiên-bản)).

Hai luồng dùng chung nguồn Kafka, cùng một backend (`state-api`) và cùng một UI:

```
                    ┌─ REALTIME ─ stream-machine-state ─▶ machine-state ──────────▶ state-api ── WebSocket /ws/machines ─┐
middleware-sim ─▶ industrial.telemetry   (Spark, trigger 1s)   (compacted)             :8000                               ├─▶ gateway :5080 ─▶ UI MES
(26 máy, 404 tag)   │                                                                    ▲                                   │
                    └─ BATCH ── raw-ingest ─▶ MinIO raw Parquet ─▶ batch-scheduler ─▶ PostgreSQL ── /api/analytics/* ───────┘
                               (Spark, 1 phút)  (Data Lake)          (Spark, 5 phút)    (fact 1 phút)
                                                                                         master-api :8001 (master data) ─────┘
```

- **Realtime**: trạng thái *hiện tại* của từng máy (độ trễ ~1–2 s).
- **Batch**: lịch sử / phân tích — OEE, sản lượng, downtime, trend tag, chất lượng dữ liệu (độ trễ ≤ ~8 phút).
  Thiết kế chi tiết: [`docs/batch-design.md`](docs/batch-design.md).

## Yêu cầu

- Docker Desktop (Compose v2). Cấp cho Docker **≥ 4 CPU, ≥ 6 GB RAM** cho realtime; **≥ 6 CPU, ≥ 10 GB RAM** khi bật thêm batch.
- Các cổng trống: 5080, 5432, 8000, 8001, 8080, 8081, 8082, 9000, 9001, 9094, 4040, 4043.

## Dựng hệ thống

```bash
cp .env.example .env                                                   # lần đầu (xem lưu ý bên dưới)
docker compose --profile telemetry --profile batch up -d --build      # realtime + batch (đầy đủ)
docker compose --profile telemetry --profile batch ps                  # kiểm tra trạng thái
```

Chỉ cần realtime: `docker compose --profile telemetry up -d --build` (bỏ `--profile batch`).

> **Lưu ý `.env`**: `.env.example` có một số biến trỏ sang máy server của nhóm (`192.168.179.176`) để chạy native
> trên Windows. Khi chạy bằng docker compose **không cần sửa**: compose tự dùng host nội bộ (`kafka:9092`, `postgres`,
> `minio`). Chỉ các biến sau được compose dùng: `KAFKA_CLUSTER_ID`, `MINIO_ROOT_USER/PASSWORD`, `MINIO_BUCKET`,
> `POSTGRES_DB/USER/PASSWORD`, `SPARK_WORKER_CORES/MEMORY`, `DASHBOARD_PORT`.

Lần đầu build mất vài phút. `kafka-init` / `minio-init` chạy một lần rồi thoát (`Exited (0)` là bình thường).
Postgres tự tạo schema + master data từ `postgres/init/*.sql` **khi volume còn trống**.
Đợi API nạp xong dữ liệu (`"ready": true`):

```bash
curl http://localhost:8000/health
```

Mở **http://localhost:5080** — UI MES (dữ liệu realtime). Thêm `?source=mock` để xem dữ liệu giả lập trong trình duyệt.

| Service | Profile | Vai trò | Truy cập từ máy host |
|---|---|---|---|
| `gateway` | — | nginx: UI + proxy `/state-api/*` → state-api, `/master-api/*` → master-api | **http://localhost:5080** |
| `dashboard` | — | UI MES (React) + backend .NET cũ (trang `/diagnostics.html`) | qua gateway |
| `master-api` | — | Master data (line, SKU, work order, kế hoạch, ca) từ PostgreSQL, fallback `config/master_data.json` | http://localhost:8001/docs |
| `middleware-sim` | telemetry | IndustrialTelemetry.Middleware chạy `SIMULATION_MODE=true`, phát dữ liệu 26 máy vào `industrial.telemetry` | |
| `stream-machine-state` | telemetry | Spark job `spark/apps/machine_state_stream.py`: giữ giá trị mới nhất mỗi (máy, tag) → `machine-state` | Spark UI http://localhost:4043 |
| `state-api` | telemetry | Realtime (WebSocket + REST đọc `machine-state`) **và** Analytics API (`/api/analytics/*` đọc PostgreSQL) | http://localhost:8000 (Swagger: `/docs`) |
| `raw-ingest` | batch | Spark job `spark/apps/raw_ingest.py`: Kafka → MinIO Parquet (Data Lake), message hỏng → `raw/_invalid` | |
| `batch-scheduler` | batch | Chạy `spark/apps/batch_kpi.py` mỗi 5 phút (incremental) + 00:30 hằng ngày (tính lại ngày hôm qua) → PostgreSQL | `docker logs -f batch-scheduler` |
| `kafka` / `kafka-ui` | — | Broker + giao diện xem topic | `localhost:9094` / http://localhost:8082 |
| `spark-master` / `spark-worker` | — | Cụm Spark | http://localhost:8080 / http://localhost:8081 |
| `minio` | — | Data Lake (bucket `smart-factory`, user/pass trong `.env`) | console http://localhost:9001 |
| `postgres` | — | Master data + bảng phân tích của batch | `localhost:5432` |

## Gọi API (Postman / curl)

Base URL: `http://localhost:8000`

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | API đã nạp xong snapshot chưa, số máy / tag |
| GET | `/api/machines` | Danh sách máy + trạng thái tóm tắt. Lọc: `?lineId=LINE_01`, `?machineType=CAN_FILLER`, `?state=RUNNING` |
| GET | `/api/machines/{machineId}` | Trạng thái mới nhất + toàn bộ tag của 1 máy |
| GET | `/api/machines/{machineId}/tags/{tagName}` | Giá trị mới nhất của 1 tag |
| GET | `/api/lines` | Số máy theo line và trạng thái |

Ví dụ:

```bash
curl http://localhost:8000/api/machines/L01_FILLER_01
curl http://localhost:8000/api/machines/L01_FILLER_01/tags/FillLevel
curl "http://localhost:8000/api/machines?lineId=LINE_03&state=RUNNING"
curl http://localhost:8000/api/lines
```

Response `GET /api/machines/L01_FILLER_01` (rút gọn):

```json
{
  "machineId": "L01_FILLER_01", "plantId": "PLANT_01", "lineId": "LINE_01",
  "processId": "FILLING", "machineType": "CARBONATED_FILLER", "equipmentCode": "FILL-L01-01",
  "sourceSystem": "simulator",
  "state": "RUNNING",
  "stateSince": "2026-11-12T15:14:57.375Z",
  "summary": { "MachineState": 2, "CurrentSpeed": 149.2, "TotalCounter": 23, "EmergencyStop": false, "...": "..." },
  "tagCount": 18,
  "lastEventTime": "2026-11-12T15:15:00.758Z",
  "ageSeconds": 1.3,
  "stale": false,
  "tags": {
    "FillLevel": { "value": 33.765, "valueType": "Float", "unit": "%", "statusCode": "Good", "isGood": true,
                   "tagCode": "FILL.L01.FILLLEVEL", "tagType": "ANALOG",
                   "eventTime": "2026-11-12T15:15:00.758Z", "emittedAt": "2026-11-12T15:15:01.167Z" },
    "MachineState": { "value": 2, "stateName": "RUNNING", "...": "..." }
  }
}
```

- `state`: `OFF` / `STARTING` / `RUNNING` / `STOPPED` / `FAULTED` / `MAINTENANCE` (từ tag `MachineState`).
- `ageSeconds`: số giây kể từ event mới nhất của máy; `stale = true` khi > 60s (đổi bằng env `STALE_AFTER_SEC`).
- `value = null` kèm `statusCode = "Bad"` nghĩa là không đọc được giá trị (không phải 0).

## Realtime qua WebSocket

Trang xem nhanh: **http://localhost:8000/ui** (HTML thuần, nhận WebSocket, thẻ máy nháy khi có cập nhật, bấm vào máy để xem toàn bộ tag).

`ws://localhost:8000/ws/machines` (Postman: **New → WebSocket**). Lọc tuỳ chọn: `?machineId=L01_FILLER_01` (nhiều máy cách nhau dấu phẩy) hoặc `?lineId=LINE_03`.

Server gửi:

| `type` | Khi nào | Nội dung |
|---|---|---|
| `snapshot` | ngay khi kết nối / đổi bộ lọc | `machines`: toàn bộ máy theo bộ lọc, mỗi máy giống `GET /api/machines/{id}` |
| `patch` | có tag thay đổi (gom mỗi 250 ms) | `machines`: summary của máy + `tags` **chỉ gồm tag vừa đổi** |
| `heartbeat` | 15 s không có gì để gửi | `serverTime`, `ready` |

Client có thể gửi (tuỳ chọn):

```json
{"action": "subscribe", "machineIds": ["L01_FILLER_01"], "lineId": null}
{"action": "ping"}
```

Frontend: gán state = `snapshot`, mỗi `patch` thì ghi đè summary của máy và merge `tags` theo `tagName`.
Mất kết nối thì kết nối lại, server tự gửi snapshot mới.

Mã máy (`machineId`):

| Line | Máy |
|---|---|
| LINE_01 | `L01_PREFEED_01` `L01_BLOWER_01` `L01_AIRCONV_01` `L01_RINSER_01` `L01_FILLER_01` `L01_CAPPER_01` `L01_LABELER_01` `L01_CODER_01` `L01_CASEPACKER_01` |
| LINE_02 | `L02_PREFEED_01` `L02_BLOWER_01` `L02_AIRCONV_01` `L02_RINSER_01` `L02_FILLER_01` `L02_CAPPER_01` `L02_LABELER_01` `L02_CODER_01` `L02_CASEPACKER_01` |
| LINE_03 | `L03_CANDEPAL_01` `L03_CANRINSER_01` `L03_CANFILLER_01` `L03_SEAMER_01` `L03_CANCODER_01` `L03_CANINSPECT_01` `L03_CASEPACKER_01` |
| SHARED | `CIP_SKID_01` |

## Luồng batch (profile `batch`)

Bật cùng realtime bằng `--profile batch` (xem [Dựng hệ thống](#dựng-hệ-thống)). Không cần thao tác thêm:

1. `raw-ingest` đọc `industrial.telemetry` **từ đầu topic** (lần đầu đọc bù dữ liệu Kafka còn giữ, ~200k message/phút)
   và ghi Parquet vào `s3a://smart-factory/raw/telemetry/ingest_date=YYYY-MM-DD/ingest_hour=HH/`.
2. `batch-scheduler` chạy mỗi 5 phút: tính lại khoảng `[lần trước − 30′, now − 3′)` → PostgreSQL.
   Lần đầu tiên chỉ tính 60 phút gần nhất; sau 00:30 (giờ VN) tự tính lại trọn ngày hôm qua.

Kiểm tra đã chạy:

```bash
docker logs raw-ingest 2>&1 | grep '^{"batch"'          # {"batch": 3, "rows": 12650, "invalid": 0}
docker logs batch-scheduler 2>&1 | grep '^{"job"'       # {"job": "incremental", "range": [...], "kpiRows": 806, ...}
curl http://localhost:8000/api/analytics/freshness       # dataUntil = batch đã tính tới đâu
```

Tính lại / nạp lịch sử theo **ngày địa phương** (tuần tự, idempotent — chạy lại không nhân đôi số liệu).
Dữ liệu chỉ có cho những ngày `raw-ingest` đã ghi vào MinIO:

```bash
docker compose --profile batch run --rm --no-deps batch-scheduler \
    /opt/batch/submit.sh --mode backfill --from 2026-11-12 --to 2026-11-14
docker compose --profile batch run --rm --no-deps batch-scheduler \
    /opt/batch/submit.sh --mode daily --date 2026-11-13              # 1 ngày
```

Bảng PostgreSQL (`postgres/init/`):

| Nhóm | Bảng | Nội dung |
|---|---|---|
| Master data (`01`, `02`) | `machine`, `line`, `product`, `shift`, `work_order`, `production_plan`, `machine_id_mapping` | danh mục máy / line / SKU / ca / đơn hàng / kế hoạch — `master-api` đọc, batch dùng để enrich |
| Batch (`03`) | `machine_kpi_1m`, `machine_kpi_1h` | mỗi máy × phút (giờ): giây theo trạng thái, số lần dừng, tổng / đạt / lỗi, ideal time — **chỉ số cộng được** |
| | `machine_state_interval` | từng khoảng trạng thái liên tục (downtime, MTTR, timeline) |
| | `tag_metric_1m` | n / sum / min / max / last của tag số theo phút (trend) |
| | `data_quality_1m` | received / invalid / duplicate / missing / late / bad quality |
| | `batch_run`, view `batch_freshness` | nhật ký chạy batch, `data_until` |
| | `stg_*` | bảng tạm của job (luôn rỗng sau mỗi lần chạy) |

> DB đã tồn tại từ trước (volume cũ) sẽ **không** tự chạy lại `postgres/init`. Áp dụng schema batch thủ công:
> `docker exec -i postgres sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB' < postgres/init/03_batch_schema.sql`

### Analytics API

Cùng `state-api` (Swagger nhóm **analytics (batch)** tại http://localhost:8000/docs). UI gọi qua gateway:
`http://localhost:5080/state-api/api/analytics/...`

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/analytics/overview` | KPI tổng quan (mặc định ca hiện tại): OEE nhà máy + từng line, sản lượng, downtime, top 5 máy dừng, data quality |
| GET | `/api/analytics/oee` | OEE, A, P, Q + phân rã thời gian. `groupBy=machine\|line\|plant\|product\|shift`, `bucket=1m\|5m\|15m\|30m\|1h\|1d\|shift` (trend) |
| GET | `/api/analytics/production` | tổng / đạt / loại, reject rate, sản phẩm mỗi giờ chạy |
| GET | `/api/analytics/downtime` | thời gian dừng, số lần, MTTR theo máy / line, top N (`states=STOPPED,FAULTED,...`) |
| GET | `/api/analytics/downtime/events` | danh sách khoảng dừng (`order=start_desc\|duration_desc`, `minDurationSec`) |
| GET | `/api/analytics/tags` · `/tags/trend` | tag có dữ liệu của 1 máy · trend avg/min/max/last |
| GET | `/api/analytics/data-quality` | chất lượng dữ liệu pipeline + `dataQualityRate` |
| GET | `/api/analytics/freshness` | `dataUntil`, độ trễ batch, các lần chạy gần nhất |

Cửa sổ thời gian (mọi endpoint): `last=15m|3h|7d` (mặc định 1h) · `preset=today|yesterday|current_shift|previous_shift` ·
`from` / `to` ISO 8601 **có múi giờ**. Tối đa 31 ngày. Lọc: `machineId`, `lineId` (nhiều giá trị cách nhau dấu phẩy).

```bash
curl "http://localhost:8000/api/analytics/overview"
curl "http://localhost:8000/api/analytics/oee?groupBy=line&preset=current_shift"
curl "http://localhost:8000/api/analytics/oee?groupBy=plant&bucket=15m&last=3h"
curl "http://localhost:8000/api/analytics/downtime?last=8h&top=5"
curl "http://localhost:8000/api/analytics/tags/trend?machineId=L01_FILLER_01&tagName=CurrentSpeed&bucket=5m&last=1h"
curl "http://localhost:8000/api/analytics/oee?machineId=L02_FILLER_01&from=2026-11-14T06:00:00%2B07:00&to=2026-11-14T14:00:00%2B07:00"
```

Công thức: `A = run / planned`, `P = ideal_time / run`, `Q = good / total`, `OEE = A × P × Q` — API **cộng các thành phần
trong cửa sổ rồi mới chia**. `planned` = thời gian trừ OFF / MAINTENANCE / NO_DATA và giờ nghỉ của ca.
OEE line / plant chỉ tính trên máy chiết (`*FILLER*`); thêm `referenceOnly=false` để cộng mọi máy.
Mỗi response có `window.dataUntil` / `window.partial` (cửa sổ vượt quá phần batch đã tính).

## Kiểm thử

So sánh API với phép tính độc lập từ topic nguồn (dừng middleware để dữ liệu đứng yên khi so):

```bash
docker compose stop middleware-sim && sleep 10
docker compose exec -T state-api python - < scripts/verify_machine_state.py     # in PASS / FAIL
docker compose start middleware-sim
```

Test WebSocket (nghe 30s, in độ trễ; nếu dừng middleware trong lúc chạy thì so trạng thái ghép từ patch với REST):

```bash
docker compose exec -T state-api python - --duration 30 < scripts/ws_client.py
docker compose exec -T state-api python - --machine L01_FILLER_01 --duration 20 --verbose < scripts/ws_client.py
```

## Vận hành

```bash
docker compose logs -f stream-machine-state                # mỗi 30s in throughput, thời gian batch
docker compose logs -f batch-scheduler                      # mỗi 5 phút 1 dòng JSON kết quả batch
P="--profile telemetry --profile batch"
docker compose $P stop                                     # dừng (giữ dữ liệu)
docker compose $P down                                     # xoá container (giữ volume)
docker compose $P down -v                                  # xoá sạch cả dữ liệu (Kafka, MinIO, PostgreSQL, checkpoint)
./scripts/reset_machine_state.sh                           # chỉ reset 2 topic + checkpoint của luồng realtime
```

- Docker Desktop khởi động lại: các service đều có `restart: unless-stopped`, tự chạy lại. Nếu job Spark
  (`stream-machine-state`, `raw-ingest`) báo mất executor sau khi `spark-master` khởi động lại: `docker restart stream-machine-state raw-ingest`.
- Batch lỗi 1 lần không sao: lần chạy sau (5 phút) tính lại khoảng từ lần thành công cuối. Lỗi được ghi ở
  `batch_run.error` / `GET /api/analytics/freshness`.
- Dung lượng Data Lake ≈ 160 B/message (~3 GB/ngày ở ~210 msg/s). Xem trong MinIO console http://localhost:9001.

- Spark chết / restart: đọc tiếp từ checkpoint, không mất event; API vẫn trả trạng thái cuối trong lúc đó.
- API restart: tự đọc lại topic compacted, vài giây là đủ trạng thái 26 máy.
- Log chi tiết từng message của middleware: `MIDDLEWARE_LOG_LEVEL=INFO docker compose --profile telemetry up -d middleware-sim`
  (mặc định `WARNING` vì log từng message rất tốn CPU).
- Máy yếu / đang chạy nặng: batch Spark chậm lại và `ageSeconds` tăng; tắt bớt ứng dụng hoặc tăng CPU/RAM cho Docker.

## Phiên bản

Hệ thống **0.4.0** (file `VERSION`) — 14/11/2026.

| Thành phần | Phiên bản |
|---|---|
| Apache Kafka (KRaft) | 3.9.0 (`apache/kafka:3.9.0`), Kafka UI `kafbat/kafka-ui:v1.5.0` |
| Apache Spark | 3.5.5 (Scala 2.12, Java 17, Python 3.10) + hadoop-aws 3.3.4, spark-sql-kafka 3.5.5, PostgreSQL JDBC 42.7.4 |
| MinIO | `alpine/minio:RELEASE.2025-10-15T17-29-55Z` |
| PostgreSQL | 16 |
| state-api | 1.1.0 — Python 3.12, FastAPI 0.115.12, confluent-kafka 2.10.0, psycopg 3.2.3 |
| master-api | 1.0 — Python 3.12, FastAPI 0.115.12, psycopg2 2.9.13 |
| middleware | IndustrialTelemetry.Middleware (Python 3.12), schemaVersion message 1.0 |
| dashboard | frontend 1.0.0 (React, Node 24 build) + backend .NET 10 |
| gateway | nginx 1.27-alpine |

| Version | Nội dung |
|---|---|
| 0.4.0 | Luồng batch: `raw-ingest` (Kafka → MinIO Parquet), `batch-scheduler` (MinIO → PostgreSQL, fact 1 phút cộng được, incremental 5′ + daily + backfill), Analytics API `/api/analytics/*` trong `state-api`; PostgreSQL bỏ 9 bảng cũ không dùng; `gateway` nginx; `master-api` chạy trong compose |
| 0.3.0 | UI MES 4 màn là app chính, master data phase 1 (`line`, `work_order`, `production_plan`), `master-api` |
| 0.2.0 | Luồng realtime: middleware giả lập → Spark → `machine-state` (compacted) → `state-api` REST + WebSocket |
| 0.1.0 | Hạ tầng docker compose: Kafka, MinIO, PostgreSQL, Spark standalone |
