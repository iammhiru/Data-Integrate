# MES UI — Đánh giá nguyên tắc thiết kế & Concept giao diện (v1.0 draft)

**Ngày:** 12/11/2026
**Trạng thái:** Draft để review — **chưa implement**
**Nguồn dữ liệu:** `IndustrialTelemetry.Middleware/metadata/catalog.json` (26 máy / 404 tag / 4 channel)
**Tài liệu liên quan:** `docs/MES_UI_UX_Design_Principles_AI_Guideline_v1.0.md`

---

## PHẦN A — ĐÁNH GIÁ `MES_UI_UX_Design_Principles_AI_Guideline_v1.0.md`

### A.1 Kết luận

Guideline **đạt** và **dùng được làm chuẩn dự án**. Nó hiếm ở chỗ chính xác ở
tầng "MES thực tế" (khác vì vãn phẩm design-system nói chung). Tuy nhiên nó
đang viết ở mức **generic MES/ISA-101**, chưa phải mức **"MES của dự án này"**.
Khoảng cách đó phải lấp bằng một tài liệu bổ sung (Concept này).

Điểm đáng khen:

| # | Nội dung | Vì sao đúng |
|---|---|---|
| 1 | §1.1 Thứ tự ưu tiên khi xung đột (an toàn → hiệu quả → đọc → nhất quán → thẩm mỹ) | Chuẩn, chống "làm đẹp" hy sinh tính đúng đắn |
| 2 | §2 Phân biệt 6 loại giao diện MES, nói rõ MES ≠ SCADA/HMI | Rất đúng; dự án này là **Monitoring**, không phải HMI điều khiển |
| 3 | §7.1 Tách trạng thái máy ≠ trạng thái kết nối ≠ data quality | Đúng trọng tâm. Không map `STOPPED`/`IDLE`/`OFFLINE`/`FAULT` về một màu |
| 4 | §7.2 Phân biệt 0 / null / bad quality / stale / disconnected; cấm thay null bằng 0 | Đúng và là quy tắc quan trọng nhất khi đọc dữ liệu OPC UA |
| 5 | §16.4 Cấm AI bịa công thức KPI/OEE, mapping tag→trạng thái máy, alarm severity | Rất đúng; tránh "thông số cho vui" |
| 6 | §19 Danh sách tham chiếu + cảnh báo không tự khai "compliant with ISA-101" | Thực tế, tránh overclaim compliance |
| 7 | §9.2 Cấm 3D chart, cấm cắt trục gây hiểu sai | Đúng |
| 8 | §15.3 Danh sách component công nghiệp (MachineStatus, OEEKPI, AlarmPanel, DowntimeTimeline...) | Khớp đúng những gì dự án cần |

Kiểm tra tính đúng của các tham chiếu: ISA-101, ISA-18.2, ISA-95/IEC 62264,
ISO 9241-210:2019, WCAG 2.2, NIST SP 800-82 Rev.3 — **tất cả đều là ấn phẩm
đúng và đúng số hiệu**. Không phát hiện trích dẫn sai.

### A.2 Điểm thiếu / cần sửa (đề xuất bổ sung cho v1.1)

Mỗi mục dưới đây là một khoảng trống thật khi áp guideline này vào dự án này:

| # | Khoảng trống | Vì sao quan trọng với dự án này | Đề xuất |
|---|---|---|---|
| G1 | **Không có quy tắc về "hợp đồng dữ liệu" giữa telemetry và UI** | `catalog.json` đã có 404 tag nhưng UI chưa có bảng ánh xạ tag → chỉ số → ý nghĩa hiển thị. Không có cơ chế này, AI/developer sẽ tự chế KPI | Thêm mục: *"Data contract: Tag → Metric Profile → UI slot"*, bắt buộc mọi chỉ số phải trace về `tagName` cụ thể |
| G2 | **Không có quy tắc phân cấp trạng thái (state hierarchy)** | Tag `MachineState` là int enum 0..5. Guideline nói "đừng suy ra từ 1 tag" nhưng không nói cách tổng hợp nhiều tag thành 1 trạng thái | Bắt buộc có bảng **State Resolution Matrix** (thứ tự ưu tiên + nguồn), ghi rõ đây là quy ước UI cần nhà máy phê duyệt |
| G3 | **Thiếu "chế độ đọc màu grayscale / high-contrast" cho ô trạng thái máy** | ISA-101 yêu cầu HMI đọc được khi in đen trắng; guideline chỉ nói "không dùng màu làm tín hiệu duy nhất" nhưng không đưa vào design token | Bổ sung: mỗi trạng thái máy phải có **icon + shape + nhãn chữ** đi kèm màu |
| G4 | **Không nói về i18n** | Dự án đang dùng nhãn tiếng Việt ("Đang chạy", "Ca", "Sản phẩm") và thuật ngữ OEM (Blow Moulding, CIP, Seamer). Cần quy tắc: nhãn UI là tiếng Việt, `machineType`/`tagName` giữ nguyên tiếng Anh kỹ thuật | Bổ sung mục i18n + quy tắc đặt tên |
| G5 | **Không có quy tắc đặt KPI ở đâu** | Chính complaint của bạn: OEE bị đẩy vào tab riêng, phải bấm "tính toán". Guideline §5.1 nói "overview trước" nhưng không ràng buộc cụ thể | Bổ sung: **KPI chính phải xuất hiện ở tầng Overview, không được ẩn sau hành động thủ công**; mọi KPI phải có nhãn phạm vi thời gian + nút drill-down |
| G6 | **Thiếu quy tắc "derived vs stored"** | OEE/downtime/quality rate là **derived** từ event stream, không phải tag gốc. UI phải phân biệt giá trị đo (từ tag) với giá trị tính (từ aggregation) | Bổ sung: mọi KPI ghi rõ nguồn: `Tag trực tiếp` / `Tính từ Spark` / `Tính từ PG batch` |
| G7 | **Thiếu quy tắc master data & "dữ liệu không có thì hiển thị gì"** | Ca/SKU/plan/order **không có trong middleware**. Nếu chưa có nguồn, UI phải hiển thị `—` + nhãn "chưa có nguồn dữ liệu", không được bịa | Bổ sung mục master-data contract, gắn với §7.2 |
| G8 | **Thiếu quy tắc alarm dictionary** | `AlarmCode` là int, không có bảng tra. UI không thể hiển thị "Alarm 417" | Bổ sung: bắt buộc có file mapping `alarmCode → mô tả/severity/response`, chưa có thì hiển thị mã + nhãn "chưa phân loại" |
| G9 | **Thiếu tiêu chí hiệu năng định lượng** | 404 tag × update ~1s; cần quy tắc throttle/batching/virtualization cụ thể | Bổ sung: ngưỡng (ví dụ ≤ 1 re-render/s theo vùng, bảng > 200 dòng dùng virtualization) |
| G10 | **Thiếu quy tắc "không được dùng dữ liệu giả trong production path" kèm cơ chế** | §16.2 có nói, nhưng chưa có quy trình đánh dấu mock | Bổ sung: mock nằm trong `/mock` riêng, badge "MOCK" bắt buộc, không trộn vào API thật |

