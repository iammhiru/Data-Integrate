# IndustrialTelemetry.Middleware

Middleware đọc dữ liệu từ **Kepware (OPC UA)** và gửi dữ liệu **đã chuẩn hóa** vào
**Kafka** theo một data contract duy nhất, để các tầng sau (Flink, lưu trữ, dashboard)
xử lý được một cách đồng nhất.

> Kế thừa tinh túy từ 2 middleware hiện có:
> **Laird** (chuẩn hóa + partition key + reconnect/state machine + thread isolation)
> × **Vinamilk** (đọc metadata từ file CSV + `equipment_map.json`).

---

## 1. Kiến trúc

```
┌────────────────────────────────────────────────────────────────┐
│                    KEPWARE (OPC UA Server)                       │
│  Channel LINE_01 / LINE_02 / LINE_03 / SHARED                   │
│  Device = Machine                                                │
└────────────────────────────┬───────────────────────────────────┘
                             │ OPC UA Subscription
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                      MIDDLEWARE (tiến trình Python)               │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
│  │ Metadata     │  │ OPC UA        │  │ Value Worker (thread)│ │
│  │ Loader       │  │ Client        │  │                      │ │
│  │              │  │               │  │  - STABLE gate       │ │
│  │ TAG_FOLDER/  │  │ SubHandler    │──▶  - dedup (LRU)       │ │
│  │  <Ch>/<Dev>  │  │ callback      │  │  - baseline filter   │ │
│  │  .csv        │  │ (thread 1)    │  │  - normalize         │ │
│  │              │  │               │  │  - send Kafka        │ │
│  │ equipment_   │  └───────┬───────┘  └──────────┬───────────┘ │
│  │ map.json     │          │ put_nowait           │             │
│  └──────────────┘          ▼                      ▼             │
│                    ┌────────────────┐    ┌───────────────────┐  │
│                    │  value_queue   │    │  KafkaProducer    │  │
│                    │  max 200 000   │    │  key = machineId  │  │
│                    └────────────────┘    └─────────┬─────────┘  │
└──────────────────────────────────────────────────────┼──────────┘
                                                       ▼
                                    Kafka: industrial.telemetry
                                    8 partitions, key = machineId
```

**Hai luồng (thread) tách biệt — không được gộp:**

| Luồng | Vai trò | Cơ chế |
|---|---|---|
| OPC UA callback thread | Nhận notification → đẩy payload thô vào queue | `put_nowait`, không chặn |
| Value worker thread | Normalize → dedup → gửi Kafka | `queue.get(timeout=1)` |

**Vì sao phải tách:** nếu gửi Kafka trực tiếp trong callback, một lần Kafka chậm sẽ
chặn luồng callback của thư viện OPC UA. Khi luồng callback bị chặn, Kepware bắt
đầu queue notification và cuối cùng **bỏ dữ liệu**. Tách luồng giữ độ trễ của
callback ở mức microsecond.

---

## 2. Cấu trúc thư mục

