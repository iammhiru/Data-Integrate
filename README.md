# Smart Manufacturing - Realtime Machine State (Nhóm 18)

Middleware (giả lập Kepware) → **Kafka** → **Spark Structured Streaming** → **Kafka compacted topic** → **REST API**

```
middleware-sim ──▶ industrial.telemetry ──▶ stream-machine-state ──▶ machine-state ──▶ state-api :8000
(26 máy, 404 tag)   (1 msg = 1 tag đổi)       (Spark, trigger 1s)      (compacted)      (FastAPI)
```

## Yêu cầu

- Docker Desktop (Compose v2), cấp cho Docker **≥ 4 CPU, ≥ 6 GB RAM**.
- Các cổng trống: 8000, 8080, 8081, 8082, 9000, 9001, 9094, 5432, 4043.

## Dựng hệ thống

```bash
cp .env.example .env                                   # lần đầu
docker compose --profile telemetry up -d --build       # build + chạy toàn bộ
docker compose --profile telemetry ps                  # kiểm tra trạng thái
```

Lần đầu build mất vài phút. `kafka-init` / `minio-init` chạy một lần rồi thoát (`Exited (0)` là bình thường).
Đợi API nạp xong dữ liệu (`"ready": true`):

```bash
curl http://localhost:8000/health
```

| Service | Vai trò | Truy cập từ máy host |
|---|---|---|
| `middleware-sim` | IndustrialTelemetry.Middleware chạy `SIMULATION_MODE=true`, phát dữ liệu 26 máy vào `industrial.telemetry` | |
| `stream-machine-state` | Spark job `spark/apps/machine_state_stream.py`: giữ giá trị mới nhất mỗi (máy, tag) → `machine-state` | Spark UI http://localhost:4043 |
| `state-api` | API đọc topic `machine-state` | http://localhost:8000 (Swagger: `/docs`) |
| `kafka` / `kafka-ui` | Broker + giao diện xem topic | `localhost:9094` / http://localhost:8082 |
| `spark-master` / `spark-worker` | Cụm Spark | http://localhost:8080 / http://localhost:8081 |
| `minio`, `postgres`, `dashboard` | Lưu trữ / dashboard của nhóm (xem `dashboard/README.md`) | 9001 / 5432 / 5080 |

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
docker compose --profile telemetry stop                    # dừng (giữ dữ liệu)
docker compose --profile telemetry down                    # xoá container (giữ volume)
docker compose --profile telemetry down -v                 # xoá sạch cả dữ liệu
./scripts/reset_machine_state.sh                           # chỉ reset 2 topic + checkpoint của luồng này
```

- Spark chết / restart: đọc tiếp từ checkpoint, không mất event; API vẫn trả trạng thái cuối trong lúc đó.
- API restart: tự đọc lại topic compacted, vài giây là đủ trạng thái 26 máy.
- Log chi tiết từng message của middleware: `MIDDLEWARE_LOG_LEVEL=INFO docker compose --profile telemetry up -d middleware-sim`
  (mặc định `WARNING` vì log từng message rất tốn CPU).
- Máy yếu / đang chạy nặng: batch Spark chậm lại và `ageSeconds` tăng; tắt bớt ứng dụng hoặc tăng CPU/RAM cho Docker.