### A.3 Quyết định đề xuất

- **Giữ guideline làm "tầng nguyên tắc" (level 1)**, không sửa nội dung hiện tại.
- **Thêm tài liệu này (level 2)** làm "tầng dự án": ánh xạ nguyên tắc → quyết định cụ thể
  cho dataset này.
- Sau khi concept chốt, **mở rộng guideline thành v1.1** bằng các mục G1–G10 ở trên,
  để guideline tự đủ sức chứa cho dự án.

---

## PHẦN B — HỢP ĐỒNG DỮ LIỆU (khớp 100% với middleware)

### B.1 Hình hình thực tế

```
PLANT_01 — 26 máy — 404 tag — 4 channel
├── LINE_01  (9 máy)  — PET bottle, có CO2
│   PREFORM_FEEDER → STRETCH_BLOW_MOULDER → AIR_CONVEYOR → BOTTLE_RINSER
│   → CARBONATED_FILLER → SCREW_CAPPER → BOTTLE_LABELER → DATE_CODER → CASE_PACKER
├── LINE_02  (9 máy)  — PET bottle, không CO2
│   ... → STILL_FILLER → ...
├── LINE_03  (7 máy)  — CAN line
│   CAN_DEPALLETIZER → CAN_RINSER → CAN_FILLER → CAN_SEAMER
│   → DATE_CODER → CAN_INSPECTION → CASE_PACKER
└── SHARED  (1 máy)  — CIP_SKID_01 (dùng chung cho 3 line)
```

### B.2 Cấu trúc tag — phân tầng theo 3 tầng "tính đặc trưng"

Mọi tag thuộc đúng 1 trong 3 tầng. Đây là nền tảng để màn popup "khác nhau theo máy".

**Tầng 1 — Core (có ở 25/26 máy, mọi máy trừ CIP_SKID):**

| tagName | Kiểu | Đơn vị | Ý nghĩa hiển thị |
|---|---|---|---|
| `MachineState` | Int enum | – | Trạng thái máy (0 OFF · 1 STARTING · 2 RUNNING · 3 STOPPED · 4 FAULTED · 5 MAINTENANCE) |
| `MachineMode` | Int enum | – | Chế độ (0 OFF · 1 MANUAL · 2 AUTO · 3 MAINTENANCE) |
| `EmergencyStop` | Bool | – | Dừng khẩn |
| `AlarmCode` | Int | – | Mã alarm (0 = không alarm) |
| `CurrentSpeed` | Float | theo máy | Tốc độ thực tế |
| `DesignSpeed` | Float | theo máy | Tốc độ thiết kế/setpoint |
| `TotalCounter` | Long | pcs/cases/pallets/cycles | Tổng đã xử lý |
| `GoodCounter` | Long | pcs | Sản lượng đạt |
| `DefectCounter` | Long | pcs | Sản lượng lỗi |

**Tầng 2 — Nhóm đặc trưng theo `machineType`** (mỗi máy có 4–10 tag)
Ví dụ: `CARBONATED_FILLER` → FillLevel, FillRate, HeadCount, CO2Pressure,
CO2FlowRate, ProductTemp, PowerConsumption, Starved, Blocked.
`STRETCH_BLOW_MOULDER` → MoldTemp, HeaterTemp, BlowPressure, BottleWeight,
CavityCount, CycleTime, PowerConsumption…

**Tầng 3 — Đặc trưng riêng (chỉ 1–2 máy)** — ví dụ `CIP_SKID` có pH,
Conductivity, ChemicalDose, TankLevel, TankTemp, FlowRate, Pressure,
CirculationOn, HeatingOn.

> **Hệ quả thiết kế:** popup chi tiết máy **không** được hard-code theo `machineId`,
> mà dựng theo `machineType` + nhóm tag đã khai báo trong catalog. Máy mới thêm
> vào catalog tự động có popup đúng, không cần sửa code UI.

### B.3 Khoảng trống dữ liệu (UI sẽ cần, middleware chưa có)