```
IndustrialTelemetry.Middleware/
├── main.py                      # Entry point + vòng lặp chính
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py              # Toàn bộ cấu hình từ biến môi trường
│   └── logging_config.py        # Console + file log theo ngày
├── core/
│   ├── tag_loader.py            # Đọc TAG_FOLDER/<Channel>/<Device>.csv
│   ├── equipment_map.py         # Đọc equipment_map.json
│   ├── value_types.py           # Ánh xạ kiểu 3 tầng (Kepware → Python → OPC UA)
│   ├── dedup.py                 # LRU dedup cache + baseline snapshot
│   ├── state_machine.py         # OpcConnectionState + ReconnectController
│   └── subscription.py          # SubscriptionRegistry + SubHandler
├── services/
│   ├── opcua_client.py          # Connect → subscribe → reconnect cycle
│   ├── simulator.py             # Nguồn dữ liệu giả lập (thay Kepware khi SIMULATION_MODE=true)
│   ├── value_worker.py          # Thread xử lý queue → Kafka
│   ├── normalizer.py            # Dựng message chuẩn
│   └── kafka_publisher.py       # Wrapper KafkaProducer
├── utils/
│   ├── event_id.py              # UUID v5 tất định
│   ├── status_codes.py          # Good / Uncertain / Bad
│   └── time_utils.py            # ISO-8601 UTC
├── tools/
    ├── selftest.py              # Self-test offline (không cần Kepware/Kafka)
    ├── integration_test.py     # Integration test end-to-end với mock
    ├── simulation_test.py      # Self-test chế độ giả lập
    ├── verify_doc.py           # Kiểm tra tài liệu bàn giao khớp catalog
    ├── gen_tag_tables.py       # Sinh bảng tag Markdown từ catalog
    ├── inject_tag_tables.py    # Chèn bảng tag vào tài liệu bàn giao
    ├── preview_message.py      # Sinh mẫu message từ metadata
    ├── address_rules.py        # Nguồn quy tắc sinh cột Address (dùng chung)
    ├── generate_tag_csv.py     # Sinh CSV + equipment_map từ catalog
    ├── generate_kepware_import_csv.py  # Sinh bộ CSV 17 cột để import Kepware
    ├── validate_metadata.py    # Kiểm tra tính nhất quán metadata
    ├── validate_kepware_import_csv.py  # Kiểm tra bộ CSV import
    ├── test_address_rules.py   # Unit test quy tắc Address
    └── check_partitioning.py   # Phân bố partition theo machineId
├── metadata/                   # Metadata đầu vào (đọc từ file)
│   ├── TAG_FOLDER/<Channel>/<Device>.csv
│   ├── KEPWARE_IMPORT/<Channel>/<Device>.csv
│   ├── catalog.json
│   ├── equipment_map.json
│   └── README.md
└── docs/
    ├── kafka_data_contract_and_storage_guide.md
    └── industrial_telemetry_kepware_middleware_kafka_design.md
```

---

## 3. Chạy thử

### 3.1. Cài đặt

```powershell
cd IndustrialTelemetry.Middleware
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

### 3.2. Self-test (offline, không cần Kepware/Kafka)

```powershell
python tools\selftest.py          # 63 check: metadata, kiểu dữ liệu, eventId, dedup, partitioning, StatusCode
python tools\integration_test.py  # 29 check: pipeline callback → queue → worker → Kafka (mock)
python tools\verify_doc.py        # 27 check: tài liệu bàn giao khớp catalog
python tools\simulation_test.py   # 29 check: chế độ giả lập (sinh dữ liệu + data contract)
python tools\test_address_rules.py # 55 check: quy tắc cột Address
```

Tất cả đều chạy offline — không cần Kepware, không cần Kafka.

### 3.2.1. Kiểm tra metadata (trước khi import vào Kepware)

```powershell
python tools\validate_metadata.py           # 404 tag, TagCode, NodeId, Address (0 lỗi)
python tools\validate_kepware_import_csv.py # bộ CSV import 17 cột (0 lỗi)
python tools\check_partitioning.py          # phân bố partition theo machineId
```

### 3.3. Xem mẫu message

```powershell
python tools\preview_message.py --machine L01_FILLER_01 --tag FillLevel
```

### 3.4. Sinh lại bảng tag cho tài liệu bàn giao

```powershell
python tools\gen_tag_tables.py --out _tag_tables.md
python tools\inject_tag_tables.py --tables _tag_tables.md `
    --doc ../kafka_data_contract_and_storage_guide.md
```

### 3.5. Chạy thật

```powershell
python main.py
```

Nhật ký nằm ở `logs/<dd-MM-YYYY>/`:
- `*_middleware.log` — vòng đời, trạng thái, lỗi
- `*_kafka-publish.log` — chi tiết từng message gửi Kafka

### 3.6. Chế độ giả lập (không cần Kepware)

Dành cho máy của đồng đội **không cài được Kepware**: bật `SIMULATION_MODE=true`
trong `.env`, middleware sẽ **không kết nối Kepware** mà tự sinh dữ liệu cho
toàn bộ 404 tag / 26 máy rồi gửi vào Kafka đúng data contract đã chốt.

```powershell
# .env
SIMULATION_MODE=true
```

```powershell
python main.py
```

