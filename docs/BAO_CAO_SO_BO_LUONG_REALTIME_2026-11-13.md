# BÁO CÁO SƠ BỘ — Luồng dữ liệu Realtime Smart Factory (OPC UA → Kafka → Spark → WebSocket → UI)

> **Ngày:** 13/11/2026 · **Nhóm:** 18 · **Trạng thái:** đã kiểm chứng end-to-end trên môi trường DEV
> **Phạm vi báo cáo:** luồng realtime (speed layer) — đọc trạng thái máy từ Kepware và đẩy lên dashboard.
> **Không bao gồm:** batch layer (ghi lịch sử/OEE vào PostgreSQL) — mới có schema + seed, chưa bật job.

---

## 1. Tóm tắt nhanh

| Hạng mục | Kết quả |
|---|---|
| Số máy trong hệ thống | **26 máy** (LINE_01: 9 · LINE_02: 9 · LINE_03: 7 · SHARED: 1 CIP Skid) |
| Số tag OPC UA | **404 tag** (đọc từ 26 file CSV metadata, mỗi máy 13–18 tag) |
| Tỷ lệ subscribe thành công | **404/404 = 100%** |
| Kafka broker | `192.168.179.176:29092` (cluster 3 broker, KRaft) |
| Topic | `industrial.telemetry` (8 partition, raw) → `machine-state` (3 partition, compacted) |
| Message đã đẩy qua Kafka | **9.548 message** (tích luỹ từ lúc bật pipeline) |
| WebSocket client đang kết nối | **2 client**, **138 patch** đã gửi |
| Lỗi phát sinh | `failed=0`, `kafka(err)=0`, `ignoredOlder=0` |
| PostgreSQL master data | **26 máy / 3 SKU / 3 line / 3 ca / 9 WO / 9 kế hoạch** — đã seed và đọc OK |
| Giao diện | `http://127.0.0.1:5173/?source=live` — trả HTTP 200 |

---

## 2. Kiến trúc luồng dữ liệu

```
┌──────────────────┐
│  Kepware OPC UA  │   opc.tcp://127.0.0.1:49320   (chạy trên máy Windows dev)
│  26 máy / 404 tag│
└────────┬─────────┘
         │ OPC UA subscription (publishing interval 100ms)
         ▼
┌──────────────────────────────────────────────┐
│  IndustrialTelemetry.Middleware  (Python)    │
│  · đọc metadata CSV (TAG_FOLDER)             │
│  · change-detection dedup (chỉ phát khi đổi) │
│  · quality Good/Uncertain/Bad                │
│  · đóng envelope data contract v1.0          │
└────────┬─────────────────────────────────────┘
         │ Kafka producer (acks=all, gzip, max_in_flight=1)
         ▼
┌──────────────────────────────────────────────┐
│  Kafka  192.168.179.176:29092                │
│  topic industrial.telemetry (8 partition)    │
└────────┬─────────────────────────────────────┘
         │ Spark Structured Streaming (trigger 1s)
         │ groupBy(machineId, tagName) + max_by(eventTime)
         ▼
┌──────────────────────────────────────────────┐
│  Kafka topic machine-state (3 partition,     │
│  cleanup.policy=compact, key=machineId|tag)  │
└────────┬─────────────────────────────────────┘
         │ consumer (assign + OFFSET_BEGINNING, giữ state trong RAM)
         ▼
┌──────────────────────────────────────────────┐
│  state-api (FastAPI) :8000                   │
│  GET /health /api/machines /api/lines        │
│  WS  /ws/machines  (snapshot + patch 250ms)  │
└────────┬─────────────────────────────────────┘
         │ WebSocket
         ▼
┌──────────────────────────────────────────────┐
│  master-api (FastAPI) :8001                  │
│  đọc master data từ PostgreSQL               │
│  (SKU, WO, kế hoạch sản lượng theo ca)      │
└────────┬─────────────────────────────────────┘
         ▼
┌──────────────────────────────────────────────┐
│  React Frontend (Vite) :5173                  │
│  http://127.0.0.1:5173/?source=live          │
└──────────────────────────────────────────────┘
```