| Dữ liệu | Nguồn hiện tại | Đề xuất |
|---|---|---|
| Ca (A/B/C), giờ ca | ❌ không có | Master data ở PostgreSQL (`shift`) |
| SKU / sản phẩm đang chạy | ❌ không có | `product` + work order ở PG |
| Plan / target sản lượng | ❌ không có | `production_plan` ở PG |
| Ideal cycle time | ❌ không có | `product.ideal_cycle_time_sec` ở PG (cần cho Performance) |
| Tên tiếng Việt của máy/công đoạn | ❌ chỉ có `equipmentCode` + `machineType` | Bổ sung `displayName` (VI) + `processName` (VI) vào `equipment_map.json` |
| Ý nghĩa mã alarm | ❌ chỉ có int | File `alarm_dictionary.json` (mã → mô tả VI, severity, hướng dẫn xử lý) |
| Bảng tra enum `MachineState`/`MachineMode` | có trong design doc §9.1 | Đưa vào catalog dưới dạng `enums` để UI không hard-code |

**Quy tắc bất di bất dịch:** mọi trường ở trên khi chưa có nguồn → UI hiển thị `—`
với nhãn *"chưa có nguồn dữ liệu"*, **không** dùng số giả, **không** dùng 0.

---

## PHẦN C — CONCEPT GIAO DIỆN

### C.1 Vấn đề cần giải quyết (chốt lại)

| Hiện trạng | Vấn đề | Concept mới |
|---|---|---|
| OEE nằm ở tab riêng, bấm "Tính toán" mới ra | Không dùng được trong vận hành hằng ngày; vi phạm §5.1 của guideline | OEE tính tự động từ stream, hiển thị ở **tầng 1 và 2**; tab Analytics chỉ để drill-down |
| 1 màn tất cả, tab dọc | Không có hierarchy ISA-95, không scale được | 4 tầng: Plant → Line → Machine → Tag |
| Mỗi máy 1 hàng tag giống nhau | Không phản ánh đặc trưng thiết bị | Popup dựng theo `machineType` |
| Trạng thái máy gộp "Dừng/Chờ/Đang chạy" | Không phân biệt FAULT vs STOPPED vs MAINTENANCE | 8 trạng thái đầy đủ + icon + nhãn |
| Catalog giả 100 máy `M001` | Không khớp dữ liệu middleware | 26 máy thật, 404 tag thật |

### C.2 Cấu trúc thông tin (IA)

```
MES
├─ 🏭 Plant Overview           ← MÀN HÌNH CHÍNH (danh sách line)
├─ ⚙ Line View                 ← bấm 1 line → mở line đó
│   ├─ Line Header (panel trạng thái chung)
│   ├─ Line Flow (sơ đồ dòng + machine card)
│   └─ Right Rail (alarms / downtime / data quality)
├─ 🔧 Machine Detail            ← Drawer/slide-over, nội dung động theo machineType
├─ 📈 Analytics
│   ├─ OEE (drill-down theo line/máy/ca)
│   ├─ Downtime & Pareto nguyên nhân
│   └─ Quality / Defect
└─ ⚙ Administration (out of scope giai đoạn này)
```

**Điều hướng tổng thể:** Sidebar trái (nhóm theo nghiệp vụ) + Top bar cố định chứa
**context toàn cục**: Plant → Line → Shift → trạng thái kết nối SignalR → đồng hồ ca →
nút Alarm (badge số alarm đang mở). Không để người dùng mất context khi drill-down.

### C.3 Màn 1 — Plant Overview (màn chính, thay thế "dashboard basic")

**Bố cục:**

```
┌──────────────────────────────────────────────────────────────────────┐
│ Topbar: PLANT_01 · Ca A (06:00–14:00) · ● Đang kết nối · 14:32 · 🔔 3 │
├──────────────────────────────────────────────────────────────────────┤
│  KPI tổng:  Sản lượng  |  OEE (A×P×Q)  |  Tỷ lệ đạt  |  Downtime   │
├──────────────────────────────────────────────────────────────────────┤
│  ┌─── LINE_01 ─────┐ ┌─── LINE_02 ─────┐ ┌─── LINE_03 ─────┐        │
│  │ ● RUNNING        │ │ ● RUNNING        │ │ ▲ STOPPED       │        │
│  │ SKU: ...  Ca A  │ │ SKU: ...  Ca A  │ │ SKU: ...        │        │
│  │ OEE 78.4%       │ │ OEE 71.2%       │ │ OEE 64.9%       │        │
│  │ A 88 P 91 Q 98  │ │ ...              │ │ ...             │        │
│  │ ▓▓▓▓░ 78/120k   │ │ ...              │ │ ...             │        │
│  │ mini: 9 máy ●●●  │ │ ...              │ │ ...             │        │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘        │
│  ┌─── CIP (SHARED) ───────────────┐  ┌─── Alarm đang mở ───────┐    │
│  │ ● RUNNING · 1 máy              │  │ L03_SEAMER_01  A-417     │    │
│  └────────────────────────────────┘  │ ...                      │    │
└──────────────────────────────────────────────────────────────────────┘
```

**Line card chứa (mỗi card phải có ý nghĩa vận hành):**
- Trạng thái tổng hợp của line (dẫn xuất từ máy kém nhất — xem C.4)
- SKU / sản phẩm đang chạy, Ca hiện tại
- OEE 3 thành phần (A/P/Q) — **luôn hiển thị, không cần bấm**
- Sản lượng thực tế vs kế hoạch (progress bar)
- Phân bố trạng thái 9 máy (dải màu + số đếm), dạng **stacked bar** (không dùng pie)
- Số alarm đang mở, downtime hiện tại
- Sparkline sản lượng 30 phút

**Click vào card → Màn 2 (Line View).**

### C.4 Màn 2 — Line View (màn trọng tâm)