Cơ chế: `SimulatedSource` sinh giá trị → đẩy vào **cùng** `value_queue` →
`ValueWorker` → `Normalizer` → Kafka. Nên message ra Kafka **giống hệt** chế
độ đọc Kepware thật: cùng schema, cùng partition key (`machineId`), cùng cơ
chế dedup, cùng `eventId` UUID v5 tất định. Khác duy nhất là
`source.system = "simulator"`.

Dữ liệu giả lập bám theo quy tắc nghiệp vụ trong design doc §9.1:
- `MachineState` đi theo chu kỳ `OFF → STARTING → RUNNING ⇄ STOPPED`, có thể
  rơi vào `FAULTED` / `MAINTENANCE`.
- `CurrentSpeed = 0` khi không `RUNNING`.
- Bộ đếm **chỉ tăng khi `RUNNING`**.
- `AlarmCode != 0` khi `FAULTED`.

Các biến cấu hình liên quan (xem `.env.example`):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `SIMULATION_MODE` | `false` | Bật/tắt chế độ giả lập |
| `SIMULATION_TICK_MS` | `200` | Nhịp quét simulator (ms) |
| `SIMULATION_SPEED_FACTOR` | `1.0` | Hệ số tốc độ — `10.0` = nhanh gấp 10 |
| `SIMULATION_DEFAULT_SCAN_MS` | `1000` | Scan Rate mặc định cho tag không khai báo |
| `SIMULATION_SEED` | `20261111` | Seed RNG — cùng seed ⇒ cùng chuỗi dữ liệu |
| `SIMULATION_QUALITY_FAULT_RATE` | `0.01` | Tỷ lệ lỗi chất lượng giả lập (0 = luôn Good) |
| `SIMULATION_SOURCE_SYSTEM` | `simulator` | Giá trị ghi trong `source.system` |

---

## 4. Metadata đầu vào

Middleware đọc metadata **từ file**, không truy vấn DB (giống cách Vinamilk làm):

```
metadata/
├── TAG_FOLDER/          # ← middleware đọc (20 cột: Kepware + TagCode)
│   ├── LINE_01/
│   │   ├── L01_PREFEED_01.csv
│   │   ├── L01_FILLER_01.csv
│   │   └── ...
│   ├── LINE_02/ ...
│   ├── LINE_03/ ...
│   └── SHARED/
│       └── CIP_SKID_01.csv
├── KEPWARE_IMPORT/      # ← dùng để import vào Kepware (17 cột chuẩn)
├── catalog.json         # Nguồn sự thật: 26 máy / 404 tag
└── equipment_map.json
```

**Quy ước:**

- `TAG_FOLDER/<Channel>/<Device>.csv` → mỗi file = một device (= một máy).
- NodeId OPC UA dựng tự động: `ns=2;s=<Channel>.<Device>.<Tag Name>`.
- `equipment_map.json` khóa theo `"<Channel>.<Device>"`.

**Cột CSV được dùng** (định dạng export chuẩn của Kepware):

| Cột | Bắt buộc | Dùng để |
|---|---|---|
| `Tag Name` | ✅ | phần cuối của NodeId |
| `Data Type` | ✅ | kiểu Kepware → ép giá trị + sinh `valueType` |
| `Eng Units` | | đơn vị đo (`-` = không có) |
| `TagType` | | `ANALOG` / `DIGITAL` / `COUNTER` / `STRING` |
| `TagCode` | ✅ | mã nghiệp vụ, duy nhất toàn hệ thống |
| `Acquisition Class` | | chỉ để hướng dẫn cấu hình Kepware — **không** đưa vào message |

---

## 5. Ánh xạ kiểu dữ liệu (3 tầng)

```
CSV (tên Kepware)  →  Python native  →  Kafka valueType (tên OPC UA)

Boolean                bool                Boolean
Int                    int                 Int32
Word                   int                 UInt16
DWord                  int                 UInt32
Long                   int                 Int64
Float                  float               Float
Double                 float               Double
String                 str                 String
```

**Ràng buộc của bài tập:** kiểu số nguyên lớn nhất chỉ dùng `Long` (Int64) và
`DWord` (UInt32). Không có `LWord`/`UInt64` trong catalog.

**Vì sao `valueType` ghi tên OPC UA chứ không phải tên Kepware:** consumer cuối là
Flink / MinIO / PostgreSQL — họ hiểu chuẩn OPC UA, không hiểu quy ước đặt tên của
Kepware. Tầng Middleware đảm nhiệm việc dịch tên này.

