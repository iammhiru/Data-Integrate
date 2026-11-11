# Kafka Data Contract & Hướng dẫn lưu Raw Data

> **Tài liệu bàn giao cho nhóm phía sau (Flink / Data Platform / BI)**
> Dự án: *Tích hợp và xử lý dữ liệu lớn — Middleware Kepware → Kafka*
> Phiên bản contract: `schemaVersion = 1.0` · Cập nhật: 11/11/2026

---

## Mục lục

1. [Tóm tắt trong 60 giây](#1-tóm-tắt-trong-60-giây)
2. [Ai làm phần nào](#2-ai-làm-phần-nào)
3. [Topic, partition, key, retention](#3-topic-partition-key-retention)
4. [Schema message đầy đủ](#4-schema-message-đầy-đủ)
5. [Giải thích từng trường](#5-giải-thích-từng-trường)
6. [Ví dụ message thực tế](#6-ví-dụ-message-thực-tế)
7. [Kiểu dữ liệu — 3 tầng](#7-kiểu-dữ-liệu--3-tầng)
8. [Quy tắc chất lượng dữ liệu](#8-quy-tắc-chất-lượng-dữ-liệu)
9. [EventId & dedup](#9-eventid--dedup)
10. [Catalog đầy đủ 404 tag / 26 máy](#10-catalog-đầy-đủ-404-tag--26-máy)
11. [Đề xuất lưu DB raw data](#11-đề-xuất-lưu-db-raw-data)
    - [11.1 Kiến trúc lưu trữ tổng thể](#111-kiến-trúc-lưu-trữ-tổng-thể)
    - [11.2 Phương án A — TimescaleDB (PostgreSQL)](#112-phương-án-a--timescaledb-postgresql)
    - [11.3 Phương án B — ClickHouse](#113-phương-án-b--clickhouse)
    - [11.4 Phương án C — MinIO + Parquet](#114-phương-án-c--minio--parquet)
    - [11.5 So sánh & khuyến nghị](#115-so-sánh--khuyến-nghị)
12. [Code mẫu consumer](#12-code-mẫu-consumer)
13. [Checklist bàn giao](#13-checklist-bàn-giao)

---

## 1. Tóm tắt trong 60 giây

| Hạng mục | Giá trị |
|---|---|
| **Topic** | `industrial.telemetry` |
| **Partitions** | 8 |
| **Message key** | `machineId` (ví dụ `L01_FILLER_01`) |
| **Value** | JSON, UTF-8, 1 record = 1 tag update |
| **Số máy** | 26 (3 line sản xuất + 1 CIP dùng chung) |
| **Số tag** | 404 |
| **Tần suất** | Xem ghi chú bên dưới — phụ thuộc mức biến động dữ liệu thực |
| **Event type** | `machine.telemetry` (duy nhất) |
| **Tính tất định** | `eventId` = UUIDv5 từ nội dung sự kiện → dedup an toàn |

**Luồng tổng thể:**

```
Kepware (OPC UA)
   └─ subscription ─▶ IndustrialTelemetry.Middleware
                         ├─ đọc metadata từ CSV + equipment_map.json
                         ├─ chuẩn hóa (ép kiểu, làm tròn, sinh eventId)
                         ├─ dedup (loại bỏ baseline replay + giá trị không đổi)
                         └─ gửi Kafka, key = machineId
                                │
                                ▼
                    Kafka: industrial.telemetry (8 partitions)
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   Flink (dedup,           MinIO (raw              PostgreSQL
   window, aggregate)       Parquet)                (tổng hợp)
```

**Điều quan trọng nhất cần nhớ:** `eventTime` là **timestamp nguồn từ Kepware**, không
phải thời điểm middleware nhận được. Mọi dedup, windowing, tính toán đều dựa vào
`eventTime`.

### Ghi chú về tần suất phát event

Tần suất **thực tế trên topic** phụ thuộc mức biến động của dữ liệu, không phải
chỉ Scan Rate — vì middleware dùng **change-detection** (chỉ phát khi giá trị thực
sự đổi).

| Mức | Cách tính | Kết quả |
|---|---|---|
| Scan rate tổng (trần) | 404 tag × Scan Rate trong CSV (100/500/1000 ms) | ~2 200 event/s |
| Thực tế (change-detection) | tag ổn định không phát; tag đo dao động phát mỗi lần đổi | **~200–1 100 event/s** (tuỳ dữ liệu thật) |

⇒ Các con số ước lượng dung lượng ở §11.5.2 dùng mức **~400 event/s** làm
kịch bản trung tính. Nhóm phía sau nên **đo lại trên dữ liệu thật** (đếm message
topic trong 1 phút × 1440) rồi điều chỉnh hạ tầng cho phù hợp.

> **Lưu ý:** khi chạy ở chế độ giả lập (`SIMULATION_MODE=true`), tần suất phát
> **không phụ thuộc Scan Rate** nữa mà do `SIMULATION_SPEED_FACTOR` quyết định —
> cần tách dữ liệu demo khỏi số liệu ước lượng (lọc theo `source.system`).

---

## 2. Ai làm phần nào

| Tầng | Phạm vi | Trạng thái | Giao tiếp |
|---|---|---|---|
| **Kepware** | Thu thập từ PLC, gửi OPC UA | ✅ | — |
| **IndustrialTelemetry.Middleware** | Đọc Kepware → chuẩn hóa → Kafka | ✅ **xong** | Topic `industrial.telemetry` |
| **Flink** | Dedup theo `eventId`, window, aggregate | ⬜ nhóm khác | Kafka consumer |
| **Data Platform** | Lưu raw + phục vụ truy vấn | ⬜ nhóm khác | Kafka → DB (§11) |
| **BI / Dashboard** | Trực quan hoá, báo cáo | ⬜ nhóm khác | DB |

**Điểm giao tiếp duy nhất giữa 2 phía là Kafka.** Nếu cần đổi schema, báo trước để
tăng `schemaVersion` — consumer cũ vẫn đọc được (họ bỏ qua trường lạ).

### Chế độ giả lập (simulation mode)

Middleware có thêm 1 chế độ chạy **không cần Kepware** — dành cho máy của đồng
đội không cài được Kepware, và để nhóm phía sau test consumer/pipeline khi chưa
có dữ liệu thật.

| | Chế độ thật | Chế độ giả lập |
|---|---|---|
| Bật bằng | (mặc định) | `SIMULATION_MODE=true` trong `.env` |
| Nguồn dữ liệu | Kepware OPC UA | `services/simulator.py` sinh giá trị cho 404 tag / 26 máy |
| `source.system` | `"kepware"` | `"simulator"` |
| Schema / partition key / dedup / `eventId` | như §4 | **giống hệt** (cùng pipeline) |

⇒ **Consumer không cần sửa gì** để đọc dữ liệu giả lập — nó tuân thủ đúng contract
§4. Chỉ cần **lọc `source.system`** nếu không muốn lẫn dữ liệu demo vào số liệu
sản xuất.

---

## 3. Topic, partition, key, retention

| Thuộc tính | Giá trị | Giải thích |
|---|---|---|
| Tên topic | `industrial.telemetry` | |
| Số partition | `8` | Đủ cho 26 máy, không partition rỗng |
| Message key | `machineId` | Mọi message của một máy → cùng partition → giữ thứ tự |
| Value serializer | JSON UTF-8 | `ensure_ascii=false`, không thêm field ngoài contract |
| Producer acks | `all` | Chỉ coi là xong khi đủ ISR xác nhận |
| Retention đề xuất | 7 ngày trên Kafka | Lịch sử dài hơn nằm ở tầng lưu trữ (§11) |

### 3.1. Phân bố partition

Kafka dùng `murmur2(key) % numPartitions`. Với 26 `machineId`:

| Partition | Số máy | Partition | Số máy |
|---|---|---|---|
| 0 | 3 | 4 | 3 |
| 1 | 2 | 5 | 3 |
| 2 | 6 | 6 | 4 |
| 3 | 2 | 7 | 3 |

→ Không partition rỗng. Partition đông nhất gánh 6 máy, ít nhất gánh 2 máy.

**Ý nghĩa thực tế:** nếu 1 máy phát nhiều hơn bình thường, partition của máy đó
nóng lên — nhưng **không ảnh hưởng** máy khác, vì partition tách biệt hoàn toàn.

### 3.2. Consumer nên đọc thế nào

- **Offset:** đọc theo partition, **không** dùng `assign()` cố định — hãy dùng
  `subscribe()` để Kafka tự cân bằng consumer group.
- **Key:** luôn deserialize `key` để biết message thuộc máy nào mà không cần parse
  JSON.
- **Consumer group:** mỗi nhóm dùng một group id riêng. Nhóm xử lý raw và nhóm làm
  tổng hợp **không** dùng chung group id.

---

## 4. Schema message đầy đủ

### 4.1. Cấu trúc

```json
{
  "eventId": "bd7daa56-39fa-5032-9511-591326f08033",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",

  "eventTime": "2026-11-11T09:15:32.412Z",

  "source": {
    "system": "kepware",
    "channel": "LINE_01",
    "device": "L01_FILLER_01",
    "nodeId": "ns=2;s=LINE_01.L01_FILLER_01.FillLevel",
    "serverTimestamp": "2026-11-11T09:15:32.408Z"
  },

  "plant": {
    "plantId": "PLANT_01",
    "lineId": "LINE_01",
    "processId": "FILLING"
  },

  "machine": {
    "machineId": "L01_FILLER_01",
    "machineType": "CARBONATED_FILLER",
    "equipmentCode": "FILL-L01-01"
  },

  "tag": {
    "tagName": "FillLevel",
    "tagCode": "FILL.L01.FILLLEVEL",
    "tagType": "ANALOG"
  },

  "measurement": {
    "value": 87.5,
    "valueType": "Float",
    "unit": "%"
  },

  "quality": {
    "statusCode": "Good",
    "isGood": true
  }
}
```

### 4.2. Sơ đồ các khóa (flat, dễ đọc)

| Đường dẫn | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| `eventId` | string (UUID) | ✅ | Định danh sự kiện, tất định |
| `eventType` | string | ✅ | Luôn `"machine.telemetry"` |
| `schemaVersion` | string | ✅ | Semver đơn giản, hiện `"1.0"` |
| `eventTime` | string (ISO-8601 UTC) | ✅ | Thời điểm sự kiện theo Kepware |
| `source.system` | string | ✅ | Nguồn gốc. Baseline `"kepware"`, chế độ giả lập `"simulator"` |
| `source.channel` | string | ✅ | Channel Kepware |
| `source.device` | string | ✅ | Device Kepware = `machineId` |
| `source.nodeId` | string | ✅ | NodeId OPC UA đầy đủ |
| `source.serverTimestamp` | string \| null | ✅ | Timestamp phía server |
| `plant.plantId` | string | ✅ | Mã nhà máy |
| `plant.lineId` | string | ✅ | Mã line |
| `plant.processId` | string | ✅ | Mã công đoạn |
| `machine.machineId` | string | ✅ | Định danh máy (khóa partition) |
| `machine.machineType` | string | ✅ | Loại máy (enum) |
| `machine.equipmentCode` | string | ✅ | Mã thiết bị nghiệp vụ |
| `tag.tagName` | string | ✅ | Tên tag trong Kepware |
| `tag.tagCode` | string | ✅ | Mã tag nghiệp vụ, unique toàn hệ thống |
| `tag.tagType` | string | ✅ | `ANALOG` / `DIGITAL` / `COUNTER` / `STRING` |
| `measurement.value` | number \| bool \| string \| null | ✅ | Giá trị đã chuẩn hóa |
| `measurement.valueType` | string | ✅ | Kiểu canonical OPC UA |
| `measurement.unit` | string \| null | ✅ | Đơn vị đo, `null` nếu không có |
| `quality.statusCode` | string | ✅ | `Good` / `Uncertain` / `Bad` |
| `quality.isGood` | boolean | ✅ | Filter nhanh |

---

## 5. Giải thích từng trường

### 5.1. `eventId` — khóa dedup xuyên suốt hệ thống

UUID **version 5** (SHA-1 based), tất định theo nội dung sự kiện:

```
eventId = uuid5(NAMESPACE, "machineId|tagName|sourceTimestamp|value|statusCode")

NAMESPACE = 6f0d2b1e-9a4c-4c0e-9a1b-2c3d4e5f6a7b
```

| Đặc tính | Ý nghĩa |
|---|---|
| Tất định | Cùng sự kiện → cùng `eventId`, kể cả khi phát lại do reconnect hoặc retry |
| Không va chạm | Khác sự kiện → khác `eventId` (xác suất va chạm cực thấy) |
| Dùng được ở mọi tầng | Middleware sinh, Flink dedup, consumer đối chiếu, lưu trữ |

**Vì sao dùng `sourceTimestamp` chứ không dùng thời điểm nhận:** nếu dùng thời điểm
nhận, mỗi lần reconnect sẽ sinh `eventId` khác → mất hoàn toàn khả năng dedup.

**Về namespace:** giá trị này được ghim cứng. Đổi namespace = hỏng dedup toàn hệ
thống. Đừng sửa.

### 5.2. `eventTime` — trường quan trọng nhất cho downstream

- Lấy từ `SourceTimestamp` của Kepware.
- **UTC**, định dạng ISO-8601, **milliseconds**, kết thúc bằng `Z`.
  - Ví dụ: `2026-11-11T09:15:32.412Z`
- Đây là trường dùng cho windowing trong Flink, time-bucket trong DB, và trục thời gian
  trên dashboard.

**Lưu ý:** nếu hệ thống của bạn cần đồng bộ với MES/ERP (giờ địa phương), hãy quy đổi
từ UTC ở tầng đọc, **không** sửa giá trị trong Kafka.

### 5.3. `source` — truy vết ngược

| Trường | Ý nghĩa |
|---|---|
| `system` | Nguồn gốc. Baseline `"kepware"`. Giữ trường này để sau này thêm PLC/simulator/MES mà không đổi schema. **Lưu ý:** khi middleware chạy ở chế độ giả lập (`SIMULATION_MODE=true`), giá trị này là `"simulator"` — consumer có thể lọc theo trường này để tách dữ liệu thật khỏi dữ liệu demo. |
| `channel` | Channel Kepware chứa device. Hiện trùng `plant.lineId`. |
| `device` | Device Kepware. **Trùng `machine.machineId`** (chốt: device chính là machine). |
| `nodeId` | NodeId OPC UA đầy đủ — dùng để truy vết ngược về tag gốc khi cần debug. |
| `serverTimestamp` | Timestamp phía server. Dùng để đo độ trễ và phát hiện clock skew. |

### 5.4. `plant` + `machine` — metadata phẳng (denormalized)

Metadata được **denormalize** (nhân sẵn vào mỗi message) thay vì để consumer phải
join bảng master data:

- **Lý do:** giá thành join lúc query lịch sử cao hơn nhiều so với việc nhân 4
  trường nhỏ vào mỗi record.
- **Hệ quả:** thêm 1 field mới vào metadata máy = đổi schema → phải tăng
  `schemaVersion`. Đổi *giá trị* (ví dụ đổi tên công đoạn) thì không cần.

| Trường | Nguồn | Ghi chú |
|---|---|---|
| `plant.plantId` | `equipment_map.json` | |
| `plant.lineId` | `equipment_map.json` | Trùng `source.channel` ở baseline |
| `plant.processId` | `equipment_map.json` | Công đoạn: FILLING, CAPPING, ... |
| `machine.machineId` | `equipment_map.json` | Trùng `source.device` |
| `machine.machineType` | `equipment_map.json` | Enum 15 loại máy |
| `machine.equipmentCode` | `equipment_map.json` | Mã nghiệp vụ, dùng để join MES |

### 5.5. `tag` — định danh tag

| Trường | Ý nghĩa |
|---|---|
| `tagName` | Tên tag trong Kepware. Khớp cột `Tag Name` của CSV. |
| `tagCode` | Mã nghiệp vụ, ví dụ `FILL.L01.FILLLEVEL`. **Unique toàn hệ thống** — dùng để join bảng tag master. |
| `tagType` | `ANALOG` (giá trị liên tục) / `DIGITAL` (0-1, enum) / `COUNTER` (tích luỹ) / `STRING` |

> Cột `Acquisition Class` (`REALTIME` / `PERIODIC`) **không có trong message**. Nó chỉ
> tồn tại trong CSV để hướng dẫn cấu hình tần suất quét trong Kepware. Tần suất phát
> ra do Kepware quyết định — middleware đọc được gì thì gửi hết, không phân loại.

### 5.6. `measurement` — giá trị

| Trường | Ý nghĩa |
|---|---|
| `value` | Giá trị đã chuẩn hóa, kiểu native tương ứng `valueType`. **`null` nếu quality là `Bad`.** |
| `valueType` | Tên kiểu canonical OPC UA: `Boolean`, `Int32`, `Int64`, `UInt16`, `UInt32`, `Float`, `Double`, `String`. |
| `unit` | Đơn vị đo lấy từ cột `Eng Units` của CSV. `null` nếu không có. |

**`valueType` là hằng số theo từng tag** — không đổi giữa các message. Nhờ vậy
consumer có thể tạo cột typed trong DB mà không cần suy luận.

### 5.7. `quality` — chất lượng dữ liệu

| Trường | Ý nghĩa |
|---|---|
| `statusCode` | Chuẩn hóa về 3 mức: `Good`, `Uncertain`, `Bad`. |
| `isGood` | Boolean thuận tiện để filter nhanh. |

---

## 6. Ví dụ message thực tế

### 6.1. Analog bình thường

```json
{
  "eventId": "bd7daa56-39fa-5032-9511-591326f08033",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-11T09:15:32.412Z",
  "source": {
    "system": "kepware",
    "channel": "LINE_01",
    "device": "L01_FILLER_01",
    "nodeId": "ns=2;s=LINE_01.L01_FILLER_01.FillLevel",
    "serverTimestamp": "2026-11-11T09:15:32.408Z"
  },
  "plant": { "plantId": "PLANT_01", "lineId": "LINE_01", "processId": "FILLING" },
  "machine": {
    "machineId": "L01_FILLER_01",
    "machineType": "CARBONATED_FILLER",
    "equipmentCode": "FILL-L01-01"
  },
  "tag": {
    "tagName": "FillLevel",
    "tagCode": "FILL.L01.FILLLEVEL",
    "tagType": "ANALOG"
  },
  "measurement": { "value": 87.5, "valueType": "Float", "unit": "%" },
  "quality": { "statusCode": "Good", "isGood": true }
}
```

### 6.2. Digital (boolean) — máy dừng khẩn cấp

```json
{
  "eventId": "8be22661-bb9c-5c17-b2f4-29a6ea2a7aec",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-11T09:17:05.881Z",
  "source": {
    "system": "kepware",
    "channel": "LINE_01",
    "device": "L01_FILLER_01",
    "nodeId": "ns=2;s=LINE_01.L01_FILLER_01.EmergencyStop",
    "serverTimestamp": "2026-11-11T09:17:05.874Z"
  },
  "plant": { "plantId": "PLANT_01", "lineId": "LINE_01", "processId": "FILLING" },
  "machine": {
    "machineId": "L01_FILLER_01",
    "machineType": "CARBONATED_FILLER",
    "equipmentCode": "FILL-L01-01"
  },
  "tag": {
    "tagName": "EmergencyStop",
    "tagCode": "FILL.L01.EMERGENCYSTOP",
    "tagType": "DIGITAL"
  },
  "measurement": { "value": true, "valueType": "Boolean", "unit": null },
  "quality": { "statusCode": "Good", "isGood": true }
}
```

### 6.3. Counter

```json
{
  "eventId": "46efa984-97af-54df-8685-f015ddc5fc76",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-11T09:18:44.120Z",
  "source": {
    "system": "kepware",
    "channel": "LINE_02",
    "device": "L02_CAPPER_01",
    "nodeId": "ns=2;s=LINE_02.L02_CAPPER_01.GoodCounter",
    "serverTimestamp": "2026-11-11T09:18:44.110Z"
  },
  "plant": { "plantId": "PLANT_01", "lineId": "LINE_02", "processId": "CAPPING" },
  "machine": {
    "machineId": "L02_CAPPER_01",
    "machineType": "SCREW_CAPPER",
    "equipmentCode": "CAPP-L02-01"
  },
  "tag": {
    "tagName": "GoodCounter",
    "tagCode": "CAPP.L02.GOODCOUNTER",
    "tagType": "COUNTER"
  },
  "measurement": { "value": 15432, "valueType": "Int64", "unit": "pcs" },
  "quality": { "statusCode": "Good", "isGood": true }
}
```

### 6.4. Chất lượng Bad — giá trị `null`

```json
{
  "eventId": "957137ea-bcb5-554c-bb30-7631a2fda642",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-11T09:20:15.004Z",
  "source": {
    "system": "kepware",
    "channel": "LINE_03",
    "device": "L03_CANFILLER_01",
    "nodeId": "ns=2;s=LINE_03.L03_CANFILLER_01.FillLevel",
    "serverTimestamp": "2026-11-11T09:20:14.998Z"
  },
  "plant": { "plantId": "PLANT_01", "lineId": "LINE_03", "processId": "FILLING" },
  "machine": {
    "machineId": "L03_CANFILLER_01",
    "machineType": "CAN_FILLER",
    "equipmentCode": "FILL-L03-01"
  },
  "tag": {
    "tagName": "FillLevel",
    "tagCode": "FILL.L03.FILLLEVEL",
    "tagType": "ANALOG"
  },
  "measurement": { "value": null, "valueType": "Float", "unit": "%" },
  "quality": { "statusCode": "Bad", "isGood": false }
}
```

### 6.5. Uncertain — đọc được nhưng không chắc chắn

```json
{
  "eventId": "e6064061-b85e-52bc-9b67-3e8af261b798",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-11T09:21:00.512Z",
  "source": {
    "system": "kepware",
    "channel": "SHARED",
    "device": "CIP_SKID_01",
    "nodeId": "ns=2;s=SHARED.CIP_SKID_01.Conductivity",
    "serverTimestamp": "2026-11-11T09:21:00.500Z"
  },
  "plant": { "plantId": "PLANT_01", "lineId": "SHARED", "processId": "CIP" },
  "machine": {
    "machineId": "CIP_SKID_01",
    "machineType": "CIP_SKID",
    "equipmentCode": "CIP-SHARED-01"
  },
  "tag": {
    "tagName": "Conductivity",
    "tagCode": "CIP.SHD.CONDUCTIVITY",
    "tagType": "ANALOG"
  },
  "measurement": { "value": 412.5, "valueType": "Float", "unit": "uS/cm" },
  "quality": { "statusCode": "Uncertain", "isGood": false }
}
```

---

## 7. Kiểu dữ liệu — 3 tầng

Giá trị đi qua 3 tầng, mỗi tầng dùng một hệ tên kiểu khác nhau:

```
CSV (tên Kepware)  →  Middleware (Python native)  →  Kafka (tên OPC UA)
```

| Kiểu trong CSV (Kepware) | Kiểu native Python | `valueType` trong Kafka |
|---|---|---|
| `Boolean` | `bool` | `Boolean` |
| `Int` | `int` | `Int32` |
| `Word` | `int` | `UInt16` |
| `DWord` | `int` | `UInt32` |
| `Long` | `int` | `Int64` |
| `Float` | `float` | `Float` |
| `Double` | `float` | `Double` |
| `String` | `str` | `String` |

### 7.1. Ràng buộc của bài tập

Catalog hiện tại chỉ dùng 4 kiểu: `Boolean` (87 tag), `Int` (99 tag), `Float`
(131 tag), `Long` (87 tag) — tổng 404 tag. Bảng ở §7 liệt kê đủ 8 kiểu vì
middleware hỗ trợ tất cả (mapping 3 tầng trong `core/value_types.py`), nhưng:

- Kiểu số nguyên lớn nhất **đang dùng** là `Long` (Int64).
- `Word` (UInt16) / `DWord` (UInt32) / `Double` / `String` đã có trong mapping và
  tài liệu, nhưng catalog **chưa dùng tới** — sẽ xuất hiện nếu sau này bổ sung tag.
- Không có `LWord`/`UInt64` trong catalog. Nếu sau này cần số 64-bit không dấu thì phải
  bổ sung vào cả CSV lẫn catalog cùng lúc.

> Bảng ánh xạ kiểu DB ở §7.5 giữ đủ `UInt16`/`UInt32`/`Double`/`String` để nhóm
> phía sau cài sẵn schema, không phải để phản ánh dữ liệu hiện có.

### 7.2. Vì sao `valueType` ghi tên OPC UA chứ không phải tên Kepware

Consumer cuối là Flink, MinIO, PostgreSQL, ClickHouse — họ hiểu chuẩn OPC UA, không
hiểu quy ước đặt tên riêng của Kepware. Nếu ghi `"Long"`, consumer phải biết thêm
*"Long của Kepware là Int64"*. Tầng Middleware đảm nhiệm việc dịch tên này.

### 7.3. Vì sao ép kiểu theo metadata chứ không đoán từ giá trị

`Long` và `Int` đều là Python `int` — nhìn runtime không phân biệt được. Nếu không
ép theo CSV, `valueType` sẽ phụ thuộc vào giá trị đọc được, và cùng một tag có thể
đổi `valueType` giữa các message → consumer không parse ổn định.

**Quy tắc vàng: `valueType` của một tag là hằng số suốt vòng đời.**

### 7.4. Quy tắc làm tròn

| Kiểu | Quy tắc |
|---|---|
| Số thực (`Float`, `Double`) | làm tròn **6 chữ số thập phân** |
| Số nguyên | làm tròn về số nguyên gần nhất |
| Boolean | `true`/`false` |
| String | giữ nguyên |

Làm tròn 6 chữ số là để `eventId` ổn định: `87.5` và `87.5000000001` phải cho cùng
một `eventId`.

### 7.5. Ánh xạ sang kiểu DB

| `valueType` | PostgreSQL | ClickHouse | Parquet |
|---|---|---|---|
| `Boolean` | `boolean` | `Bool` | `bool` |
| `Int32` | `integer` | `Int32` | `int32` |
| `Int64` | `bigint` | `Int64` | `int64` |
| `UInt16` | `smallint` | `UInt16` | `uint16` |
| `UInt32` | `bigint` | `UInt32` | `uint32` |
| `Float` | `real` | `Float32` | `float` |
| `Double` | `double precision` | `Float64` | `double` |
| `String` | `text` | `String` | `string` |

**Lưu ý về `UInt32`:** giá trị tối đa là 4 294 967 295, vượt giới hạn `integer` của
PostgreSQL → **phải dùng `bigint`**. Tương tự, `UInt16` tối đa 65 535 vượt giới hạn
`smallint` (32 767) → cũng nên dùng `integer`.

---

## 8. Quy tắc chất lượng dữ liệu

| `statusCode` | `isGood` | `value` | Khi nào xảy ra |
|---|---|---|---|
| `Good` | `true` | giá trị thật | Bình thường |
| `Uncertain` | `false` | giữ giá trị đọc được | Sensor rung, giá trị đọc được nhưng không chắc chắn |
| `Bad` | `false` | **`null`** | Mất kết nối, lỗi thiết bị, tag không tồn tại |

> **Lưu ý về đường đi thực tế của `Uncertain`/`Bad` (chế độ đọc Kepware):**
>
> Middleware chuẩn hóa `StatusCode` về 3 mức như bảng trên. Tuy nhiên ở **tầng
> OPC UA callback**, middleware **bỏ qua (không dispatch) mọi event có quality
> `Bad` hoặc `Uncertain`** — trừ khi sự kiện đó là lần phục hồi từ chất lượng
> xấu sang `Good` (khi đó event được `force` và gửi ngay).
>
> Lý do: khi Kepware mất kết nối, OPC UA trả về giá trị `0` kèm quality xấu.
> Gửi giá trị `0` đó đi sẽ làm downstream hiểu sai (counter bị hiểu là reset,
> máy bị hiểu là dừng). Giá trị thật sẽ được gửi lại ngay khi phục hồi.
>
> ⇒ **Thực tế trên topic `industrial.telemetry`, các event `Good` chiếm gần
> 100%.** Trường `quality` vẫn luôn có mặt trong message (đúng contract), và
> giá trị `Bad`/`Uncertain` **có thể** xuất hiện — nhưng chỉ trong 2 tình huống:
> 1. Middleware đang chạy ở **chế độ giả lập** (`SIMULATION_MODE=true`), nơi
>    `SIMULATION_QUALITY_FAULT_RATE` cố tình sinh ra lỗi chất lượng để nhóm phía
>    sau test được đường xử lý `value = null`.
> 2. Chất lượng xấu đến **giữa chừng** một lần đọc tốt — middleware bỏ qua lần
>    đọc xấu đó, nhưng nếu server đổi chất lượng ngay sau đó thì giá trị được
>    gửi kèm quality hiện tại.
>
> **Consumer vẫn phải xử lý `value = null` và `statusCode != 'Good'`** như tài liệu
> mô tả — vì đó là hợp đồng của schema, không phải tối ưu hóa hiện tại.

### 8.1. Nguyên tắc bất di bất dịch

> **Không bao giờ bịa giá trị thay thế cho dữ liệu hỏng.**

Một giá trị `null` + `isGood: false` nói rõ *"không biết"*. Một giá trị `0` nói dối
rằng *"giá trị là 0"* — và sẽ khiến counter bị hiểu là reset, máy bị hiểu là dừng,
biểu đồ vẽ sai.

### 8.2. Cảnh báo cho consumer

- **Đếm sự kiện lỗi** bằng `quality.statusCode != 'Good'` → KPI "tỷ lệ mất dữ liệu".
- **Khi tính trung bình / tổng**, phải **loại `value IS NULL`** — nếu không, `SUM` sẽ
  bỏ sót giá trị, còn `AVG` sẽ chia sai mẫu số.
- **Khi vẽ gap trên biểu đồ:** nối điểm qua `null`, đừng vẽ `0`.
- **Khi dựng KPI "sản lượng":** chỉ đếm `COUNTER` có `statusCode = 'Good'`.

### 8.3. Baseline replay — không phải lỗi

Ngay sau khi kết nối lại, Kepware gửi lại toàn bộ giá trị hiện tại. Middleware
**loại bỏ** lô giá trị đầu tiên này (baseline snapshot) trước khi gửi đi. Vì vậy:

> Khi bắt đầu đọc Kafka, bạn **không** thấy giá trị "tức thời" của mọi tag — chỉ
> thấy dữ liệu *thay đổi* sau đó. Đây là hành vi cố ý, không phải mất dữ liệu.

Hệ quả: nếu bạn cần trạng thái hiện tại của máy, hãy giữ state cuối cùng của mỗi
tag trong consumer (hoặc dùng bảng "latest value" ở tầng DB, xem §11.2).

---

## 9. EventId & dedup

### 9.1. Ba tầng chống trùng

| Tầng | Cơ chế | Ở đâu |
|---|---|---|
| 1. Baseline snapshot | Chụp giá trị hiện tại ngay sau subscribe, **không phát** | Middleware |
| 2. LRU dedup cache | Chỉ phát khi giá trị **thực sự đổi** | Middleware |
| 3. `eventId` UUIDv5 | Tất định theo nội dung sự kiện | Downstream |

### 9.2. Consumer nên dedup thế nào

**Khuyến nghị:** dùng `eventId` làm khóa dedup ở tầng Flink, với state TTL bằng
**2 giờ** (đủ để bao phủ cả trường hợp retry dài).

```sql
-- TimescaleDB
CREATE TABLE dedup_events (
    event_id UUID PRIMARY KEY,
    seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
SELECT 1 FROM dedup_events WHERE event_id = ?;
```

Trong Flink, cách phổ biến là dùng `KeyedProcessFunction` với `ValueState` +
`event-time timer` để tự động xoá state cũ.

### 9.3. Có cần dedup không?

Trong điều kiện hiện tại, middleware đã lọc khá kỹ nên **duplicate gần như không
xảy ra**. Nhưng:

- Kafka có thể phát lại message khi consumer rebalance (at-least-once).
- Khi reconnect, có thể phát lại 1 vài sự kiện biên.

⇒ **Nên dedup ở tầng lưu trữ** (unique constraint trên `eventId`), và **không bắ
buộc** dedup ở tầng Kafka.

### 9.4. At-least-once vs exactly-once

| Yếu tố | Thực tế |
|---|---|
| Producer | `acks=all` + `retries=10` + `max_in_flight=1` → idempotent |
| Consumer | Mặc định **at-least-once** |
| Đảm bảo exactly-once | Chỉ khi consumer bật checkpoint + transaction, hoặc dedup bằng `eventId` |

**Khuyến nghị cho nhóm lưu trữ:** dùng `eventId` làm unique key ở DB → đơn giản,
chắc chắn, không cần cấu hình transaction phức tạp.

---

## 10. Catalog đầy đủ 404 tag / 26 máy

### 10.1. Danh sách máy theo line

| Line | Công đoạn | Máy | `machineType` | Số tag |
|---|---|---|---|---|
| LINE_01 | PREFORM_FEEDING | L01_PREFEED_01 | PREFORM_FEEDER | 14 |
| LINE_01 | BLOW_MOULDING | L01_BLOWER_01 | STRETCH_BLOW_MOULDER | 18 |
| LINE_01 | BOTTLE_CONVEYING | L01_AIRCONV_01 | AIR_CONVEYOR | 13 |
| LINE_01 | RINSING | L01_RINSER_01 | BOTTLE_RINSER | 16 |
| LINE_01 | FILLING | L01_FILLER_01 | CARBONATED_FILLER | 18 |
| LINE_01 | CAPPING | L01_CAPPER_01 | SCREW_CAPPER | 15 |
| LINE_01 | LABELLING | L01_LABELER_01 | BOTTLE_LABELER | 15 |
| LINE_01 | CODING | L01_CODER_01 | DATE_CODER | 13 |
| LINE_01 | CASE_PACKING | L01_CASEPACKER_01 | CASE_PACKER | 18 |
| LINE_02 | PREFORM_FEEDING | L02_PREFEED_01 | PREFORM_FEEDER | 14 |
| LINE_02 | BLOW_MOULDING | L02_BLOWER_01 | STRETCH_BLOW_MOULDER | 18 |
| LINE_02 | BOTTLE_CONVEYING | L02_AIRCONV_01 | AIR_CONVEYOR | 13 |
| LINE_02 | RINSING | L02_RINSER_01 | BOTTLE_RINSER | 16 |
| LINE_02 | FILLING | L02_FILLER_01 | STILL_FILLER | 18 |
| LINE_02 | CAPPING | L02_CAPPER_01 | SCREW_CAPPER | 15 |
| LINE_02 | LABELLING | L02_LABELER_01 | BOTTLE_LABELER | 15 |
| LINE_02 | CODING | L02_CODER_01 | DATE_CODER | 13 |
| LINE_02 | CASE_PACKING | L02_CASEPACKER_01 | CASE_PACKER | 18 |
| LINE_03 | CAN_DEPALLETTIZING | L03_CANDEPAL_01 | CAN_DEPALLETIZER | 15 |
| LINE_03 | RINSING | L03_CANRINSER_01 | CAN_RINSER | 16 |
| LINE_03 | FILLING | L03_CANFILLER_01 | CAN_FILLER | 18 |
| LINE_03 | SEAMING | L03_SEAMER_01 | CAN_SEAMER | 16 |
| LINE_03 | CODING | L03_CANCODER_01 | DATE_CODER | 13 |
| LINE_03 | INSPECTION | L03_CANINSPECT_01 | CAN_INSPECTION | 14 |
| LINE_03 | CASE_PACKING | L03_CASEPACKER_01 | CASE_PACKER | 18 |
| SHARED | CIP | CIP_SKID_01 | CIP_SKID | 14 |

**Tổng: 26 máy · 404 tag.**

### 10.2. Danh mục tag chi tiết

<!-- BEGIN GENERATED TAG TABLES -->

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|

### L01_PREFEED_01 — PREFORM_FEEDER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `PREFORM_FEEDING`  
- **Equipment code:** `PREF-L01-01`  
- **Số tag:** 14

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `PREF.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `PREF.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `PREF.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `PREF.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `PREF.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | preform/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `PREF.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | preform/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `PREF.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `PREF.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `PREF.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `PREF.L01.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `PREF.L01.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `PREF.L01.PREFORMFEEDRATE` | `PreformFeedRate` | `Float` | preform/min | ANALOG | Tan suat cap preform thuc te |
| `PREF.L01.HOPPERLEVEL` | `HopperLevel` | `Float` | % | ANALOG | Muc thay the trong hopper |
| `PREF.L01.HOPPERLEVELLOW` | `HopperLevelLow` | `Boolean` | — | DIGITAL | True khi muc hopper duoi nguong can bo sung |

### L01_BLOWER_01 — STRETCH_BLOW_MOULDER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `BLOW_MOULDING`  
- **Equipment code:** `BLOW-L01-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `BLOW.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `BLOW.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `BLOW.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `BLOW.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `BLOW.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `BLOW.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `BLOW.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `BLOW.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `BLOW.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `BLOW.L01.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `BLOW.L01.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `BLOW.L01.CYCLETIME` | `CycleTime` | `Float` | s | ANALOG | Thoi gian mot chu ky thoi chai |
| `BLOW.L01.BLOWPRESSURE` | `BlowPressure` | `Float` | bar | ANALOG | Ap suat thoi trong khu thoi chai |
| `BLOW.L01.HEATERTEMP` | `HeaterTemp` | `Float` | degC | ANALOG | Nhiet do heater thoi PET |
| `BLOW.L01.MOLDTEMP` | `MoldTemp` | `Float` | degC | ANALOG | Nhiet do khuon |
| `BLOW.L01.CAVITYCOUNT` | `CavityCount` | `Int32` | — | DIGITAL | So khuon ep trong khuon |
| `BLOW.L01.BOTTLEWEIGHT` | `BottleWeight` | `Float` | g | ANALOG | Khoi luong chai rong |
| `BLOW.L01.POWERCONSUMPTION` | `PowerConsumption` | `Float` | kW | ANALOG | Cong suat tieu thu tinh theo moc thoi gian |

### L01_AIRCONV_01 — AIR_CONVEYOR

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `BOTTLE_CONVEYING`  
- **Equipment code:** `ACONV-L01-01`  
- **Số tag:** 13

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `ACONV.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `ACONV.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `ACONV.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `ACONV.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `ACONV.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | m/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `ACONV.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | m/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `ACONV.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `ACONV.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `ACONV.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `ACONV.L01.AIRPRESSURE` | `AirPressure` | `Float` | bar | ANALOG | Ap suat duong cap khi nen |
| `ACONV.L01.AIRFLOWRATE` | `AirFlowRate` | `Float` | Nm3/h | ANALOG | Lu luong khi nen |
| `ACONV.L01.MOTORSPEED` | `MotorSpeed` | `Float` | rpm | ANALOG | Toc do dong co hanh |
| `ACONV.L01.POWERCONSUMPTION` | `PowerConsumption` | `Float` | kW | ANALOG | Cong suat tieu thu |

### L01_RINSER_01 — BOTTLE_RINSER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `RINSING`  
- **Equipment code:** `RINSE-L01-01`  
- **Số tag:** 16

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `RINSE.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `RINSE.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `RINSE.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `RINSE.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `RINSE.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `RINSE.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `RINSE.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `RINSE.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `RINSE.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `RINSE.L01.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `RINSE.L01.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `RINSE.L01.RINSEWATERPRESSURE` | `RinseWaterPressure` | `Float` | bar | ANALOG | Ap suat nuoc rua |
| `RINSE.L01.RINSEWATERTEMP` | `RinseWaterTemp` | `Float` | degC | ANALOG | Nhiet do nuoc rua |
| `RINSE.L01.RINSEWATERFLOWRATE` | `RinseWaterFlowRate` | `Float` | m3/h | ANALOG | Lu luong nuoc rua |
| `RINSE.L01.NOZZLEPRESSURE` | `NozzlePressure` | `Float` | bar | ANALOG | Ap suat vo phun |
| `RINSE.L01.CIPPHASE` | `CIPPhase` | `Int32` | — | DIGITAL | Pha CIP hien tai (enum muc 0-4) |

### L01_FILLER_01 — CARBONATED_FILLER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `FILLING`  
- **Equipment code:** `FILL-L01-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `FILL.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `FILL.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `FILL.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `FILL.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `FILL.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `FILL.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `FILL.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `FILL.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `FILL.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `FILL.L01.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `FILL.L01.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `FILL.L01.FILLLEVEL` | `FillLevel` | `Float` | % | ANALOG | Muc chiet rot chai |
| `FILL.L01.FILLRATE` | `FillRate` | `Float` | bottles/min | ANALOG | Toc do chiet rot thuc te |
| `FILL.L01.HEADCOUNT` | `HeadCount` | `Int32` | — | DIGITAL | So dau chiet |
| `FILL.L01.CO2PRESSURE` | `CO2Pressure` | `Float` | bar | ANALOG | Ap suat CO2 |
| `FILL.L01.CO2FLOWRATE` | `CO2FlowRate` | `Float` | Nm3/h | ANALOG | Lu luong CO2 |
| `FILL.L01.PRODUCTTEMP` | `ProductTemp` | `Float` | degC | ANALOG | Nhiet do san pham |
| `FILL.L01.POWERCONSUMPTION` | `PowerConsumption` | `Float` | kW | ANALOG | Cong suat tieu thu |

### L01_CAPPER_01 — SCREW_CAPPER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `CAPPING`  
- **Equipment code:** `CAPP-L01-01`  
- **Số tag:** 15

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CAPP.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CAPP.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CAPP.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CAPP.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CAPP.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CAPP.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CAPP.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CAPP.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `CAPP.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CAPP.L01.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `CAPP.L01.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `CAPP.L01.TORQUE` | `Torque` | `Float` | Nm | ANALOG | Mo-men xoan van nap |
| `CAPP.L01.CAPFEEDRATE` | `CapFeedRate` | `Float` | caps/min | ANALOG | Tan suat cap nap |
| `CAPP.L01.CAPMISSING` | `CapMissing` | `Boolean` | — | DIGITAL | True khi phat hien thieu nap |
| `CAPP.L01.TORQUEHIGH` | `TorqueHigh` | `Boolean` | — | DIGITAL | True khi mo-men van nap vuot nguong |

### L01_LABELER_01 — BOTTLE_LABELER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `LABELLING`  
- **Equipment code:** `LABL-L01-01`  
- **Số tag:** 15

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `LABL.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `LABL.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `LABL.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `LABL.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `LABL.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `LABL.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `LABL.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `LABL.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `LABL.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `LABL.L01.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `LABL.L01.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `LABL.L01.LABELROLLREMAINING` | `LabelRollRemaining` | `Float` | m | ANALOG | Chieu dai cuon nhan con lai |
| `LABL.L01.LABELAPPLYCOUNT` | `LabelApplyCount` | `Int64` | pcs | COUNTER | So nhan da dan |
| `LABL.L01.LABELMISSING` | `LabelMissing` | `Boolean` | — | DIGITAL | True khi phat hien thieu nhan |
| `LABL.L01.LABELROLLLOW` | `LabelRollLow` | `Boolean` | — | DIGITAL | True khi cuon nhan sap het |

### L01_CODER_01 — DATE_CODER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `CODING`  
- **Equipment code:** `CODE-L01-01`  
- **Số tag:** 13

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CODE.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CODE.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CODE.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CODE.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CODE.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | pcs/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CODE.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | pcs/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CODE.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CODE.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CODE.L01.PRINTCOUNT` | `PrintCount` | `Int64` | pcs | COUNTER | So ma da in |
| `CODE.L01.INKLEVEL` | `InkLevel` | `Float` | % | ANALOG | Muc muc in |
| `CODE.L01.INKLOW` | `InkLow` | `Boolean` | — | DIGITAL | True khi muc muc thap |
| `CODE.L01.PRINTQUALITY` | `PrintQuality` | `Int32` | — | DIGITAL | Chat luong in (enum muc 0-2) |
| `CODE.L01.NOZZLEHEIGHT` | `NozzleHeight` | `Float` | mm | ANALOG | Do cao voi phun |

### L01_CASEPACKER_01 — CASE_PACKER

- **Channel / Line:** `LINE_01` / `LINE_01`  
- **Process:** `CASE_PACKING`  
- **Equipment code:** `CASE-L01-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CASE.L01.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CASE.L01.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CASE.L01.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CASE.L01.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CASE.L01.CURRENTSPEED` | `CurrentSpeed` | `Float` | cases/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CASE.L01.DESIGNSPEED` | `DesignSpeed` | `Float` | cases/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CASE.L01.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CASE.L01.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `CASE.L01.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CASE.L01.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `CASE.L01.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `CASE.L01.CASECOUNT` | `CaseCount` | `Int64` | cases | COUNTER | So thung da dong |
| `CASE.L01.BOTTLESPERCASE` | `BottlesPerCase` | `Int32` | pcs | DIGITAL | So chai trong mot thung |
| `CASE.L01.CASEFORMAT` | `CaseFormat` | `Int32` | — | DIGITAL | Dinh dang thung (enum muc 0-2) |
| `CASE.L01.PALLETCOUNT` | `PalletCount` | `Int64` | pallets | COUNTER | So pallet da tao |
| `CASE.L01.FILMREMAINING` | `FilmRemaining` | `Float` | m | ANALOG | Chieu dai mang goi con lai |
| `CASE.L01.FILMLOW` | `FilmLow` | `Boolean` | — | DIGITAL | True khi mang goi sap het |
| `CASE.L01.CASEJAM` | `CaseJam` | `Boolean` | — | DIGITAL | True khi phat hien ket thung |

### L02_PREFEED_01 — PREFORM_FEEDER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `PREFORM_FEEDING`  
- **Equipment code:** `PREF-L02-01`  
- **Số tag:** 14

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `PREF.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `PREF.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `PREF.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `PREF.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `PREF.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | preform/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `PREF.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | preform/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `PREF.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `PREF.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `PREF.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `PREF.L02.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `PREF.L02.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `PREF.L02.PREFORMFEEDRATE` | `PreformFeedRate` | `Float` | preform/min | ANALOG | Tan suat cap preform thuc te |
| `PREF.L02.HOPPERLEVEL` | `HopperLevel` | `Float` | % | ANALOG | Muc thay the trong hopper |
| `PREF.L02.HOPPERLEVELLOW` | `HopperLevelLow` | `Boolean` | — | DIGITAL | True khi muc hopper duoi nguong can bo sung |

### L02_BLOWER_01 — STRETCH_BLOW_MOULDER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `BLOW_MOULDING`  
- **Equipment code:** `BLOW-L02-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `BLOW.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `BLOW.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `BLOW.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `BLOW.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `BLOW.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `BLOW.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `BLOW.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `BLOW.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `BLOW.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `BLOW.L02.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `BLOW.L02.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `BLOW.L02.CYCLETIME` | `CycleTime` | `Float` | s | ANALOG | Thoi gian mot chu ky thoi chai |
| `BLOW.L02.BLOWPRESSURE` | `BlowPressure` | `Float` | bar | ANALOG | Ap suat thoi trong khu thoi chai |
| `BLOW.L02.HEATERTEMP` | `HeaterTemp` | `Float` | degC | ANALOG | Nhiet do heater thoi PET |
| `BLOW.L02.MOLDTEMP` | `MoldTemp` | `Float` | degC | ANALOG | Nhiet do khuon |
| `BLOW.L02.CAVITYCOUNT` | `CavityCount` | `Int32` | — | DIGITAL | So khuon ep trong khuon |
| `BLOW.L02.BOTTLEWEIGHT` | `BottleWeight` | `Float` | g | ANALOG | Khoi luong chai rong |
| `BLOW.L02.POWERCONSUMPTION` | `PowerConsumption` | `Float` | kW | ANALOG | Cong suat tieu thu tinh theo moc thoi gian |

### L02_AIRCONV_01 — AIR_CONVEYOR

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `BOTTLE_CONVEYING`  
- **Equipment code:** `ACONV-L02-01`  
- **Số tag:** 13

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `ACONV.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `ACONV.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `ACONV.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `ACONV.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `ACONV.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | m/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `ACONV.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | m/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `ACONV.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `ACONV.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `ACONV.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `ACONV.L02.AIRPRESSURE` | `AirPressure` | `Float` | bar | ANALOG | Ap suat duong cap khi nen |
| `ACONV.L02.AIRFLOWRATE` | `AirFlowRate` | `Float` | Nm3/h | ANALOG | Lu luong khi nen |
| `ACONV.L02.MOTORSPEED` | `MotorSpeed` | `Float` | rpm | ANALOG | Toc do dong co hanh |
| `ACONV.L02.POWERCONSUMPTION` | `PowerConsumption` | `Float` | kW | ANALOG | Cong suat tieu thu |

### L02_RINSER_01 — BOTTLE_RINSER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `RINSING`  
- **Equipment code:** `RINSE-L02-01`  
- **Số tag:** 16

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `RINSE.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `RINSE.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `RINSE.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `RINSE.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `RINSE.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `RINSE.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `RINSE.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `RINSE.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `RINSE.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `RINSE.L02.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `RINSE.L02.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `RINSE.L02.RINSEWATERPRESSURE` | `RinseWaterPressure` | `Float` | bar | ANALOG | Ap suat nuoc rua |
| `RINSE.L02.RINSEWATERTEMP` | `RinseWaterTemp` | `Float` | degC | ANALOG | Nhiet do nuoc rua |
| `RINSE.L02.RINSEWATERFLOWRATE` | `RinseWaterFlowRate` | `Float` | m3/h | ANALOG | Lu luong nuoc rua |
| `RINSE.L02.NOZZLEPRESSURE` | `NozzlePressure` | `Float` | bar | ANALOG | Ap suat vo phun |
| `RINSE.L02.CIPPHASE` | `CIPPhase` | `Int32` | — | DIGITAL | Pha CIP hien tai (enum muc 0-4) |

### L02_FILLER_01 — STILL_FILLER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `FILLING`  
- **Equipment code:** `FILL-L02-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `FILL.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `FILL.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `FILL.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `FILL.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `FILL.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `FILL.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `FILL.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `FILL.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `FILL.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `FILL.L02.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `FILL.L02.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `FILL.L02.FILLLEVEL` | `FillLevel` | `Float` | % | ANALOG | Muc chiet rot chai |
| `FILL.L02.FILLRATE` | `FillRate` | `Float` | bottles/min | ANALOG | Toc do chiet rot thuc te |
| `FILL.L02.HEADCOUNT` | `HeadCount` | `Int32` | — | DIGITAL | So dau chiet |
| `FILL.L02.WATERTEMP` | `WaterTemp` | `Float` | degC | ANALOG | Nhiet do nuoc chiet |
| `FILL.L02.WATERCONDUCTIVITY` | `WaterConductivity` | `Float` | uS/cm | ANALOG | Do dan nuoc |
| `FILL.L02.FILLINGPRESSURE` | `FillingPressure` | `Float` | bar | ANALOG | Ap suat trong qua trinh chiet |
| `FILL.L02.PRODUCTTEMP` | `ProductTemp` | `Float` | degC | ANALOG | Nhiet do san pham |

### L02_CAPPER_01 — SCREW_CAPPER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `CAPPING`  
- **Equipment code:** `CAPP-L02-01`  
- **Số tag:** 15

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CAPP.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CAPP.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CAPP.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CAPP.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CAPP.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CAPP.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CAPP.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CAPP.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `CAPP.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CAPP.L02.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `CAPP.L02.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `CAPP.L02.TORQUE` | `Torque` | `Float` | Nm | ANALOG | Mo-men xoan van nap |
| `CAPP.L02.CAPFEEDRATE` | `CapFeedRate` | `Float` | caps/min | ANALOG | Tan suat cap nap |
| `CAPP.L02.CAPMISSING` | `CapMissing` | `Boolean` | — | DIGITAL | True khi phat hien thieu nap |
| `CAPP.L02.TORQUEHIGH` | `TorqueHigh` | `Boolean` | — | DIGITAL | True khi mo-men van nap vuot nguong |

### L02_LABELER_01 — BOTTLE_LABELER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `LABELLING`  
- **Equipment code:** `LABL-L02-01`  
- **Số tag:** 15

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `LABL.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `LABL.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `LABL.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `LABL.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `LABL.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | bottles/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `LABL.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | bottles/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `LABL.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `LABL.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `LABL.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `LABL.L02.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `LABL.L02.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `LABL.L02.LABELROLLREMAINING` | `LabelRollRemaining` | `Float` | m | ANALOG | Chieu dai cuon nhan con lai |
| `LABL.L02.LABELAPPLYCOUNT` | `LabelApplyCount` | `Int64` | pcs | COUNTER | So nhan da dan |
| `LABL.L02.LABELMISSING` | `LabelMissing` | `Boolean` | — | DIGITAL | True khi phat hien thieu nhan |
| `LABL.L02.LABELROLLLOW` | `LabelRollLow` | `Boolean` | — | DIGITAL | True khi cuon nhan sap het |

### L02_CODER_01 — DATE_CODER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `CODING`  
- **Equipment code:** `CODE-L02-01`  
- **Số tag:** 13

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CODE.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CODE.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CODE.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CODE.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CODE.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | pcs/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CODE.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | pcs/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CODE.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CODE.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CODE.L02.PRINTCOUNT` | `PrintCount` | `Int64` | pcs | COUNTER | So ma da in |
| `CODE.L02.INKLEVEL` | `InkLevel` | `Float` | % | ANALOG | Muc muc in |
| `CODE.L02.INKLOW` | `InkLow` | `Boolean` | — | DIGITAL | True khi muc muc thap |
| `CODE.L02.PRINTQUALITY` | `PrintQuality` | `Int32` | — | DIGITAL | Chat luong in (enum muc 0-2) |
| `CODE.L02.NOZZLEHEIGHT` | `NozzleHeight` | `Float` | mm | ANALOG | Do cao voi phun |

### L02_CASEPACKER_01 — CASE_PACKER

- **Channel / Line:** `LINE_02` / `LINE_02`  
- **Process:** `CASE_PACKING`  
- **Equipment code:** `CASE-L02-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CASE.L02.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CASE.L02.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CASE.L02.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CASE.L02.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CASE.L02.CURRENTSPEED` | `CurrentSpeed` | `Float` | cases/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CASE.L02.DESIGNSPEED` | `DesignSpeed` | `Float` | cases/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CASE.L02.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CASE.L02.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `CASE.L02.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CASE.L02.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `CASE.L02.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `CASE.L02.CASECOUNT` | `CaseCount` | `Int64` | cases | COUNTER | So thung da dong |
| `CASE.L02.BOTTLESPERCASE` | `BottlesPerCase` | `Int32` | pcs | DIGITAL | So chai trong mot thung |
| `CASE.L02.CASEFORMAT` | `CaseFormat` | `Int32` | — | DIGITAL | Dinh dang thung (enum muc 0-2) |
| `CASE.L02.PALLETCOUNT` | `PalletCount` | `Int64` | pallets | COUNTER | So pallet da tao |
| `CASE.L02.FILMREMAINING` | `FilmRemaining` | `Float` | m | ANALOG | Chieu dai mang goi con lai |
| `CASE.L02.FILMLOW` | `FilmLow` | `Boolean` | — | DIGITAL | True khi mang goi sap het |
| `CASE.L02.CASEJAM` | `CaseJam` | `Boolean` | — | DIGITAL | True khi phat hien ket thung |

### L03_CANRINSER_01 — CAN_RINSER

- **Channel / Line:** `LINE_03` / `LINE_03`  
- **Process:** `RINSING`  
- **Equipment code:** `RINSE-L03-01`  
- **Số tag:** 16

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `RINSE.L03.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `RINSE.L03.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `RINSE.L03.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `RINSE.L03.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `RINSE.L03.CURRENTSPEED` | `CurrentSpeed` | `Float` | cans/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `RINSE.L03.DESIGNSPEED` | `DesignSpeed` | `Float` | cans/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `RINSE.L03.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `RINSE.L03.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `RINSE.L03.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `RINSE.L03.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `RINSE.L03.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `RINSE.L03.RINSEWATERPRESSURE` | `RinseWaterPressure` | `Float` | bar | ANALOG | Ap suat nuoc rua |
| `RINSE.L03.RINSEWATERTEMP` | `RinseWaterTemp` | `Float` | degC | ANALOG | Nhiet do nuoc rua |
| `RINSE.L03.RINSEWATERFLOWRATE` | `RinseWaterFlowRate` | `Float` | m3/h | ANALOG | Lu luong nuoc rua |
| `RINSE.L03.NOZZLEPRESSURE` | `NozzlePressure` | `Float` | bar | ANALOG | Ap suat vo phun |
| `RINSE.L03.CIPPHASE` | `CIPPhase` | `Int32` | — | DIGITAL | Pha CIP hien tai (enum muc 0-4) |

### L03_CANFILLER_01 — CAN_FILLER

- **Channel / Line:** `LINE_03` / `LINE_03`  
- **Process:** `FILLING`  
- **Equipment code:** `FILL-L03-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `FILL.L03.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `FILL.L03.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `FILL.L03.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `FILL.L03.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `FILL.L03.CURRENTSPEED` | `CurrentSpeed` | `Float` | cans/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `FILL.L03.DESIGNSPEED` | `DesignSpeed` | `Float` | cans/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `FILL.L03.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `FILL.L03.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `FILL.L03.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `FILL.L03.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `FILL.L03.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `FILL.L03.FILLLEVEL` | `FillLevel` | `Float` | % | ANALOG | Muc chiet lon |
| `FILL.L03.FILLRATE` | `FillRate` | `Float` | cans/min | ANALOG | Toc do chiet lon thuc te |
| `FILL.L03.HEADCOUNT` | `HeadCount` | `Int32` | — | DIGITAL | So dau chiet |
| `FILL.L03.CO2PRESSURE` | `CO2Pressure` | `Float` | bar | ANALOG | Ap suat CO2 |
| `FILL.L03.CO2FLOWRATE` | `CO2FlowRate` | `Float` | Nm3/h | ANALOG | Lu luong CO2 |
| `FILL.L03.PRODUCTTEMP` | `ProductTemp` | `Float` | degC | ANALOG | Nhiet do san pham |
| `FILL.L03.POWERCONSUMPTION` | `PowerConsumption` | `Float` | kW | ANALOG | Cong suat tieu thu |

### L03_CANCODER_01 — DATE_CODER

- **Channel / Line:** `LINE_03` / `LINE_03`  
- **Process:** `CODING`  
- **Equipment code:** `CODE-L03-01`  
- **Số tag:** 13

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CODE.L03.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CODE.L03.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CODE.L03.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CODE.L03.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CODE.L03.CURRENTSPEED` | `CurrentSpeed` | `Float` | pcs/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CODE.L03.DESIGNSPEED` | `DesignSpeed` | `Float` | pcs/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CODE.L03.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CODE.L03.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CODE.L03.PRINTCOUNT` | `PrintCount` | `Int64` | pcs | COUNTER | So ma da in |
| `CODE.L03.INKLEVEL` | `InkLevel` | `Float` | % | ANALOG | Muc muc in |
| `CODE.L03.INKLOW` | `InkLow` | `Boolean` | — | DIGITAL | True khi muc muc thap |
| `CODE.L03.PRINTQUALITY` | `PrintQuality` | `Int32` | — | DIGITAL | Chat luong in (enum muc 0-2) |
| `CODE.L03.NOZZLEHEIGHT` | `NozzleHeight` | `Float` | mm | ANALOG | Do cao voi phun |

### L03_CASEPACKER_01 — CASE_PACKER

- **Channel / Line:** `LINE_03` / `LINE_03`  
- **Process:** `CASE_PACKING`  
- **Equipment code:** `CASE-L03-01`  
- **Số tag:** 18

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CASE.L03.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CASE.L03.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CASE.L03.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CASE.L03.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CASE.L03.CURRENTSPEED` | `CurrentSpeed` | `Float` | cases/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `CASE.L03.DESIGNSPEED` | `DesignSpeed` | `Float` | cases/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `CASE.L03.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `CASE.L03.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `CASE.L03.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `CASE.L03.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `CASE.L03.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `CASE.L03.CASECOUNT` | `CaseCount` | `Int64` | cases | COUNTER | So thung da dong |
| `CASE.L03.CANSPERCASE` | `CansPerCase` | `Int32` | pcs | DIGITAL | So lon trong mot thung |
| `CASE.L03.CASEFORMAT` | `CaseFormat` | `Int32` | — | DIGITAL | Dinh dang thung (enum muc 0-2) |
| `CASE.L03.PALLETCOUNT` | `PalletCount` | `Int64` | pallets | COUNTER | So pallet da tao |
| `CASE.L03.FILMREMAINING` | `FilmRemaining` | `Float` | m | ANALOG | Chieu dai mang goi con lai |
| `CASE.L03.FILMLOW` | `FilmLow` | `Boolean` | — | DIGITAL | True khi mang goi sap het |
| `CASE.L03.CASEJAM` | `CaseJam` | `Boolean` | — | DIGITAL | True khi phat hien ket thung |

### L03_CANDEPAL_01 — CAN_DEPALLETIZER

- **Channel / Line:** `LINE_03` / `LINE_03`  
- **Process:** `CAN_DEPALLETTIZING`  
- **Equipment code:** `DEPL-L03-01`  
- **Số tag:** 15

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `DEPL.L03.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `DEPL.L03.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `DEPL.L03.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `DEPL.L03.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `DEPL.L03.CURRENTSPEED` | `CurrentSpeed` | `Float` | cans/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `DEPL.L03.DESIGNSPEED` | `DesignSpeed` | `Float` | cans/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `DEPL.L03.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `DEPL.L03.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `DEPL.L03.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `DEPL.L03.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `DEPL.L03.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `DEPL.L03.CANFEEDRATE` | `CanFeedRate` | `Float` | cans/min | ANALOG | Tan suat cap lon |
| `DEPL.L03.LAYERCOUNT` | `LayerCount` | `Int32` | — | DIGITAL | So lop lon tren pallet |
| `DEPL.L03.PALLETCOUNT` | `PalletCount` | `Int64` | pallets | COUNTER | So pallet da xu ly |
| `DEPL.L03.GRIPPERFAULT` | `GripperFault` | `Boolean` | — | DIGITAL | True khi co loi co gia |

### L03_SEAMER_01 — CAN_SEAMER

- **Channel / Line:** `LINE_03` / `LINE_03`  
- **Process:** `SEAMING`  
- **Equipment code:** `SEAM-L03-01`  
- **Số tag:** 16

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `SEAM.L03.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `SEAM.L03.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `SEAM.L03.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `SEAM.L03.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `SEAM.L03.CURRENTSPEED` | `CurrentSpeed` | `Float` | cans/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `SEAM.L03.DESIGNSPEED` | `DesignSpeed` | `Float` | cans/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `SEAM.L03.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `SEAM.L03.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `SEAM.L03.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `SEAM.L03.STARVED` | `Starved` | `Boolean` | — | DIGITAL | True khi may thieu san pham / nguyen lieu dau vao |
| `SEAM.L03.BLOCKED` | `Blocked` | `Boolean` | — | DIGITAL | True khi dau ra may bi chan do cong doan sau hoac buffer day |
| `SEAM.L03.SEAMTORQUE` | `SeamTorque` | `Float` | Nm | ANALOG | Mo-men xoan tao duong bien |
| `SEAM.L03.SEAMPRESSURE` | `SeamPressure` | `Float` | bar | ANALOG | Ap suat tao duong bien |
| `SEAM.L03.SEAMQUALITY` | `SeamQuality` | `Int32` | — | DIGITAL | Chat luong duong bien (enum muc 0-2) |
| `SEAM.L03.SEAMDEFECTCOUNT` | `SeamDefectCount` | `Int64` | pcs | COUNTER | So duong bien khong dat |
| `SEAM.L03.CANVACUUM` | `CanVacuum` | `Float` | kPa | ANALOG | Ap suat chan khong trong lon |

### L03_CANINSPECT_01 — CAN_INSPECTION

- **Channel / Line:** `LINE_03` / `LINE_03`  
- **Process:** `INSPECTION`  
- **Equipment code:** `INSP-L03-01`  
- **Số tag:** 14

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `INSP.L03.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `INSP.L03.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `INSP.L03.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `INSP.L03.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `INSP.L03.CURRENTSPEED` | `CurrentSpeed` | `Float` | cans/min | ANALOG | Toc do thuc te hien tai; ve 0 khi may dung |
| `INSP.L03.DESIGNSPEED` | `DesignSpeed` | `Float` | cans/min | ANALOG | Toc do thiet ke / dinh muc mo phong |
| `INSP.L03.TOTALCOUNTER` | `TotalCounter` | `Int64` | pcs | COUNTER | Tong so don vi may da xu ly, tich luy |
| `INSP.L03.GOODCOUNTER` | `GoodCounter` | `Int64` | pcs | COUNTER | So don vi dat theo logic may |
| `INSP.L03.DEFECTCOUNTER` | `DefectCounter` | `Int64` | pcs | COUNTER | So don vi loi / loai ra do may ghi nhan |
| `INSP.L03.INSPECTIONCOUNT` | `InspectionCount` | `Int64` | pcs | COUNTER | So lon da kiem tra |
| `INSP.L03.DEFECTRATE` | `DefectRate` | `Float` | % | ANALOG | Ty le loi cua hang gan nhat |
| `INSP.L03.INSPECTRESULT` | `InspectResult` | `Int32` | — | DIGITAL | Ket qua kiem tra (enum muc 0-2) |
| `INSP.L03.REJECTREASON` | `RejectReason` | `Int32` | — | DIGITAL | Ly do loai (enum muc 0-4) |
| `INSP.L03.CAMERAFAULT` | `CameraFault` | `Boolean` | — | DIGITAL | True khi loi camera kiem tra |

### CIP_SKID_01 — CIP_SKID

- **Channel / Line:** `SHARED` / `SHARED`  
- **Process:** `CIP`  
- **Equipment code:** `CIP-SHARED-01`  
- **Số tag:** 14

| TagCode | TagName | valueType | Unit | TagType | Ý nghĩa |
|---|---|---|---|---|---|
| `CIP.SHD.MACHINESTATE` | `MachineState` | `Int32` | — | DIGITAL | Trang thai may (enum muc 0-5) |
| `CIP.SHD.MACHINEMODE` | `MachineMode` | `Int32` | — | DIGITAL | Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `CIP.SHD.EMERGENCYSTOP` | `EmergencyStop` | `Boolean` | — | DIGITAL | True khi mach dung khanh dang tac dong |
| `CIP.SHD.ALARMCODE` | `AlarmCode` | `Int32` | — | DIGITAL | 0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong |
| `CIP.SHD.TOTALCOUNTER` | `TotalCounter` | `Int64` | cycles | COUNTER | Tong so chu ky CIP da chay |
| `CIP.SHD.TANKTEMP` | `TankTemp` | `Float` | degC | ANALOG | Nhiet do be chua CIP |
| `CIP.SHD.TANKLEVEL` | `TankLevel` | `Float` | % | ANALOG | Muc be chua CIP |
| `CIP.SHD.CONDUCTIVITY` | `Conductivity` | `Float` | uS/cm | ANALOG | Do dan dung dich CIP |
| `CIP.SHD.PH` | `pH` | `Float` | pH | ANALOG | Chi so pH cua dung dich |
| `CIP.SHD.FLOWRATE` | `FlowRate` | `Float` | m3/h | ANALOG | Lu luong hoi luu |
| `CIP.SHD.PRESSURE` | `Pressure` | `Float` | bar | ANALOG | Ap suat duong hoi luu |
| `CIP.SHD.CHEMICALDOSE` | `ChemicalDose` | `Float` | L | ANALOG | Luong hoa chat da bo sung |
| `CIP.SHD.HEATINGON` | `HeatingOn` | `Boolean` | — | DIGITAL | True khi may nuoi dang bat |
| `CIP.SHD.CIRCULATIONON` | `CirculationOn` | `Boolean` | — | DIGITAL | True khi bom hoi luu dang chay |

<!-- END GENERATED TAG TABLES -->

---

## 11. Đề xuất lưu DB raw data

> ⚠️ **Lọc `source.system` trước khi ghi vào DB.**
> Topic `industrial.telemetry` có thể chứa lẫn dữ liệu giả lập
> (`source.system = "simulator"`) nếu đồng đội chạy middleware ở chế độ
> `SIMULATION_MODE=true` để demo. Dữ liệu đó **không phải dữ liệu sản xuất** —
> không được tính vào KPI OEE, sản lượng hay báo cáo sự cố.
>
> ```sql
> WHERE source_system = 'kepware'
> ```
>
> (Schema DB ở §11.2/§11.3 nên thêm cột `source_system TEXT` để lưu lại trường này.)

### 11.1. Kiến trúc lưu trữ tổng thể

```
Kafka (industrial.telemetry, 7 ngày)
   │
   ├──► Flink ──► MinIO (raw Parquet, giữ lâu, chi phí rẻ)
   │              └──► gọi lại để backfill khi cần
   │
   └──► Sink ──► ClickHouse hoặc TimescaleDB
                  (truy vấn tương tác, dashboard)
```

**Nguyên tắc tách 2 tầng lưu trữ:**

| Tầng | Vai trò | Công nghệ | Retention |
|---|---|---|---|
| **Raw / archive** | Giữ toàn bộ lịch sử, giá rẻ, query chậm | **MinIO + Parquet** | 12–24 tháng |
| **Serving / query** | Truy vấn tương tác, dashboard nhanh | **TimescaleDB** hoặc **ClickHouse** | 30–90 ngày (chi tiết) + lâu dài (tổng hợp) |

**Vì sao cần cả hai:**
- Parquet trên object storage: giá ~$5/TB/tháng, giữ được vài năm, nhưng query
  tương tác cần Spark.
- TimescaleDB/ClickHouse: query nhanh, nhưng giữ 2 năm chi tiết ở 400 eps sẽ tốn
  không ít dung lượng.

⇒ **Raw ở MinIO, phục vụ truy vấn ở DB, và luôn có đường backfill từ MinIO về DB.**

### 11.2. Phương án A — TimescaleDB (PostgreSQL)

**Phù hợp nhất nếu nhóm đã quen PostgreSQL** và khối lượng query không lớn.

#### 11.2.1. Bảng raw (hypertable)

```sql
-- Extension time series
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Bảng raw telemetry: 1 dòng = 1 sự kiện tag
CREATE TABLE telemetry_raw (
    event_time      TIMESTAMPTZ   NOT NULL,      -- eventTime từ Kafka
    event_id        UUID          NOT NULL,      -- khóa dedup
    machine_id      TEXT          NOT NULL,
    tag_code        TEXT          NOT NULL,
    tag_name        TEXT          NOT NULL,
    tag_type        TEXT          NOT NULL,      -- ANALOG/DIGITAL/COUNTER/STRING

    value_num       DOUBLE PRECISION,            -- giá trị số (NULL nếu không phải số)
    value_bool      BOOLEAN,                     -- giá trị boolean
    value_text      TEXT,                        -- giá trị chuỗi
    value_type      TEXT         NOT NULL,       -- Boolean/Int32/Int64/UInt16/UInt32/Float/Double/String

    unit            TEXT,                        -- đơn vị (NULL nếu không có)
    status_code     TEXT         NOT NULL,       -- Good/Uncertain/Bad
    is_good         BOOLEAN      NOT NULL,

    -- metadata phẳng (denormalized)
    plant_id        TEXT         NOT NULL,
    line_id         TEXT         NOT NULL,
    process_id      TEXT         NOT NULL,
    machine_type    TEXT         NOT NULL,
    equipment_code  TEXT         NOT NULL,
    channel         TEXT         NOT NULL,
    node_id         TEXT         NOT NULL,
    server_time     TIMESTAMPTZ,
    source_system   TEXT         NOT NULL,       -- kepware / simulator — LỌC theo cột này

    PRIMARY KEY (event_time, event_id)
);

-- Biến thành hypertable, chunk 7 ngày
SELECT create_hypertable(
    'telemetry_raw',
    'event_time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Index theo máy + tag (truy vấn đồ thị)
CREATE INDEX idx_telemetry_machine_tag
    ON telemetry_raw (machine_id, tag_code, event_time DESC);

-- Index theo tag (truy vấn so sánh nhiều máy cùng tag)
CREATE INDEX idx_telemetry_tag_time
    ON telemetry_raw (tag_code, event_time DESC);

-- Index theo thời gian (báo cáo theo giờ/ngày)
CREATE INDEX idx_telemetry_time
    ON telemetry_raw (event_time DESC);
```

**Về `value_num` / `value_bool` / `value_text` — 3 cột thay vì 1 cột `value`:**

Đây là quyết định quan trọng nhất khi lưu raw vào SQL.

| Lựa chọn | Ưu | Nhược |
|---|---|---|
| 1 cột `value` kiểu `JSONB` | Đơn giản, linh hoạt | Chậm hơn ~3–5× khi filter `value > 80`, không index được |
| 1 cột `value` kiểu `TEXT` | Đơn giản | Phải cast khi query, không index được, mất kiểu |
| **3 cột tách theo miền** ✅ | Query số **rất nhanh**, index được, ép kiểu tự động | Thêm cột, phải biết trước quy tắc |

Với 404 tag có kiểu cố định, ta biết trước tag nào là số / bool / chuỗi ⇒ **3 cột là
lựa chọn tốt nhất**. Và vì `value_type` là hằng số theo tag, ta có thể dùng
**generated column** để chuẩn hóa tự động:

```sql
ALTER TABLE telemetry_raw
    ADD COLUMN value_num GENERATED ALWAYS AS (
        CASE WHEN value_type IN ('Int32','Int64','UInt16','UInt32','Float','Double')
             THEN value_num END
    ) STORED;
```

> Nếu chỉ muốn làm nhanh, hãy dùng **PostgreSQL thuần** với cột `value DOUBLE
> PRECISION` + cột `value_raw JSONB` (giữ nguyên message gốc để audit). Cách này
> đơn giản hơn nhiều và vẫn đáp ứng 90% nhu cầu truy vấn.

#### 11.2.2. Bảng trạng thái hiện tại (latest value)

```sql
CREATE TABLE telemetry_latest (
    machine_id   TEXT NOT NULL,
    tag_code     TEXT NOT NULL,
    value_num    DOUBLE PRECISION,
    value_bool   BOOLEAN,
    value_text   TEXT,
    value_type   TEXT NOT NULL,
    unit         TEXT,
    status_code  TEXT NOT NULL,
    is_good      BOOLEAN NOT NULL,
    event_time   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (machine_id, tag_code)
);
```

Cập nhật bằng UPSERT (Flink sink hoặc CDC):

```sql
INSERT INTO telemetry_latest
    (machine_id, tag_code, value_num, value_bool, value_text,
     value_type, unit, status_code, is_good, event_time)
VALUES (...)
ON CONFLICT (machine_id, tag_code) DO UPDATE SET
    value_num   = EXCLUDED.value_num,
    value_bool  = EXCLUDED.value_bool,
    value_text  = EXCLUDED.value_text,
    status_code = EXCLUDED.status_code,
    is_good     = EXCLUDED.is_good,
    event_time  = EXCLUDED.event_time
WHERE EXCLUDED.event_time >= telemetry_latest.event_time;
```

Mục đích: dashboard "trạng thái hiện tại của toàn bộ nhà máy" — query 1 bảng, không
cần quét lịch sử.

#### 11.2.3. Bảng tổng hợp theo giờ (cho BI)

```sql
CREATE TABLE telemetry_hourly (
    bucket       TIMESTAMPTZ NOT NULL,
    machine_id   TEXT NOT NULL,
    tag_code     TEXT NOT NULL,
    tag_name     TEXT NOT NULL,
    unit         TEXT,
    avg_value    DOUBLE PRECISION,
    min_value    DOUBLE PRECISION,
    max_value    DOUBLE PRECISION,
    last_value   DOUBLE PRECISION,
    sample_count INTEGER NOT NULL,
    good_count   INTEGER NOT NULL,
    bad_count    INTEGER NOT NULL,
    PRIMARY KEY (bucket, machine_id, tag_code)
);

SELECT create_hypertable(
    'telemetry_hourly', 'bucket',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);
```

Cần **continuous aggregate** của TimescaleDB để tự động gom:

```sql
CREATE MATERIALIZED VIEW telemetry_hourly_mv
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', event_time) AS bucket,
    machine_id,
    tag_code,
    ANY_VALUE(tag_name)   AS tag_name,
    ANY_VALUE(unit)       AS unit,
    avg(value_num)        AS avg_value,
    min(value_num)        AS min_value,
    max(value_num)        AS max_value,
    last(value_num, event_time) AS last_value,
    count(*)              AS sample_count,
    count(*) FILTER (WHERE is_good) AS good_count,
    count(*) FILTER (WHERE NOT is_good) AS bad_count
FROM telemetry_raw
WHERE value_num IS NOT NULL
GROUP BY bucket, machine_id, tag_code
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'telemetry_hourly_mv',
    start_offset => INTERVAL '2 hours',
    end_offset   => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes'
);
```

#### 11.2.4. Bảng trạng thái máy (cho dashboard OEE / sự cố)

```sql
CREATE TABLE machine_state_events (
    event_time   TIMESTAMPTZ NOT NULL,
    machine_id   TEXT NOT NULL,
    state_code   INTEGER NOT NULL,      -- MachineState: 0=OFF 1=STARTING 2=RUNNING 3=STOPPED 4=FAULTED 5=MAINTENANCE
    state_name   TEXT NOT NULL,
    alarm_code   INTEGER,
    is_good      BOOLEAN NOT NULL,
    PRIMARY KEY (machine_id, event_time)
);
```

Bảng này nhỏ (vài chục nghìn dòng/ngày) nhưng **cực kỳ giá trị** cho phân tích
downtime và OEE.

#### 11.2.5. Retention

```sql
-- Chi tiết: giữ 90 ngày
SELECT add_retention_policy('telemetry_raw', INTERVAL '90 days');
-- Tổng hợp giờ: giữ 2 năm
SELECT add_retention_policy('telemetry_hourly', INTERVAL '730 days');
```

### 11.3. Phương án B — ClickHouse

**Phù hợp nhất nếu khối lượng lớn và cần query nhanh trên dữ liệu thô.**

#### 11.3.1. Bảng raw

```sql
CREATE DATABASE IF NOT EXISTS telemetry;

CREATE TABLE telemetry.telemetry_raw
(
    event_time     DateTime64(3, 'UTC'),
    event_id       UUID,
    machine_id     LowCardinality(String),
    tag_code       LowCardinality(String),
    tag_name       LowCardinality(String),
    tag_type       LowCardinality(String),

    value_num      Float64,
    value_bool     UInt8,
    value_text     String,
    value_type     LowCardinality(String),

    unit           LowCardinality(String),
    status_code    LowCardinality(String),
    is_good        UInt8,

    plant_id       LowCardinality(String),
    line_id        LowCardinality(String),
    process_id     LowCardinality(String),
    machine_type   LowCardinality(String),
    equipment_code LowCardinality(String),
    channel        LowCardinality(String),
    node_id        String,
    server_time    DateTime64(3, 'UTC'),
    source_system  LowCardinality(String)   -- kepware / simulator — LỌC theo cột này
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (machine_id, tag_code, event_time)
TTL toDateTime(event_time) + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;
```

**Vì sao `LowCardinality(String)`:** `machine_id` có 26 giá trị, `tag_code` có 404,
`status_code` có 3. `LowCardinality` lưu dạng dictionary → **nhỏ hơn 5–10×** và query
nhanh hơn nhiều so với `String` thường.

**Vì sao `ORDER BY (machine_id, tag_code, event_time)`:** đúng thứ tự truy vấn phổ
biến nhất (1 máy, 1 tag, theo thời gian) → ClickHouse prune được rất nhiều
granule.

#### 11.3.2. Bảng latest value

```sql
CREATE TABLE telemetry.telemetry_latest
(
    machine_id   LowCardinality(String),
    tag_code     LowCardinality(String),
    value_num    Float64,
    value_bool   UInt8,
    value_text   String,
    value_type   LowCardinality(String),
    unit         LowCardinality(String),
    status_code  LowCardinality(String),
    is_good      UInt8,
    event_time   DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(event_time)
ORDER BY (machine_id, tag_code);
```

#### 11.3.3. Materialized view tổng hợp theo phút

```sql
CREATE MATERIALIZED VIEW telemetry.telemetry_1m_mv
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(bucket)
ORDER BY (machine_id, tag_code, bucket)
AS SELECT
    toStartOfMinute(event_time)      AS bucket,
    machine_id,
    tag_code,
    any(tag_name)                   AS tag_name,
    any(unit)                       AS unit,
    avg(value_num)                  AS avg_value,
    min(value_num)                  AS min_value,
    max(value_num)                  AS max_value,
    argMax(value_num, event_time)   AS last_value,
    count()                         AS sample_count,
    countIf(is_good = 1)            AS good_count,
    countIf(is_good = 0)            AS bad_count
FROM telemetry.telemetry_raw
WHERE value_num IS NOT NULL
GROUP BY bucket, machine_id, tag_code;
```

#### 11.3.4. Ví dụ query

```sql
-- Tốc độ thực tế của 1 máy trong 1 giờ
SELECT
    toStartOfMinute(event_time) AS t,
    argMax(value_num, event_time) AS speed
FROM telemetry.telemetry_raw
WHERE machine_id = 'L01_FILLER_01'
  AND tag_code = 'FILL.L01.CURRENTSPEED'
  AND event_time >= now() - INTERVAL 1 HOUR
GROUP BY t
ORDER BY t;
```

### 11.4. Phương án C — MinIO + Parquet

**Phù hợp nhất cho lưu trữ raw lâu dài, giá rẻ.**

#### 11.4.1. Cấu trúc lưu trữ

```
s3://industrial-telemetry-raw/
├── dt=2026-11-11/
│   ├── part-00000.parquet
│   ├── part-00001.parquet
│   └── ...
├── dt=2026-11-12/
└── _SUCCESS
```

Partition theo **ngày** (`dt=YYYY-MM-DD`) — chuẩn Hive, mọi engine đọc được.

#### 11.4.2. Schema Parquet

```python
# Định nghĩa schema (dùng pyarrow hoặc Avro schema file)
telemetry_raw_schema = {
    "eventId":       "string",     # UUID
    "eventType":     "string",
    "schemaVersion": "string",
    "eventTime":     "timestamp[ms, tz=UTC]",
    "system":        "string",
    "channel":       "string",
    "device":        "string",
    "nodeId":        "string",
    "serverTimestamp": "timestamp[ms, tz=UTC]",
    "plantId":       "string",
    "lineId":        "string",
    "processId":     "string",
    "machineId":     "string",
    "machineType":   "string",
    "equipmentCode": "string",
    "tagName":       "string",
    "tagCode":       "string",
    "tagType":       "string",
    "value":         "double",     # NULL nếu không phải số
    "valueType":     "string",
    "unit":          "string",
    "statusCode":    "string",
    "isGood":        "boolean",
    "sourceSystem":  "string",     # kepware / simulator
}
```

**Vấn đề của Parquet: `value` là union type.** Parquet không có kiểu "số hoặc chuỗi
tùy ý". Ba cách xử lý:

| Cách | Cách làm | Đánh giá |
|---|---|---|
| A. Cột `value` kiểu `double` | Chuỗi → `null`, boolean → 0/1 | Đơn giản, mất thông tin string |
| B. **3 cột `value_num` / `value_bool` / `value_text`** ✅ | Giữ nguyên cả 3 miền | Khuyến nghị — nhất quán với §11.2 và §11.3 |
| C. Cột `value` kiểu `string` + cột `value_num` kiểu `double` | Cả bản gốc lẫn bản số | Tốn gấp đôi, nhưng tiện cho audit |

⇒ Dùng **cách B**, giống hệt schema DB ở §11.2 và §11.3 → cùng một logic đọc cho
cả 3 nơi.

#### 11.4.3. Quy tắc nén

| Mức | Kích thước | Tốc độ đọc | Khuyến nghị |
|---|---|---|---|
| `snappy` | 1× | Rất nhanh | Mặc định cho dữ liệu truy vấn thường xuyên |
| `zstd` | ~3–5× nhỏ hơn | Nhanh | ✅ **Khuyến nghị cho raw** |
| `gzip` | ~4× nhỏ hơn | Chậm nhất | Chỉ khi tương thích công cụ cũ |

**Ước lượng dung lượng:**

```
400 event/s × 86 400 s/ngày = 34,560,000 event/ngày
× ~250 byte/event (Parquet + zstd, đã lược bớt metadata dư) ≈ 8.6 GB/ngày
× 365 ngày ≈ 3.1 TB/năm
```

⇒ Với 3.1 TB/năm, MinIO rẻ hơn nhiều so với giữ chi tiết trong DB.

#### 11.4.4. Đọc lại bằng DuckDB (không cần Spark)

```sql
-- Query trực tiếp file Parquet trên MinIO/S3
SELECT
    date_trunc('hour', event_time) AS t,
    machine_id,
    avg(value_num) AS avg_speed
FROM read_parquet('s3://industrial-telemetry-raw/dt=2026-11-*/*.parquet',
                   hive_partitioning = 1)
WHERE tag_code = 'FILL.L01.CURRENTSPEED'
  AND is_good = true
GROUP BY 1, 2
ORDER BY 1;
```

DuckDB đọc Parquet trên S3 **rất nhanh** và không cần Spark cluster — rất hợp cho
bài tập lớn.

### 11.5. So sánh & khuyến nghị

| Tiêu chí | TimescaleDB | ClickHouse | MinIO + Parquet |
|---|---|---|---|
| Ghi nhanh | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Query tương tác | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ (cần DuckDB/Spark) |
| Giá lưu dài hạn | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Giữ 1–2 năm chi tiết | ⭐⭐ (tốn) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Độ phức tạp vận hành | ⭐⭐⭐⭐ (quen rồi) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Phù hợp đồng đội | Postgres sẵn có | Học mới | Học mới |

#### 11.5.1. Khuyến nghị cho bài tập lớn này

> **Chọn: ClickHouse (raw + tổng hợp) + MinIO/Parquet (archive)**
>
> Lý do:
> 1. Tần suất ~400 eps × 404 tag là khối lượng mà PostgreSQL thuần sẽ khó chịu
>    (34,5M dòng/ngày). ClickHouse xử lý thoải mái. *(Xem ghi chú tần suất ở §1 —
>    con số này là kịch bản trung tính, cần đo lại trên dữ liệu thật.)*
> 2. ClickHouse có materialized view → tổng hợp theo phút/giờ gần như miễn phí.
> 3. MinIO giữ raw lâu dài với giá rẻ, phục vụ backfill khi cần.
> 4. DuckDB đọc Parquet trực tiếp → nhóm BI có thể tự query archive mà không cần
>    đụng vào hạ tầng chính.

**Phương án B (ít công sức hơn, chấp nhận được):**

> **TimescaleDB + MinIO/Parquet** — nếu nhóm đã có Postgres sẵn và thời gian làm
> bài tập có hạn. Dùng hypertable + continuous aggregate; query phút/giờ vẫn
> nhanh.

**Phương án C (nhanh nhất để demo):**

> **Chỉ TimescaleDB, không cần MinIO** — chấp nhận giới hạn retention 90 ngày.
> Nhanh nhất để có dữ liệu truy vấn được, phù hợp khi trình bày.

#### 11.5.2. Ước lượng dung lượng (tất cả phương án)

> ⚠️ **Các con số dưới đây dựa trên kịch bản ~400 event/s** (34,5M dòng/ngày).
> Xem ghi chú tần suất ở §1: nếu dữ liệu thật biến động nhiều hơn, tần suất có
> thể lên tới ~1 100 event/s → **nhân đôi số dòng và dung lượng**.
> Nhóm phía sau nên đo lại trên dữ liệu thật trước khi chốt hạ tầng.

| Tầng | Rows/ngày | Ước lượng | Ghi chú |
|---|---|---|---|
| Kafka (7 ngày) | 34,5M | ~10–15 GB/ngày | `acks=all`, `compression=gzip` |
| ClickHouse raw (365 ngày) | 34,5M | ~3–5 TB | `LowCardinality` + `zstd` giúp nhiều |
| ClickHouse 1m aggregate | ~1M/ngày | ~100 MB/ngày | 36× nhỏ hơn raw |
| ClickHouse 1h aggregate | ~36K/ngày | ~5 MB/ngày | |
| TimescaleDB raw (90 ngày) | 34,5M | ~40–60 GB | ước lượng sơ bộ, cần đo thực tế |
| MinIO Parquet (365 ngày) | 34,5M | ~2,5–3 TB | zstd |

#### 11.5.3. Cấu hình Kafka consumer cho sink

```properties
# Đọc từ đầu topic (nếu muốn backfill dữ liệu cũ)
auto.offset.reset=earliest
# Commit theo batch — giảm overhead
enable.auto.commit=false
max.poll.records=2000
max.poll.interval.ms=300000
# Xử lý message lỗi: đưa sang DLQ thay vì làm cả partition dừng
```

**Về DLQ (Dead Letter Queue):** nếu một message không parse được (ví dụ schema đổi mà
consumer chưa kịp update), **đừng** để nó làm chết consumer — ghi nó vào topic
`industrial.telemetry.dlq` cùng lý do, rồi đi tiếp.

---

## 12. Code mẫu consumer

### 12.1. Python — đọc và in

```python
import json
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "industrial.telemetry",
    bootstrap_servers=["localhost:9092"],
    group_id="my-consumer",
    auto_offset_reset="earliest",
    enable_auto_commit=False,
    key_deserializer=lambda k: k.decode("utf-8") if k else None,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
)

for record in consumer:
    msg = record.value
    print(
        f"[{record.partition}:{record.offset}] "
        f"{msg['eventTime']} {msg['machine']['machineId']} "
        f"{msg['tag']['tagName']} = {msg['measurement']['value']} "
        f"{msg['measurement']['unit'] or ''} "
        f"({msg['quality']['statusCode']})"
    )
    consumer.commit()
```

### 12.2. Python — dedup bằng `eventId`

```python
import json
from kafka import KafkaConsumer

seen: set[str] = set()
MAX_SEEN = 500_000

consumer = KafkaConsumer(
    "industrial.telemetry",
    bootstrap_servers=["localhost:9092"],
    group_id="dedup-consumer",
    auto_offset_reset="earliest",
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
)

for record in consumer:
    msg = record.value
    event_id = msg["eventId"]

    if event_id in seen:
        continue                     # trùng → bỏ qua
    seen.add(event_id)
    if len(seen) > MAX_SEEN:
        seen = set(list(seen)[-MAX_SEEN // 2:])   # cắt bớt

    # ... xử lý message ...
```

### 12.3. Python — ghi vào TimescaleDB

```python
import json
import psycopg2
from kafka import KafkaConsumer

conn = psycopg2.connect(
    host="localhost", port=5432,
    dbname="telemetry", user="telemetry", password="secret",
)
cur = conn.cursor()

consumer = KafkaConsumer(
    "industrial.telemetry",
    bootstrap_servers=["localhost:9092"],
    group_id="timescale-writer",
    auto_offset_reset="earliest",
    enable_auto_commit=False,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
)

BATCH = 1000
batch = []

for record in consumer:
    m = record.value
    meas, qual = m["measurement"], m["quality"]

    # Chỉ lưu dữ liệu sản xuất — bỏ qua dữ liệu giả lập (SIMULATION_MODE).
    if m["source"]["system"] != "kepware":
        continue

    value_num = value_bool = value_text = None
    if qual["statusCode"] != "Bad":
        if meas["valueType"] == "Boolean":
            value_bool = meas["value"]
        elif meas["valueType"] == "String":
            value_text = meas["value"]
        else:
            value_num = meas["value"]

    batch.append((
        m["eventTime"], m["eventId"],
        m["machine"]["machineId"], m["tag"]["tagCode"], m["tag"]["tagName"],
        m["tag"]["tagType"],
        value_num, value_bool, value_text, meas["valueType"], meas["unit"],
        qual["statusCode"], qual["isGood"],
        m["plant"]["plantId"], m["plant"]["lineId"], m["plant"]["processId"],
        m["machine"]["machineType"], m["machine"]["equipmentCode"],
        m["source"]["channel"], m["source"]["nodeId"], m["source"]["serverTimestamp"],
        m["source"]["system"],
    ))

    if len(batch) >= BATCH:
        _flush(cur, batch)
        conn.commit()
        batch = []

if batch:
    _flush(cur, batch)
    conn.commit()


def _flush(cur, rows):
    cur.executemany("""
        INSERT INTO telemetry_raw (
            event_time, event_id, machine_id, tag_code, tag_name, tag_type,
            value_num, value_bool, value_text, value_type, unit,
            status_code, is_good,
            plant_id, line_id, process_id, machine_type, equipment_code,
            channel, node_id, server_time, source_system
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (event_time, event_id) DO NOTHING
    """, rows)
```

### 12.4. Flink — dedup theo `eventId`

```java
// Dedup theo eventId, state tự xoá sau 2 giờ
public class EventIdDedup extends KeyedProcessFunction<String, TelemetryEvent, TelemetryEvent> {

    private transient ValueState<String> lastEventId;

    @Override
    public void open(Configuration parameters) {
        lastEventId = getRuntimeContext().getState(
            new ValueStateDescriptor<>("lastEventId", String.class));
    }

    @Override
    public void processElement(TelemetryEvent event, Context ctx, Collector<TelemetryEvent> out)
            throws Exception {
        String previous = lastEventId.value();
        if (event.eventId.equals(previous)) {
            return;                       // trùng → bỏ qua
        }
        lastEventId.update(event.eventId);

        // Hẹn giờ xoá state sau 2 giờ
        ctx.timerService().registerEventTimeTimer(
            event.eventTime.toInstant().plus(Duration.ofHours(2)));

        out.collect(event);
    }

    @Override
    public void onTimer(long timestamp, OnTimerContext ctx, Collector<TelemetryEvent> out) {
        lastEventId.clear();
    }
}
```

**Lưu ý về state TTL:** nếu dùng RocksDB state backend, hãy đặt
`state.ttl` và bật incremental checkpointing — nếu không, state sẽ phình to theo
thời gian.

### 12.5. Kiểm tra nhanh dữ liệu trong Kafka

```bash
# Xem 5 message đầu (không cần code)
kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic industrial.telemetry \
  --from-beginning --max-messages 5 \
  --property print.key=true \
  --property key.separator=" | "
```

```bash
# Đếm số message
kafka-run-class.sh kafka.tools.GetOffsetShell \
  --bootstrap-server localhost:9092 --topic industrial.telemetry
```

---

## 13. Checklist bàn giao

### 13.1. Phía nhận (Data Platform / Flink)

- [ ] Tạo consumer với group id riêng, `auto.offset.reset=earliest` nếu cần backfill.
- [ ] Deserialize `key` để lấy `machineId` không cần parse JSON.
- [ ] Kiểm tra `schemaVersion` — bỏ qua field lạ, hỗ trợ version cũ.
- [ ] Xử lý `measurement.value = null` (không ép về 0).
- [ ] Lọc `quality.statusCode != 'Good'` khi tính trung bình.
- [ ] Dedup bằng `eventId` (unique key ở DB, hoặc state TTL 2h ở Flink).
- [ ] Dùng `eventTime` (không phải thời điểm nhận) cho mọi windowing / time-bucket.
- [ ] Thiết lập DLQ cho message không parse được.
- [ ] **Lọc `source.system == 'kepware'`** nếu topic có thể chứa dữ liệu giả lập
      (`SIMULATION_MODE=true`) — không tính dữ liệu demo vào KPI sản xuất.
- [ ] Dựng bảng `latest value` để dashboard trạng thái hiện tại.

### 13.2. Phía Middleware (đã xong)

- [x] Đọc metadata từ `TAG_FOLDER/<Channel>/<Device>.csv` + `equipment_map.json`
- [x] Chuẩn hóa message theo contract §4
- [x] Ép kiểu 3 tầng, số nguyên lớn nhất `Long` (Int64)
- [x] `eventId` UUIDv5 tất định
- [x] Dedup: baseline snapshot + LRU cache
- [x] Chất lượng: `Good` / `Uncertain` / `Bad`, `Bad` → `value = null`
- [x] Gửi Kafka: `acks=all`, `retries=10`, `max_in_flight=1`, `key = machineId`
- [x] Reconnect: backoff `1→2→5→10→20→30s`, single-flight, inactivity guard
- [x] Thread isolation: callback thread ≠ worker thread
- [x] Partition: 8 partition, không rỗng, spread 2–6 máy
- [x] Chế độ giả lập (`SIMULATION_MODE=true`): không cần Kepware, sinh dữ liệu
      đúng contract cho 404 tag / 26 máy — xem README §3.6
- [x] Self-test offline: `python tools/selftest.py` → 68/68 pass
- [x] Self-test chế độ giả lập: `python tools/simulation_test.py` → 29/29 pass

### 13.3. Câu hỏi cần làm rõ với nhóm phía sau

| # | Câu hỏi | Gợi ý |
|---|---|---|
| 1 | Kafka retention bao nhiêu ngày? | 7 ngày baseline; lịch sử dài hơn ở tầng lưu trữ |
| 2 | Có cần topic riêng cho quality event? | Hiện tại gộp chung `industrial.telemetry` (1 event type) |
| 3 | Có cần topic riêng cho `MachineState`? | Nếu nhóm Flink cần độ trễ cực thấp cho trạng thái máy |
| 4 | Có dùng `equipmentCode` để join MES? | Đã có sẵn trong message |
| 5 | Có cần thêm field vào message? | Tăng `schemaVersion`, consumer cũ vẫn đọc được |
| 6 | Topic có dùng chung cho dữ liệu giả lập không? | **Hiện có** — chế độ `SIMULATION_MODE=true` ghi vào cùng topic, phân biệt bằng `source.system = "simulator"`. Nếu nhóm phía sau muốn topic riêng thì báo để middleware tách topic. |

---

## Phụ lục — File liên quan

| File | Nội dung |
|---|---|
| `industrial_telemetry_kepware_middleware_kafka_design.md` | Design spec đầy đủ (kiến trúc, chốt lý thuyết) |
| `IndustrialTelemetry.Middleware/` | Source code middleware |
| `IndustrialTelemetry.Middleware/README.md` | Hướng dẫn chạy middleware (bao gồm chế độ giả lập §3.6) |
| `IndustrialTelemetry.Middleware/services/simulator.py` | Nguồn dữ liệu giả lập — dùng khi `SIMULATION_MODE=true` |
| `metadata/README.md` | **Hướng dẫn import CSV vào Kepware** (cho người vận hành) |
| `metadata/catalog.json` | Catalog 26 máy / 404 tag (nguồn chân lý) |
| `metadata/equipment_map.json` | Map `Channel.Device` → metadata máy |
| `metadata/TAG_FOLDER/` | 26 file CSV 20 cột — **middleware đọc lúc chạy** |
| `metadata/KEPWARE_IMPORT/` | 26 file CSV 17 cột — **dùng để import vào Kepware** |
| `tools/generate_tag_csv.py` | Sinh CSV + equipment_map từ catalog |
| `tools/generate_kepware_import_csv.py` | Sinh bộ CSV 17 cột để import Kepware |
| `tools/validate_kepware_import_csv.py` | Kiểm tra bộ import trước khi nạp |
| `tools/validate_metadata.py` | Kiểm tra tính nhất quán metadata |