Bố cục 3 vùng, cố định khi cuộn:

```
┌───────────────────────────────────────────────────────────────────────┐
│ LINE_01  · PET Bottle · SKU: ABC-500 · Ca A 06:00–14:00 · ● RUNNING  │  ← LINE HEADER
│ ┌─────────────┬──────────┬──────────┬───────────┬───────────────────┐ │
│ │ OEE 78.4%   │ A 88.1%  │ P 91.2%  │ Q 97.6%  │ Sản lượng 78.2k/│ │
│ │ (A×P×Q)     │ 88/120k  │ 82.4k    │ 76.3k    │ 120k  · 65.2%    │ │
│ └─────────────┴──────────┴──────────┴───────────┴───────────────────┘ │
├───────────────────────────────────────────────────────────────────────┤
│ LINE FLOW  ───────────────────────────────────────────────────────────  │
│  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐  ┌──────┐    │
│  │PREFEED│→  │BLOWER│→  │AIRCNV│→  │RINSER│→  │FILLER│→ │CAPPER│    │
│  │ ●    │   │ ●    │   │ ▲    │   │ ●    │   │ ●    │  │ ●    │    │
│  │120/min│   │115/min│  │ 0/min │   │118/min│  │112/min│ │ 0/min │    │
│  │98.2%  │   │97.0%  │   │ 0.0% │   │99.1%  │  │99.4%  │ │ 0.0%  │    │
│  └──────┘   └──────┘   └──────┘   └──────┘   └──────┘  └──────┘    │
│  ...→ LABELER → CODER → CASEPACKER                                   │
├───────────────────────────────────────────────────────────────────────┤
│ RIGHT RAIL: Alarm đang mở (3) │ Downtime 20' │ Data quality 99.2%  │
└───────────────────────────────────────────────────────────────────────┘
```

#### C.4.1 Line Header — "panel trạng thái chung"

| Nhóm | Trường | Nguồn |
|---|---|---|
| Định danh | Line ID, mô tả line, plant | master |
| Sản xuất | SKU đang chạy, ca, thời gian đã trôi / còn lại của ca | PG master `[NEEDS SOURCE]` |
| Sản lượng | Thực tế / kế hoạch / % | PG + tag đếm |
| OEE | OEE = A × P × Q, mỗi thành phần có công thức tooltip | Spark/PG (`architecture.txt` §6 — **đã có công thức được duyệt**) |
| Trạng thái | Line state, alarm count, downtime hiện tại | từ máy |

#### C.4.2 Machine Card — trạng thái + vài thông số đúng nghĩa

Mỗi card hiển thị **tối đa 6–8 trường**, chọn theo đặc trưng máy (không phải mọi tag):

```
┌─────────────────────────┐
│ FILL-L01-01   FILLER    │  ← equipmentCode + machineType
│ ● RUNNING         AUTO  │  ← badge trạng thái (icon+màu+chữ) + mode
│                         │
│ Tốc độ    112 / 120    │  ← CurrentSpeed / DesignSpeed (bottles/min)
│ ▓▓▓▓▓▓▓▓▓▓░░  93.3%   │
│ Mức chiết  87.5 %      │  ← tag đặc trưng nhất của máy
│ Sản lượng  78,204 / 412│  ← GoodCounter / DefectCounter
│ ─────────────────────── │
│ ⚠ A-417 · 12:41:03     │  ← alarm (nếu có) · thời điểm nhận gần nhất
└─────────────────────────┘
```

**Quy tắc hiển thị bắt buộc:**
- Mọi số có **đơn vị** (theo `catalog.json`), dùng **tabular numerals**.
- Giá trị `null` → `—`, không phải `0`. Có quality khác Good → gắn dấu chấm màu + tooltip.
- Tag cũ hơn ngưỡng → badge "stale" + thời điểm nhận gần nhất (ngưỡng theo `scan_rate_ms` của tag, **không** dùng 1 timeout chung).
- Card **không** tự đổi layout khi realtime update (tránh nhảy).
- Số trên card phải là **số có ý nghĩa vận hành** — ví dụ máy nén khí nên có áp suất, máy sấy nên có nhiệt độ; tuyệt đối không hiển thị tag vô nghĩa (vd. `TotalCounter` của CIP_SKID là `cycles` — phải ghi rõ đơn vị).

#### C.4.3 Line Flow — bố cục dòng

- Sơ đồ theo đúng thứ tự `processId` (đã có sẵn trong catalog → không cần vẽ tay).
- Mũi tên vật chất nối các trạm.
- Machine dùng chung (CIP_SKID) đặt ở **Lane "Shared"** phía dưới, nối bằng nét đứt vào các line nó phục vụ — tránh nhân bản máy vào từng line.
- Nhóm theo vùng công nghiệp (nếu có) bằng nền nhạt + nhãn vùng.

### C.5 Màn 3 — Machine Detail (popup/slide-over, nội dung động theo máy)

Bố cục: **Slide-over phải** (không phải modal nhỏ), rộng ~720px, 4 tab.

