# Metadata — hướng dẫn import vào Kepware

Thư mục này là **nguồn chân lý duy nhất** cho toàn bộ metadata của dự án.

```
metadata/
├── catalog.json          # Nguồn sự thật: 26 máy, 404 tag
├── equipment_map.json    # Map "Channel.Device" → metadata máy (sinh tự động)
├── TAG_FOLDER/           # CSV đầy đủ 20 cột — middleware đọc thư mục này
└── KEPWARE_IMPORT/       # CSV 17 cột — dùng để import vào Kepware
```

---

## Hai bộ CSV: dùng cái nào ở đâu?

| Thư mục | Cột | Dùng để |
|---|---|---|
| `TAG_FOLDER/` | 18 cột Kepware + `TagCode`, `Acquisition Class` | **Middleware đọc** — cần `TagCode` để join với `equipment_map.json` |
| `KEPWARE_IMPORT/` | 17 cột chuẩn Kepware (đã bỏ `TagType`, `TagCode`, `Acquisition Class`) | **Import vào Kepware** — không cần cột phu của project |

> **Đừng import file trong `TAG_FOLDER/` vào Kepware.** Nếu import nhầm, Kepware sẽ
> tạo 3 cột phụ không mong muốn trong project.

---

## Quy trình import vào Kepware

### Bước 1 — Tạo channel trước

Trong Kepware tạo 4 channel, tên **khớp chính xác** tên thư mục:

- `LINE_01`
- `LINE_02`
- `LINE_03`
- `SHARED`

### Bước 2 — Import từng channel

Với mỗi channel:

1. Click phải channel → **Import Tags...** (hoặc `Tools > Import Tags`).
2. Chọn **mọi file CSV** trong `KEPWARE_IMPORT/<Channel>/` của channel đó.
3. Chọn device đích tạo trong channel (tên device phải khớp tên file, ví dụ
   `L01_FILLER_01`).

Kepware tự sinh `NodeId` theo cấu trúc channel → device → tag.

### Bước 3 — Kiểm tra NodeId

Mở browser của Kepware, xác nhận NodeId có dạng:

```
ns=2;s=LINE_01.L01_FILLER_01.FillLevel
```

Middleware dựng NodeId theo đúng quy tắc này
(`ns=2;s={channel}.{device}.{tagName}`) — nếu Kepware sinh khác, subscribe sẽ
không tìm thấy tag.

> Cột `Address` trong CSV (`K0001`, `B0003`…) là **địa chỉ tag simulator**,
> khác hoàn toàn với NodeId. Middleware không đọc cột này.

### Bước 4 — Kiểm tra kiểu dữ liệu

Cột `Data Type` đã dùng **đúng tên kiểu của Kepware** nên Kepware giữ nguyên khi
import:

| Kiểu trong CSV | Kepware hiểu là | `valueType` ghi ra Kafka |
|---|---|---|
| `Boolean` | Boolean | `Boolean` |
| `Int` | Int16/Int32 | `Int32` |
| `Word` | UInt16 | `UInt16` |
| `DWord` | UInt32 | `UInt32` |
| `Long` | Int64 | `Int64` |
| `Float` | Float32 | `Float` |
| `Double` | Float64 | `Double` |

**Lưu ý counter:** mọi tag `COUNTER` dùng `Long` (64-bit). Không dùng `Word`
(UInt16) — sẽ tràn sau ~65.535 đơn vị.

### Bước 5 — Kiểm tra tần suất quét

Cột `Scan Rate` đã điều sẵn theo nhóm:

| Loại tag | Scan Rate |
|---|---|
| `DIGITAL` (trạng thái, alarm) | 100 ms |
| `ANALOG` (giá trị đo) | 500 ms |
| `COUNTER` (bộ đếm) | 1000 ms |

Đây là **cấu hình của Kepware**. Middleware đọc mọi thứ Kepware phát ra, không
tự lọc theo tần suất.

---

## Sinh lại CSV

```powershell
# Bộ đầy đủ (middleware đọc) + equipment_map.json
python tools/generate_tag_csv.py

# Bộ import Kepware (17 cột)
python tools/generate_kepware_import_csv.py

# Kiểm tra
python tools/validate_metadata.py            # bộ đầy đủ: 404 tag, 404 TagCode
python tools/validate_kepware_import_csv.py  # bộ import: 17 cột, 0 lỗi
```

**Quy tắc:** `catalog.json` là nguồn sự thật. Sửa tag trong `catalog.json` rồi
chạy lại 2 lệnh trên — **không sửa tay các file CSV**.

---

## Cấu trúc file CSV import (17 cột)