### 2.1. Ranh giới trách nhiệm từng thành phần

| Thành phần | Công nghệ | Vai trò | File chính |
|---|---|---|---|
| Middleware | Python + `python-opcua` + `confluent-kafka` | Đọc OPC UA → chuẩn hoá → Kafka | `IndustrialTelemetry.Middleware/main.py`, `services/opcua_client.py`, `core/subscription.py` |
| Stream engine | PySpark 3.5.5 (local mode) | Compact raw → trạng thái mới nhất | `spark/apps/machine_state_stream.py` |
| Realtime API | FastAPI + `confluent-kafka` | Giữ state trong RAM, đẩy WebSocket | `services/state-api/app.py` |
| Master API | FastAPI + `psycopg` | Master data từ PostgreSQL | `services/master-api/app.py` |
| Frontend | React + Vite + TypeScript | 4 màn hình MES | `dashboard/frontend/src/mock/` |
| Hạ tầng | Docker Compose trên Linux | Kafka + PostgreSQL + MinIO | `docker/docker-compose.server.yml` |

---

## 3. Số liệu máy đã kiểm chứng

### 3.1. Theo dây chuyền

| Line | Số máy | Trạng thái quan sát được |
|---|---|---|
| LINE_01 (chai nhựa) | 9 | RUNNING 5 · STOPPED 3 · FAULTED 1 |
| LINE_02 (chai nhựa) | 9 | RUNNING 4 · STOPPED 3 · FAULTED 2 |
| LINE_03 (hộp) | 7 | RUNNING 3 · STOPPED 2 · FAULTED 1 · MAINTENANCE 1 |
| SHARED | 1 | STOPPED 1 (CIP Skid) |
| **Tổng** | **26** | |

Danh sách đầy đủ 26 máy (lấy từ `equipment_map.json` + CSV metadata):

| # | machineId | machineType | Line | Số tag |
|---|---|---|---|---|
| 1 | `L01_PREFEED_01` | PREFORM_FEEDER | LINE_01 | 14 |
| 2 | `L01_BLOWER_01` | STRETCH_BLOW_MOULDER | LINE_01 | 18 |
| 3 | `L01_AIRCONV_01` | AIR_CONVEYOR | LINE_01 | 13 |
| 4 | `L01_RINSER_01` | BOTTLE_RINSER | LINE_01 | 16 |
| 5 | `L01_FILLER_01` | CARBONATED_FILLER | LINE_01 | 18 |
| 6 | `L01_CAPPER_01` | SCREW_CAPPER | LINE_01 | 15 |
| 7 | `L01_LABELER_01` | BOTTLE_LABELER | LINE_01 | 15 |
| 8 | `L01_CODER_01` | DATE_CODER | LINE_01 | 13 |
| 9 | `L01_CASEPACKER_01` | CASE_PACKER | LINE_01 | 18 |
| 10 | `L02_PREFEED_01` | PREFORM_FEEDER | LINE_02 | 14 |
| 11 | `L02_BLOWER_01` | STRETCH_BLOW_MOULDER | LINE_02 | 18 |
| 12 | `L02_AIRCONV_01` | AIR_CONVEYOR | LINE_02 | 13 |
| 13 | `L02_RINSER_01` | BOTTLE_RINSER | LINE_02 | 16 |
| 14 | `L02_FILLER_01` | STILL_FILLER | LINE_02 | 18 |
| 15 | `L02_CAPPER_01` | SCREW_CAPPER | LINE_02 | 15 |
| 16 | `L02_LABELER_01` | BOTTLE_LABELER | LINE_02 | 15 |
| 17 | `L02_CODER_01` | DATE_CODER | LINE_02 | 13 |
| 18 | `L02_CASEPACKER_01` | CASE_PACKER | LINE_02 | 18 |
| 19 | `L03_CANDEPAL_01` | CAN_DEPALLETTIZER | LINE_03 | 15 |
| 20 | `L03_CANRINSER_01` | CAN_RINSER | LINE_03 | 16 |
| 21 | `L03_CANFILLER_01` | CAN_FILLER | LINE_03 | 18 |
| 22 | `L03_SEAMER_01` | CAN_SEAMER | LINE_03 | 16 |
| 23 | `L03_CANCODER_01` | DATE_CODER | LINE_03 | 13 |
| 24 | `L03_CANINSPECT_01` | CAN_INSPECTION | LINE_03 | 14 |
| 25 | `L03_CASEPACKER_01` | CASE_PACKER | LINE_03 | 18 |
| 26 | `CIP_SKID_01` | CIP_SKID | SHARED | 14 |