```
┌──────────────────────────────────────────────────────────────────┐
│ FILL-L01-01 · CARBONATED_FILLER          ● RUNNING · AUTO      │
│ LINE_01 › FILLING · Cầu FILL L01 · ● kết nối OK · 12:41:03     │
├──────────────────────────────────────────────────────────────────┤
│ [ Tổng quan ] [ Thông số ] [ Biểu đồ ] [ Sự kiện ]             │
├──────────────────────────────────────────────────────────────────┤
│  TỔNG QUAN                                                   │
│  ┌─ Trạng thái ─────────┬─ Sản lượng ─────────┬─ Hiệu suất ──┐  │
│  │ State: RUNNING       │ Total   412,880    │ Current  112  │  │
│  │ Mode : AUTO          │ Good   410,772     │ Design   120  │  │
│  │ E-Stop: false        │ Defect    2,108    │ Tỷ lệ  93.3% │  │
│  │ Alarm: 0             │ Yield  99.49%      │ Power 18.4 kW│  │
│  │ Starved: false       │                       │               │  │
│  │ Blocked: false       │                       │               │  │
│  └──────────────────────┴──────────────────────┴───────────────┘  │
│  ┌─ Thông số đặc trưng (auto theo machineType) ────────────────┐  │
│  │ FillLevel 87.5 % │ FillRate 112 bottles/min │ HeadCount 6   │  │
│  │ CO2Press 3.2 bar │ CO2Flow 258 Nm3/h         │ ProdTemp 8.1°C│  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Xu hướng (sparkline 30') ─────────────────────────────────┐   │
│  │ [FillLevel] [CurrentSpeed] [CO2Pressure]  ← chọn tag để xem │   │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Alarm & sự kiện gần đây ─────────────────────────────────┐   │
│  │ 12:41 A-417  Rò rỉ CO2 — chưa xử lý                         │   │
│  │ 11:02 STATE  STOPPED → RUNNING                              │   │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**Cơ chế "nội dung động":**
- Lấy `machineType` → tra **Metric Profile** (nhóm tag) → dựng lưới thông số.
- Ví dụ so sánh 2 máy cùng line nhưng khác loại:
  - `CARBONATED_FILLER`: FillLevel, FillRate, CO2Pressure, CO2FlowRate, ProductTemp, HeadCount, PowerConsumption
  - `STILL_FILLER`: FillLevel, FillRate, FillingPressure, WaterTemp, WaterConductivity, ProductTemp, HeadCount
  - `CIP_SKID`: pH, Conductivity, ChemicalDose, TankTemp, TankLevel, FlowRate, Pressure, CirculationOn, HeatingOn
- **Tầng tab "Thông số"** liệt kê **toàn bộ tag** của máy (404 tag / 26 máy → mỗi máy 13–18 tag, rất vừa) — không cần phân trang.
- Tab "Biểu đồ": chọn 1–3 tag để vẽ; mặc định chọn tag đặc trưng.
- Tab "Sự kiện": timeline chuyển trạng thái + alarm (nguồn: batch `downtime_event`).

### C.6 State Resolution Matrix (đề xuất, **cần nhà máy phê duyệt**)

Ưu tiên từ trên xuống, dùng để gán màu & nhãn cho ô trạng thái:

| # | Điều kiện | Trạng thái UI | Màu | Icon | Nhãn VI |
|---|---|---|---|---|---|
| 1 | Không có dữ liệu / quality≠Good quá hạn | `NO_DATA` | Xám đậm | `?` | Mất dữ liệu |
| 2 | `MachineState=4` hoặc `EmergencyStop=true` | `FAULT` | Đỏ | `!` | Lỗi |
| 3 | `MachineState=5` hoặc `MachineMode=3` | `MAINTENANCE` | Xám | wrench | Bảo trì |
| 4 | `MachineState=1` | `STARTING` | Xanh dương | spinner | Khởi động |
| 5 | `MachineState=2` và `Starved=true` | `STARVED` | Hổ phách | `!` | Thiếu nguyên liệu |
| 6 | `MachineState=2` và `Blocked=true` | `BLOCKED` | Cam | `⛔` | Tắc nghẽn |
| 7 | `MachineState=2` | `RUNNING` | Xanh | `▶` | Đang chạy |
| 8 | `MachineState=3` | `STOPPED` | Xám trung | `■` | Dừng |
| 9 | `MachineState=0` | `OFF` | Than | `⏻` | Tắt |
| 10 | `AlarmCode≠0` (khi state không fault) | `WARNING` | Vàng | `⚠` | Cảnh báo |

**Line state** = trạng thái "xấu nhất" trong 9 máy, theo thứ tự:
`FAULT > MAINTENANCE > BLOCKED > STARVED > STOPPED > STARTING > RUNNING`.

> ⚠ **Xung đột cần bạn chốt:** trong ảnh tham khảo bạn gửi, **đỏ = dừng**. Nhưng
> guideline §6.3/§7.1 yêu cầu phân biệt *dừng có chủ đích* với *lỗi*. Đề xuất
> của tôi: **Đỏ = lỗi (FAULT)**, **Xám = dừng (STOPPED)** — an toàn hơn vì người
> vận hành không bị "đỏ hóa" mọi lần dừng chuyển sản phẩm. Nếu bạn muốn giữ đúng
> quy ước đỏ = dừng, ta sẽ đổi và dùng **icon + nhãn** để bù lại.

### C.7 Realtime & hiệu năng

| Quy tắc | Giá trị |
|---|---|
| Nguồn | SignalR hub `/hubs/telemetry`, event `Snapshot` (đã có sẵn) |
| Chu kỳ nhận | 1 Hz (backend push) |
| Frontend throttle render | ≤ 1 lần/s; chỉ re-render vùng có thay đổi (memo theo `machineId`) |
| Bảng > 200 dòng | virtualization |
| Stale threshold | theo `scan_rate_ms` của từng tag × hệ số (KHÔNG một timeout chung) |
| Giữ context | realtime update không được làm mất scroll / focus / selection / filter đang chọn |
| Khi mất kết nối | hiển thị "Đang mất kết nối" + đóng băng giá trị kèm badge stale, KHÔNG giữ số như thể còn sống |

### C.8 Design token (đề xuất bổ sung ngoài guideline)

**Màu trạng thái máy** (đủ tương phản, kiểm tra được ở grayscale):

| Token | Hex | Nền | Chữ |
|---|---|---|---|
| `state.running` | `#15803D` | `#DCFCE7` | `#14532D` |
| `state.stopped` | `#475569` | `#E2E8F0` | `#1E293B` |
| `state.fault` | `#DC2626` | `#FEE2E2` | `#7F1D1D` |
| `state.starved` | `#D97706` | `#FEF3C7` | `#78350F` |
| `state.blocked` | `#EA580C` | `#FFEDD5` | `#7C2D12` |
| `state.maintenance` | `#64748B` | `#F1F5F9` | `#334155` |
| `state.starting` | `#2563EB` | `#DBEAFE` | `#1E3A8A` |
| `state.off` | `#334155` | `#F8FAFC` | `#0F172A` |
| `state.warning` | `#CA8A04` | `#FEF9C3` | `#713F12` |
| `state.nodata` | `#94A3B8` | `#F8FAFC` | `#475569` |