**Vì sao phải ép kiểu theo metadata chứ không đoán từ giá trị:** `Long` và `Int`
đều là Python `int` — nhìn runtime không phân biệt được. Nếu không ép, `valueType`
sẽ phụ thuộc giá trị đọc được và có thể đổi giữa các message. Ép theo CSV ⇒
`valueType` của một tag là **hằng số** suốt vòng đời.

---

## 6. Cơ chế bảo đảm độ ổn định

### 6.1. Máy trạng thái kết nối

```
CONNECTING ──▶ SUBSCRIBING ──▶ DEGRADED ──▶ STABLE
     ▲             │              │           │
     └─────────────┴──────────────┴───────────┘
                   RECONNECTING
```

Chỉ gửi Kafka khi trạng thái là `STABLE` và kết nối còn active. Sự kiện phát ra
lúc `DEGRADED` bị bỏ qua — gửi dữ liệu khi kết nối chập chờn tạo nhiễu lớn hơn
giá trị của nó.

**Ngoại lệ chu kỳ khởi động đầu tiên:** ngay sau lần subscribe đầu tiên,
middleware chuyển thẳng sang `STABLE` mà không chờ đạt tỷ lệ subscribe.
Lý do: lúc setup, Kepware thường chưa có đủ device/tag, nên tỷ lệ subscribe
thấp là chuyện bình thường — nếu chặn theo tỷ lệ thì middleware sẽ không gửi
được gì lên Kafka dù các tag đã subscribe đều có dữ liệu tốt.

> **Tỷ lệ subscribe chỉ tính trên các tag KHÔNG bị invalid.** Tag báo
> `BadNodeIdUnknown` (chưa tạo trong Kepware) bị loại khỏi cả mẫu số lẫn tử số.
> Cùng cách tính với middleware Laird (`recompute_subscribe_gate_ratio`) và
> Vinamilk (`SubscriptionRegistry.ok_ratio`).

### 6.2. Reconnect (hard reset)

1. `subscription.delete()` → `client.disconnect()`
2. Xóa cache node, xóa dedup cache
3. Tạo `Client` mới, `session_timeout = 600000`
4. Nạp lại tag từ metadata
5. Subscribe hàng loạn, đếm tỷ lệ thành công
6. Chụp baseline snapshot
7. Vào `DEGRADED`, chờ đủ `STABLE_QUIET_SECONDS` không lỗi → `STABLE`

- **Backoff:** `1s → 2s → 5s → 10s → 20s → 30s` (+ jitter nhỏ)
- **Single-flight:** `ReconnectController.enter()` đảm bảo chỉ một chu kỳ chạy
- **Inactivity guard:** im lặng quá `INACTIVITY_TIMEOUT_S` → reconnect

### 6.3. Chống gửi trùng (3 tầng)

1. **Baseline snapshot** — ngay sau subscribe, chụp giá trị hiện tại của mọi node và
   **không phát** ra Kafka. Đây là nguồn nhiễu lớn nhất sau reconnect.
2. **LRU dedup cache** — NodeId → khóa `(normalized_value)`; chỉ phát khi giá trị
   thực sự đổi.
3. **EventId tất định (UUID v5)** — `uuid5(NAMESPACE, machineId|tagName|sourceTimestamp|value|statusCode)`
   → downstream dedup không cần state phía server.

### 6.4. Chất lượng dữ liệu

| StatusCode | Hành vi |
|---|---|
| `Good` | Gửi bình thường, `isGood: true` |
| `Uncertain` | Gửi, giữ giá trị, `isGood: false` |
| `Bad` | Gửi với `value: null`, `isGood: false` |

**Nguyên tắc:** không bao giờ bịa giá trị thay thế cho dữ liệu hỏng. `null` +
`isGood: false` nói rõ "không biết"; `0` nói dối rằng "giá trị là 0".