### 3.2. Nhóm tag theo loại (thiết bị chung)

| Nhóm tag | Ý nghĩa | Ví dụ |
|---|---|---|
| `MachineState` / `MachineMode` | Trạng thái (0–5: OFF/STARTING/RUNNING/STOPPED/FAULTED/MAINTENANCE) & chế độ (OFF/MANUAL/AUTO/MAINTENANCE) | có ở cả 26 máy |
| `AlarmCode` / `EmergencyStop` | Mã alarm, cỡu khẩn | `L01_RINSER_01` alarm 627, `L02_PREFEED_01` alarm 577 |
| `CurrentSpeed` / `DesignSpeed` | Tốc độ thực tế / thiết kế (bottles·min⁻¹, cans·min⁻¹, caps·min⁻¹…) | dao động 86–147 |
| `TotalCounter` / `GoodCounter` / `DefectCounter` | Bộ đếm sản lượng tích luỹ | 18–61 pcs ở lần chạy đầu |
| `Starved` / `Blocked` | Thiếu nguyên liệu / nghẽn đầu ra | |
| Nghiệp vụ riêng | FillLevel, WaterTemp, CO2Pressure, SeamTorque, InkLevel, LabelRollRemaining, TankLevel, pH, Conductivity… | theo từng loại máy |

---

## 4. Những gì đã kiểm chứng (bằng số liệu thực tế)

### 4.1. Middleware đọc Kepware thật

```
[SUBSCRIBE] tags=404 attempted=404 ok=404 fail=0 invalid(cumulative)=0
[OPC] Subscription established: 404 tag(s), ratio=100%
State SUBSCRIBING -> DEGRADED (subscribed 404/404 (ratio 100% of valid tags))
State DEGRADED -> STABLE (ratio 100%, 10s without errors)
```

→ **404/404 tag subscribe thành công, 0 lỗi, 0 tag invalid.** Quality của toàn bộ node chuyển sang `Good`.

### 4.2. Vòng lặp middleware ổn định

```
[STATS] state=STABLE active=True queue=0/200000
         published=159 skipped(dedup=0 baseline=0 state=245) failed=0
         kafka(sent=159 err=0)
```

| Chỉ số | Giá trị | Ý nghĩa |
|---|---|---|
| `state` | `STABLE` | Kết nối OPC UA ổn định |
| `queue` | `0/200000` | Hàng đợi không bị nghẽn |
| `published` | 159 → 404 (khi bật snapshot đầu) | Số message đã đẩy lên Kafka |
| `skipped(state)` | 245 | Giá trị bị chặn lúc đầu khi chưa lên STABLE — **đúng thiết kế**, không phải lỗi |
| `failed` / `kafka(err)` | 0 / 0 | Không mất message nào |

### 4.3. Spark đọc Kafka và compact đúng

```json
{"batch": 18, "inputRows": 234, "inputRowsPerSec": 178.6, "processedRowsPerSec": 200.9, "stateRows": 404, "updatedRows": 133}
{"batch": 42, "inputRows": 302, "inputRowsPerSec": 210.9, "processedRowsPerSec": 229.8, "stateRows": 404, "updatedRows": 157}
```

| Chỉ số | Giá trị |
|---|---|
| Throughput đo được | **178 – 230 event/s** (mục tiêu thiết kế: 500–1.000) |
| Số key trong state store | **404** (26 máy × tag, đúng bằng tổng tag) |
| Trigger | 1 giây, `outputMode=update` |
| Checkpoint | `.spark-checkpoints/machine-state` — restart không mất event |