Nền ứng dụng: `#0F172A` (dark, phù hợp phòng điều khiển) hoặc `#F8FAFC` (light).
Chữ: 1 font, tabular numerals cho mọi số.

---

## PHẦN D — Đề xuất triển khai (sau khi chốt)

### D.1 Cấu trúc thư mục frontend (đề xuất)

```
dashboard/frontend/src/
├── app/
│   ├── App.tsx                    ← chỉ làm shell + routing
│   ├── routes/
│   │   ├── PlantOverview.tsx
│   │   ├── LineView.tsx
│   │   ├── MachineDetail.tsx
│   │   └── analytics/…
├── design-system/
│   ├── tokens.css                 ← màu, spacing, typography, radius
│   └── theme.css
├── components/
│   ├── shell/                     ← Sidebar, TopBar, ContextBar
│   ├── line/                      ← LineHeader, LineFlow, MachineCard, LineStateBadge
│   ├── machine/                   ← MachineDrawer, TagGrid, MetricProfile, TrendChart
│   ├── kpi/                       ← KpiCard, OeeTriple, ProgressBar
│   └── common/                    ← StatusBadge, DataQualityDot, Sparkline, StaleBadge, EmptyState
├── domain/                        ← TYPES + logic thuần, không phụ thuộc React
│   ├── catalog.ts                 ← parse catalog.json → 26 máy / metric profile
│   ├── machine-state.ts           ← State Resolution Matrix
│   ├── oee.ts                     ← công thức OEE (theo architecture.txt §6)
│   └── metrics.ts                 ← định nghĩa KPI + nguồn
├── data/
│   ├── signalr.ts
│   ├── snapshot-store.ts          ← store ngoài React (tránh re-render toàn trang)
│   └── mock/                      ← mock TÁCH RIÊNG, badge "MOCK"
└── styles/
```

### D.2 Nguồn dữ liệu cho UI (2 pha)

| Pha | Nguồn | Nội dung |
|---|---|---|
| **UI hôm nay (mock → thật)** | `catalog.json` (frontend copy, sinh từ middleware) + `/api/snapshot` | 26 máy, 404 tag, giá trị realtime |
| **Pha tích hợp** | `catalog.json` + `/api/catalog` + `/api/metrics` (Spark/PG) | + OEE, plan, ca, SKU, downtime, alarm |

`catalog.json` **sinh ra từ middleware** (single source of truth) — không copy tay.

### D.3 Trình tự thực hiện đề xuất

1. ~~**Mock 3 màn** (Plant Overview, Line View, Machine Detail)~~ — ✅ **ĐÃ XONG**
   (xem `dashboard/frontend/mock.html`, mở `http://127.0.0.1:5173/mock.html`).
2. Chốt design token + State Resolution Matrix.
3. Bổ sung `displayName`/`processName` (VI) vào `equipment_map.json`; thêm `alarm_dictionary.json`.
4. Xây design system + component library.
5. Tích hợp SignalR thật, thay mock.
6. Mở rộng: Analytics (OEE drill-down, Downtime Pareto, Quality).
7. Backend: thay `Catalog.cs` giả (100 máy `M001`) bằng catalog thật 26 máy/404 tag; thêm endpoint OEE/plan/shift.

---

## PHẦN E — CẦN BẠN CHỐT (5 quyết định)

1. **Màu trạng thái**: đỏ = LỖI (khuyến nghị, đúng ISA-101) hay đỏ = DỪNG (theo ảnh tham khảo)?
2. **Nền giao diện**: dark (phòng điều khiển, như `Laird.System.UI`) hay light (như `Vinamilk.MES.UI`)?
3. **Có dùng `Laird.System.UI` (SvelteKit) làm nền thay vì React không?** Hiện dashboard đang là React 19 + Vite; `Laird.System.UI` đã có sẵn `factorymap` (zone → machine → detail) rất giống ý tưởng của bạn.
4. **Ca / SKU / kế hoạch lấy từ đâu?** Master data PostgreSQL, hay để UI tạm hiển thị `—`?
5. **Mock 3 màn nào trước?** Đề xuất: Plant Overview → Line View (LINE_01) → Machine Detail (FILLER & CIP để thấy rõ sự khác biệt theo `machineType`).

---

## PHẦN F — QUYẾT ĐỊNH ĐÃ CHỐT (từ mock review)