```csv
Tag Name,Address,Data Type,Respect Data Type,Client Access,Scan Rate,Scaling,Raw Low,Raw High,Scaled Low,Scaled High,Scaled Data Type,Clamp Low,Clamp High,Eng Units,Description,Negate Value
MachineState,K0000,Int,1,R/W,100,,,,,,,,,-,Trang thai may (enum muc 0-5),
EmergencyStop,B0020,Boolean,1,R/W,100,,,,,,,,,-,True khi mach dung khanh dang tac dong,
CurrentSpeed,K0040,Float,1,R/W,500,,,,,,,,,bottles/min,Toc do thuc te hien tai; ve 0 khi may dung,
TotalCounter,K0060,Long,1,R/W,1000,,,,,,,,pcs,Tong so chai da xu ly,
```

**Encoding:** UTF-8 **có BOM** (`utf-8-sig`) — giống hệt file Kepware export ra.
Nội dung thuần ASCII (không dấu) nên không lỗi font tiếng Việt.

---

## Quy tắc cột `Address` (logic tag simulator)

Địa chỉ dạng `<tiền đo><ordinal 4 chữ số>`:

| Tiền đo | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `B` | `Boolean` | Rờ rạc |
| `K` | `Int`, `Word`, `DWord`, `Long`, `Float`, `Double` | Giá trị số |
| `S` | `String` | Chuỗi |

**Ordinal đếm liên tục trong 1 CHANNEL**, tăng dần theo thứ tự
device (alphabet) → thứ tự tag trong device — **không reset** khi đổi device
cũng không reset khi đổi tiền đo. **Giãn cách 10 đơn vị**: tag thứ N (1-based)
trong channel nhận địa chỉ `(N − 1) × 10`:

```csv
# LINE_01/L01_AIRCONV_01.csv  (ordinal 1-2)
MachineState,K0000,Int
MachineMode,K0010,Int
# LINE_01/L01_BLOWER_01.csv  (ordinal 3-...)
EmergencyStop,B0020,Boolean     ← ordinal vẫn đếm tiếp, không reset
AlarmCode,K0030,Int
```

> ⚠️ **Vì sao đếm theo CHANNEL chứ không theo device:** Kepware resolve
> `Address` theo phạm vi **channel**, không phải device. Hai tag thuộc hai
> device khác nhau nhưng cùng channel mà trùng `Address` sẽ bị ghi đè lên
> nhau khi simulator ghi giá trị. Vì vậy địa chỉ phải **không trung trong
> toàn channel**.
>
> Các channel khác nhau (`LINE_01` vs `LINE_02`) được phép dùng lại cùng địa
> chỉ — vì chúng nằm ở channel riêng biệt.

**Vì sao giãn cách 10:** mỗi tag chiếm một "ô địa chỉ" riêng, cách nhau 10
đơn vị. Nhờ đó:
- Không ghi đè vòng đếm trong bộ đếm (register/memory của simulator).
- Khi cần thêm tag mới **chen giữa** các tag cũ, chỉ phải sửa địa chỉ của
  tag mới — không phải dồn toàn bộ địa chỉ của các tag phía sau.

Tham số nằm trong `tools/address_rules.py` (`ADDRESS_STRIDE = 10`) — đổi 1 hằng
số là đổi được cho toàn hệ thống.

> Đây là **biến thể** của pattern file Kepware tham khảu Vinamilk
> (`PX3L01L/ChietRot_Line1.csv` với `B0001, K0002, K0003…`). Khác ở chỗ: file
> tham khảu dùng công thức `number = ordinal` (1, 2, 3…) và không có khoảng
> trống; project này dùng `number = (ordinal − 1) × 10`.

> ⚠️ **`Address` KHÔNG phải NodeId.** NodeId là
> `ns=2;s={channel}.{device}.{tagName}`, do Kepware sinh và middleware tự
> dựng lại. Đổi `Address` không ảnh hưởng gì tới middleware.

Quy tắc nằm trong `tools/address_rules.py`, dùng chung cho generator và
validator — không nhân bản logic.

---

## Mapping `equipment_map.json`

| Trường | Ví dụ | Nguồn |
|---|---|---|
| `plantId` | `PLANT_01` | Khóa cấp nhà máy |
| `machines["LINE_01.L01_FILLER_01"].machineId` | `L01_FILLER_01` | Trùng tên device |
| `...machineType` | `CARBONATED_FILLER` | Loại máy (enum 15 giá trị) |
| `...equipmentCode` | `FILL-L01-01` | Mã nghiệp vụ |
| `...lineId` | `LINE_01` | Trùng channel |
| `...processId` | `FILLING` | Công đoạn |

Middleware dùng map này để điền khối `plant` + `machine` trong message Kafka.
