# Thiết kế dữ liệu công nghiệp chuẩn hóa

## Kepware → Middleware → Apache Kafka

**Phiên bản:** 2.0 (sửa đổi so với bản 1.0)
**Ngày:** 11/11/2026
**Trạng thái:** Baseline đã chốt — sẵn sàng triển khai
**Phạm vi:** Mô hình nhà máy, line/công đoạn/máy, tag catalog, tầng mapping
metadata, canonical message schema, Kafka topic/partition và logic mô phỏng.

**Quyết định đã chốt (xem §1.4):**

| # | Quyết định | Nguồn |
|---|-----------|-------|
| 1 | Metadata lấy theo Vinamilk: **CSV tag + JSON catalog** | Giữ tinh túy middleware Vinamilk, mở rộng thêm trường |
| 2 | **`device` chính là `machine`**; `machineId` của tài liệu này = tên device | Sửa theo chốt của nhóm |
| 3 | **Một `eventType` duy nhất**, không phân lớp tag | Middleware không phân loại tag — xem §1.2 |
| 4 | `eventId` = **UUID v5 deterministic** (hash từ nội dung event) | Chốt theo khuyến nghị — hỗ trợ dedup |
| 5 | Không durable spool ở baseline; giữ hành vi middleware hiện tại | Ưu tiên tốc độ, ghi nhận rủi ro tại §12 |
| 6 | NodeId theo chuẩn Vinamilk 3 cấp: `ns=2;s={channel}.{device}.{tag}` | Sửa theo chốt của nhóm |

---

## 1. Mục tiêu và nguyên tắc thiết kế

Tài liệu này thống nhất mô hình dữ liệu giả lập và hợp đồng dữ liệu giữa
Kepware, Middleware và Kafka. Mục tiêu là để các thành viên có thể độc
lập xây dựng simulator, cấu hình Kepware, viết Middleware và phát triển
consumer mà không tự đặt tên máy/tag/schema khác nhau.

### 1.1. Phạm vi của Middleware

Middleware chỉ làm các việc sau:

1.  Kết nối/nhận dữ liệu từ Kepware OPC UA.
2.  Nhận notification hoặc cập nhật tag do Kepware cung cấp.
3.  Ánh xạ tag nguồn sang định danh chuẩn đã thống nhất.
4.  Giữ nguyên giá trị, kiểu dữ liệu, đơn vị, timestamp và quality; bổ sung
    metadata cần thiết.
5.  Tạo **một Kafka record cho mỗi tag update** và gửi đi ngay.
6.  Ghi nhận lỗi gửi, retry và trạng thái backlog theo chính sách
    reliability.

Middleware **không**: - Tự polling/scan tag theo timer ứng dụng. - Tự
cấu hình scan rate hoặc sampling interval. - Chờ gom đủ tag của một
máy. - Gom nhiều tag thành một snapshot/batch message ở tầng ứng dụng. -
Tính OEE, sản lượng nghiệp vụ, chất lượng sản phẩm hay join dữ liệu
MES/QMS. - Tự bịa giá trị thay thế khi tag BAD/UNCERTAIN.

**Cấu hình scan rate, sampling interval, publishing interval, deadband
và queue của OPC UA được quản lý ở Kepware/OPC UA configuration.**
Middleware chỉ tiêu thụ các cập nhật Kepware phát ra.

Lưu ý: OPC UA Subscription vẫn có publishing cycle; một Publish response
có thể chứa nhiều notification. Middleware cần tách từng
notification/tag update thành một Kafka record riêng. Không đợi hết một
Publish response mới xử lý toàn bộ theo kiểu gom batch nghiệp vụ. Kafka
client có thể tối ưu network request nội bộ, nhưng mỗi Kafka record vẫn
là một tag update độc lập.

### 1.2. Cách lấy dữ liệu: cứ đọc được gì, gửi hết

**Quyết định:** Middleware **không phân loại tag**, **không tự polling**,
**không quyết định tần suất**. Mọi thứ Kepware phát ra, Middleware đều
gửi sang Kafka.

```
Kepware quyết định: scan rate, sampling interval, publishing interval,
deadband, queue size, cấu hình data-change vs exception-reporting
        │
        ▼
Middleware chỉ: nhận notification → chuẩn hóa → gửi Kafka (1 record / 1 tag update)
```

| Trách nhiệm | Thuộc về |
|---|---|
| Quyết định tag có được đọc không, đọc bao lâu một lần | **Kepware** |
| Phát notification khi giá trị đổi hay khi đủ chu kỳ | **Kepware** |
| Chuẩn hóa giá trị, kiểu dữ liệu, đơn vị, timestamp, quality | **Middleware** |
| Bổ sung metadata máy, sinh `eventId`, gửi Kafka | **Middleware** |
| Gom theo partition, đảm bảo thứ tự theo máy | **Kafka** |

**Hệ quả — những gì không còn tồn tại:**

-   Không có trường `acquisitionClass` trong message.
-   Không có hàng đợi ưu tiên REALTIME/PERIODIC.
-   Không có logic "chỉ phát khi giá trị đổi" phân biệt theo lớp.

**Điều này giải quyết triệt để một nghịch lý của bản 1.0.** Bản đó đòi
phân loại REALTIME/PERIODIC ở tầng middleware, nhưng tần suất lại do
Kepware quyết định. Kết quả là middleware biết "tag này là REALTIME"
nhưng không làm gì khác biệt với nó — vì cơ chế phát nằm ở Kepware.
Phân loại đó chỉ có tác dụng là **tài liệu**, không phải logic.

**Vẫn giữ `acquisitionClass` trong CSV — nhưng chỉ để hướng dẫn người
vận hành cấu hình Kepware**, không đưa vào message. Cột này là gợi ý:
"tag này nên cấu hình data-change, tag kia nên cấu hình theo chu kỳ".

**Còn cột `Scan Rate`?** CSV export từ Kepware có sẵn cột này (giá trị
`100` = 100ms trong file CSV của Vinamilk). Ở project mới, người vận hành
cấu hình trực tiếp trên Kepware, nên **không cần** đọc `Scan Rate` từ
CSV. Xem §8.3.


### 1.3. Nguyên tế thực tế

-   Tag đặc thù phụ thuộc chức năng máy. Filler có áp suất/lưu lượng
    chiết; capper có torque; seamer có seam parameters; case packer có
    carton jam và bottles-per-case.
-   Không gán một tag cho máy nếu máy không đo, tính toán hoặc nhận biết
    được thông tin đó.
-   Một số thông số có thể đến từ thiết bị inspection chuyên dụng thay
    vì PLC của máy chính.
-   Các dải giá trị trong tài liệu là **dải mô phỏng đề xuất**, không
    phải giới hạn kỹ thuật của một model máy thương mại cụ thể.
-   Nhà máy giả lập là một mô hình logic; không tuyên bố đang tích hợp
    với một nhà máy hoặc MES/QMS thực tế.

### 1.4. Các quyết định đã chốt

Những điểm dưới đây là quyết định của nhóm, không mở lại thảo luận.

**Q1 — Tầng mapping metadata (theo Vinamilk).**
Metadata của Middleware lấy từ **CSV tag** + **JSON catalog** trên disk,
không đọc SQL Server và không phụ thuộc Redis. Bản gốc Vinamilk đọc CSV
Kepware export và `equipment_map.json`; bản mới giữ cùng cấu trúc nhưng
**bổ sung các trường còn thiếu** (`Data Type`, `Eng Units`, `machineType`,
`lineId`, `processId`, `plantId`, enum mapping). Chi tiết ở §8.

**Q2 — `device` chính là `machine`.**
Trong hệ Kepware, mỗi thiết bị là một `device` nằm trong một `channel`.
Trong tài liệu này, `machineId` **chính là** tên `device` đó. Không có
hai định danh song song cho cùng một máy. `machineCode` là mã nghiệp vụ
tùy chọn, do người vận hành định nghĩa trong catalog.

Ký hiệu dùng xuyên suốt tài liệu:

| Khái niệm tài liệu này | Khái niệm Kepware | Ví dụ |
|---|---|---|
| `machineId` | `device` | `L01_FILLER_01` |
| `lineId` | `channel` | `LINE_01` |
| `tag` | `Tag Name` | `MachineState` |
| `nodeId` | — | `ns=2;s=LINE_01.L01_FILLER_01.MachineState` |

**Q3 — Một `eventType` duy nhất.**
`eventType = "machine.telemetry"` cho **mọi** tag update, không phân biệt
loại. Không tách `machine.tag.changed` / `machine.tag.sampled`. Lý do:

-   Mọi tag đều là "một tag update" — không có gì về mặt schema để
    phân biệt, vì `measurement.value` vẫn cùng kiểu.
-   Tách 2 `eventType` buộc Flink phải duy trì 2 stream và union lại về
    cùng một logic → phức tạp mà không thu được gì.
-   Không cần `acquisitionClass` trong message: tần suất đã do Kepware
    quyết định, middleware không làm gì khác biệt theo lớp (xem §1.2).

**Q4 — `eventId` deterministic (UUID v5).**
`eventId` được tính từ nội dung event, không phải UUID v4 ngẫu nhiên.
Công thức (§5.6). Hệ quả: cùng một sự kiện phát ra nhiều lần (reconnect
replay, retry) sẽ mang **cùng `eventId`** → downstream dedup được chính
xác. Điều này đáp ứng yêu cầu "duplicate detection" của đề bài.

**Q5 — Không durable spool ở baseline.**
Giữ hành vi middleware hiện tại: hàng đợi trong RAM, fire-and-forget với
callback kiểm tra lỗi. Rủi ro mất dữ liệu khi Kafka outage hoặc process
restart được **ghi nhận tường minh** tại §12.2 và phải được đo và báo
cáo trong phần đánh giá.

**Q6 — NodeId 3 cấp theo chuẩn Vinamilk.**
`ns=2;s={channel}.{device}.{tag}`. Ví dụ:
`ns=2;s=LINE_01.L01_FILLER_01.MachineState`.

Lưu ý: `Laird.OPCUAServer.Net` sinh NodeId **4 cấp** theo mẫu
`{Channel}.{Device}.{Group}.{TagName}`. Nếu dùng server đó thay Kepware
thật thì phải sửa §8.3 cho khớp. Baseline giả định **Kepware thật**, do
nhóm tự cấu hình.

---

## 2. Mô hình nhà máy

### 2.1. Tổng quan

Nhà máy sản xuất đồ uống với ba line:

| Line ID | Sản phẩm/bao bì | Đặc điểm |
|---------|------------------|-----------|
| `LINE_01` | Đồ uống có gas, chai PET | Có thổi chai PET, chiết rót có gas, đóng nắp |
| `LINE_02` | Nước tinh khiết, chai PET | Có thổi chai PET, chiết rót nước không gas, đóng nắp |
| `LINE_03` | Đồ uống đóng lon nhôm | Cấp lon, rửa lon, chiết lon, ghép mí lon |

Có một cụm CIP dùng chung, không thuộc riêng line nào.

**Điều chỉnh về tính thực tế:** Hai line PET dùng preform và máy stretch
blow moulder để tạo chai tại line. Không dùng depalletizer chai rỗng làm
máy đầu line trong baseline này. Line lon sử dụng can depalletizer và
seamer; seamer không được gọi là capper.

### 2.2. Luồng công đoạn

#### LINE_01 — Carbonated PET

`Preform Feeding → Stretch Blow Moulding → Bottle Air Conveying → Bottle Rinsing → Carbonated Filling → Capping → Labelling → Date Coding → Case Packing`

#### LINE_02 — Purified Water PET

`Preform Feeding → Stretch Blow Moulding → Bottle Air Conveying → Bottle Rinsing → Still Water Filling → Capping → Labelling → Date Coding → Case Packing`

#### LINE_03 — Aluminium Can

`Can Depalletizing → Can Rinsing → Can Filling → Can Seaming → Date Coding → Can Inspection → Case Packing`

#### Shared Utility — CIP

`CIP Tank / Heating / Chemical Dosing / Circulation / Return`

CIP được mô phỏng như một cụm thiết bị dùng chung phục vụ vệ sinh các
đường ống/bồn/thiết bị. Chỉ đưa các tag cấp skid vào Kafka; chưa mô
phỏng đầy đủ từng van và nhánh đường ống.

### 2.3. Danh sách máy

Cột `device` chính là `machineId` (Q2). Cột `machineType` là enum chuẩn
dùng trong schema (P1 của bản 1.0 — đã bổ sung).

| Line / khu vực | Process ID | `device` = `machineId` | `machineType` | Loại máy |
|----------------|-----------|----------------------|---------------|---------|
| LINE_01 | `PREFORM_FEEDING` | `L01_PREFEED_01` | `PREFORM_FEEDER` | Preform Feeder |
| LINE_01 | `BLOW_MOULDING` | `L01_BLOWER_01` | `STRETCH_BLOW_MOULDER` | PET Stretch Blow Moulder |
| LINE_01 | `BOTTLE_CONVEYING` | `L01_AIRCONV_01` | `AIR_CONVEYOR` | Bottle Air Conveyor |
| LINE_01 | `RINSING` | `L01_RINSER_01` | `BOTTLE_RINSER` | Bottle Rinser |
| LINE_01 | `FILLING` | `L01_FILLER_01` | `CARBONATED_FILLER` | Carbonated Beverage Filler |
| LINE_01 | `CAPPING` | `L01_CAPPER_01` | `SCREW_CAPPER` | Screw Capper |
| LINE_01 | `LABELLING` | `L01_LABELER_01` | `BOTTLE_LABELER` | Bottle Labeller |
| LINE_01 | `CODING` | `L01_CODER_01` | `DATE_CODER` | Inkjet/Laser Date Coder |
| LINE_01 | `CASE_PACKING` | `L01_CASEPACKER_01` | `CASE_PACKER` | Case Packer |
| LINE_02 | `PREFORM_FEEDING` | `L02_PREFEED_01` | `PREFORM_FEEDER` | Preform Feeder |
| LINE_02 | `BLOW_MOULDING` | `L02_BLOWER_01` | `STRETCH_BLOW_MOULDER` | PET Stretch Blow Moulder |
| LINE_02 | `BOTTLE_CONVEYING` | `L02_AIRCONV_01` | `AIR_CONVEYOR` | Bottle Air Conveyor |
| LINE_02 | `RINSING` | `L02_RINSER_01` | `BOTTLE_RINSER` | Bottle Rinser |
| LINE_02 | `FILLING` | `L02_FILLER_01` | `STILL_FILLER` | Still Water Filler |
| LINE_02 | `CAPPING` | `L02_CAPPER_01` | `SCREW_CAPPER` | Screw Capper |
| LINE_02 | `LABELLING` | `L02_LABELER_01` | `BOTTLE_LABELER` | Bottle Labeller |
| LINE_02 | `CODING` | `L02_CODER_01` | `DATE_CODER` | Inkjet/Laser Date Coder |
| LINE_02 | `CASE_PACKING` | `L02_CASEPACKER_01` | `CASE_PACKER` | Case Packer |
| LINE_03 | `CAN_DEPALLETTIZING` | `L03_CANDEPAL_01` | `CAN_DEPALLETIZER` | Can Depalletizer |
| LINE_03 | `RINSING` | `L03_CANRINSER_01` | `CAN_RINSER` | Can Rinser |
| LINE_03 | `FILLING` | `L03_CANFILLER_01` | `CAN_FILLER` | Beverage Can Filler |
| LINE_03 | `SEAMING` | `L03_SEAMER_01` | `CAN_SEAMER` | Can Seamer |
| LINE_03 | `CODING` | `L03_CANCODER_01` | `DATE_CODER` | Can Date Coder |
| LINE_03 | `INSPECTION` | `L03_CANINSPECT_01` | `CAN_INSPECTION` | Can Inspection System |
| LINE_03 | `CASE_PACKING` | `L03_CASEPACKER_01` | `CASE_PACKER` | Can Case Packer |
| SHARED | `CIP` | `CIP_SKID_01` | `CIP_SKID` | Central CIP Skid |

**Tổng:** 25 máy trên 3 line + 1 cụm CIP dùng chung = **26 asset/machine
endpoint** được mô phỏng. `plantId` của toàn bộ là `PLANT_01`.

### 2.4. Quy mô dữ liệu dự kiến

| Chỉ số | Giá trị |
|--------|---------|
| Số máy | 26 |
| Số tag | **404** |
| Tag REALTIME (trạng thái, cờ, enum) | **177** |
| Tag PERIODIC (giá trị đo, counter) | **227** |
| Trong đó: cờ `Boolean` | 87 |
| Trong đó: enum / số đếm nhỏ (`Int`) | 99 |
| Trong đó: giá trị đo (`Float`) | 131 |
| Trong đó: bộ đếm tích luỹ (`Long`) | 87 |
| Tag trung bình mỗi máy | 15,5 (thuộc khoảng 10–20 của đề bài) |
| Tag/máy thấp nhất – cao nhất | 13 (`L0*_CODER_01`, `L01/L02_AIRCONV_01`) – 18 (filler, blower, case packer) |
| Tần suất | **Do Kepware quyết định** — xem §1.2 |
| Tổng events/s ở tần suất mặc định | ~227 (chỉ tag giá trị đo, 1 Hz) → ~400 (nếu tất cả tag đều đổi) |
| Tổng events/s ở chế độ stress | 500 – 1.000 (tăng scan rate tại Kepware) |
| Số partition Kafka | **8** (xem §7.3) |
| Events/partition ở stress | ~60 – 125 |

Tổng tag được tính bằng script từ catalog tại §4, **không phải ước lượng
tay** — mỗi dòng trong bảng §4.1 là một tag thực. Khi bổ sung hoặc bớt
tag, phải chạy lại script để cập nhật số liệu này.

---

## 3. Quy ước tag dùng chung

Các tag dưới đây được áp dụng cho máy khi có ý nghĩa vật lý/chức năng.
Không bắt buộc mọi máy phải có đủ tất cả tag chung.

| Tag | Data Type (Kepware) | Unit | Gợi ý cấu hình | Ý nghĩa / quy tắc |
|-----|-----------|------|----------------|------------------|
| `MachineState` | `Int` | — | REALTIME | Trạng thái tổng thể (enum §9.1) |
| `MachineMode` | `Int` | — | REALTIME | 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | `Boolean` | — | REALTIME | Mạch dừng khẩn đang tác động |
| `AlarmCode` | `Int` | — | REALTIME | 0 = không có alarm; mã khác 0 là alarm đang hoạt động |
| `Starved` | `Boolean` | — | REALTIME | Máy thiếu sản phẩm/nguyên liệu đầu vào |
| `Blocked` | `Boolean` | — | REALTIME | Đầu ra máy bị chặn do công đoạn sau/buffer |
| `CurrentSpeed` | `Float` | xem §4.1 | PERIODIC | Tốc độ thực tế; về 0 khi máy dừng |
| `DesignSpeed` | `Float` | xem §4.1 | PERIODIC | Tốc độ thiết kế/định mức mô phỏng |
| `TotalCounter` | `Long` | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | `Long` | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | `Long` | pcs | PERIODIC | Số đơn vị lỗi/loại ra do máy ghi nhận |