| # | Quyết định | Ghi chú |
|---|---|---|
| F1 | **Màu trạng thái**: đỏ = LỖI (FAULT), xám = DỪNG (STOPPED) | Đúng ISA-101. Màu KHÔNG phải tín hiệu duy nhất — mọi trạng thái đều có glyph + nhãn tiếng Việt |
| F2 | **Nền giao diện**: dark (phòng điều khiển) | Token định nghĩa ở `src/mock/tokens.css` |
| F3 | **Stack**: giữ React 19 + Vite | Mock tách riêng ở `mock.html` + `src/mock/`, không ảnh hưởng app chính |
| F4 | **Master data**: PostgreSQL | Ca / SKU / kế hoạch / tên tiếng Việt / alarm dictionary |
| F5 | **Mock 3 màn**: Plant Overview → Line View (LINE_01) → Machine Detail | ✅ đã build, xem `mock.html` |

### F.1 — Quy tắc dữ liệu rút ra từ mock (bắt buộc khi tích hợp thật)

Các lỗi đã phát hiện khi dựng mock — **những lỗi này sẽ lặp lại nếu không ràng buộc
ở tầng backend**, nên ghi lại thành quy tắc:

| # | Quy tắc | Lý do |
|---|---|---|
| F1.1 | **Bộ đếm phải cùng đơn vị với kế hoạch.** `TotalCounter` là *tích luỹ từ đầu đời máy*, kế hoạch ca là *theo ca* → phải có bảng `shift_counter_snapshot` (mốc đầu ca) để tính sản lượng ca = `counter_now - counter_at_shift_start` | Nếu không: "đạt 3929%" — vô nghĩa |
| F1.2 | **Máy tham chiếu để tính OEE của line phải là công đoạn CHIẾT** (ra sản phẩm chính, đơn vị pcs). Không dùng "máy đầu tiên" vì máy đầu đếm preform/nắp — khác đơn vị | Sai số lượng × 9 nếu cộng cả line |
| F1.3 | **Đơn vị là thuộc tính của TAG, không phải của giá trị.** UI phải đọc `unit` từ catalog, không hard-code "đv/ph" | Băng tải là `m/min`, đóng thùng là `cases/min`, máy kiểm tra là `cans/min` |
| F1.4 | **Mỗi loại máy có bộ đếm khác nhau.** 24/26 máy có `GoodCounter`; `DATE_CODER` chỉ có `PrintCount`. UI phải tra bộ đếm theo `machineType` | Hiện "Đạt: —" là dấu hiệu UI chưa đúng, không phải thiếu dữ liệu |
| F1.5 | **Tốc độ thiết kế phải theo đúng đơn vị của từng máy** (`DESIGN_SPEED_BY_UNIT`) | Dùng chung một con số → Performance tính sai |
| F1.6 | **Yield chỉ hiện khi máy thực sự có cặp `GoodCounter`/`TotalCounter`.** Máy chỉ có `PrintCount` thì không hiện Yield | Hiện "Yield: —" gây hiểu nhầm là mất dữ liệu |
| F1.7 | **`MachineState` stale mới được coi là mất trạng thái.** Tag phụ stale chỉ gắn badge tại chỗ | 1 tag hỏng không được làm cả máy thành `NO_DATA` |

### F.2 — Nhận ký lỗi đã sửa trong mock (để tránh tái phát)

| Lỗi | Nguyên nhân | Bài học |
|---|---|---|
| Toàn bộ giao diện mất style | `tokens.css` dùng comment `//` — **CSS không hỗ trợ `//`**, trình duyệt nuốt mất block `:root` chứa toàn bộ token | Comment CSS phải dùng `/* */`. Nên có lint rule chặn |
| Card máy không đổi màu theo trạng thái | `border-left` viết tĩnh trong CSS | Trạng thái phải bind động từ `STATUS_META` |
| "đạt 3929%" | Bộ đếm tích luỹ vs kế hoạch theo ca | → F1.1 |
| Tốc độ hiện "9 / 9 đv/ph" cho băng tải khí | Hard-code "đv/ph" | → F1.3 |
| "Đạt: —" cho DATE_CODER | Chỉ tìm `GoodCounter` | → F1.4 |
| Metric không hiện đơn vị (`°C` thành `degC`, `µS/cm` thành `uS/cm`) | Hàm `unitOf()` trả `null` | → F1.3 + bảng ánh xạ unit → ký hiệu SI |
| `DefectRate = 51%` | Dùng chung profile `%` = 55 ± 22 | Profile analog phải theo **ý nghĩa thông số**, không theo đơn vị |
| "Lượt in 0" | Bộ đếm khởi đầu từ 0 | Seed theo ca, hoặc dùng mốc đầu ca (F1.1) |

---

## G. Đợt cải tiến 2 — theo góp ý review UI (2026-11-12)

Nguồn góp ý: `work.md` (review của AI khác) + `prompt.md` (design requirement) +
ảnh tham khảo `docs/screenshots/Dashboard_sample*.png`, `UI2x2.png`.

### G.1 — Nguyên tắc bất di bất dịch: KHÔNG thanh trượt trong component

**Yêu cầu:** "tránh cho việc thanh trượt xuất hiện trong các component trên giao diện
nhất có thể".

Quyết định: **chỉ còn 1 thanh cuộn ở cấp TRANG**. Không component con nào được
tạo `overflow: auto/scroll` (trừ `.dr-body` của drawer — vì drawer là lớp phủ
toàn màn hình, cuộn bên trong là hành vi chuẩn).

Cách thực hiện cho sơ đồ dòng chảy (`components/ProcessFlow.tsx`):

1. Dàn máy theo **lưới co giãn**; số cột tính bằng `ResizeObserver` từ bề rộng
   thật của container — không dùng `overflow-x` để "giấu" vấn đề.
2. Ưu tiên bố cục **nhiều hàng cân đối** (`cols = ceil(n/2)`) thay vì dồn hết
   vào 1 hàng — khớp với mẫu 2×2 trong `UI2x2.png`.