> ⚠ Throughput hiện ở mức **hàng trăm event/s** vì middleware đang chạy **change-detection dedup** (chỉ phát khi giá trị đổi) với 404 tag trên 26 máy. Khi bật chế độ phát liên tục (simulation) hoặc tăng số tag, throughput sẽ lên.

### 4.4. state-api phục vụ REST + WebSocket

```json
{"status":"ok","topic":"machine-state","ready":true,
 "machines":26,"tags":404,"messagesConsumed":9548,"ignoredOlder":0,
 "wsClients":2,"wsPatchesSent":138,
 "offsets":{"0":3384,"1":3485,"2":2676}}
```

| Chỉ số | Giá trị | Ý nghĩa |
|---|---|---|
| `ready` | `true` | Đã nạp xong snapshot từ đầu topic |
| `machines` / `tags` | **26 / 404** | Khớp 100% với CSV + equipment_map |
| `messagesConsumed` | **9.548** | Tổng message đã xử lý |
| `ignoredOlder` | **0** | Không có event đến muộn bị loại — không mất dữ liệu |
| `wsClients` / `wsPatchesSent` | 2 / 138 | WebSocket hoạt động, patch truyền tới client |
| `offsets` | 3 partition đều có dữ liệu | Phân phối đều, không nghẽn partition |

### 4.5. Master data từ PostgreSQL

```
[OK ] machine          26 dòng
[OK ] product           3 dòng
[OK ] line              3 dòng
[OK ] shift             3 dòng
[OK ] work_order        9 dòng
[OK ] production_plan   9 dòng
```

- `master-api /health` → `{"status":"ok","source":"postgres","postgresConfigured":true,"machines":26,"lines":3,"products":3,"workOrders":9}`
- **Nguồn = `postgres`** (không phải fallback JSON) → frontend đang đọc master data thật.
- 3 SKU: `CAN-330-SUGAR` (ICT 0.5877) · `PET-500-COKE` (0.4234) · `PET-500-WATER` (0.5047)
- 9 kế hoạch sản lượng (3 line × 3 ca): LINE_01 = 57.400 pcs/ca · LINE_02 = 52.600 pcs/ca · LINE_03 = 44.000 pcs/ca

### 4.6. Frontend

- `http://127.0.0.1:5173/` → **HTTP 200**
- Chế độ LIVE: `http://127.0.0.1:5173/?source=live` (WebSocket thật)
- Chế độ MOCK: `http://127.0.0.1:5173/` (dữ liệu giả, badge "MOCK")
- Nút `MOCK ⇄ LIVE` trên topbar để chuyển nhanh.

---

## 5. Data contract (đã chốt, đang áp dụng)

Mỗi **1 message = 1 tag đổi giá trị**. Key Kafka = `machineId`.

```json
{
  "eventId": "uuid",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-13T13:29:13.215Z",
  "source":  { "system": "kepware", "channel": "LINE_01", "device": "L01_FILLER_01",
               "nodeId": "ns=2;s=LINE_01.L01_FILLER_01.CurrentSpeed",
               "serverTimestamp": "..." },
  "plant":   { "plantId": "PLANT_01", "lineId": "LINE_01", "processId": "FILLING" },
  "machine": { "machineId": "L01_FILLER_01", "machineType": "CARBONATED_FILLER",
               "equipmentCode": "FILL-L01-01" },
  "tag":     { "tagName": "CurrentSpeed", "tagCode": "FILL.L01.CURRENTSPEED",
               "tagType": "ANALOG" },
  "measurement": { "value": "141.0", "valueType": "Float", "unit": "bottles/min" },
  "quality": { "statusCode": "Good", "isGood": true }
}
```

**Nguyên tắc đã áp dụng:**
- Timestamp → UTC ISO-8601; `eventTime` = timestamp nguồn từ Kepware, `ingestedAt` = lúc middleware đẩy.
- Giá trị hỏng → `value = null`, `isGood = false` — **không bịa giá trị thay thế**.
- `eventId` sinh từ nội dung sự kiện → downstream dedup được.
- `MachineState` được map sang tên: `0=OFF, 1=STARTING, 2=RUNNING, 3=STOPPED, 4=FAULTED, 5=MAINTENANCE`.