**Quy tắc:**

-   `CurrentSpeed` không được âm; nếu `MachineState` là
    STOPPED/FAULTED/MAINTENANCE thì tốc độ thường bằng 0.
-   `GoodCounter + DefectCounter` không nhất thiết bằng `TotalCounter` ở mọi
    máy nếu định nghĩa counter khác nhau. Với mỗi machine type phải ghi rõ
    đơn vị đếm là chai, lon, preform, thùng hay chu kỳ.
-   Counter tích lũy không reset ngẫu nhiên. Nếu mô phỏng reset, phải phát
    sự kiện trạng thái/khởi động và downstream cần nhận diện counter reset.
-   `Starved`/`Blocked` chỉ áp dụng cho máy có logic phát hiện tình trạng
    đầu vào/đầu ra. Không gán bừa cho coder hoặc thiết bị đo độc lập.
-   Các tag chung có thể được bỏ khỏi máy nếu không hợp lý về mặt thiết bị;
    danh mục ở phần 4 là danh sách áp dụng cụ thể. Ví dụ `DATE_CODER` không
    có `GoodCounter` (máy đóng mã không phân loại sản phẩm), `CIP_SKID`
    không có tốc độ và không có good/defect counter.

**Về `RuntimeHours`:** không thêm tag này. Thời gian chạy thực (runtime)
được **Flink tính** từ các chuyển trạng thái `MachineState` — đây là dữ
liệu dẫn xuất (derived), không nên nhét vào telemetry để tránh hai nguồn
sự thật cho cùng một đại lượng.

**Về năng lượng (`energy`):** đề bài §3.1.1 có nêu `energy`. Baseline bổ
sung `PowerConsumption` cho các máy tiêu thụ đáng kể (blower, filler, bơm
CIP) — xem §4. Không gán cho toàn bộ máy vì sẽ làm catalog rối mà không
phục vụ phân tích nào cụ thể.

## 4. Danh mục tag

### 4.1. Danh mục tag theo từng máy

Mỗi dòng dưới đây là **một dòng trong file CSV** của máy đó (`TAG_FOLDER/<Channel>/<Device>.csv`). Cột `Data Type` dùng **đúng tên kiểu của Kepware** (`Boolean`, `Int`, `Float`, `Long`...) để khớp với CSV export/import — xem §8.3.1.1. Cột `Gợi ý` là hướng dẫn cấu hình Kepware, không phải logic của middleware (§1.2).

#### `L01_PREFEED_01` — PREFORM_FEEDER (14 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | preform/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | preform/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `PreformFeedRate` | Float | Float | preform/min | PERIODIC | Tần suất cấp preform thực tế |
| `HopperLevel` | Float | Float | % | PERIODIC | Mức thay thế trong hopper |
| `HopperLevelLow` | Boolean | Boolean | - | REALTIME | True khi mức hopper dưới ngưỡng cần bổ sung |

#### `L01_BLOWER_01` — STRETCH_BLOW_MOULDER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `CycleTime` | Float | Float | s | PERIODIC | Thời gian một chu kỳ thổi chai |
| `BlowPressure` | Float | Float | bar | PERIODIC | Áp suất thổi trong khu thổi chai |
| `HeaterTemp` | Float | Float | degC | PERIODIC | Nhiệt độ heater thổi PET |
| `MoldTemp` | Float | Float | degC | PERIODIC | Nhiệt độ khuôn |
| `CavityCount` | Int | Int32 | - | PERIODIC | Số khuôn ép trong khuôn |
| `BottleWeight` | Float | Float | g | PERIODIC | Khối lượng chai chai rỗng |
| `PowerConsumption` | Float | Float | kW | PERIODIC | Công suất tiêu thụ tính theo mốc thời gian |

#### `L01_AIRCONV_01` — AIR_CONVEYOR (13 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | m/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | m/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `AirPressure` | Float | Float | bar | PERIODIC | Áp suất đường cấp khí nén |
| `AirFlowRate` | Float | Float | Nm3/h | PERIODIC | Lưu lượng khí nén |
| `MotorSpeed` | Float | Float | rpm | PERIODIC | Tốc độ động cơ hành |
| `PowerConsumption` | Float | Float | kW | PERIODIC | Công suất tiêu thụ |

#### `L01_RINSER_01` — BOTTLE_RINSER (16 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `RinseWaterPressure` | Float | Float | bar | PERIODIC | Áp suất nước rửa |
| `RinseWaterTemp` | Float | Float | degC | PERIODIC | Nhiệt độ nước rửa |
| `RinseWaterFlowRate` | Float | Float | m3/h | PERIODIC | Lưu lượng nước rửa |
| `NozzlePressure` | Float | Float | bar | PERIODIC | Áp suất vò phun |
| `CIPPhase` | Int | Int32 | - | REALTIME | Pha CIP hiện tại (enum mục 0-4) |

#### `L01_FILLER_01` — CARBONATED_FILLER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `FillLevel` | Float | Float | % | PERIODIC | Mức chiết rót chai |
| `FillRate` | Float | Float | bottles/min | PERIODIC | Tốc độ chiết rót thực tế |
| `HeadCount` | Int | Int32 | - | PERIODIC | Số đầu chiết |
| `CO2Pressure` | Float | Float | bar | PERIODIC | Áp suất CO2 |
| `CO2FlowRate` | Float | Float | Nm3/h | PERIODIC | Lưu lượng CO2 |
| `ProductTemp` | Float | Float | degC | PERIODIC | Nhiệt độ sản phẩm |
| `PowerConsumption` | Float | Float | kW | PERIODIC | Công suất tiêu thụ |

#### `L01_CAPPER_01` — SCREW_CAPPER (15 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `Torque` | Float | Float | Nm | PERIODIC | Mô-men xoắn vặn nắp |
| `CapFeedRate` | Float | Float | caps/min | PERIODIC | Tần suất cấp nắp |
| `CapMissing` | Boolean | Boolean | - | REALTIME | True khi phát hiện thiếu nắp |
| `TorqueHigh` | Boolean | Boolean | - | REALTIME | True khi mô-men vặn nắp vượt ngưỡng |

#### `L01_LABELER_01` — BOTTLE_LABELER (15 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `LabelRollRemaining` | Float | Float | m | PERIODIC | Chiều dài cuộn nhãn còn lại |
| `LabelApplyCount` | Long | Int64 | pcs | PERIODIC | Số nhãn đã dán |
| `LabelMissing` | Boolean | Boolean | - | REALTIME | True khi phát hiện thiếu nhãn |
| `LabelRollLow` | Boolean | Boolean | - | REALTIME | True khi cuộn nhãn sắp hết |

#### `L01_CODER_01` — DATE_CODER (13 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | pcs/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | pcs/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `PrintCount` | Long | Int64 | pcs | PERIODIC | Số mã đã in |
| `InkLevel` | Float | Float | % | PERIODIC | Mực mực in |
| `InkLow` | Boolean | Boolean | - | REALTIME | True khi mực mực thấp |
| `PrintQuality` | Int | Int32 | - | REALTIME | Chất lượng in (enum mục 0-2) |
| `NozzleHeight` | Float | Float | mm | PERIODIC | Độ cao vòi phun |

#### `L01_CASEPACKER_01` — CASE_PACKER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cases/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cases/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `CaseCount` | Long | Int64 | cases | PERIODIC | Số thùng đã đóng |
| `BottlesPerCase` | Int | Int32 | pcs | PERIODIC | Số chai trong một thùng |
| `CaseFormat` | Int | Int32 | - | REALTIME | Định dạng thùng (enum mục 0-2) |
| `PalletCount` | Long | Int64 | pallets | PERIODIC | Số pallet đã tạo |
| `FilmRemaining` | Float | Float | m | PERIODIC | Chiều dài màng gói còn lại |
| `FilmLow` | Boolean | Boolean | - | REALTIME | True khi màng gói sắp hết |
| `CaseJam` | Boolean | Boolean | - | REALTIME | True khi phát hiện kẹt thùng |

#### `L02_PREFEED_01` — PREFORM_FEEDER (14 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | preform/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | preform/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `PreformFeedRate` | Float | Float | preform/min | PERIODIC | Tần suất cấp preform thực tế |
| `HopperLevel` | Float | Float | % | PERIODIC | Mức thay thế trong hopper |
| `HopperLevelLow` | Boolean | Boolean | - | REALTIME | True khi mức hopper dưới ngưỡng cần bổ sung |

#### `L02_BLOWER_01` — STRETCH_BLOW_MOULDER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `CycleTime` | Float | Float | s | PERIODIC | Thời gian một chu kỳ thổi chai |
| `BlowPressure` | Float | Float | bar | PERIODIC | Áp suất thổi trong khu thổi chai |
| `HeaterTemp` | Float | Float | degC | PERIODIC | Nhiệt độ heater thổi PET |
| `MoldTemp` | Float | Float | degC | PERIODIC | Nhiệt độ khuôn |
| `CavityCount` | Int | Int32 | - | PERIODIC | Số khuôn ép trong khuôn |
| `BottleWeight` | Float | Float | g | PERIODIC | Khối lượng chai chai rỗng |
| `PowerConsumption` | Float | Float | kW | PERIODIC | Công suất tiêu thụ tính theo mốc thời gian |

#### `L02_AIRCONV_01` — AIR_CONVEYOR (13 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | m/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | m/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `AirPressure` | Float | Float | bar | PERIODIC | Áp suất đường cấp khí nén |
| `AirFlowRate` | Float | Float | Nm3/h | PERIODIC | Lưu lượng khí nén |
| `MotorSpeed` | Float | Float | rpm | PERIODIC | Tốc độ động cơ hành |
| `PowerConsumption` | Float | Float | kW | PERIODIC | Công suất tiêu thụ |

#### `L02_RINSER_01` — BOTTLE_RINSER (16 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `RinseWaterPressure` | Float | Float | bar | PERIODIC | Áp suất nước rửa |
| `RinseWaterTemp` | Float | Float | degC | PERIODIC | Nhiệt độ nước rửa |
| `RinseWaterFlowRate` | Float | Float | m3/h | PERIODIC | Lưu lượng nước rửa |
| `NozzlePressure` | Float | Float | bar | PERIODIC | Áp suất vò phun |
| `CIPPhase` | Int | Int32 | - | REALTIME | Pha CIP hiện tại (enum mục 0-4) |

#### `L02_FILLER_01` — STILL_FILLER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `FillLevel` | Float | Float | % | PERIODIC | Mức chiết rót chai |
| `FillRate` | Float | Float | bottles/min | PERIODIC | Tốc độ chiết rót thực tế |
| `HeadCount` | Int | Int32 | - | PERIODIC | Số đầu chiết |
| `WaterTemp` | Float | Float | degC | PERIODIC | Nhiệt độ nước chiết |
| `WaterConductivity` | Float | Float | uS/cm | PERIODIC | Độ dẫn nước |
| `FillingPressure` | Float | Float | bar | PERIODIC | Áp suất trong quá trình chiết |
| `ProductTemp` | Float | Float | degC | PERIODIC | Nhiệt độ sản phẩm |

#### `L02_CAPPER_01` — SCREW_CAPPER (15 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `Torque` | Float | Float | Nm | PERIODIC | Mô-men xoắn vặn nắp |
| `CapFeedRate` | Float | Float | caps/min | PERIODIC | Tần suất cấp nắp |
| `CapMissing` | Boolean | Boolean | - | REALTIME | True khi phát hiện thiếu nắp |
| `TorqueHigh` | Boolean | Boolean | - | REALTIME | True khi mô-men vặn nắp vượt ngưỡng |

#### `L02_LABELER_01` — BOTTLE_LABELER (15 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | bottles/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `LabelRollRemaining` | Float | Float | m | PERIODIC | Chiều dài cuộn nhãn còn lại |
| `LabelApplyCount` | Long | Int64 | pcs | PERIODIC | Số nhãn đã dán |
| `LabelMissing` | Boolean | Boolean | - | REALTIME | True khi phát hiện thiếu nhãn |
| `LabelRollLow` | Boolean | Boolean | - | REALTIME | True khi cuộn nhãn sắp hết |

#### `L02_CODER_01` — DATE_CODER (13 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | pcs/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | pcs/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `PrintCount` | Long | Int64 | pcs | PERIODIC | Số mã đã in |
| `InkLevel` | Float | Float | % | PERIODIC | Mực mực in |
| `InkLow` | Boolean | Boolean | - | REALTIME | True khi mực mực thấp |
| `PrintQuality` | Int | Int32 | - | REALTIME | Chất lượng in (enum mục 0-2) |
| `NozzleHeight` | Float | Float | mm | PERIODIC | Độ cao vòi phun |

#### `L02_CASEPACKER_01` — CASE_PACKER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cases/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cases/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `CaseCount` | Long | Int64 | cases | PERIODIC | Số thùng đã đóng |
| `BottlesPerCase` | Int | Int32 | pcs | PERIODIC | Số chai trong một thùng |
| `CaseFormat` | Int | Int32 | - | REALTIME | Định dạng thùng (enum mục 0-2) |
| `PalletCount` | Long | Int64 | pallets | PERIODIC | Số pallet đã tạo |
| `FilmRemaining` | Float | Float | m | PERIODIC | Chiều dài màng gói còn lại |
| `FilmLow` | Boolean | Boolean | - | REALTIME | True khi màng gói sắp hết |
| `CaseJam` | Boolean | Boolean | - | REALTIME | True khi phát hiện kẹt thùng |

#### `L03_CANDEPAL_01` — CAN_DEPALLETIZER (15 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `CanFeedRate` | Float | Float | cans/min | PERIODIC | Tần suất cấp lon |
| `LayerCount` | Int | Int32 | - | PERIODIC | Số lớp lon trên pallet |
| `PalletCount` | Long | Int64 | pallets | PERIODIC | Số pallet đã xử lý |
| `GripperFault` | Boolean | Boolean | - | REALTIME | True khi có lỗi cơ gia |

#### `L03_CANRINSER_01` — CAN_RINSER (16 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `RinseWaterPressure` | Float | Float | bar | PERIODIC | Áp suất nước rửa |
| `RinseWaterTemp` | Float | Float | degC | PERIODIC | Nhiệt độ nước rửa |
| `RinseWaterFlowRate` | Float | Float | m3/h | PERIODIC | Lưu lượng nước rửa |
| `NozzlePressure` | Float | Float | bar | PERIODIC | Áp suất vò phun |
| `CIPPhase` | Int | Int32 | - | REALTIME | Pha CIP hiện tại (enum mục 0-4) |

#### `L03_CANFILLER_01` — CAN_FILLER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `FillLevel` | Float | Float | % | PERIODIC | Mức chiết lọn |
| `FillRate` | Float | Float | cans/min | PERIODIC | Tốc độ chiết lọn thực tế |
| `HeadCount` | Int | Int32 | - | PERIODIC | Số đầu chiết |
| `CO2Pressure` | Float | Float | bar | PERIODIC | Áp suất CO2 |
| `CO2FlowRate` | Float | Float | Nm3/h | PERIODIC | Lưu lượng CO2 |
| `ProductTemp` | Float | Float | degC | PERIODIC | Nhiệt độ sản phẩm |
| `PowerConsumption` | Float | Float | kW | PERIODIC | Công suất tiêu thụ |

#### `L03_SEAMER_01` — CAN_SEAMER (16 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `SeamTorque` | Float | Float | Nm | PERIODIC | Mô-men xoắn tạo đường biên |
| `SeamPressure` | Float | Float | bar | PERIODIC | Áp suất tạo đường biên |
| `SeamQuality` | Int | Int32 | - | REALTIME | Chất lượng đường biên (enum mục 0-2) |
| `SeamDefectCount` | Long | Int64 | pcs | PERIODIC | Số đường biên không đạt |
| `CanVacuum` | Float | Float | kPa | PERIODIC | Áp suất chân không trong lon |

#### `L03_CANCODER_01` — DATE_CODER (13 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | pcs/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | pcs/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `PrintCount` | Long | Int64 | pcs | PERIODIC | Số mã đã in |
| `InkLevel` | Float | Float | % | PERIODIC | Mực mực in |
| `InkLow` | Boolean | Boolean | - | REALTIME | True khi mực mực thấp |
| `PrintQuality` | Int | Int32 | - | REALTIME | Chất lượng in (enum mục 0-2) |
| `NozzleHeight` | Float | Float | mm | PERIODIC | Độ cao vòi phun |

#### `L03_CANINSPECT_01` — CAN_INSPECTION (14 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cans/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `InspectionCount` | Long | Int64 | pcs | PERIODIC | Số lon đã kiểm tra |
| `DefectRate` | Float | Float | % | PERIODIC | Tỷ lệ lỗi của hàng gần nhất |
| `InspectResult` | Int | Int32 | - | REALTIME | Kết quả kiểm tra (enum mục 0-2) |
| `RejectReason` | Int | Int32 | - | REALTIME | Lý do loại (enum mục 0-4) |
| `CameraFault` | Boolean | Boolean | - | REALTIME | True khi lỗi camera kiểm tra |