3. Mũi tên nối được vẽ trên **lớp phủ** (`pointer-events: none`, `overflow: hidden`),
   vị trí đo trực tiếp từ `getBoundingClientRect()` → luôn khớp layout thực tế và
   không bao giờ làm tăng `scrollWidth`.

Bảng tag trong Machine Detail: `table-layout: fixed` + `overflow-wrap: anywhere`
thay cho `.table-scroll`.

### G.2 — Tách 3 chiều trạng thái độc lập (theo `prompt.md` §4)

| Chiều | Nguồn | Nơi hiển thị |
|---|---|---|
| **Machine state** | `MachineState` + `EmergencyStop`/`Starved`/`Blocked`/`AlarmCode` | Badge trạng thái, viền trái card, chip trong Plant Overview |
| **Connection state** | **KÊNH** (`channel`), không phải máy | Badge "Kết nối / Yếu / Mất kết nối" ở header line + card plant |
| **Data quality** | `quality` + `stale` + tuổi bản ghi | Chấm "Mới / Cũ / Không có" trên card & header drawer |

⚠ **Không suy luận connection state từ machine state** (và ngược lại). Máy vẫn
`RUNNING` nhưng kết nối PLC rớt → trạng thái máy là "không xác định", dữ liệu
là "cũ", kết nối là "yếu".

Module mới: `domain/quality.ts` (`ConnectionState`, `Freshness`, `freshnessOf`).

### G.3 — Quy tắc hiển thị thời gian (chống lệch timestamp)

Middleware trả ISO-8601 theo **UTC (hệt giờ)**. UI hiển thị theo **giờ địa
phương nhà máy** (`domain/time.ts`). Trước đây UI cắt chuỗi ISO bằng `.slice(11,19)`
→ lệch 7h so với đồng hồ topbar. **Không được cắt chuỗi thời gian thủ công.**

### G.4 — Hiển thị tiến độ kế hoạch (chống "còn 0 pcs")

`domain/plan.ts` → `planProgress(actual, plan)`:

- dưới kế hoạch → `còn X pcs`
- đạt/vượt kế hoạch → `vượt X pcs` (không bao giờ hiện "còn 0 pcs")

### G.5 — Performance không được vượt 100%

Máy thật **không bao giờ vượt tốc độ thiết kế ổn định**. Mock trước đây dao động
quanh `designSpeed` (±5%) → Performance có lúc = 100%+ → OEE sai. Nay dao động
trong khoảng **92–100%** (`CurrentSpeed = design × wobble`, `wobble ∈ [0.92, 1]`).

### G.6 — Đơn vị hiển thị: chuẩn hoá cả "trên phút" → "trên giờ"

`displayUnit()` nay chuyển thêm `*/min` → `*/ph` (`preform/ph`, `chai/ph`,
`lon/ph`, `nắp/ph`, `pcs/ph`, `thùng/ph`, `m/ph`) — nhà máy VN đọc quen đơn vị
"trên giờ". Đơn vị vẫn lấy từ **catalog tag**, không hard-code theo từng máy.

### G.7 — Bổ sung màn thứ 4: Alarm & Event Center

`pages/AlarmCenter.tsx`. Phân biệt 3 loại thông báo:

- **Alarm** — đang tồn tại, cần xử lý. Nguồn: tag `AlarmCode`.
- **Event** — đã xảy ra. Nguồn: pipeline sự kiện downtime.
- **Notification** — thông báo vận hành. **Chưa có nguồn riêng trong middleware**
  → hiện mới là mô tả, chưa có dữ liệu.

⚠ Không tự suy diễn `severity` của alarm từ mã alarm — chỉ dùng mã do thiết bị
cung cấp.

### G.8 — Điều chỉnh theo góp ý mà KHÔNG làm (có lý do)

| Góp ý | Quyết định | Lý do |
|---|---|---|
| "Thêm trạng thái luồng: Blocked / Starved / Flow interrupted cho các kết nối giữa công đoạn" | **Không thêm** | Góp ý tự nói "không nên suy luận Blocked/Starved chỉ từ RUNNING/STOPPED; cần có dữ liệu đầu vào/đầu ra tương ứng". Catalog hiện **không có** tag đầu vào/đầu ra theo từng công đoạn → sẽ là bịa dữ liệu. Cần bổ sung tag ở tầng middleware trước. |
| "Mini-map / danh sách toàn bản máy để định vị nhanh" | **Thay bằng** panel "Các công đoạn" (danh sách đầy đủ 9 máy + trạng thái + thời điểm cập nhật) | Đã có sẵn trong rail, nay đưa thành panel rõ ràng |
| "Đưa nhiều KPI hơn lên hàng đầu" | **Giữ 4 KPI** + chuyển phần còn lại xuống khu vực phân tích | Đúng góp ý §1.2.A |
| "Production Trend actual vs target" | **Đã thêm** ở Plant Overview và Line View | Yêu cầu của `prompt.md` §3 |

### G.9 — Kiểm thử tự động

`tests/mock-ui.spec.ts` — 13 test, chạy ở 4 kích thước màn hình
(1920 / 1600 / 1280 / 1024):

- Không phần tử nào có overflow ngang ở cả 4 màn hình.
- 9 máy của line đều nằm trong khung nhìn (không bị cắt bên phải).
- Số mũi tên nối = số máy − 1.
- Timestamp trên card khớp đồng hồ topbar (< 2 phút).
- Vượt kế hoạch → hiện "vượt", không hiện "còn 0".
- Performance ≤ 100%.

Chạy: `npx playwright test tests/mock-ui.spec.ts` (cần dev server ở :5173).