---

## 6. Cơ chế đáng chú ý (thiết kế mới trong đợt này)

### 6.1. Change-detection dedup + periodic refresh

Middleware **chỉ phát message khi giá trị thực sự thay đổi** (`USE_TIMESTAMP_IN_RECONNECT_DEDUP=false`). Đây là baseline của design doc vì `eventId` sinh từ nội dung sự kiện — gửi lặp giá trị không đổi sẽ sinh `eventId` khác nhau và làm dedup downstream vô nghĩa.

**Hệ quả:** tag tĩnh (máy dừng, counter đứng yên) không có `datachange` → `eventTime` của bản ghi cũ dần hết hạn → dashboard hiện `NO_DATA` dù kết nối hoàn hảo.

**Giải pháp vừa triển khai:** cơ chế `REFRESH_INTERVAL_S` (mặc định 20s) đọc lại giá trị hiện tại của tag theo chu kỳ — mô phỏng polling của một OPC UA client thông thường. Vì Kepware cập nhật `SourceTimestamp` ở **mỗi lần scan**, `eventTime` vẫn "sống" dù giá trị không đổi.

- Đọc **xoay vòng**, mỗi lượt tối đa `REFRESH_BATCH_SIZE=40` tag → không tắc cổng chặn STABLE.
- Giá trị quality `Bad`/`Uncertain` bị bỏ qua (giống `SubHandler`) → không phát ra số `0` gây hiểu sai.

### 6.2. `PUBLISH_INITIAL_SNAPSHOT`

Mặc định `false`: lần khởi động đầu tiên, middleware chụp baseline và **không** phát → dashboard trống cho tới khi giá trị đổi lần đầu.

Đặt `true` → ở **chu kỳ khởi động đầu tiên** mở cổng chặn STABLE trước khi subscribe và bỏ qua cơ chế chặn baseline replay → toàn bộ 404 tag được phát ngay, dashboard có trạng thái hiện tại của tất cả máy. Sau reconnect, cơ chế chặn baseline vẫn hoạt động bình thường (tránh phát lại lô giá trị cũ).

### 6.3. Cổng chặn STABLE & reconnect

- Tỷ lệ subscribe tính trên `tags - invalid` (loại `BadNodeIdUnknown` khỏi mẫu số) → nếu không, tỷ lệ luôn thấp và cổng chặn không bao giờ mở.
- `DEGRADED → STABLE` khi: subscribe ratio ≥ 90% **và** 10s không lỗi transport.
- Reconnect hard reset: `subscription.delete()` → `disconnect()` → xoá cache node + dedup → tạo Client mới → subscribe lại → chụp baseline lại. Backoff 1s → 2s → 5s → 10s → 20s → 30s (kèm jitter).

---

## 7. Cách chạy lại (tái lập được)

### 7.1. Hạ tầng (máy Linux server)

```bash
# Kafka (đã có) — broker ngoài mạng LAN: 29092
# PostgreSQL + MinIO
cd /home/dev/smart-factory
docker compose -f docker-compose.server.yml up -d
docker compose -f docker-compose.server.yml ps
```

### 7.2. Pipeline (máy Windows dev)

```powershell
cd E:\Work\SFSVcongty\Laird\Code\Data-Integrate

# ① GIẢ LẬP — không cần Kepware, dữ liệu liên tục
.\scripts\run-sim.ps1

# ② THẬT — đọc Kepware qua OPC UA
.\scripts\run-real.ps1
```

> ⚠ **Spark KHÔNG chạy trên máy Windows** — Spark đã chạy trong Docker trên server
> `192.168.179.176` (`spark-raw-ingest` / `spark-machine-state` / `spark-batch-kpi`).
> Chạy thêm Spark local sẽ khiến **2 job ghi cùng topic `machine-state`** → giá trị
> trên UI nhấp nháy. Script `run-sim.ps1` / `run-real.ps1` vì vậy chỉ khởi động:
> state-api (:8000) → master-api (:8001) → middleware → frontend Vite (:5173).
> Log nằm ở `Data-Integrate\logs\{state-api,master-api,middleware}.{out,err}`.