#### `L03_CASEPACKER_01` — CASE_PACKER (18 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `CurrentSpeed` | Float | Float | cases/min | PERIODIC | Tốc độ thực tế hiện tại; về 0 khi máy dừng |
| `DesignSpeed` | Float | Float | cases/min | PERIODIC | Tốc độ thiết kế / định mức mô phỏng |
| `TotalCounter` | Long | Int64 | pcs | PERIODIC | Tổng số đơn vị máy đã xử lý, tích lũy |
| `GoodCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị đạt theo logic máy |
| `DefectCounter` | Long | Int64 | pcs | PERIODIC | Số đơn vị lỗi / loại ra do máy ghi nhận |
| `Starved` | Boolean | Boolean | - | REALTIME | True khi máy thiếu sản phẩm / nguyên liệu đầu vào |
| `Blocked` | Boolean | Boolean | - | REALTIME | True khi đầu ra máy bị chặn do công đoạn sau hoặc buffer đầy |
| `CaseCount` | Long | Int64 | cases | PERIODIC | Số thùng đã đóng |
| `CansPerCase` | Int | Int32 | pcs | PERIODIC | Số lon trong một thùng |
| `CaseFormat` | Int | Int32 | - | REALTIME | Định dạng thùng (enum mục 0-2) |
| `PalletCount` | Long | Int64 | pallets | PERIODIC | Số pallet đã tạo |
| `FilmRemaining` | Float | Float | m | PERIODIC | Chiều dài màng gói còn lại |
| `FilmLow` | Boolean | Boolean | - | REALTIME | True khi màng gói sắp hết |
| `CaseJam` | Boolean | Boolean | - | REALTIME | True khi phát hiện kẹt thùng |

#### `CIP_SKID_01` — CIP_SKID (14 tag)

| Tag | Data Type (Kepware) | OPC UA | Unit | Gợi ý | Ý nghĩa |
|---|---|---|---|---|---|
| `MachineState` | Int | Int32 | - | REALTIME | Trạng thái máy (enum mục 0-5) |
| `MachineMode` | Int | Int32 | - | REALTIME | Chế độ điều khiển: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE |
| `EmergencyStop` | Boolean | Boolean | - | REALTIME | True khi mạch dừng khẩn đang tác động |
| `AlarmCode` | Int | Int32 | - | REALTIME | 0 = không có alarm; giá trị khác 0 là mã alarm đang hoạt động |
| `TotalCounter` | Long | Int64 | cycles | PERIODIC | Tổng số chu kỳ CIP đã chạy |
| `TankTemp` | Float | Float | degC | PERIODIC | Nhiệt độ bể chứa CIP |
| `TankLevel` | Float | Float | % | PERIODIC | Mức bể chứa CIP |
| `Conductivity` | Float | Float | uS/cm | PERIODIC | Độ dẫn dung dịch CIP |
| `pH` | Float | Float | pH | PERIODIC | Chỉ số pH của dung dịch |
| `FlowRate` | Float | Float | m3/h | PERIODIC | Lưu lượng hồi lưu |
| `Pressure` | Float | Float | bar | PERIODIC | Áp suất đường hồi lưu |
| `ChemicalDose` | Float | Float | L | PERIODIC | Lượng hóa chất đã bổ sung |
| `HeatingOn` | Boolean | Boolean | - | REALTIME | True khi máy nưới đang bật |
| `CirculationOn` | Boolean | Boolean | - | REALTIME | True khi bơm hồi lưu đang chạy |

### 4.2. Tổng hợp số tag theo máy

| Máy | machineType | Số tag | REALTIME | PERIODIC |
|---|---|---|---|---|
| `L01_PREFEED_01` | PREFORM_FEEDER | 14 | 7 | 7 |
| `L01_BLOWER_01` | STRETCH_BLOW_MOULDER | 18 | 6 | 12 |
| `L01_AIRCONV_01` | AIR_CONVEYOR | 13 | 4 | 9 |
| `L01_RINSER_01` | BOTTLE_RINSER | 16 | 7 | 9 |
| `L01_FILLER_01` | CARBONATED_FILLER | 18 | 6 | 12 |
| `L01_CAPPER_01` | SCREW_CAPPER | 15 | 8 | 7 |
| `L01_LABELER_01` | BOTTLE_LABELER | 15 | 8 | 7 |
| `L01_CODER_01` | DATE_CODER | 13 | 6 | 7 |
| `L01_CASEPACKER_01` | CASE_PACKER | 18 | 9 | 9 |
| `L02_PREFEED_01` | PREFORM_FEEDER | 14 | 7 | 7 |
| `L02_BLOWER_01` | STRETCH_BLOW_MOULDER | 18 | 6 | 12 |
| `L02_AIRCONV_01` | AIR_CONVEYOR | 13 | 4 | 9 |
| `L02_RINSER_01` | BOTTLE_RINSER | 16 | 7 | 9 |
| `L02_FILLER_01` | STILL_FILLER | 18 | 6 | 12 |
| `L02_CAPPER_01` | SCREW_CAPPER | 15 | 8 | 7 |
| `L02_LABELER_01` | BOTTLE_LABELER | 15 | 8 | 7 |
| `L02_CODER_01` | DATE_CODER | 13 | 6 | 7 |
| `L02_CASEPACKER_01` | CASE_PACKER | 18 | 9 | 9 |
| `L03_CANDEPAL_01` | CAN_DEPALLETIZER | 15 | 7 | 8 |
| `L03_CANRINSER_01` | CAN_RINSER | 16 | 7 | 9 |
| `L03_CANFILLER_01` | CAN_FILLER | 18 | 6 | 12 |
| `L03_SEAMER_01` | CAN_SEAMER | 16 | 7 | 9 |
| `L03_CANCODER_01` | DATE_CODER | 13 | 6 | 7 |
| `L03_CANINSPECT_01` | CAN_INSPECTION | 14 | 7 | 7 |
| `L03_CASEPACKER_01` | CASE_PACKER | 18 | 9 | 9 |
| `CIP_SKID_01` | CIP_SKID | 14 | 6 | 8 |
| **Tổng** | — | **404** | **177** | **227** |

### 4.3. Thống kê kiểu dữ liệu

| Data Type (Kepware) | OPC UA tương ứng | Số tag | Dùng cho |
|---|---|---|---|
| `Float` | Float | 131 | Giá trị đo vật lý (áp suất, nhiệt độ, lưu lượng...) |
| `Int` | Int32 | 99 | Enum trạng thái, mã alarm, số đếm nhỏ không tích luỹ |
| `Boolean` | Boolean | 87 | Cờ trạng thái, alarm, sự kiện |
| `Long` | Int64 | 87 | Bộ đếm tích luỹ (sản lượng, số thùng, số pallet) |
| **Tổng** | — | **404** | |

### 4.4. Quy tắc vận hành của tag

| Quy tắc | Mô tả |
|---|---|
| Đơn vị đo | Dùng đúng đơn vị trong bảng. Middleware **không** quy đổi đơn vị, chỉ ghi kèm `unit` |
| Kiểu dữ liệu | Khai báo trong CSV là **tên kiểu Kepware**; Middleware ánh xạ sang OPC UA theo bảng §9.5 |
| Reset counter | Counter chỉ tăng, không reset ngẫu nhiên. Khi reset có chủ đích, phải phát kèm sự kiện trạng thái |
| `Starved` / `Blocked` | Chỉ gán cho máy có logic phát hiện đầu vào / đầu ra thực tế |
| Giá trị thiếu | Không tự bịa giá trị. Nếu Kepware trả trạng thái `BAD`, giữ nguyên quality và ghi `value: null` |
| Độ chính xác | Số thực làm tròn 6 chữ số thập phân trước khi ghi vào Kafka |
| Tần suất | **Do Kepware quyết định** — Middleware không cấu hình, không đếm, không lọc theo tần suất (§1.2) |
| `CIP_SKID` | Không có tốc độ và không có good/defect counter. `TotalCounter` của CIP mang đơn vị `cycles` |
| Counter | Bắt buộc kiểu `Long` (64-bit) — xem cảnh báo tràn giá trị tại §8.3.2 |

---

## 5. Canonical message schema

### 5.1. Nguyên tắc

1.  **Một record = một tag update.** Không gom nhiều tag vào một message.
2.  **Một `eventType` duy nhất:** `machine.telemetry`.
3.  **Tất cả trường luôn hiện diện.** Không có trường tùy chọn — trường
    không có giá trị thì `null`. Điều này giúp consumer viết được schema
    cố định (Avro/JSON Schema) mà không cần xử lý trường thiếu.
4.  **Đơn vị và kiểu dữ liệu đi kèm giá trị.** `value` không bao giờ
    đứng một mình; luôn có `valueType` và `unit`.
5.  **Timestamp theo UTC, ISO-8601.**

### 5.2. Schema đầy đủ

```json
{
  "eventId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
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

### 5.3. Giải thích từng trường

#### `eventId` — khóa dedup xuyên suốt hệ thống

UUID version 5 (SHA-1 based), tất định theo nội dung sự kiện:

```
eventId = uuid5(NAMESPACE_TELEMETRY, canonical_string)
canonical_string = f"{machineId}|{tagName}|{sourceTimestamp}|{value}|{statusCode}"
```

| Đặc tính | Giải thích |
|---|---|
| Tất định | Cùng sự kiện → cùng `eventId`, kể cả khi phát lại do reconnect hoặc retry |
| Không va chạm | Khác sự kiện → khác `eventId` (xác suất va chạm cực thấp) |
| Dùng được ở mọi tầng | Middleware sinh, Flink dedup, consumer đối chiếu, lưu trữ |

**Lưu ý về `sourceTimestamp`:** dùng timestamp nguồn từ Kepware
(`SourceTimestamp`), không dùng thời điểm Middleware nhận được. Nếu
dùng thời điểm nhận, mỗi lần reconnect sẽ sinh `eventId` khác → mất
khả năng dedup. Xem §6.4 về cơ chế loại bỏ baseline replay.

**Xung đột tiền điểm:** vì `eventId` chỉ gắn với nội dung giá trị, một
tag PERIODIC 1 Hz với giá trị **không đổi** sẽ sinh ra `eventId` giống
nhau ở các lần lặp liên tiếp. Hai hướng xử lý:

-   **Khuyến nghị (chọn):** Middleware chỉ phát event khi giá trị thực sự
    thay đổi (so sánh với giá trị cuối cùng đã gửi của tag đó). Điều này
    loại bỏ nhiễu 1 Hz và làm `eventId` thực sự là định danh sự kiện.
    Logic này **tương đương** với hành vi hiện có của middleware Laird
    (dedup theo `(normalized_value, timestamp)`).
-   **Phương án thay thế:** thêm `sequenceNumber` của Kepware vào
    `canonical_string`. Cách này chính xác hơn nhưng phụ thuộc cấu
    hình Kepware (sequence number phải tăng đơn điệu).

Baseline chọn hướng 1 (change-detection), đồng thời giữ cơ chế dedup
cache sẵn có.

#### `eventType`

Luôn là `"machine.telemetry"`. Xem Q3 ở §1.4.

#### `schemaVersion`

Cho phép thêm/bớt trường về sau mà không phá consumer. Consumer phải
kiểm tra version và bỏ qua trường lạ.

#### `eventTime`

Thời điểm sự kiện xảy ra theo quan điểm của hệ thống nguồn (Kepware),
UTC, ISO-8601 với milliseconds. Đây là trường Flink dùng cho windowing.

#### `source`

| Trường | Ý nghĩa |
|---|---|
| `system` | Nguồn gốc dữ liệu. Baseline: `"kepware"`. Giữ trường này để sau này thêm nguồn khác (PLC, simulator, MES) mà không đổi schema |
| `channel` | Channel Kepware chứa device. Tương ứng `lineId` |
| `device` | Device Kepware. Tương ứng `machineId` (Q2) |
| `nodeId` | NodeId đầy đủ, dùng để truy vết ngược về tag gốc khi cần |
| `serverTimestamp` | `ServerTimestamp` của Kepware. Dùng để đo độ trễ và phát hiện clock skew |

`eventTime` lấy từ `SourceTimestamp`; `serverTimestamp` giữ riêng để
không mất thông tin chẩn đoán.

#### `plant` và `machine`

Metadata phẳng (denormalized) để consumer không cần join với bảng
master data để biết `machineType` / `lineId`. Denormalize ở tầng
Middleware vì giá thành join lúc query lịch sử cao hơn nhiều so với
việc nhân 3–4 trường nhỏ vào mỗi record.

| Trường | Nguồn |
|---|---|
| `plantId` | Catalog (`equipment_map.json`) |
| `lineId` | Catalog — trùng `source.channel` ở baseline, giữ cả hai để tương lai channel không còn là line |
| `processId` | Catalog |
| `machineId` | Trùng `source.device` ở baseline |
| `machineType` | Catalog — enum ở §2.3 |
| `equipmentCode` | Catalog — mã nghiệp vụ tùy chọn |

#### `tag`

| Trường | Nguồn | Ghi chú |
|---|---|---|
| `tagName` | Tên tag trong Kepware | Khớp cột `Tag Name` của CSV |
| `tagCode` | CSV | Mã nghiệp vụ tùy chọn, ví dụ `FILL.L01.FILLLEVEL` |
| `tagType` | CSV | `ANALOG` / `DIGITAL` / `COUNTER` / `STRING` |

Cột `acquisitionClass` **không có trong message** — xem §1.2. Nó chỉ tồn
tại trong CSV để hướng dẫn cấu hình Kepware.

#### `measurement`

| Trường | Ý nghĩa |
|---|---|
| `value` | Giá trị đã chuẩn hóa. Kiểu native Python tương ứng `valueType`. Nếu status không Good → `null` |
| `valueType` | Tên kiểu OPC UA canonical: `Boolean`, `Int32`, `Int64`, `Float`, `Double`, `String` — xem bảng đầy đủ ở §9.5 |
| `unit` | Đơn vị từ CSV. `"-"` nghĩa là không có đơn vị (đặt `null` khi ghi Kafka) |

**Về `valueType`:** dùng đúng tên kiểu variant của OPC UA, không phải
tên kiểu ngôn ngữ (`float64`, `int`, `bool`). Consumer có thể dùng
thư viện OPC UA để parse lại mà không cần bảng tra riêng.

**Về `null`:** nếu Kepware trả `BAD` status, **không** ghi giá trị cũ
hoặc giá trị 0. Ghi `value: null` và `quality.isGood: false`. Đây là
quy tắc quan trọng để downstream không hiểu sai "máy dừng" là "máy lỗi".

#### `quality`

| Trường | Ý nghĩa |
|---|---|
| `statusCode` | Chuỗi trạng thái chuẩn hóa: `Good`, `Uncertain`, `Bad` |
| `isGood` | Boolean thuận tiện để filter nhanh |

Chuẩn hóa `StatusCode` OPC UA về 3 mức giúp lọc nhiễu mà vẫn giữ được
thông tin quan trọng. Chi tiết cơ chế ánh xạ ở §9.4.

### 5.4. Ví dụ message thực tế

**REALTIME — máy chuyển sang trạng thái lỗi:**

```json
{
  "eventId": "b2c3d4e5-6f70-4182-93a4-b5c6d7e8f901",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-11T09:15:32.412Z",
  "source": {
    "system": "kepware",
    "channel": "LINE_01",
    "device": "L01_FILLER_01",
    "nodeId": "ns=2;s=LINE_01.L01_FILLER_01.MachineState",
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
    "tagName": "MachineState",
    "tagCode": "FILL.L01.MACHINESTATE",
    "tagType": "DIGITAL"
  },
  "measurement": {
    "value": 3,
    "valueType": "Int32",
    "unit": null
  },
  "quality": {
    "statusCode": "Good",
    "isGood": true
  }
}
```

**PERIODIC — giá trị đo có chất lượng `Uncertain`:**

```json
{
  "eventId": "c3d4e5f6-7081-4293-a4b5-c6d7e8f90123",
  "eventType": "machine.telemetry",
  "schemaVersion": "1.0",
  "eventTime": "2026-11-11T09:15:33.001Z",
  "source": {
    "system": "kepware",
    "channel": "LINE_03",
    "device": "L03_CANFILLER_01",
    "nodeId": "ns=2;s=LINE_03.L03_CANFILLER_01.CO2Pressure",
    "serverTimestamp": "2026-11-11T09:15:33.000Z"
  },
  "plant": {
    "plantId": "PLANT_01",
    "lineId": "LINE_03",
    "processId": "FILLING"
  },
  "machine": {
    "machineId": "L03_CANFILLER_01",
    "machineType": "CAN_FILLER",
    "equipmentCode": "FILL-L03-01"
  },
  "tag": {
    "tagName": "CO2Pressure",
    "tagCode": "FILL.L01.CO2PRESSURE",
    "tagType": "ANALOG"
  },
  "measurement": {
    "value": null,
    "valueType": "Float",
    "unit": "bar"
  },
  "quality": {
    "statusCode": "Uncertain",
    "isGood": false
  }
}
```

### 5.5. Ví dụ nhiều tag của cùng một máy

Bốn record riêng biệt, cùng partition (vì cùng `machineId` → cùng key),
đúng thứ tự:

```json
{"eventId":"...","eventType":"machine.telemetry","eventTime":"2026-11-11T09:15:32.100Z","source":{"device":"L01_FILLER_01","nodeId":"ns=2;s=LINE_01.L01_FILLER_01.FillLevel",...},"tag":{"tagName":"FillLevel"},"measurement":{"value":87.5,"valueType":"Float","unit":"%"},...}
{"eventId":"...","eventType":"machine.telemetry","eventTime":"2026-11-11T09:15:32.200Z","source":{"device":"L01_FILLER_01","nodeId":"ns=2;s=LINE_01.L01_FILLER_01.FillRate",...},"tag":{"tagName":"FillRate"},"measurement":{"value":12400.0,"valueType":"Float","unit":"bottles/min"},...}
{"eventId":"...","eventType":"machine.telemetry","eventTime":"2026-11-11T09:15:32.300Z","source":{"device":"L01_FILLER_01","nodeId":"ns=2;s=LINE_01.L01_FILLER_01.MachineState",...},"tag":{"tagName":"MachineState"},"measurement":{"value":2,"valueType":"Int32","unit":null},...}
{"eventId":"...","eventType":"machine.telemetry","eventTime":"2026-11-11T09:15:32.400Z","source":{"device":"L01_FILLER_01","nodeId":"ns=2;s=LINE_01.L01_FILLER_01.AlarmCode",...},"tag":{"tagName":"AlarmCode"},"measurement":{"value":1042,"valueType":"Int32","unit":null},...}
```

Đây là bằng chứng cho **"một record = một tag update"**: 4 tag → 4
record, không gom. Consumer vẫn có thể gom lại theo `machineId` +
cửa sổ thời gian trong Flink nếu cần.

### 5.6. Thuật toán sinh `eventId`

```python
import uuid

# Namespace cố định cho project - KHÔNG đổi sau khi đã phát dữ liệu
TELEMETRY_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def build_event_id(machine_id: str, tag_name: str,
                   source_timestamp: str, value, status_code: str) -> str:
    """UUID v5 tất định từ nội dung sự kiện.

    source_timestamp: ISO-8601 string của SourceTimestamp (không phải thời điểm nhận).
    value: giá trị đã chuẩn hóa (str/int/float/bool/None).
    """
    canonical = "|".join([
        machine_id,
        tag_name,
        source_timestamp,
        "" if value is None else str(value),
        status_code,
    ])
    return str(uuid.uuid5(TELEMETRY_NS, canonical))
```

**Lưu ý:** `str(value)` phải ổn định. Với số thực, dùng giá trị **đã
làm tròn 6 chữ số thập phân** (sau khi normalize) — nếu không, `87.5`
và `87.5000000001` sẽ sinh ra hai `eventId` khác nhau cho cùng một sự kiện.

**Lưu ý về namespace:** UUID dùng làm namespace phải được **chốt cố định
và ghi vào tài liệu này**. Đổi namespace giữa các lần chạy sẽ làm
dedup của Flink hỏng.

---

## 6. Kiến trúc Middleware

### 6.1. Sơ đồ luồng

```
┌─────────────────────────────────────────────────────────────────┐
│                        KEPWARE (OPC UA Server)                   │
│  Channel LINE_01 / LINE_02 / LINE_03 / SHARED                    │
│  Device = Machine, Tag theo catalog §4                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ OPC UA Subscription
                            │ (MonitoredItem, data change notification)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MIDDLEWARE (tiến trình Python)                │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │ Metadata     │   │ OPC UA       │   │ Value Worker       │  │
│  │ Loader       │   │ Client       │   │ (1 thread)         │  │
│  │              │   │              │   │                    │  │
│  │ đọc CSV +    │   │ SubHandler   │──▶│ value_queue        │  │
│  │ equipment_   │   │ callback     │   │ (maxsize 200000)   │  │
│  │ map.json     │   │ thread       │   │                    │  │
│  └──────┬───────┘   └──────────────┘   └─────────┬──────────┘  │
│         │                                           │             │
│         │ metadata index                           ▼             │
│         │ (nodeId → tag info)            ┌────────────────────┐  │
│         │                                 │ Normalizer        │  │
│         │                                 │ - ép kiểu native   │  │
│         │                                 │ - round 6 decimals │  │
│         │                                 │ - sinh eventId     │  │
│         │                                 │ - dedup cache      │  │
│         │                                 └─────────┬──────────┘  │
│         │                                           │             │
│         │                                           ▼             │
│         │                                 ┌────────────────────┐  │
│         │                                 │ Kafka Producer     │  │
│         │                                 │ key = machineId    │  │
│         │                                 │ acks=all, retry=10 │  │
│         │                                 └─────────┬──────────┘  │
└───────────────────────────────────────────────────┼─────────────┘
                                                    │
                                                    ▼
                                    ┌────────────────────────────┐
                                    │  Kafka: industrial.telemetry│
                                    │  8 partitions, key=machineId│
                                    └────────────────────────────┘
```

### 6.2. Hai luồng (thread) tách biệt

| Luồng | Vai trò | Cơ chế |
|---|---|---|
| **OPC UA callback thread** | Nhận notification từ Kepware, đẩy payload thô vào `value_queue` | `put_nowait`, không chặn |
| **Value worker thread** | Lấy payload từ queue, normalize, dedup, gửi Kafka | `get(timeout=1)` |

**Vì sao tách hai luồng:** nếu gửi Kafka trực tiếp trong callback, một
lần Kafka chậm sẽ chặn luồng callback của thư viện OPC UA. Khi luồng
callback bị chặn, Kepware bắt đầu queue notification và cuối cùng bỏ
dữ liệu. Tách luồng giữ độ trễ của callback ở mức microsecond.

Đây chính là cơ chế `value_event_worker` trong middleware Laird, giữ nguyên.

**Một hàng đợi duy nhất, không phân loại.** Middleware không tách queue
theo loại tag. Lý do: tần suất phát ra do Kepware quyết định (§1.2), nên
middleware không biết trước cái nào là "sự kiện" và cái nào là "giá trị
đo" để ưu tiên. Tách queue sẽ đòi middleware phỏng đoán ý định của
Kepware — dễ sai, và thêm độ phức tạp không mang lại lợi ích đo được.

Tải ở tần suất mặc định (~230–400 events/s) thấp hơn rất nhiều so với
khả năng xử lý của một luồng Python gửi Kafka. Nếu stress test (§10.5)
cho thấy nghẽn ở tần suất cao, đó là lúc cân nhắc thêm — và khi đó phải
giữ nguyên thứ tự trong từng queue để không phá tính đơn thứ tự theo máy.

### 6.3. Hàng đợi trong RAM và backpressure

Giữ nguyên mô hình hiện tại (Q5):

| Tham số | Giá trị | Ý nghĩa |
|---|---|---|
| `VALUE_QUEUE_MAXSIZE` | 200000 | Sức chứa hàng đợi giá trị |
| `VALUE_QUEUE_WARN_THRESHOLD` | 50000 | Ngưỡng cảnh báo log |
| `VALUE_QUEUE_GET_TIMEOUT_SEC` | 1 | Timeout khi chờ item |

**Hành vi khi đầy hàng đợi:** `put_nowait` ném `queue.Full` → callback
ghi log cảnh báo và **bỏ qua** event đó. Không chặn luồng OPC UA.

**Đánh giá rủi ro:** ở tần suất chuẩn, 200000 slot trong khi tốc độ
sinh event là ~400/s nghĩa là hàng đợi chứa được **≈ 8 phút** dữ liệu
nếu Kafka hoàn toàn chết. Thực tế sẽ không bao giờ đầy trừ khi Kafka
sập lâu. Ở chế độ stress (1000 eps), đầy trong ~3 phút.

Đây là điểm yếu đã biết của mô hình không có durable spool — ghi nhận
tường minh tại §12.2.

### 6.4. Chống trùng lặp (dedup)

Cơ chế hiện có của middleware Laird, giữ nguyên về nguyên tắc:

**Cache gửi gần nhất, LRU có giới hạn:**

| Tham số | Giá trị |
|---|---|
| `NODE_CACHE_MAX` | 50000 |
| Cấu trúc | `OrderedDict[nodeId → dedup_key]` |

**Khóa dedup:** `(normalized_value, timestamp)` — dùng timestamp khi
`USE_TIMESTAMP_IN_RECONNECT_DEDUP` bật, nếu không chỉ dùng
`normalized_value`.

**Chuẩn hóa giá trị để so sánh** (`normalize_compare_value`):

| Kiểu | Quy tắc so sánh |
|---|---|
| `bool` | `True` → `"1"`, `False` → `"0"` |
| Số 0/1 | `"0"` / `"1"` |
| Chuỗi | `strip()` + `casefold()`; `"true"`/`"1"` → `"1"`, `"false"`/`"0"` → `"0"` |
| Khác | `str(value).strip().casefold()` |

**Chuẩn hóa giá trị để ghi** (`normalize_value`):

| Kiểu | Quy tắc |
|---|---|
| `float` | `round(value, 6)` |
| `bytes` | Decode UTF-8, lỗi thì `str(value)` |
| Khác | Giữ nguyên |

**Baseline snapshot:** ngay sau khi subscribe thành công, hệ thống chụp
giá trị hiện tại của tất cả node làm baseline, và **không phát** các
giá trị baseline đó ra Kafka. Mục đích: loại bỏ dữ liệu cũ mà Kepware
gửi lại ngay khi subscribe — đây là nguồn phát sinh nhiễu lớn nhất sau
reconnect.

Sau khi reconnect, dedup cache được xóa (`clear_kafka_dedup_cache`) vì
timestamp nguồn đã thay đổi.

### 6.5. Máy trạng thái kết nối

Giữ nguyên máy trạng thái của middleware Laird:

```
CONNECTING ──▶ SUBSCRIBING ──▶ DEGRADED ──▶ STABLE
     ▲             │              │           │
     └─────────────┴──────────────┴───────────┘
                   RECONNECTING
```

| Trạng thái | Ý nghĩa | Hành vi |
|---|---|---|
| `CONNECTING` | Đang mở session OPC UA | Chưa subscribe |
| `SUBSCRIBING` | Đang tạo MonitoredItem hàng loạt | Đếm tỷ lệ subscribe thành công |
| `DEGRADED` | Kết nối còn nhưng có lỗi vận hành | Vẫn nhận dữ liệu, cảnh báo |
| `STABLE` | Ổn định, không lỗi OPC UA trong `STABLE_QUIET_SECONDS` | Gửi Kafka bình thường |
| `RECONNECTING` | Đang hard-reset client + subscription | Tạm dừng gửi |

**Cổng chặn trạng thái (`should_publish_kafka`):** chỉ gửi Kafka khi
trạng thái là `STABLE` và kết nối còn active. Sự kiện phát ra trong
`DEGRADED` bị bỏ qua — đây là hành vi có chủ đích: gửi dữ liệu lúc
kết nối chập chờn tạo nhiễu lớn hơn giá trị của nó.

**Chu kỳ reconnect (hard reset):**

| Bước | Hành động |
|---|---|
| 1 | `subscription.delete()` → `client.disconnect()` |
| 2 | Xóa cache node, xóa dedup cache |
| 3 | Tạo `Client` mới, `session_timeout = 600000` |
| 4 | Nạp lại tag từ metadata |
| 5 | Subscribe hàng loạt, đếm tỷ lệ thành công |
| 6 | Chụp baseline snapshot |
| 7 | Vào `DEGRADED`, chờ đủ `STABLE_QUIET_SECONDS` không lỗi → `STABLE` |

**Backoff:** `(1s, 2s, 5s, 10s, 20s, 30s)` — giữ nguyên, đặt ở mức cuối
(30s) sau khi hết các bước. Có jitter nhỏ để tránh nhiều middleware
reconnect đồng loạt.

**Single-flight:** `ReconnectController._enter_reconnect()` đảm bảo chỉ
một chu kỳ reconnect chạy tại một thời điểm. Nhiều lời gọi `request()`
trong lúc đang reconnect bị bỏ qua.

**Inactivity guard:** nếu đã có datachange trước đó nhưng sau đó im lặng
quá `INACTIVITY_TIMEOUT_S`, kích hoạt reconnect. Đây là lưới an toàn
phụ cho trường hợp socket còn mở nhưng server không gửi gì.

### 6.6. Retry khi gửi Kafka

Cấu hình producer (giữ nguyên giá trị hiện tại):

| Tham số | Giá trị | Tác dụng |
|---|---|---|
| `acks` | `all` | Chỉ coi là thành công khi đủ ISR xác nhận → không mất dữ liệu |
| `retries` | 10 | Số lần thử lại khi gặp lỗi có thể retry |
| `max_in_flight_requests_per_connection` | 1 | Đảm bảo thứ tự, tránh reorder khi retry |
| `linger_ms` | 50 | Gom record trong 50ms trước khi gửi |
| `batch_size` | 65536 | Ngưỡng byte để đóng batch |

**Mỗi `producer.send()` được gắn callback thành công và callback lỗi.**
Callback lỗi ghi log với `nodeId`, giá trị và exception. Đây là điểm
cần lưu ý: khi `send()` thất bại hoàn toàn (không phải lỗi mạng có thể
retry), dữ liệu đó **bị mất** trong baseline. Xem §12.2.

**Ghi chú về `enable_idempotence`:** với `acks=all`, `retries=10` và
`max_in_flight=1`, producer đã đạt ngữ nghĩa idempotent của Kafka.
Bật thêm `enable_idempotence=True` là tùy chọn — cần kiểm tra phiên bản
`kafka-python` hỗ trợ. Baseline giữ cấu hình hiện tại.

### 6.7. Batching: tầng ứng dụng vs tầng mạng

Đây là điểm dễ nhầm nhất, nên tách rõ:

| Tầng | Hành vi | Quyết định |
|---|---|---|
| **Ứng dụng** (Middleware) | **1 Kafka record cho mỗi tag update**. Không gom nhiều tag thành một record | Giữ nguyên |
| **Mạng** (Kafka client) | Client tự gom record cùng partition thành batch trước khi gửi, theo `linger_ms` và `batch_size` | Nhờ cấu hình producer |

**Kết quả:** về mặt logic, mỗi tag update là một message riêng biệt —
consumer nhận được từng record, có thể xử lý độc lập. Về mặt hiệu năng
mạng, client vẫn gom batch nên không lãng phí round-trip.

Đây là lý do **không** cần thêm lớp batching ở tầng ứng dụng. Lớp đó
sẽ phá vỡ nguyên tắc "một record = một tag update" và làm giảm khả
năng truy vết, dedup theo `eventId`, và xử lý REALTIME với độ trễ thấp.

### 6.8. Xử lý lỗi chất lượng dữ liệu

| Tình huống | Hành vi |
|---|---|
| `StatusCode` = Good | Gửi bình thường |
| `StatusCode` = Uncertain | Gửi, nhưng `quality.statusCode = "Uncertain"`, `isGood = false`, `value` vẫn giữ |
| `StatusCode` = Bad | Gửi với `value = null`, `isGood = false` |
| Chuyển Bad → Good | Ghi log `[QUALITY RECOVERED]`, phát lại giá trị |
| NodeId không tồn tại | Bỏ qua, ghi log cảnh báo, đưa vào `invalid_tag_set` |

**Nguyên tắc:** không bao giờ bịa giá trị thay thế cho dữ liệu hỏng.
Một giá trị `null` + `isGood: false` nói rõ "không biết", còn `0` nói
dối rằng "giá trị là 0".

### 6.9. Cấu trúc thư mục dự kiến

Kế thừa cách tổ chức module của Vinamilk (đã tách `core/`, `services/`,
`utils/`) và giữ phần xuất Kafka của Laird:

```
IndustrialTelemetry.Middleware/
├── config/
│   ├── settings.py              # Đọc biến môi trường, hợp nhất cấu hình
│   └── logging_config.py        # Console + file log theo ngày
├── core/
│   ├── tag_loader.py            # Đọc CSV tag, dựng NodeId, index metadata
│   ├── equipment_map.py         # Đọc equipment_map.json, map channel.device
│   ├── value_types.py           # Ánh xạ kiểu 3 tầng (Kepware → Python → OPC UA)
│   ├── subscription.py          # SubscriptionRegistry, SubHandler
│   ├── state_machine.py         # OpcConnectionState, ReconnectController
│   └── dedup.py                 # Dedup cache, baseline snapshot
├── services/
│   ├── opcua_client.py          # Kết nối, subscribe, reconnect cycle
│   ├── value_worker.py          # Thread đọc value_queue
│   ├── normalizer.py            # Ép kiểu, round, sinh eventId
│   └── kafka_publisher.py       # KafkaProducer wrapper
├── utils/
│   ├── status_codes.py          # Chuẩn hóa OPC UA StatusCode
│   ├── event_id.py              # Sinh UUID v5
│   └── time_utils.py            # ISO-8601 UTC
├── tools/
│   ├── selftest.py              # Self-test offline (59 check)
│   ├── integration_test.py      # Integration test end-to-end với mock (29 check)
│   ├── verify_doc.py            # Kiểm tra tài liệu bàn giao khớp catalog
│   ├── gen_tag_tables.py        # Sinh bảng tag Markdown từ catalog
│   ├── inject_tag_tables.py     # Chèn bảng tag vào tài liệu bàn giao
│   └── preview_message.py       # Sinh mẫu message từ metadata
├── main.py
├── requirements.txt
├── .env.example
└── README.md
```

**Vị trí metadata:** metadata dùng chung nằm ở thư mục anh em
`TichHopDuLieuLon_BaiTapLon/metadata/` (nguồn chân lý duy nhất cho CSV +
`equipment_map.json` + `catalog.json`). Middleware trỏ tới bằng:

```
TAG_FOLDER=../metadata/TAG_FOLDER
EQUIPMENT_MAP_FILE=../metadata/equipment_map.json
```

Nhờ vậy CSV chỉ tồn tại ở một chỗ — không lo trôi phiên bản giữa middleware và
các tool sinh tài liệu.

**Nguyên tắc phân tách:**

| Module | Trách nhiệm | Không được làm |
|---|---|---|
| `core/tag_loader.py` | Đọc CSV, dựng NodeId, index | Không kết nối OPC UA |
| `core/equipment_map.py` | Đọc JSON, join metadata | Không biết về OPC UA |
| `services/opcua_client.py` | Kết nối, subscribe, callback | Không gửi Kafka trực tiếp |
| `services/normalizer.py` | Chuẩn hóa giá trị, sinh `eventId` | Không truy cập hàng đợi |
| `services/kafka_publisher.py` | Gửi Kafka, callback lỗi | Không biết về OPC UA |

Ranh giới này cho phép test từng phần độc lập: `normalizer` test không
cần OPC UA, `kafka_publisher` test không cần Kepware.

---

## 7. Thiết kế Kafka

### 7.1. Topic

| Thuộc tính | Giá trị |
|---|---|
| Tên topic | `industrial.telemetry` |
| Số partition | 8 |
| Replication factor | 1 (môi trường đơn broker) — production nên là 3 |
| Retention | `7d` (baseline), `30d` nếu cần khớp đề bài |
| Cleanup policy | `delete` |

**Đặt tên topic:** dùng `industrial.telemetry` — đủ cụ thể để không đụng
với topic khác, nhưng không gắn cứng vào `machine` để sau này có thể
thêm `industrial.telemetry.dlq` hoặc `industrial.alarm` mà không phá
quy ước.

### 7.2. Key và thứ tự

**Key = `machineId`**, serialize thành UTF-8 bytes:

```python
producer.send(
    "industrial.telemetry",
    key=str(message["machine"]["machineId"]).encode("utf-8"),
    value=message,
)
```

| Đặc tính | Hệ quả |
|---|---|
| Cùng máy → cùng partition | Thứ tự các event của một máy được bảo toàn |
| Máy khác → partition khác nhau | Xử lý song song theo máy |
| Phân bổ theo `murmur2` | Kafka dùng `murmur2(key) % numPartitions` |

**Vì sao key là `machineId` chứ không phải `nodeId`:**

-   Toàn bộ phân tích downstream (OEE, sản lượng, downtime) đều gom theo
    máy. Key theo máy giữ thứ tự thời gian của cả máy, cần thiết để
    tính "thời gian dừng" hay "chu kỳ sản xuất".
-   Nếu key theo `nodeId`, các event của cùng một máy sẽ nằm rải rác
    ở nhiều partition → mất thứ tự toàn cục của máy, và Flink phải
    gom lại bằng key mới.
-   Số tag trên một máy (13–18) không quá nhiều để một partition xử lý
    thoải mái.

### 7.3. Số partition: 8, và lý do

Đây là điểm bản 1.0 sai, cần nêu rõ. Con số "6 partition" trong bản 1.0
là **con số ước lượng theo cảm tính**, chưa được kiểm chứng. Khi tính
thật bằng thuật toán `murmur2` của Kafka trên 26 `machineId` thực tế:

| Số partition | Partition được dùng | Máy tối thiểu | Máy tối đa | Lệch | max/ideal | Đánh giá |
|---|---|---|---|---|---|---|
| 3 | 3 | 3 | 12 | 9 | 1,38 | Quá ít, 1 partition gánh 12 máy |
| 4 | 4 | 5 | 10 | 5 | 1,54 | Tốt nhất về cân bằng nhưng ít partition |
| 5 | 5 | 2 | 9 | 7 | 1,73 | Lệch |
| **6** | 6 | **1** | **9** | **8** | **2,08** | **Lệch nặng — bản 1.0 chọn số này** |
| **8** | **8** | **2** | **6** | **4** | **1,85** | **Cân bằng tốt, đủ partition để mở rộng** |
| 12 | 10 | 1 | 7 | 6 | 3,23 | 2 partition trống, còn lại lệch |
| 16 | 14 | 1 | 4 | 3 | 2,46 | Nhiều partition rỗng |

**Chọn 8 partition:**

| Tiêu chí | Đánh giá |
|---|---|
| Cân bằng tải | 8 partition: 2–6 máy/partition, lệch 4. Tốt nhất trong nhóm 5–10 partition |
| Không partition rỗng | Cả 8 partition đều có máy |
| Headroom | Tốc độ stress 1000 eps ÷ 8 = 125 eps/partition — chưa cần scale |
| Tương thích tăng trưởng | Nếu sau này mở rộng lên 50–100 máy, số partition cần tăng theo |

**Lưu ý quan trọng:** số partition của một topic Kafka **không thể giảm**.
Nếu cần tăng thì phải tạo topic mới và rebalance consumer. Vì vậy nên
chọn dư chút ngay từ đầu. Baseline 8 partition; nếu nhóm dự kiến mở
rộng lên 50–100 máy ngay thì nên dùng 12–16 ngay từ đầu — nhưng 12
partition theo phép tính trên có 2 partition rỗng, nên **16 partition**
là lựa chọn hợp lý hơn cho trường hợp mở rộng.

**Khuyến nghị cuối cùng:**

| Quy mô | Số partition |
|---|---|
| Baseline 26 máy (đề bài hiện tại) | **8** |
| Nếu mở rộng lên 50–100 máy | **16** (tạo topic mới, không giảm) |

**Ghi chú:** với 26 máy, sự lệch 2–6 máy/partition không ảnh hưởng đáng
kể về hiệu năng vì tổng tải (125 eps/partition ở chế độ stress) thấp hơn
nhiều so với khả năng của một partition. Số partition được chọn chủ yếu
để có đủ headroom và tránh partition rỗng.

**Bảng ánh xạ máy → partition (8 partition, key = `machineId`).** Tính
bằng `murmur2(machineId) & 0x7FFFFFFF % 8` — cùng thuật toán Kafka
dùng. Có thể kiểm chứng lại bằng `tools/check_partitioning.py`:

| Partition | Máy | Số máy |
|---|---|---|
| P0 | `L02_RINSER_01`, `L02_FILLER_01`, `L02_CAPPER_01` | 3 |
| P1 | `L02_LABELER_01`, `L03_CANDEPAL_01` | 2 |
| P2 | `L01_BLOWER_01`, `L01_RINSER_01`, `L01_CAPPER_01`, `L02_PREFEED_01`, `L02_AIRCONV_01`, `L02_CODER_01` | 6 |
| P3 | `L01_PREFEED_01`, `L03_CANCODER_01` | 2 |
| P4 | `L01_AIRCONV_01`, `L01_CODER_01`, `L03_SEAMER_01` | 3 |
| P5 | `L01_FILLER_01`, `L02_CASEPACKER_01`, `CIP_SKID_01` | 3 |
| P6 | `L01_CASEPACKER_01`, `L02_BLOWER_01`, `L03_CANFILLER_01`, `L03_CASEPACKER_01` | 4 |
| P7 | `L01_LABELER_01`, `L03_CANRINSER_01`, `L03_CANINSPECT_01` | 3 |

**Quan sát đáng chú ý:** `L02_FILLER_01` (máy nước tĩnh) và `L03_CANFILLER_01`
(máy chiết lon) rơi vào **hai partition khác nhau** (P0 và P6) — dù là hai
máy cùng công đoạn `FILLING`. Đây là hệ quả đúng của hashing: phân bổ
theo *máy*, không theo *công đoạn*. Nhưng vì phân tích downstream luôn
gom theo `machineId` (key Kafka) chứ không theo partition, nên điều này
không ảnh hưởng gì.

**Cũng lưu ý:** `CIP_SKID_01` nằm cùng partition P5 với `L01_FILLER_01`
và `L02_CASEPACKER_01`. Vì CIP là thiết bị dùng chung cho cả 3 line,
nó sẽ bị "gộp" vào luồng của 2 máy đó. Nếu sau này luồng CIP cần
xử lý riêng, phải tách nó thành topic riêng — không thể chỉ dựa vào
partition.

### 7.4. Cấu hình producer đầy đủ

```python
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS,           # ví dụ "localhost:9092"
    acks="all",
    retries=10,
    max_in_flight_requests_per_connection=1,
    linger_ms=50,
    batch_size=65536,
    value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
    key_serializer=lambda k: k,                 # đã encode sẵn
)
```

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `KAFKA_BROKERS` | `localhost:9092` | Địa chỉ broker |
| `KAFKA_TOPIC` | `industrial.telemetry` | Topic đích |
| `KAFKA_ACKS` | `all` | Mức xác nhận |
| `KAFKA_RETRIES` | `10` | Số lần retry |
| `KAFKA_MAX_IN_FLIGHT` | `1` | Số request chưa hoàn tất mỗi connection |
| `KAFKA_LINGER_MS` | `50` | Độ trễ gom batch |
| `KAFKA_BATCH_SIZE` | `65536` | Kích thước batch |
| `VALUE_QUEUE_MAXSIZE` | `200000` | Sức chứa hàng đợi giá trị |
| `VALUE_QUEUE_WARN_THRESHOLD` | `50000` | Ngưỡng cảnh báo tồn đọng |
| `NODE_CACHE_MAX` | `50000` | Sức chứa dedup cache |
| `USE_TIMESTAMP_IN_RECONNECT_DEDUP` | `true` | Có dùng timestamp trong khóa dedup |

### 7.5. Backpressure và giới hạn tốc độ

Không đặt `max_block_ms` hay rate limiter ở baseline. Lý do: khi Kafka
chậm, `producer.send()` sẽ block tối đa `max_block_ms` (mặc định
60.000ms) trong `send()` — nhưng lời gọi này xảy ra ở **value worker
thread**, không phải callback thread. Nên khi Kafka chậm:

1.  Callback thread vẫn đẩy được vào `value_queue` (RAM).
2.  Value worker chậm dần, hàng đợi dồn lên.
3.  Khi hàng đợi đầy → bắt đầu drop, và ghi log cảnh báo.

Đây là hành vi **có kiểm soát**: dữ liệu bị drop có log, có thể đo được,
không phải treo cả middleware. Đây là đánh đổi đã chốt ở Q5 và được
ghi nhận tại §12.2.

### 7.6. Topic Dead Letter

Chưa triển khai ở baseline. Nếu thêm sau, quy ước:

| Thuộc tính | Giá trị |
|---|---|
| Tên | `industrial.telemetry.dlq` |
| Nội dung | Message gốc + `dlqReason` + `dlqTimestamp` |
| Khi nào | Message không serialize được, hoặc vi phạm schema |

Lưu ý: message không serialize được gần như không xảy ra với schema cố
định, nên DLQ ở baseline có giá trị thấp. Giá trị thật sự của DLQ sẽ
là khi bổ sung enrichment từ master data.

### 7.7. Sơ đồ luồng dữ liệu đầy đủ

```
Kepware
  │
  ▼  OPC UA subscription (404 monitored items)
┌─────────────────────────────────────────────────────────┐
│ Middleware                                               │
│                                                          │
│  Callback thread ──▶ value_queue (RAM, 200000)          │
│                          │                               │
│                          ▼                               │
│                    Value worker                          │
│                          │                               │
│                          ├─▶ normalize_value()            │
│                          ├─▶ normalize_compare_value()    │
│                          ├─▶ dedup check                  │
│                          ├─▶ build_event_id()  [UUIDv5]   │
│                          └─▶ producer.send(key=machineId) │
└─────────────────────────────────────────────────────────┘
  │
  ▼  key = machineId, murmur2 → partition
┌─────────────────────────────────────────────────────────┐
│ Kafka: industrial.telemetry (8 partitions)              │
│                                                          │
│  partition 0: L01_*, L03_*   partition 4: L02_*, ...    │
│  (mỗi máy → đúng 1 partition → thứ tự theo máy)         │
└─────────────────────────────────────────────────────────┘
  │
  ▼
Flink (nhóm khác phụ trách): dedup theo eventId, window, aggregate
  │
  ├─▶ MinIO (raw Parquet)
  └─▶ PostgreSQL (bảng tổng hợp)
```

---

## 8. Tầng mapping metadata

### 8.1. Nguyên tắc

Metadata được lấy từ **file trên disk**, không truy vấn SQL Server, không
phụ thuộc Redis. Lý do:

-   Middleware phải khởi động được ngay cả khi SQL Server hoặc Redis
    đang lỗi. Nếu không có metadata thì không subscribe được, mà không
    subscribe thì không có dữ liệu.
-   Metadata là thứ thay đổi ít, nhưng phải **kiểm soát được** (version
    trong git, review được, rollback được).
-   Tách metadata khỏi hạ tầng giúp test middleware không cần dựng
    database.

Cấu trúc bám theo Vinamilk: **CSV cho tag, JSON cho mapping máy**.

### 8.2. Cây thư mục metadata

```
metadata/
├── TAG_FOLDER/
│   ├── LINE_01/
│   │   ├── L01_PREFEED_01.csv
│   │   ├── L01_BLOWER_01.csv
│   │   ├── L01_AIRCONV_01.csv
│   │   ├── L01_RINSER_01.csv
│   │   ├── L01_FILLER_01.csv
│   │   ├── L01_CAPPER_01.csv
│   │   ├── L01_LABELER_01.csv
│   │   ├── L01_CODER_01.csv
│   │   └── L01_CASEPACKER_01.csv
│   ├── LINE_02/
│   │   └── (9 file tương tự LINE_01)
│   ├── LINE_03/
│   │   └── (6 file)
│   └── SHARED/
│       └── CIP_SKID_01.csv
└── equipment_map.json
```

Quy ước giữ nguyên từ Vinamilk:

-   Thư mục con của `TAG_FOLDER` = **Channel** của Kepware.
-   Tên file CSV (không extension) = **Device** của Kepware.
-   `Device` = `machineId` (Q2).

**Về `SHARED`:** channel `SHARED` chứa CIP — dùng chung cho cả 3 line.
Trong `equipment_map.json`, CIP được gán `lineId = "SHARED"`.

### 8.3. Định dạng file CSV tag

Cột bắt buộc: `Tag Name`. Các cột khác là tùy chọn, nhưng **baseline
yêu cầu đủ** vì chúng được dùng để sinh message.

| Cột | Bắt buộc | Kiểu | Mô tả |
|---|---|---|---|
| `Tag Name` | ✅ | text | Tên tag trong Kepware. Thành phần cuối của NodeId |
| `TagCode` | ✅ | text | Mã nghiệp vụ. Dùng làm `tag.tagCode` trong message. Bản gốc Vinamilk bỏ qua dòng thiếu cột này |
| `TagType` | ⬜ | enum | `ANALOG` / `DIGITAL` / `COUNTER` / `STRING` |
| `Data Type` | ⬜ | Kepware | Kiểu dữ liệu theo **tên kiểu của Kepware**: `Boolean`, `Int`, `Float`, `Long`, `Word`, `DWord`, `String` — xem §8.3.1.1 |
| `Eng Units` | ⬜ | text | Đơn vị đo. `-` hoặc rỗng = không có đơn vị |
| `Acquisition Class` | ⬜ | enum | `REALTIME` / `PERIODIC` — **chỉ để hướng dẫn cấu hình Kepware, không đưa vào message** |
| `Description` | ⬜ | text | Mô tả tự do, không đưa vào Kafka |

**Mở rộng so với Vinamilk:** bản gốc chỉ dùng `Tag Name`, `TagType`,
`TagCode`. Bản này bổ sung `Data Type`, `Eng Units`, `Acquisition Class`
— đúng theo chốt P0-1: giữ cách đọc metadata của Vinamilk nhưng bổ
sung các trường còn thiếu, và định nghĩa chúng trong Middleware.

**Cột nào là bắt buộc trong thực tế:**

| Cột | Nếu thiếu |
|---|---|
| `Tag Name` | Dòng bị bỏ qua (không có tên thì không tạo được NodeId) |
| `TagCode` | Dòng bị bỏ qua — giữ hành vi Vinamilk |
| `Data Type` | Middleware suy ra từ `TagType`: `DIGITAL` → `Boolean`, `ANALOG` → `Float`, `COUNTER` → `Long`, `STRING` → `String`. Nên khai rõ trong CSV để không phải suy đoán |
| `Eng Units` | `unit = null` trong message |
| `Acquisition Class` | Không ảnh hưởng logic — middleware không dùng cột này |

#### 8.3.1. `Data Type` và `Eng Units` — khác nhau ở chỗ nào?

Hai cột này **không trùng nhau**, chúng trả lời hai câu hỏi khác nhau:

| Cột | Trả lời câu hỏi | Ví dụ |
|---|---|---|
| `Data Type` | Giá trị được **mã hóa** thế nào | `Float` |
| `Eng Units` | Giá trị **đo được** cái gì | `%`, `bar`, `Nm3/h`, `bottles/min` |

Chúng **trực giao**: cùng một `Data Type` nhưng khác đơn vị là những
đại lượng hoàn toàn khác nhau.

| Ví dụ tag | `Data Type` | `Eng Units` | Nghĩa là gì |
|---|---|---|---|
| `FillLevel` | `Float` | `%` | Mức chiết rót chai tính theo phần trăm |
| `BlowPressure` | `Float` | `bar` | Áp suất thổi trong khu thổi chai |
| `CurrentSpeed` (filler) | `Float` | `bottles/min` | Tốc độ chiết rót theo số chai/phút |
| `CurrentSpeed` (air conveyor) | `Float` | `m/min` | Tốc độ vận chuyển theo mét/phút |
| `TotalCounter` | `Long` | `pcs` | Bộ đếm tích luỹ, đơn vị đếm là sản phẩm |
| `EmergencyStop` | `Boolean` | `-` | Cờ, không có đơn vị |

**Tóm lại:** `Data Type` quyết định **cách đọc và ghi giá trị** (mã hóa,
dung lượng, kiểu JSON); `Eng Units` quyết định **ý nghĩa vật lý** của
con số đó. Thiếu `Eng Units` thì `12.000` là 12 nghìn chai/phút hay
12 nghìn mét/phút — không phân biệt được. Thiếu `Data Type` thì
middleware không biết đọc giá trị theo kiểu nào.

```
Float + %        → 87.5 nghĩa là "87.5% mức chiết rót"
Float + bar      → 87.5 nghĩa là "87.5 bar áp suất"
Float + Nm3/h    → 87.5 nghĩa là "87.5 Nm3/h lưu lượng khí nén"
```

Nếu bỏ `Eng Units`, con số `87.5` trong Kafka **không mang ý nghĩa** —
consumer không biết đó là phần trăm hay bar, và mọi phép tổng hợp,
biểu đồ, ngưỡng cảnh báo đều trở nên vô nghĩa.

**Vì sao CSV của Vinamilk để trống cột này?** Vì tag của họ gần như
toàn **boolean flag** và **counter**: `B3M01` (Boolean), `B3M03` (Word,
counter sản lượng) — họ dùng `Word` cho counter sản lượng, đây chính là
lỗi xem §8.3.2. Boolean không có đơn vị; counter tính bằng "pcs"
cũng không cần ghi rõ. Kiểm tra toàn bộ 8 file CSV của Vinamilk (197
tag) cho thấy `Eng Units` **rỗng ở 100%**.

Project này khác: catalog có **131 tag giá trị đo thật** (`Float`) — `FillLevel`,
`CO2Pressure`, `RinseWaterFlowRate`, `TankTemp`, `ProductTemp`... Không
có đơn vị thì toàn bộ giá trị đo trong hệ thống mất nghĩa. Đây chính là
điểm cần **bổ sung so với Vinamilk**, và là lý do cột `Eng Units` được
giữ lại trong baseline.

**Quy tắc điền cột `Eng Units`:**

| Loại tag | `Eng Units` |
|---|---|
| Giá trị đo vật lý (`FillLevel`, `CO2Pressure`, `TankTemp`) | Bắt buộc — đơn vị SI hoặc ngành |
| Tốc độ dây chuyền (`CurrentSpeed`) | Bắt buộc — đơn vị theo máy, xem §4.1 |
| Bộ đếm sản lượng (`TotalCounter`, `CaseCount`) | Bắt buộc — `pcs`, `cases`, `pallets`, `cycles` |
| Boolean flag (`EmergencyStop`, `Starved`) | `-` — không có đơn vị |
| Enum trạng thái (`MachineState`, `AlarmCode`) | `-` — không có đơn vị |
| Số đếm đơn vị cố định (`HeadCount`, `BottlesPerCase`) | `pcs` hoặc `-` nếu là hằng số |

**Quy ước chuẩn hóa đơn vị** (để downstream so sánh được):

| Đại lượng | Đơn vị chuẩn |
|---|---|
| Nhiệt độ | `degC` (không dùng `C` hay `°C`) |
| Áp suất | `bar` |
| Lưu lượng khí nén | `Nm3/h` |
| Lưu lượng nước | `m3/h` |
| Độ dẫn | `uS/cm` |
| Công suất | `kW` |
| Mức / tỷ lệ | `%` |
| Mô-men xoắn | `Nm` |
| Tốc độ dây chuyền | `m/min` |
| Sản lượng | `pcs`, `cases`, `pallets`, `cycles` |

**Đơn vị không được quy đổi trong Middleware.** Middleware chỉ ghi kèm
chuỗi `unit` vào message. Việc quy đổi (ví dụ `bar` → `kPa`) là việc
của consumer, và phải dùng bảng tra đơn vị chuẩn ở trên.

#### 8.3.1.1. Các kiểu số của Kepware và cách ánh xạ sang OPC UA

Kepware dùng tên kiểu riêng (lấy từ Visual Basic/PLC), khác tên OPC UA:

| Kiểu Kepware | OPC UA tương ứng | Python | Dung lượng | Khoảng giá trị |
|---|---|---|---|---|
| `Boolean` | `Boolean` | `bool` | 1 bit | `True` / `False` |
| `Byte` | `Byte` | `int` | 8 bit | 0 – 255 |
| `Short` | `Int16` | `int` | 16 bit | −32.768 – 32.767 |
| `Word` | `UInt16` | `int` | 16 bit | 0 – 65.535 |
| `Int` | `Int32` | `int` | 32 bit | −2,1 tỷ – 2,1 tỷ |
| `DWord` | `UInt32` | `int` | 32 bit | 0 – 4,29 tỷ |
| `Long` | `Int64` | `int` | 64 bit | ±9,2 x 10¹⁸ |
| `LWord` | `UInt64` | `int` | 64 bit | 0 – 1,8 x 10¹⁹ |
| `Float` | `Float` | `float` | 32 bit | số thực 32-bit |
| `Double` | `Double` | `float` | 64 bit | số thực 64-bit |
| `String` | `String` | `str` | — | chuỗi |

**Cột `Data Type` trong CSV dùng tên kiểu Kepware** (`Boolean`, `Int`,
`Float`, `Long`), vì CSV này chính là file export từ Kepware — import
lại vào Kepware thì phải dùng đúng tên mà Kepware hiểu.

**Middleware ánh xạ sang OPC UA khi ghi ra Kafka.** Trường `valueType`
trong message ghi **tên OPC UA** (`Int32`, `Int64`, `Float`...), không
phải tên Kepware. Lý do: consumer cuối là Flink/MinIO/PostgreSQL, họ
hiểu chuẩn OPC UA chứ không hiểu quy ước của Kepware.

```python
# core/opc_types.py — ánh xạ dùng chung cho cả middleware và Validator
KEPWARE_TO_OPCUA = {
    "Boolean": "Boolean",
    "Byte":    "Byte",
    "Short":   "Int16",
    "Word":    "UInt16",
    "Int":     "Int32",
    "DWord":   "UInt32",
    "Long":    "Int64",
    "LWord":   "UInt64",
    "Float":   "Float",
    "Double":  "Double",
    "String":  "String",
}
```

**Đây chính là bảng ánh xạ đã có sẵn trong code của bạn** — `Middleware_DBKafka.py`
và `Vinamilk.Kepware.Middleware/utils/value_helpers.py` đều có cùng một
bảng `VariantType → tên`. Ở project mới, bảng này được đảo chiều thành
`KEPWARE_TO_OPCUA` để đọc từ CSV, và giữ nguyên bảng cũ để đọc từ
server (kiểm tra kiểu thực tế).

**Quy ước chọn kiểu trong project này:**

| Nhóm tag | Kiểu Kepware | OPC UA | Ghi chú |
|---|---|---|---|
| Cờ boolean | `Boolean` | `Boolean` | `EmergencyStop`, `Starved`, `Blocked`... |
| Enum trạng thái, mã alarm | `Int` | `Int32` | `MachineState`, `AlarmCode`, `CIPPhase` |
| Số đếm nhỏ không tích luỹ | `Int` | `Int32` | `HeadCount`, `BottlesPerCase`, `LayerCount` |
| Giá trị đo vật lý | `Float` | `Float` | Áp suất, nhiệt độ, lưu lượng, tốc độ |
| **Bộ đếm tích luỹ** | **`Long`** | **`Int64`** | `TotalCounter`, `GoodCounter`, `DefectCounter`, `CaseCount`... |

**Về `Float` vs `Double`:** cả hai đều là số thực. `Float` (32-bit) đủ
cho giá trị công nghiệp và **tiết kiệm 1/2 băng thông** so với `Double`.
Baseline chọn `Float` cho toàn bộ giá trị đo. Khi Middleware nhận được
kiểu thực tế từ server mà khác `Float` (ví dụ Kepware trả `Double`),
giá trị vẫn được ép về `float` Python bình thường — không cần xử lý
đặc biệt.

**Về `Long` — cảnh báo quan trọng:** `Long` trong OPC UA là **Int64
(có dấu)**, không phải `Int32`. Nhiều người tưởng `Long` là 32-bit vì
quen với C# (`long` = 64-bit) hoặc Java. Kiểm tra lại: bảng ánh xạ
trong `opc_commander.py` của bạn ghi rõ `"Long": VariantType.Int64` —
đúng. Nhưng `Laird.OPCUAServer.Net` (server giả lập) hiện **chưa hỗ trợ**
`Long`/`LWord` — `Program.cs` chỉ map tới `UInt16`, `UInt32`, `Int16`,
`Int32`, `Float`. Nếu test bằng server giả lập thì phải bổ sung, còn
Kepware thật thì không vấn đề.



#### 8.3.1.2. Quy tắc file CSV: export từ Kepware rồi thêm cột

File CSV trong project này **không** được tạo tay từ đầu. Quy trình đúng:

```
1. Tạo tag trong Kepware với kiểu và scan rate đúng
2. Export CSV từ Kepware (Tags > Export Tags...)
3. Thêm cột phụ vào CSV (TagCode, Acquisition Class)
4. Import lại vào Kepware (Tags > Import Tags...)
```

**Cột chuẩn của Kepware** (18 cột, giữ nguyên tên và thứ tự):
`Tag Name`, `Address`, `Data Type`, `Respect Data Type`, `Client Access`,
`Scan Rate`, `Scaling`, `Raw Low`, `Raw High`, `Scaled Low`, `Scaled High`,
`Scaled Data Type`, `Clamp Low`, `Clamp High`, `Eng Units`, `Description`,
`Negate Value`, `TagType`.

**Cột bổ sung do project này thêm** (đặt **sau** cột `TagType`):

| Cột | Vị trí | Bắt buộc? | Ý nghĩa |
|---|---|---|---|
| `TagCode` | sau `TagType` | ✅ Có | Mã nghiệp vụ ổn định, dùng làm key downstream |
| `Acquisition Class` | sau `TagCode` | ⬜ Tùy chọn | Gợi ý REALTIME / PERIODIC. Middleware **không** dùng để lọc (§1.2) |

**Hai bộ CSV trong `metadata/`:**

| Thư mục | Cột | Dùng để |
|---|---|---|
| `TAG_FOLDER/` | 18 cột Kepware + `TagCode` + `Acquisition Class` | **Middleware đọc** — cần `TagCode` để join `equipment_map.json` |
| `KEPWARE_IMPORT/` | 17 cột chuẩn Kepware (đã bỏ `TagType`, `TagCode`, `Acquisition Class`) | **Import vào Kepware** — file đã sẵn sàng để nạp, không có cột phụ |

Sinh bộ import bằng `python tools/generate_kepware_import_csv.py`, kiểm tra bằng
`python tools/validate_kepware_import_csv.py`.

**Quy tắc bắt buộc khi import:**

1. **Cột `Data Type` phải đúng tên kiểu của Kepware.** Nếu ghi `Int32`
   hoặc `Int64`, Kepware sẽ không nhận — nó chỉ hiểu `Boolean`, `Int`,
   `Word`, `DWord`, `Long`, `Float`, `Double`, `String`.
2. **Cột `Eng Units` không bắt buộc trong Kepware** nhưng có giá trị: nhiều
   tag có cùng tên nhưng khác đơn vị (`CurrentSpeed` là `bottles/min` ở
   filler nhưng `m/min` ở air conveyor). Giữ cột nếu đang import lại
   Kepware — nếu không, đơn vị sẽ bị Kepware ghi đè.
3. **Cột `TagCode` phải duy nhất trong toàn nhà máy.** Trùng `TagCode` là
   lỗi cấu hình, Middleware phải log cảnh báo và bỏ qua tag lỗi.
4. **Cột `Address` phải theo quy tắc tag simulator** (§8.3.1.3) — đừng
   sửa tay, hãy sinh lại bằng `tools/generate_tag_csv.py`.

#### 8.3.1.3. Quy tắc cột `Address` (logic tag simulator)

Vì dữ liệu của bài tập là **mô phỏng**, cột `Address` phải theo đúng
logic mà Kepware của Vinamilk dùng cho tag simulator — địa chỉ dạng
`<tiền đo><ordinal 4 chữ số>`:

| Tiền đo | Kiểu dữ liệu Kepware | Ý nghĩa |
|---|---|---|
| `B` | `Boolean` | Rờ rạc (discrete) |
| `K` | `Int`, `Word`, `DWord`, `Long`, `Float`, `Double` | Giá trị số (analog / counter) |
| `S` | `String` | Chuỗi |

**Quy tắc đánh số:** ordinal **đếm liên tục trong 1 CHANNEL**, tăng dần theo
thứ tự device (alphabet) → thứ tự tag trong device — **không reset** khi đổi
device, cũng **không reset** khi đổi tiền đo. **Giãn cách 10 đơn vị**: tag
thứ N (1-based) trong channel nhận địa chỉ `(N − 1) × 10`.

```csv
# LINE_01/L01_AIRCONV_01.csv  (ordinal 1-2 của channel LINE_01)
Tag Name,Address,Data Type
MachineState,K0000,Int
MachineMode,K0010,Int
# LINE_01/L01_BLOWER_01.csv  (ordinal 3-... của channel LINE_01)
EmergencyStop,B0020,Boolean      ← ordinal vẫn đếm tiếp, không reset về B0000
AlarmCode,K0030,Int
CurrentSpeed,K0040,Float
```

> ⚠️ **Vì sao đếm theo CHANNEL chứ không theo device:** Kepware resolve
> `Address` theo phạm vi **channel**, không phải device. Hai tag thuộc hai
> device khác nhau nhưng cùng channel mà trùng `Address` sẽ bị ghi đè lên
> nhau khi simulator ghi giá trị. Vì vậy địa chỉ phải **không trung trong
> toàn channel**. Các channel khác nhau (`LINE_01` vs `LINE_02`) được phép
> dùng lại cùng địa chỉ.

**Vì sao giãn cách 10:** mỗi tag chiếm một "ô địa chỉ" riêng, cách nhau 10
đơn vị. Nhờ đó:
- Không ghi đè vòng đếm trong bộ đếm (register/memory của simulator).
- Khi cần thêm tag mới **chen giữa** các tag cũ, chỉ phải sửa địa chỉ của
  tag mới — không phải dồn toàn bộ địa chỉ của các tag phía sau.

Tham số `ADDRESS_STRIDE = 10` nằm trong `tools/address_rules.py` — đổi 1 hằng số
là đổi được cho toàn hệ thống.

Đây là **biến thể** của pattern file Kepware tham khảu
(`Vinamilk/kepware_tags_running/PX3L01L/ChietRot_Line1.csv`): file tham khảu
dùng công thức `number = ordinal` (1, 2, 3…) và không có khoảng trống; project
này dùng `number = (ordinal − 1) × 10`.

> ⚠️ **Cột `Address` KHÔNG phải NodeId.** NodeId OPC UA vẫn do Kepware sinh
> theo `ns=2;s={channel}.{device}.{tagName}` (§5.2). Middleware **không** đọc
> cột `Address` để dựng NodeId — nó dựng NodeId từ *tên thư mục channel* +
> *tên file device* + *cột `Tag Name`*. Vì vậy đổi `Address` không ảnh hưởng
> gì tới middleware.

**Nguồn sự thật:** `catalog.json` (thứ tự tag trong mỗi máy quyết định
ordinal). `tools/address_rules.py` chứa toàn bộ quy tắc dùng chung cho cả
generator và validator — không nhân bản logic.

#### 8.3.2. Cảnh báo: `Word` không dùng được cho bộ đếm tích lũy

CSV export từ Kepware của Vinamilk dùng `Word` (UInt16) cho các bộ đếm:

```
B3M03,K0003,Word,1,R/W,100,...,Tong San Luong,,OEE,Counter
```

`Word` có giá trị tối đa **65535**. Với bộ đếm sản lượng tích lũy chạy
liên tục 30 ngày, giá trị sẽ **tràn về 0** — và đây là loại lỗi nguy
hiểm nhất vì nó **không báo lỗi**, chỉ làm sai số liệu âm thầm.

Kepware có 3 kiểu số phổ biến cho số nguyên: `Word` (16-bit không dấu),
`DWord` (32-bit không dấu), `Long` (64-bit **có dấu**). Dung lượng khác
nhau rất xa, và sai lựa chọn sẽ làm hỏng dữ liệu theo cách **không báo
lỗi**:

| Kiểu | Dung lượng | Dùng cho counter tích lũy? |
|---|---|---|
| `Word` (UInt16) | 0 – 65.535 | ❌ Tràn sau **vài giây** ở tốc độ cao |
| `DWord` (UInt32) | 0 – 4,29 tỷ | ⚠️ Tràn sau ~248 ngày ở tốc độ cao nhất |
| `Long` (Int64) | ±9,2 x 10¹⁸ | ✅ **Bắt buộc cho mọi counter tích lũy** |

**Số liệu thật** (mô phỏng chạy 24/7, không ngừng máy):

| Tốc độ máy | Giá trị sau 30 ngày | `Word` | `DWord` | `Long` |
|---|---|---|---|---|
| 12.000 chai/phút (filler, capper, seamer...) | 518.400.000 | ❌ tràn sau 328s | ✅ | ✅ |
| 400 lon/phút (can depalletizer) | 17.280.000 | ❌ tràn sau 2,7h | ✅ | ✅ |
| 200 thùng/phút (case packer) | 8.640.000 | ❌ tràn sau 5,5h | ✅ | ✅ |
| 120 preform/phút (preform feeder) | 5.184.000 | ❌ tràn sau 9,1h | ✅ | ✅ |
| 4 chu kỳ/giờ (CIP) | 172.800 | ❌ tràn sau 11,4 ngày | ✅ | ✅ |

Sau **365 ngây**, ở tốc độ 12.000/phút: giá trị đạt 6,3 tỷ → `DWord` tràn
sau ~248 ngày, `Long` tràn sau ~124 ngày.

**Kết luận:** dù đề bài chỉ cần 30 ngày lịch sử, `Long` là lựa chọn
đúng. `DWord`/`Long` (Int32) sẽ hỏng khi hệ thống chạy lâu hơn vài
tháng — và lỗi đó hiện ra rất muộn, khi số liệu đã sai.

**Yêu cầu bắt buộc khi cấu hình Kepware cho project này:**

| Tag | Data Type bắt buộc |
|---|---|
| `TotalCounter`, `GoodCounter`, `DefectCounter` | **`Long`** |
| `CaseCount`, `PalletCount`, `PrintCount`, `LabelApplyCount`, `InspectionCount`, `SeamDefectCount`, `TotalCycleCount` | **`Long`** |
| `MachineState`, `MachineMode`, `AlarmCode`, `CIPPhase`, `CaseFormat`, `PrintQuality`, `SeamQuality`, `InspectResult`, `RejectReason` | `Int` |
| Mọi giá trị đo vật lý | `Float` |
| Mọi cờ boolean | `Boolean` |

**Kiểm tra lúc khởi động:** Middleware nên so `Data Type` trong CSV với
kiểu thực tế mà Kepware trả về (đọc `node.get_data_type_as_variant_type()`).
Nếu CSV khai `Long` nhưng Kepware trả `UInt16`, log cảnh báo tên tag —
vì đó là dấu hiệu counter sắp tràn.

**Ví dụ `metadata/TAG_FOLDER/LINE_01/L01_FILLER_01.csv`** — theo đúng
format export của Kepware (18 cột chuẩn) + 2 cột bổ sung
(`TagCode`, `Acquisition Class`) đặt sau `TagType`:

```csv
Tag Name,Address,Data Type,Respect Data Type,Client Access,Scan Rate,Scaling,Raw Low,Raw High,Scaled Low,Scaled High,Scaled Data Type,Clamp Low,Clamp High,Eng Units,Description,Negate Value,TagType,TagCode,Acquisition Class
MachineState,K0000,Int,1,R/W,100,,,,,,,,,-,Trang thai may,,DIGITAL,FILL.L01.MACHINESTATE,REALTIME
MachineMode,K0010,Int,1,R/W,100,,,,,,,,,-,Che do dieu khien,,DIGITAL,FILL.L01.MACHINEMODE,REALTIME
EmergencyStop,B0020,Boolean,1,R/W,100,,,,,,,,,-,Dung khanh,,DIGITAL,FILL.L01.EMERGENCYSTOP,REALTIME
AlarmCode,K0030,Int,1,R/W,100,,,,,,,,,-,Ma alarm dang hoat dong,,DIGITAL,FILL.L01.ALARMCODE,REALTIME
CurrentSpeed,K0040,Float,1,R/W,500,,,,,,,,,bottles/min,Toc do thuc te,,ANALOG,FILL.L01.CURRENTSPEED,PERIODIC
DesignSpeed,K0050,Float,1,R/W,500,,,,,,,,,bottles/min,Toc do thiet ke,,ANALOG,FILL.L01.DESIGNSPEED,PERIODIC
TotalCounter,K0060,Long,1,R/W,1000,,,,,,,,pcs,Tong so chai da xu ly,,COUNTER,FILL.L01.TOTALCOUNTER,PERIODIC
GoodCounter,K0070,Long,1,R/W,1000,,,,,,,,pcs,So chai dat,,COUNTER,FILL.L01.GOODCOUNTER,PERIODIC
DefectCounter,K0080,Long,1,R/W,1000,,,,,,,,pcs,So chai loi,,COUNTER,FILL.L01.DEFECTCOUNTER,PERIODIC
Starved,B0090,Boolean,1,R/W,100,,,,,,,,,-,Thieu san pham dau vao,,DIGITAL,FILL.L01.STARVED,REALTIME
Blocked,B0100,Boolean,1,R/W,100,,,,,,,,,-,Dau ra bi chan,,DIGITAL,FILL.L01.BLOCKED,REALTIME
FillLevel,K0110,Float,1,R/W,500,,,,,,,,,%,Muc chiet rot,,ANALOG,FILL.L01.FILLLEVEL,PERIODIC
FillRate,K0120,Float,1,R/W,500,,,,,,,,,bottles/min,Toc do chiet rot,,ANALOG,FILL.L01.FILLRATE,PERIODIC
HeadCount,K0130,Int,1,R/W,1000,,,,,,,,-,So dau chiet,,COUNTER,FILL.L01.HEADCOUNT,PERIODIC
CO2Pressure,K0140,Float,1,R/W,500,,,,,,,,,bar,Ap suat CO2,,ANALOG,FILL.L01.CO2PRESSURE,PERIODIC
CO2FlowRate,K0150,Float,1,R/W,500,,,,,,,,,Nm3/h,Luu luong CO2,,ANALOG,FILL.L01.CO2FLOW,PERIODIC
ProductTemp,K0160,Float,1,R/W,500,,,,,,,,,degC,Nhiet do san pham,,ANALOG,FILL.L01.PRODUCTTEMP,PERIODIC
PowerConsumption,K0170,Float,1,R/W,500,,,,,,,,,kW,Cong suat tieu thu,,ANALOG,FILL.L01.POWERCONSUMPTION,PERIODIC
```

**Lưu ý về cột `Address`:** xem §8.3.1.3 bên dưới — đây là địa chỉ theo
logic **tag simulator** (tiền đo theo kiểu dữ liệu + ordinal 4 chữ số, giãn cách
10 đơn vị), khác hoàn toàn với NodeId.

**Lưu ý về `Scan Rate`:** đây là cấu hình **của Kepware**, không phải của
middleware. Giá trị gợi ý: `100` (100 ms) cho tag trạng thái, `1000` cho
counter, `500`–`1000` cho giá trị đo. Middleware đọc mọi thứ Kepware
phát ra, không tự lọc theo tần suất (§1.2).

**Lưu ý về cột `Eng Units`:** giá trị `-` nghĩa là không có đơn vị —
middleware sẽ ghi `unit: null` vào Kafka.

### 8.4. Định dạng `equipment_map.json`

Bản gốc Vinamilk hỗ trợ 3 định dạng (object đơn giản, object chi tiết,
mảng). Bản này dùng **object chi tiết** với đầy đủ metadata cần thiết.

```json
{
  "plantId": "PLANT_01",
  "machines": {
    "LINE_01.L01_FILLER_01": {
      "machineId": "L01_FILLER_01",
      "machineType": "CARBONATED_FILLER",
      "equipmentCode": "FILL-L01-01",
      "lineId": "LINE_01",
      "processId": "FILLING",
      "plantId": "PLANT_01",
      "description": "Chiet rot nuoc co gas PET line 1"
    },
    "LINE_02.L02_FILLER_01": {
      "machineId": "L02_FILLER_01",
      "machineType": "STILL_FILLER",
      "equipmentCode": "FILL-L02-01",
      "lineId": "LINE_02",
      "processId": "FILLING",
      "plantId": "PLANT_01",
      "description": "Chiet rot nuoc tinh khiet line 2"
    },
    "SHARED.CIP_SKID_01": {
      "machineId": "CIP_SKID_01",
      "machineType": "CIP_SKID",
      "equipmentCode": "CIP-SHARED-01",
      "lineId": "SHARED",
      "processId": "CIP",
      "plantId": "PLANT_01",
      "description": "Cum CIP dung chung"
    }
  }
}
```

**Khóa là `<Channel>.<Device>`** — giữ nguyên từ Vinamilk. Dùng khóa
này thay vì chỉ `Device` vì tên device có thể trùng giữa các channel
(tình huống này không xảy ra ở baseline, nhưng thiết kế phải chịu được).

**Các trường bắt buộc trong mỗi entry:**

| Trường | Bắt buộc | Dùng cho |
|---|---|---|
| `machineId` | ✅ | `machine.machineId` — trùng `source.device` |
| `machineType` | ✅ | `machine.machineType` — enum ở §2.3 |
| `lineId` | ✅ | `plant.lineId` |
| `processId` | ✅ | `plant.processId` |
| `plantId` | ✅ | `plant.plantId` |
| `equipmentCode` | ⬜ | `machine.equipmentCode` |
| `description` | ⬜ | Chỉ để đọc, không đưa vào Kafka |

**Kiểm tra lúc khởi động:** mọi `Channel.Device` có trong CSV phải có
entry trong `equipment_map.json`. Thiếu thì báo lỗi rõ ràng tên
máy và **không subscribe máy đó** — thay vì âm thầm gửi message thiếu
metadata. Đây là hành vi chặn lỗi cấu hình, rất quan trọng vì message
thiếu `machineType` sẽ hỏng mọi phép tổng hợp downstream.

### 8.5. Quy trình tạo CSV từ catalog

`metadata/catalog.json` là **nguồn sự thật duy nhất**. Quy trình đã được
script hóa hoàn toàn:

```bash
# 1. Sinh 26 file CSV + equipment_map.json từ catalog.json
python tools/generate_tag_csv.py

# 2. Sinh bộ CSV sạch để import Kepware (bỏ 3 cột phu)
python tools/generate_kepware_import_csv.py

# 3. Kiểm tra trước khi nộp vào Kepware
python tools/validate_metadata.py
python tools/validate_kepware_import_csv.py

# 4. Kiểm chứng phân bổ partition
python tools/check_partitioning.py
```

**Sau khi sinh CSV:**

1.  Người vận hành import 26 file CSV vào Kepware (mỗi channel một
    lần), lấy từ `metadata/KEPWARE_IMPORT/<Channel>/<Device>.csv` — bộ này
    đã bỏ `TagType`, `TagCode`, `Acquisition Class`, đúng 17 cột chuẩn
    Kepware. Xem `metadata/README.md` để biết quy trình import chi tiết.
2.  Kepware tự sinh `NodeId`. Kiểm tra lại bằng browser:
    `ns=2;s={channel}.{device}.{tagName}`. Cột `Address` giữ nguyên theo
    logic tag simulator (§8.3.1.3) — không phải NodeId.
3.  Kiểu dữ liệu đã có sẵn trong cột `Data Type` (tên kiểu Kepware) —
    Kepware giữ nguyên khi import, không cần cấu hình lại.
4.  Tần suất quét lấy từ cột `Scan Rate`. Đây là cấu hình **của Kepware**,
    middleware không đọc cột này (§1.2).

**Hai bộ CSV phục vụ hai mục đích khác nhau — đừng nhầm:**

| Thư mục | Cột | Ai dùng |
|---|---|---|
| `metadata/TAG_FOLDER/` | 18 cột Kepware + `TagCode` + `Acquisition Class` | **Middleware** đọc lúc chạy |
| `metadata/KEPWARE_IMPORT/` | 17 cột chuẩn Kepware | **Người vận hành** import vào Kepware |

> Import nhầm file trong `TAG_FOLDER/` sẽ tạo 3 cột phu không mong muốn trong
> project Kepware. Luôn lấy file từ `KEPWARE_IMPORT/`.

**Quy tắc commit:** commit cả `catalog.json` (nguồn sự thật) lẫn 26 file
CSV của cả hai bộ (sản phẩm sinh). Lý do: người vận hành cần CSV để import vào
Kepware, và có thể sửa tay (đổi `TagCode`, đổi `Scan Rate`) — khi đó
phải sửa ngược lại `catalog.json` để hai bên không lệch.

**Vì sao cần `validate_metadata.py`:** Kepware **không báo lỗi rõ ràng**
khi cột `Data Type` sai tên — nó âm thầm bỏ qua tag hoặc tạo tag với kiểu
mặc định. Validator chặn lỗi này trước khi nó xảy ra. Nó kiểm tra:

| Kiểm tra | Lý do |
|---|---|
| Đủ 18 cột chuẩn Kepware | Thiếu cột → Kepware không import đúng |
| `Data Type` là tên kiểu Kepware | `Int32`/`Int64` bị Kepware từ chối |
| `TagCode` duy nhất toàn nhà máy | Trùng → downstream gộp nhầm máy |
| `Tag Name` duy nhất trong file | Trùng → NodeId trùng |
| Mỗi máy có entry trong `equipment_map.json` | Thiếu → message thiếu `machineType` |
| Counter không dùng kiểu 16/32 bit | Tràn giá trị, không báo lỗi (§8.3.2) |
| NodeId không trùng | Trùng → subscribe đè lên nhau |
| Tag `ANALOG` kiểu `Float` có `Eng Units` | Thiếu đơn vị → dữ liệu vô nghĩa |

### 8.6. Index metadata trong bộ nhớ

Sau khi nạp, Middleware dựng index để tra cứu O(1) khi xử lý callback:

```python
# nodeId → thông tin tag + metadata máy
nodeid_to_taginfo: dict[str, dict] = {
    "ns=2;s=LINE_01.L01_FILLER_01.FillLevel": {
        "nodeId": "ns=2;s=LINE_01.L01_FILLER_01.FillLevel",
        "channel": "LINE_01",
        "device": "L01_FILLER_01",
        "tagName": "FillLevel",
        "tagCode": "FILL.L01.FILLLEVEL",
        "tagType": "ANALOG",
        "dataType": "Float",
        "unit": "%",
        "machineType": "CARBONATED_FILLER",
        "equipmentCode": "FILL-L01-01",
        "lineId": "LINE_01",
        "processId": "FILLING",
        "plantId": "PLANT_01",
    },
    # ...
}
```

Index này là nguồn duy nhất mà `normalizer` và `kafka_publisher` dùng để
bổ sung metadata vào message. Nhờ vậy, các module này không cần biết về
CSV hay JSON.

---

## 9. Enum và chuẩn hóa giá trị

### 9.1. MachineState

| Giá trị | Tên | Ý nghĩa |
|---|---|---|
| 0 | `OFF` | Máy tắt, không năng lượng |
| 1 | `STARTING` | Đang khởi động |
| 2 | `RUNNING` | Đang chạy sản xuất |
| 3 | `STOPPED` | Đã dừng có chủ đích (hết ca, hết nguyên liệu) |
| 4 | `FAULTED` | Lỗi, đang dừng do sự cố |
| 5 | `MAINTENANCE` | Đang bảo trì |

**Luật chuyển trạng thái hợp lệ:**

```
OFF → STARTING → RUNNING ⇄ STOPPED
                ↓  ↓
              FAULTED   MAINTENANCE
```

| Luật | Mô tả |
|---|---|
| Tốc độ khi không `RUNNING` | `CurrentSpeed = 0` |
| Bộ đếm tăng khi | Chỉ tăng ở trạng thái `RUNNING` |
| Vào `FAULTED` | `AlarmCode` khác 0 |
| Vào `MAINTENANCE` | `AlarmCode` có thể bằng 0 |

### 9.2. MachineMode

| Giá trị | Tên | Ý nghĩa |
|---|---|---|
| 0 | `OFF` | Tắt |
| 1 | `MANUAL` | Chạy tay, có người vận hành |
| 2 | `AUTO` | Chạy tự động |
| 3 | `MAINTENANCE` | Chế độ bảo trì |

### 9.3. Các enum khác

**CIPPhase** (tag `CIPPhase` của máy rửa):

| Giá trị | Tên | Ý nghĩa |
|---|---|---|
| 0 | `IDLE` | Không CIP |
| 1 | `CHEMICAL` | Pha hóa chất |
| 2 | `HEATING` | Gia nhiệt |
| 3 | `CIRCULATION` | Hồi lưu |
| 4 | `RINSE` | Xả tráng |

**CaseFormat** (tag `CaseFormat` của case packer):

| Giá trị | Tên | Ý nghĩa |
|---|---|---|
| 0 | `STANDARD` | Thùng tiêu chuẩn |
| 1 | `TRAY` | Thùng khay |
| 2 | `SHRINK` | Thùng co |

**PrintQuality** (tag `PrintQuality` của date coder):

| Giá trị | Tên | Ý nghĩa |
|---|---|---|
| 0 | `GOOD` | Mã in rõ |
| 1 | `PARTIAL` | Mờ, cần kiểm tra |
| 2 | `FAIL` | Không đọc được |

**SeamQuality** (tag `SeamQuality` của can seamer): 0 `GOOD`, 1 `SUSPECT`, 2 `FAIL`.

**InspectResult** (tag `InspectResult` của can inspection): 0 `PASS`, 1 `REJECT`, 2 `RECALL`.

**RejectReason** (tag `RejectReason` của can inspection):

| Giá trị | Tên | Ý nghĩa |
|---|---|---|
| 0 | `NONE` | Không loại |
| 1 | `SEAM_DEFECT` | Đường biên lỗi |
| 2 | `DENT` | Móp |
| 3 | `LEAK` | Rò |
| 4 | `PRINT_DEFECT` | Mã in lỗi |

### 9.4. Chuẩn hóa `StatusCode` OPC UA

OPC UA có hàng chục `StatusCode`. Middleware chuẩn hóa về 3 mức:

| Mức | Điều kiện | `isGood` |
|---|---|---|
| `Good` | `StatusCode.is_good()` == True | `true` |
| `Uncertain` | `is_good()` == False nhưng `is_uncertain()` == True | `false` |
| `Bad` | Còn lại | `false` |

```python
def normalize_status_code(status_code) -> tuple[str, bool]:
    """Chuẩn hóa OPC UA StatusCode → (label, is_good)."""
    if status_code is None:
        return "Good", True
    if getattr(status_code, "is_good", None) and status_code.is_good():
        return "Good", True
    if getattr(status_code, "is_uncertain", None) and status_code.is_uncertain():
        return "Uncertain", False
    return "Bad", False
```

**Quy tắc giá trị:** với `Uncertain`, giữ nguyên giá trị đọc được và
đặt `isGood: false`. Với `Bad`, đặt `value: null`.

Lý do phân biệt hai mức `Uncertain` và `Bad`: `Uncertain` thường là
"sensor đang bị rung, đọc được nhưng không chắc chắn" — giá trị vẫn
có ích cho phân tích xu hướng, chỉ cần cảnh báo. `Bad` là "không đọc
được" — giá trị không tồn tại.

### 9.5. Ánh xạ kiểu dữ liệu qua 3 tầng

Giá trị đi qua 3 tầng, mỗi tầng dùng một hệ tên kiểu khác nhau:

```
CSV (tên Kepware)  →  Middleware (Python native)  →  Kafka (tên OPC UA)
Boolean                bool                           Boolean
Int                    int                            Int32
Float                  float                          Float
Long                   int                            Int64
```

| Kiểu trong CSV (Kepware) | Kiểu native Python | `valueType` ghi ra Kafka (OPC UA) |
|---|---|---|
| `Boolean` | `bool` | `Boolean` |
| `Byte` | `int` | `Byte` |
| `Short` | `int` | `Int16` |
| `Word` | `int` | `UInt16` |
| `Int` | `int` | `Int32` |
| `DWord` | `int` | `UInt32` |
| `Long` | `int` | `Int64` |
| `LWord` | `int` | `UInt64` |
| `Float` | `float` | `Float` |
| `Double` | `float` | `Double` |
| `String` | `str` | `String` |

**Vì sao `valueType` ghi tên OPC UA chứ không phải tên Kepware:** consumer
cuối là Flink, MinIO, PostgreSQL — họ hiểu chuẩn OPC UA, không hiểu quy
ước đặt tên của Kepware. Nếu ghi `Long`, consumer phải biết thêm "Long
của Kepware là Int64" — vì vậy tầng Middleware đảm nhiệm việc dịch tên
này.

**Ghi chú về `Float` vs `Double`:** cả hai đều ánh xạ sang `float` trong
Python (Python chỉ có một kiểu số thực). `valueType` ghi ra Kafka giữ
lại phân biệt gốc, để consumer biết độ chính xác lý thuyết của giá trị.

**Ghi chú về kiểu `int`:** `Word`, `DWord`, `Long` đều là số nguyên và
đều ánh xạ sang `int` của Python (số nguyên tùy ý, không tràn). Nhưng
`valueType` ghi ra vẫn phân biệt — vì nếu không, consumer sẽ không biết
counter gốc là 16-bit hay 64-bit, và không thể cảnh báo tràn.

**Kiểu thực tế từ server có quyền ưu tiên.** Nếu CSV khai `Long` nhưng
Kepware trả về `UInt16`, Middleware nên:
1. Ghi `valueType` theo **kiểu thực tế** (`UInt16`) để phản ánh đúng dữ
   liệu.
2. Log cảnh báo tên tag — cấu hình CSV và Kepware lệch nhau, và counter
   có nguy cơ tràn.

---

## 10. Kiểm thử và nghiệm thu

### 10.1. Test tầng metadata

| Test | Mục tiêu | Tiêu chí |
|---|---|---|
| Đọc CSV | Nạp đúng 26 file, 404 tag | Số tag khớp §4.2 |
| NodeId | Đúng mẫu 3 cấp | Regex `^ns=2;s=[^.]+\.[^.]+\..+$` |
| Thiếu `equipment_map` | Báo lỗi rõ tên máy, không subscribe máy đó | Log chứa `LINE_01.L01_FILLER_01` |
| Encoding | CSV tiếng Việt đọc được | Thử `utf-8-sig` → `utf-8` → `cp1258` → `cp1252` → `latin-1` |
| Dòng lỗi | Dòng thiếu `Tag Name` hoặc `TagCode` bị bỏ qua, có log cảnh báo | Không crash |
| Trùng NodeId | Bỏ qua và cảnh báo | Không subscribe trùng |

### 10.2. Test tầng normalize

| Test | Đầu vào | Kỳ vọng |
|---|---|---|
| Round float | `87.1234567` | `87.123457` |
| Bool | `True` | `True` |
| Bytes | `b"abc"` | `"abc"` |
| Bytes lỗi | `b"\xff\xfe"` | `"b'\\xff\\xfe'"` (fallback `str`) |
| Status Good | `Good` | `("Good", True)` |
| Status Uncertain | `Uncertain` | `("Uncertain", False)`, giữ giá trị |
| Status Bad | `Bad` | `("Bad", False)`, `value = null` |
| `eventId` tất định | Cùng input 2 lần | Cùng `eventId` |
| `eventId` khác event | Khác `sourceTimestamp` | Khác `eventId` |
| `eventId` ổn định với float | `87.5` vs `87.5000000001` | Cùng `eventId` (sau khi round 6) |

### 10.3. Test tầng Kafka

| Test | Mục tiêu | Tiêu chí |
|---|---|---|
| Key | Kiểm tra key gửi đi | Đúng `machineId.encode("utf-8")` |
| Partition | Kiểm tra phân bổ | Mỗi máy luôn 1 partition, khớp §7.3 |
| Thứ tự | 100 event cùng máy | Đọc lại từ Kafka → đúng thứ tự |
| Kafka down | Producer lỗi | Callback lỗi được gọi, log đầy đủ, không crash |
| Kafka phục hồi | Khôi phục broker | Tự gửi tiếp, không cần restart middleware |
| Schema | Validate message | Đủ mọi trường bắt buộc, không có trường thừa |

### 10.4. Test tích hợp với Kepware

| Test | Mục tiêu | Tiêu chí |
|---|---|---|
| Kết nối | Subscribe thành công | Tỷ lệ subscribe 100% cho 404 monitored item |
| Nhận dữ liệu | Có event đến | Tần suất khớp cấu hình Kepware |
| Baseline | Không phát giá trị baseline | Số event ngay sau subscribe = 0 |
| Reconnect | Rút cáp / restart Kepware | Tự kết nối lại, subscribe lại, tiếp tục phát |
| Backoff | Quan sát thời gian giữa các lần thử | `(1s, 2s, 5s, 10s, 20s, 30s)` |
| Dedup | Giá trị không đổi | Không phát lại event trùng |
| Chất lượng | Ép `Bad` status | Message có `value: null`, `isGood: false` |

### 10.5. Test tải

| Kịch bản | Mục tiêu | Tiêu chí |
|---|---|---|
| Tải chuẩn | 400 eps | Không mất event, độ trễ end-to-end < 2s |
| Tải cao | 1000 eps | Không mất event, hàng đợi không đầy |
| Kafka chết 60s | Mất kết nối broker | Hàng đợi dồn, sau khi broker sống lại → phát đủ, không mất dữ liệu đã vào queue |
| Kafka chết 10 phút | Vượt ngưỡng queue | Bắt đầu drop, **log cảnh báo rõ ràng** — đây là hành vi được chấp nhận ở Q5 |
| Bộ nhớ | Theo dõi RSS | Ổn định, không tăng unbounded |

**Đo độ trễ end-to-end:** `eventTime` (từ Kepware) → thời điểm consumer
đọc được. Mục tiêu: p95 < 2 giây ở tải chuẩn.

### 10.6. Checklist nghiệm thu

- [ ] Đọc đủ 26 file CSV, 404 tag, 404 monitored item subscribe thành công
- [ ] `equipment_map.json` có đủ 26 máy, mọi máy có `machineType`
- [ ] Message có đủ 6 nhóm trường theo §5.2, không có trường thừa
- [ ] `eventId` là UUID v5 hợp lệ, tất định qua 2 lần chạy
- [ ] `eventType` luôn là `machine.telemetry`
- [ ] Key Kafka = `machineId`, mỗi máy 1 partition, thứ tự theo máy giữ nguyên
- [ ] Giá trị `Bad` → `value: null`, không bịa giá trị thay thế
- [ ] Reconnect tự động với backoff đúng kịch bản
- [ ] Không phát event trùng sau reconnect
- [ ] Load test đạt 1000 eps mà không mất event
- [ ] `valueType` trong message khớp bảng ánh xạ §9.5 (không có giá trị lạ như `Long`, `Int`, `UInt16`)
- [ ] 26 file CSV import thử vào Kepware không báo lỗi kiểu dữ liệu

---

## 11. Kế hoạch triển khai

### 11.1. Các giai đoạn

| Giai đoạn | Nội dung | Đầu ra |
|---|---|---|
| **G1 — Metadata** | Sinh `catalog.json` → 26 file CSV + `equipment_map.json`. CSV theo **đúng format import của Kepware** (§8.3.1.2), cột `Data Type` dùng tên kiểu Kepware (§8.3.1.1) | Metadata load được, 404 tag, CSV import được vào Kepware không lỗi |
| **G2 — Core** | `tag_loader`, `equipment_map`, `normalizer`, `event_id`, `status_codes` | Test tầng metadata + normalize pass |
| **G3 — OPC UA** | `opcua_client`, `subscription`, `state_machine` | Kết nối Kepware, nhận dữ liệu |
| **G4 — Kafka** | `kafka_publisher`, `value_worker` | Message vào Kafka đúng schema |
| **G5 — Tích hợp** | Ghép các phần, test với Kepware thật | End-to-end chạy |
| **G6 — Load test** | Chạy kịch bản §10.5, đo độ trễ, đo drop | Báo cáo số liệu |
| **G7 — Bàn giao** | Tài liệu, chạy hướng dẫn, cấu hình Kepware | Cho phần Flink tiếp nhận |

### 11.2. Thứ tự ưu tiên

G2 và G3 có thể làm song song vì G2 không phụ thuộc Kepware. G4 phụ
thuộc G2 (cần normalizer) nhưng không phụ thuộc G3. Nên:

```
G1 ──▶ G2 ──┬──▶ G4 ──┐
            └──▶ G3 ───┴──▶ G5 ──▶ G6 ──▶ G7
```

### 11.3. Rủi ro kỹ thuật

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| NodeId 4 cấp thay vì 3 cấp trong Kepware | Cao | Kiểm tra ngay G3: browse server và so NodeId thực tế với catalog |
| `device` của Kepware không khớp tên file CSV | Cao | Đặt tên file CSV theo đúng tên device, dùng script sinh |
| Kepware chưa cấu hình đúng kiểu dữ liệu | Trung bình | Bảng mapping `Data Type` → kiểu OPC UA tại §8.3.1.1; middleware so kiểu CSV với kiểu server thực tế lúc khởi động |
| CSV ghi sai tên kiểu (vd `Int32` thay vì `Int`) | Cao | Kepware từ chối import; `validate_metadata.py` chặn trước khi nộp |
| Subscription vượt giới hạn của Kepware | Trung bình | 404 item là rất nhỏ so với giới hạn điển hình (hàng nghìn) |
| Độ trễ do queue dồn khi tải cao | Thấp | Đo p95 ở G6, điều chỉnh `linger_ms` |
| Đồng hồ lệch giữa Kepware và Middleware | Trung bình | Dùng `SourceTimestamp` làm `eventTime`, lưu `serverTimestamp` riêng để chẩn đoán |

### 11.4. Điểm cần nhóm chốt

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| 1 | `TotalCounter` của CIP mang đơn vị gì? | `cycles`, và bỏ `TotalCycleCount` (giữ 1 nguồn sự thật) |
| 2 | Có dùng `equipmentCode` không, hay chỉ cần `machineId`? | Giữ `equipmentCode` — hữu ích khi join với MES sau này |
| 3 | Retention Kafka 7 ngày hay 30 ngày? | 7 ngày ở baseline; đề bài nhắc 30 ngày lịch sử → nếu cần thì để ở tầng lưu trữ (MinIO) thay vì Kafka |
| 4 | Có giữ lại topic `machine_events` (tên của Laird) không? | Không. Dùng `industrial.telemetry` — nhất quán với tài liệu này |
| 5 | Có cần `runtimeHours` như tag không? | Không — Flink tính từ chuyển trạng thái (§3) |
| 6 | `machineType` có đủ 15 giá trị trong §2.3 chưa? | Chốt enum, sau này thêm giá trị mới là mở rộng, không phá |

---

## 12. Rủi ro đã biết

### 12.1. Rủi ro đã được chấp nhận

| Rủi ro | Mức | Vì sao chấp nhận | Đo bằng cách nào |
|---|---|---|---|
| Mất dữ liệu khi process chết (không có durable spool) | Trung bình | Q5 — ưu tiên tốc độ, giữ hành vi middleware hiện tại | Đếm số event nhận ở Kafka so với số event sinh từ Kepware |
| Drop event khi queue đầy | Trung bình | Q5 — có log cảnh báo, hành vi kiểm soát được | Log `[VALUE QUEUE] full` — đếm số lần xuất hiện |
| Mất event khi `producer.send()` thất bại hoàn toàn | Thấp | Có `acks=all` + `retries=10`; lỗi cứng là ngoại lệ hiếm | Đếm callback lỗi |
| Độ trễ khi tải cao | Thấp | Ứng viên giới hạn | p95 end-to-end ở G6 |

### 12.2. Hướng nâng cấp nếu cần

Nếu đề bài yêu cầu **đảm bảo không mất dữ liệu** tuyệt đối, các hướng
nâng cấp theo thứ tự từ rẻ đến đắt:

| Hướng | Cách làm | Chi phí |
|---|---|---|
| 1. Tăng độ bền producer | Bật `enable_idempotence=True`, tăng `max_in_flight` | Rất thấp |
| 2. Disk buffer cho Kafka client | `kafka-python` không hỗ trợ sẵn; dùng `confluent-kafka` với `queue.buffering.backpressure` hoặc `file` plugin | Thấp |
| 3. Durable spool cục bộ | Ghi message ra file/DB tạm trước khi gửi Kafka, đọc lại khi phục hồi | Trung bình |
| 4. Kafka là hàng đợi bền vững | Đây chính là cách đang làm — vấn đề chỉ là khi **producer** chết, không phải khi Kafka chết | — |

**Ghi nhận quan trọng:** Kafka đã là hàng đợi bền vững. Rủi ro thực sự
của mô hình hiện tại là khi **Middleware** chết — dữ liệu nằm trong RAM
của tiến trình bị mất. Đây là ranh giới rõ ràng của quyết định Q5, và
cần trình bày trung thực trong báo cáo.

---

## 13. Phụ lục

### 13.1. Tóm tắt hợp đồng dữ liệu

| Khía cạnh | Giá trị |
|---|---|
| Topic | `industrial.telemetry` |
| Partitions | 8 (16 nếu mở rộng lên 50–100 máy) |
| Key | `machineId` (UTF-8 bytes) |
| Value | JSON, UTF-8, không escape non-ASCII |
| Event type | `machine.telemetry` (duy nhất) |
| Schema version | `1.0` |
| Số record | 1 record / 1 tag update |
| `eventId` | UUID v5, tất định từ nội dung sự kiện |
| Timestamp | `eventTime` = SourceTimestamp, UTC ISO-8601 |
| Số máy | 26 |
| Số tag | 404 (177 REALTIME, 227 PERIODIC) |
| NodeId | `ns=2;s={channel}.{device}.{tag}` |

### 13.2. Danh sách file — đã tạo ✅

```
IndustrialTelemetry.Middleware/
├── config/settings.py
├── config/logging_config.py
├── core/tag_loader.py
├── core/equipment_map.py
├── core/value_types.py         # Ánh xạ kiểu 3 tầng (§9.5)
├── core/subscription.py
├── core/state_machine.py
├── core/dedup.py
├── services/opcua_client.py
├── services/value_worker.py
├── services/normalizer.py
├── services/kafka_publisher.py
├── utils/status_codes.py
├── utils/event_id.py
├── utils/time_utils.py
├── tools/selftest.py            # 59 check offline
├── tools/integration_test.py    # 29 check end-to-end (mock)
├── tools/verify_doc.py          # 20 check tài liệu ↔ catalog
├── tools/gen_tag_tables.py
├── tools/inject_tag_tables.py
├── tools/preview_message.py
├── .env.example
├── main.py
├── requirements.txt
└── README.md
```

Metadata nằm ở thư mục anh em `TichHopDuLieuLon_BaiTapLon/metadata/` (nguồn chân lý
duy nhất):

```
metadata/
├── catalog.json                   # Nguồn sự thật: 26 máy, 404 tag
├── equipment_map.json             # Sinh tự động từ catalog.json
├── README.md                      # Hướng dẫn import Kepware
├── TAG_FOLDER/                    # 20 cột — middleware đọc
│   ├── LINE_01/                   # 9 file CSV
│   ├── LINE_02/                   # 9 file CSV
│   ├── LINE_03/                   # 6 file CSV
│   └── SHARED/                    # 1 file CSV (CIP)
└── KEPWARE_IMPORT/                # 17 cột — import vào Kepware
    ├── LINE_01/
    ├── LINE_02/
    ├── LINE_03/
    └── SHARED/
```

```
tools/
├── address_rules.py             # Quy tắc sinh cột Address (B/K/S + ordinal) — dùng chung
├── generate_tag_csv.py            # Sinh 26 CSV (20 cột) + equipment_map.json từ catalog.json
├── generate_kepware_import_csv.py # Sinh 26 CSV sạch (17 cột) để import Kepware
├── validate_metadata.py           # Kiểm tra CSV ↔ equipment_map ↔ catalog + Address
├── validate_kepware_import_csv.py # Kiểm tra bộ import: đúng 17 cột, đủ 404 tag, Address đúng
└── check_partitioning.py          # Kiểm chứng phân bổ murmur2 → partition
```

### 13.2.1. Tài liệu bàn giao

| File | Nội dung | Đối tượng |
|---|---|---|
| `kafka_data_contract_and_storage_guide.md` | Data contract đầy đủ + catalog 404 tag + đề xuất lưu DB raw (TimescaleDB / ClickHouse / MinIO-Parquet) + code mẫu consumer + checklist bàn giao | **Nhóm phía sau** (Flink / Data Platform / BI) |

Tài liệu này là **hợp đồng giữa 2 phía**. Mọi thay đổi schema phải được thông báo
trước và kèm tăng `schemaVersion`.

### 13.3. Checklist metadata cho Kepware

Khi cấu hình Kepware, nhớ rằng:

- [ ] Tạo channel theo đúng tên thư mục: `LINE_01`, `LINE_02`, `LINE_03`, `SHARED`
- [ ] Tạo device theo đúng tên file CSV: `L01_FILLER_01`, ...
- [ ] Tạo tag theo đúng cột `Tag Name`
- [ ] Đặt kiểu dữ liệu theo cột `Data Type` — dùng **đúng tên kiểu Kepware** (`Boolean`, `Int`, `Float`, `Long`), xem §8.3.1.1
- [ ] **Counter bắt buộc kiểu `Long`** (64-bit) — xem §8.3.2
- [ ] Gợi ý cấu hình theo cột `Acquisition Class`:
      - `REALTIME` → data change, publishing interval ngắn
      - `PERIODIC` → scan rate theo chu kỳ, queue đủ lớn
- [ ] Xác nhận NodeId sinh ra là `ns=2;s={channel}.{device}.{tag}`
- [ ] Kiểm tra namespace index là `2`
- [ ] Thử tắt/mở máy và kiểm tra counter không bị tràn (xem §8.3.2)
- [ ] Export CSV từ Kepware để xác nhận cột `Data Type` đúng tên kiểu Kepware
- [ ] Kiểm tra `Data Type` trong CSV khớp kiểu Kepware trả về (`Long` ↔ Int64)

### 13.4. Lịch sử thay đổi tài liệu

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| 1.0 | — | Bản khởi tạo do AI khác soạn. Có lỗi: NodeId 4 cấp, 6 partition không kiểm chứng, hai `eventType`, số tag ước lượng |
| **2.0** | 11/11/2026 | Chốt 6 quyết định (§1.4). Sửa NodeId về 3 cấp theo Vinamilk. Gộp về 1 `eventType`. Thêm `eventId` UUID v5. Tính lại số partition bằng murmur2 thật (8 thay vì 6). Sinh lại catalog 404 tag bằng script. Bổ sung `equipment_map.json` mở rộng, `Data Type`, `Eng Units`, `machineType`. Bổ sung phần kiểm thử, rủi ro, kế hoạch triển khai |
| **2.1** | 11/11/2026 | Bỏ phân lớp REALTIME/PERIODIC ở tầng middleware — tần suất do Kepware quyết định, middleware "đọc được gì gửi hết" (§1.2). Bỏ `acquisitionClass` khỏi message. Bổ sung §8.3.1 giải thích `Data Type` vs `Eng Units` và §8.3.2 cảnh báo tràn counter `Word` → phải dùng `Long` (64-bit) |
| **2.2** | 11/11/2026 | **Sửa lỗi cốt lõi về kiểu dữ liệu.** Toàn bộ catalog và §3 chuyển sang **tên kiểu của Kepware** (`Boolean`, `Int`, `Float`, `Long`) trong cột `Data Type` — trước đó dùng tên OPC UA (`Int32`, `Int64`, `Double`) khiến CSV không import được vào Kepware. Thêm §8.3.1.1 (bảng kiểu Kepware → OPC UA), §8.3.1.2 (quy trình export rồi thêm cột), §9.5 (ánh xạ 3 tầng). Sửa §8.3.2: counter bắt buộc `Long` (64-bit), có số liệu chu kỳ tràn thực tế. Thống kê: 87 tag `Boolean`, 99 `Int`, 131 `Float`, 87 `Long` |
| **2.3** | 11/11/2026 | **Hoàn thành code middleware.** Triển khai đầy đủ `IndustrialTelemetry.Middleware/` (17 module + 6 tool) theo đúng các chốt trong tài liệu này: đọc metadata kiểu Vinamilk, chuẩn hóa + partition key + reconnect/state machine kiểu Laird, thread isolation 2 luồng, 3 tầng dedup, ép kiểu theo CSV. Thêm `core/value_types.py` cho tầng mapping §9.5. Sửa §6.9 cấu trúc thư mục cho khớp code thực tế + metadata dùng chung ở `../metadata/`. Thêm §13.2.1 tài liệu bàn giao `kafka_data_contract_and_storage_guide.md`. Kiểm thử offline: selftest 59/59, integration 29/29, verify_doc 20/20 |
| **2.4** | 11/11/2026 | **Bộ CSV import Kepware.** Tách rõ 2 bộ CSV: `TAG_FOLDER/` (20 cột, middleware đọc) và `KEPWARE_IMPORT/` (17 cột chuẩn Kepware, bỏ `TagType`/`TagCode`/`Acquisition Class` — dùng để import vào Kepware). Thêm `tools/generate_kepware_import_csv.py` + `tools/validate_kepware_import_csv.py` (0 lỗi, đủ 404 tag). Thêm `metadata/README.md` hướng dẫn import từng bước. Encoding UTF-8 có BOM, giống hệt file Kepware export |
| **2.5** | 11/11/2026 | **Sửa cột `Address` theo logic tag simulator.** Trước đây `Address` = `{device}.{tagName}` (không đúng logic simulator). Nay sinh `<tiền đo><ordinal 4 chữ số>`: `B`=Boolean, `K`=giá trị số, `S`=String; ordinal đếm **chung trong 1 device** từ `0001`, không reset khi đổi tiền đo — giống hệt file Kepware tham khảu Vinamilk (`ChietRot_Line1.csv`: `B0001, K0002, K0003…`). Thêm `tools/address_rules.py` làm nguồn quy tắc duy nhất (generator + validator dùng chung). Cả 2 validator giờ kiểm tra format / ordinal / tiền đo của `Address`. Thêm §8.3.1.3. **Không ảnh hưởng middleware**: NodeId vẫn dựng từ `ns=2;s={channel}.{device}.{tagName}`, không đọc cột `Address` |
| **2.6** | 11/11/2026 | **Giãn cách địa chỉ `Address` 10 đơn vị.** Công thức đổi từ `number = ordinal` sang `number = (ordinal − 1) × 10` → `B0000, K0010, K0020, B0030…` (thay vì `B0001, K0002, K0003, B0004…`). Mỗi tag chiếm một "ô địa chỉ" riêng: tránh ghi đè vòng đếm trong bộ đếm, và cho phép chèn tag mới giữa các tag cũ mà không phải dồn lại địa chỉ các tag phía sau. Thêm `ADDRESS_STRIDE = 10` vào `tools/address_rules.py` (đổi 1 hằng số là đổi được toàn hệ thống). Validator dùng chung `make_address()` với generator để không phân kỳ logic. Sinh lại 26 file `TAG_FOLDER/` + 26 file `KEPWARE_IMPORT/` (404 tag). **Không ảnh hưởng middleware**: cột `Address` không phải NodeId, middleware không đọc cột này |
| **2.7** | 11/11/2026 | **Sửa lỗi trùng `Address` giữa các device cùng channel.** Ordinal trước đây **reset theo device** → 9 device trong `LINE_01` đều bắt đầu bằng `K0000`/`B0000`… Nguyên nhân: Kepware resolve `Address` theo phạm vi **channel**, không phải device — hai tag khác device nhưng cùng channel mà trùng `Address` sẽ bị **ghi đè lên nhau** khi simulator ghi giá trị (ghi 1 tag → mọi tag cùng `Address` trong channel cùng đổi giá trị). Nay ordinal đếm **liên tục xuyên suốt channel** theo thứ tự device (alphabet) → thứ tự tag trong device; chỉ reset khi sang channel khác (`LINE_01` và `LINE_02` vẫn được phép dùng lại cùng địa chỉ). Thêm `assign_channel_addresses()` + `expected_channel_addresses()` vào `tools/address_rules.py`; generator + cả 2 validator dùng chung, thêm check **Address duy nhất trong toàn channel** (0 lỗi, 404 tag). Sinh lại 26 file `TAG_FOLDER/` + 26 file `KEPWARE_IMPORT/`. **Không ảnh hưởng middleware**: cột `Address` không phải NodeId, middleware không đọc cột này — nhưng **Kepware phải import lại CSV** để có địa chỉ mới |

---

## 14. Trạng thái triển khai

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Metadata (catalog, CSV, equipment_map) | ✅ xong | 26 máy / 404 tag, validator pass |
| Bộ CSV import Kepware (17 cột) | ✅ xong | `metadata/KEPWARE_IMPORT/` — 26 file, 404 tag, 0 lỗi |
| Data contract (`schemaVersion 1.0`) | ✅ xong | Xem `kafka_data_contract_and_storage_guide.md` |
| Code middleware | ✅ xong | 17 module + 6 tool, 108 check offline pass |
| Test tự động (offline) | ✅ xong | `selftest.py` · `integration_test.py` · `verify_doc.py` |
| Cấu hình Kepware thật | ⬜ chờ | Dùng CSV trong `metadata/TAG_FOLDER/` để import |
| Chạy end-to-end với Kepware + Kafka | ⬜ chờ | Cần môi trường thật |
| Tầng Flink / lưu trữ | ⬜ nhóm khác | Theo hướng dẫn §11 của tài liệu bàn giao |

**Lệnh kiểm tra trước khi demo:**

```powershell
cd IndustrialTelemetry.Middleware
python tools\selftest.py           # 59/59
python tools\integration_test.py   # 29/29
python tools\verify_doc.py         # 20/20
```

---

**Tài liệu này là hợp đồng dữ liệu giữa Kepware, Middleware và các
consumer downstream. Khi có thay đổi, phải cập nhật ở đây trước rồi mới
sửa code.**