> **Lưu ý định dạng StatusCode của python-opcua:** `str(ua.StatusCode)` trả về
> chuỗi có wrapper — `"StatusCode(Good)"`, `"StatusCode(BadNoCommunication)"` —
> **không** phải `"Good"`. `utils/status_codes.py` bóc wrapper và dùng phép
> **chứa** (`"bad" in s`) chứ không dùng `startswith`, đúng như Laird và
> Vinamilk. Nếu dùng `startswith("good")` thì mọi tag sẽ bị phân loại nhầm
> thành `Bad` và mọi giá trị đều bị ghi ra Kafka với `value = null`.

### 6.5. Cấu hình Kafka producer

| Tham số | Giá trị | Tác dụng |
|---|---|---|
| `acks` | `all` | Chỉ coi là thành công khi đủ ISR xác nhận |
| `retries` | `10` | Số lần thử lại |
| `max_in_flight_requests_per_connection` | `1` | Giữ thứ tự, tránh reorder |
| `linger_ms` | `50` | Gom record trong 50ms |
| `batch_size` | `65536` | Ngưỡng byte đóng batch |

Với bộ cấu hình này producer đã đạt ngữ nghĩa idempotent của Kafka.

**Batching:** ở tầng ứng dụng, **1 Kafka record cho mỗi tag update** — không gom
nhiều tag vào một record. Gom batch là việc của Kafka client ở tầng mạng.

---

## 7. Partitioning

- **Key = `machineId`** → mọi message của một máy nằm trong cùng partition,
  giữ đúng thứ tự theo máy.
- **8 partitions**, phân bố bằng `murmur2(machineId) % 8`:
  `[3, 2, 6, 2, 3, 3, 4, 3]` máy/partition — không partition rỗng, không partition
  quá tải (spread 2–6 máy).

Đổi số partition không cần sửa code (Kafka tự tính lại), nhưng **không được đổi
sau khi đã có dữ liệu** nếu không cần migrate.

---

## 8. Cấu hình quan trọng

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `OPC_SERVER_URL` | `opc.tcp://localhost:49320` | Địa chỉ Kepware |
| `TAG_FOLDER` | `metadata/TAG_FOLDER` | Thư mục CSV tag |
| `EQUIPMENT_MAP_FILE` | `metadata/equipment_map.json` | File map máy |
| `KAFKA_BROKERS` | `localhost:9092` | Danh sách broker |
| `KAFKA_TOPIC` | `industrial.telemetry` | Topic đích |
| `VALUE_QUEUE_MAXSIZE` | `200000` | Sức chứa queue (≈ 8 phút dữ liệu nếu Kafka chết) |
| `USE_TIMESTAMP_IN_RECONNECT_DEDUP` | `false` | `false` = change-detection |
| `INACTIVITY_TIMEOUT_S` | `600` | Ngưỡng reconnect khi im lặng |
| `STABLE_QUIET_SECONDS` | `10` | Thời gian yên lặng để lên STABLE |
| `SCHEMA_VERSION` | `1.0` | Version của data contract |
| `SIMULATION_MODE` | `false` | Bật chế độ giả lập — không cần Kepware (xem §3.6) |

---

## 9. Điểm yếu đã biết

| Vấn đề | Mức độ | Ghi chú |
|---|---|---|
| Không có durable spool | Trung bình | Queue in-RAM. Kafka chết > 8 phút ⇒ mất dữ liệu. |
| `send()` thất bại hoàn toàn ⇒ mất message | Thấp | `retries=10` + `acks=all` đã xử lý phần lớn lỗi. |
| Chưa có schema registry (Avro/Protobuf) | Thấp | Contract ở dạng JSON + `schemaVersion`. |
| `eventId` dùng SHA-1 (UUID v5) | Thấp | Chấp nhận được cho dedup, không dùng cho bảo mật. |

---

## 10. Tài liệu liên quan

| File | Nội dung |
|---|---|
| `docs/industrial_telemetry_kepware_middleware_kafka_design.md` | Design spec đầy đủ |
| `docs/kafka_data_contract_and_storage_guide.md` | **Data contract + hướng dẫn lưu DB raw** (gửi đồng đội) |
| `metadata/catalog.json` | Catalog 26 máy / 404 tag |
| `metadata/README.md` | Hướng dẫn import metadata vào Kepware |
| `tools/generate_tag_csv.py` | Sinh CSV + equipment_map từ catalog |
| `tools/validate_metadata.py` | Kiểm tra tính nhất quán metadata |