`run-all.ps1` (script tổng quát, có tuỳ chọn Spark local):

```powershell
.\scripts\run-all.ps1 -Mode Simulation            # giả lập (mặc định)
.\scripts\run-all.ps1 -Mode Real                  # Kepware thật
.\scripts\run-all.ps1 -Mode Simulation -SkipSpark:$false   # chạy thêm Spark local
```

Chạy riêng từng thành phần:

```powershell
.\scripts\run-middleware.ps1 -Mode Simulation   # middleware giả lập
.\scripts\run-middleware.ps1 -Mode Real         # middleware đọc Kepware thật
.\scripts\run-state-api.ps1                    # state-api :8000
.\scripts\run-master-api.ps1                   # master-api :8001
.\scripts\run-spark.ps1                        # Spark Structured Streaming (LOCAL - tránh!)
.\scripts\run-raw-ingest.ps1                   # Spark raw-ingest (LOCAL - tránh!)
.\scripts\run-batch-kpi.ps1                    # Spark batch KPI (LOCAL - tránh!)
```

### 7.3. Kiểm tra

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health | Select -Expand Content
Invoke-WebRequest http://127.0.0.1:8001/health | Select -Expand Content
Invoke-WebRequest http://127.0.0.1:5173/ -UseBasicParsing | Select -Expand StatusCode
.\.venv\Scripts\python.exe scripts\check_master_db.py
```

### 7.4. Ghi giá trị test vào Kepware

```powershell
# Liệt kê tag ghi được (machineId + nodeId + kiểu)
.\.venv\Scripts\python.exe scripts\kepware_write.py --list

# Ghi 1 giá trị → middleware phát message → UI cập nhật sau ~1–2s
.\.venv\Scripts\python.exe scripts\kepware_write.py --machine L01_FILLER_01 --tag CurrentSpeed --value 141.0
.\.venv\Scripts\python.exe scripts\kepware_write.py --machine L01_FILLER_01 --tag MachineState  --value 2
```

> Script tự thử lần lượt các `VariantType` (Float → Double → Int64 → Int32) vì Kepware reject sai kiểu bằng `BadTypeMismatch`.

### 7.5. Reset luồng trạng thái (khi cần chạy lại từ đầu)

```powershell
.\.venv\Scripts\python.exe scripts\reset_machine_state.py
# xoá topic machine-state + checkpoint Spark, giữ nguyên industrial.telemetry
```

---

## 8. Hạ tầng & cấu hình tham chiếu

| Thành phần | Địa chỉ | Ghi chú |
|---|---|---|
| Kafka broker (LAN) | `192.168.179.176:29092` | advertised listener cho client ngoài Docker |
| Kafka UI | `192.168.179.176:8085` | web UI, **không phải** port broker |
| PostgreSQL | `192.168.179.176:5432` | db `smart_factory`, user `sf_user` |
| MinIO S3 | `http://192.168.179.176:9000` | bucket `smart-factory` |
| MinIO Console | `http://192.168.179.176:9001` | |
| Kepware OPC UA | `opc.tcp://127.0.0.1:49320` | chạy trên máy Windows dev |
| state-api | `http://127.0.0.1:8000` | REST + WebSocket |
| master-api | `http://127.0.0.1:8001` | |
| Frontend | `http://127.0.0.1:5173` | |

### 8.1. Chủ đề Kafka

| Topic | Partition | Policy | Nội dung |
|---|---|---|---|
| `industrial.telemetry` | 8 | delete | raw envelope, 1 message = 1 tag đổi giá trị |
| `machine-state` | 3 | **compact** | trạng thái mới nhất, key = `machineId\|tagName` |

---

## 9. Việc còn lại (kế hoạch giai đoạn tiếp theo)

| # | Hạng mục | Mức độ | Ghi chú |
|---|---|---|---|
| 1 | Bật **batch layer**: `machine-state` → PostgreSQL, tính OEE/downtime/quality theo ca | Cao | Schema 16 bảng đã có + seed master data; cần job ghi lịch sử |
| 2 | **Lịch sử theo ca** trên UI (trend, alarm history) | Cao | Hiện UI chỉ giữ lịch sử trong phiên kết nối |
| 3 | Gắn `idealCycleTime` từ PG vào công thức OEE của UI | Trung bình | Đang suy ra `60 / DesignSpeed` |
| 4 | Đồng bộ ca (shift rollover) — reset baseline + run time tại mốc ca | Trung bình | |
| 5 | Bảng **alarm** để xem lại sự kiện đã qua + nút Acknowledge | Trung bình | Hiện chỉ suy ra alarm từ luồng `AlarmCode` |
| 6 | Nâng throughput lên mục tiêu 500–1.000 event/s | Trung bình | Cần đo lại với workload nặng hơn (nhiều tag + phát liên tục) |
| 7 | Tag đầu vào/đầu ra cho flow state (Block/Starve) | Thấp | Cần bổ sung ở tầng metadata |
| 8 | Xác thực / phân quyền cho dashboard | Thấp | Chưa có backend auth |

---

## 10. Rủi ro & điểm cần lưu ý

| Rủi ro | Mức độ | Xử lý hiện tại |
|---|---|---|
| Mật khẩu PostgreSQL/MinIO đang là mặc định trong repo | ⚠ Cao | Chỉ dùng cho DEV — **bắt buộc đổi trước production** |
| Firewall máy server | ⚠ Cao | `ufw` trên máy 192.168.179.176 đang **chưa bật** (`Firewall not enabled`) — hiện mọi port đều lộ, kể cả khi thêm rule |
| MinIO chưa dùng được (port 9000 vẫn lỗi từ máy Windows) | Trung bình | Đã tạm gác; pipeline realtime không cần MinIO |
| Chưa có lịch sử lưu trữ (chỉ state trong RAM của state-api) | Trung bình | Mất state khi restart state-api cho tới khi đọc lại topic — topic compacted nên vẫn giữ trạng thái cuối |
| Tag tĩnh không có message mới nếu bỏ periodic refresh | Thấp | Đã có `REFRESH_INTERVAL_S=20s` |
| Không có auth cho state-api / master-api | Thấp | Chỉ bind `0.0.0.0` trong môi trường DEV nội bộ |

---

## 11. Tài liệu & mã nguồn tham chiếu

| File | Nội dung |
|---|---|
| `docs/architecture.txt` | Tài liệu kiến trúc gốc (data source, schema, component, công thức OEE) |
| `docs/INTEGRATION_LIVE_WS_2026-11-13.md` | Quyết định thiết kế tích hợp LIVE WebSocket ↔ React |
| `docs/deploy-remote-infra.md` | Hướng dẫn cài PostgreSQL + MinIO trên máy Linux server |
| `IndustrialTelemetry.Middleware/docs/*_design.md` | Design doc middleware + data contract Kafka |
| `IndustrialTelemetry.Middleware/metadata/TAG_FOLDER/**.csv` | 26 file CSV = metadata 404 tag |
| `IndustrialTelemetry.Middleware/metadata/equipment_map.json` | Ánh xạ 26 máy → machineType / equipmentCode / line |
| `spark/apps/machine_state_stream.py` | Job compact `industrial.telemetry` → `machine-state` |
| `services/state-api/app.py` | REST + WebSocket state API |
| `services/master-api/app.py` | Master data API (PostgreSQL) |
| `postgres/init/*.sql` | Schema 16 bảng + seed master data |

### 11.1. Commit đã push lên nhánh `development`

| Commit | Nội dung |
|---|---|
| `e71608c` | Thêm compose server (PostgreSQL + MinIO) + hướng dẫn cài đặt trên máy Linux 192.168.179.176 |
| *(commit mới)* | Middleware: periodic refresh + `PUBLISH_INITIAL_SNAPSHOT`; script `kepware_write.py`, `reset_machine_state.py`; tài liệu báo cáo |

---

**Người lập báo cáo:** Nhóm 18 · **Ngày:** 13/11/2026
**Trạng thái:** luồng realtime đã kiểm chứng end-to-end (Kepware → Kafka → Spark → state-api → WebSocket → UI) với 26 máy / 404 tag, 0 lỗi phát sinh.
