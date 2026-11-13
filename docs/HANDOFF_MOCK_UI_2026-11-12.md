# Bàn giao phiên làm việc — MES Mock UI (2026-11-12)

> **Đọc file này TRƯỚC khi bắt đầu.** Nó ghi lại toàn bộ trạng thái, quyết định thiết kế
> và việc còn lại.

---

## 0. ⚠ LÝ DO PHIÊN NÀY KHÔNG ĐỌC ĐƯỢC ẢNH — CẦN MỞ PHIÊN MỚI

Phiên làm việc vừa rồi **hoàn tất phần code**, nhưng **không đọc được file ảnh** —
kể cả ảnh chụp màn hình đơn giản (SVG 200×120 với chữ "BATYEU TEXT SAMPLE").

**Các lần thử đều thất bại:**

| Cách thử | Kết quả |
|---|---|
| `Read` trên `UI2x2.png`, `Dashboard_sample.png`, `Dashboard_sample_2.png` | Trả về "Read image file" nhưng **không hiển thị nội dung hình ảnh** cho tôi |
| `Read` trên ảnh JPG bạn đính kèm trong chat | Tương tự — không hiển thị |
| `browser_take_screenshot` (ảnh chụp tab trình duyệt) | Không hiển thị |
| `computer_screenshot` (ảnh chụp màn hình máy) | Không hiển thị |
| Nhúng SVG `data:` URI vào trình duyệt rồi chụp lại | Không hiển thị |
| Thu nhỏ ảnh bằng PIL (Pillow) rồi đọc lại | Không hiển thị |

**Kết luận:** đây là **giới hạn của phiên/phiên bản model đang chạy**, KHÔNG phải file hỏng
(các file PNG đều mở được bằng PIL: `UI2x2.png` 1536×1024, `Dashboard_sample.png` 1568×1003,
`Dashboard_sample_2.png` 1842×1001).

**Cách đã dùng để vượt qua:** bạn nhờ AI khác xem ảnh rồi dựng lại thành file HTML mô tả
trung thực — `docs/mes_dashboard_2x2.html` (302 dòng, có chú thích spec chi tiết ở đầu file).
Tôi đã đọc file này để hiểu bố cục. **Đây là nguồn spec hình ảnh đáng tin cậy cho phiên mới.**

### Việc cần làm NGAY khi mở phiên mới

1. `Read` lại 3 ảnh: `docs/screenshots/UI2x2.png`, `Dashboard_sample.png`, `Dashboard_sample_2.png`.
2. Nếu vẫn không đọc được → dùng `docs/mes_dashboard_2x2.html` làm spec chính (đã đầy đủ).
3. So sánh mock hiện tại với ảnh thật và tiếp tục chỉnh.

---

## 1. Yêu cầu gốc của phiên này

Bạn yêu cầu (nguyên văn, tóm tắt):

1. **Sửa lỗi bố trí sơ đồ dòng chảy** — đang phải dùng thanh trượt ngang để xem dòng chảy.
2. **Tuyệt đối tránh thanh trượt xuất hiện trong các component** trên giao diện.
3. **Mock lại UI** theo góp ý của AI khác (`Data-Integrate/work.md` + `Data-Integrate/prompt.md`)
   và 3 ảnh tham khảo, **đặc biệt ảnh 2x2** (`UI2x2.png`).

## 2. Tài liệu & ảnh tham khảo

| File | Nội dung |
|---|---|
| `Data-Integrate/work.md` | Review UI của AI khác (227 dòng) — đánh giá điểm mạnh/yếu + đề xuất |
| `Data-Integrate/prompt.md` | Design requirement chuẩn (97 dòng) — 4 màn, phân biệt trạng thái, không bịa dữ liệu |
| `Data-Integrate/docs/screenshots/UI2x2.png` | **Ảnh quan trọng nhất** — bố cục 2×2 4 màn hình |
| `Data-Integrate/docs/screenshots/Dashboard_sample.png` | Mẫu dashboard |
| `Data-Integrate/docs/screenshots/Dashboard_sample_2.png` | Mẫu dashboard (biến thể) |
| `Data-Integrate/docs/mes_dashboard_2x2.html` | **Bản HTML dựng lại từ ảnh** (do AI khác tạo) — spec hình ảnh đáng tin cậy |
| `Data-Integrate/docs/MES_UI_Concept_v1.0.md` | Tài liệu concept gốc — đã cập nhật §F và §G |

## 3. Trạng thái code hiện tại

### 3.1 Đã hoàn thành & đã kiểm chứng ✅

#### a) Sơ đồ dòng chảy — KHÔNG thanh trượt ngang

File mới: `dashboard/frontend/src/mock/components/ProcessFlow.tsx`

- Bỏ `flex` + `overflow-x: auto` → **lưới co giãn**.
- Số cột tính bằng `ResizeObserver` từ bề rộng thật của container (không đoán bằng media query).
- Ưu tiên bố cục **nhiều hàng cân đối**: `cols = ceil(n/2)` → 9 máy thành lưới **3×3**
  (khớp tinh thần mẫu 2×2 trong `UI2x2.png`), có trần theo bề rộng thật.
- Mũi tên nối vẽ trên **lớp phủ** (`.flow-overlay`: `pointer-events:none`, `overflow:hidden`),
  vị trí đo trực tiếp bằng `getBoundingClientRect()` → luôn khớp layout thực tế,
  **không bao giờ làm tăng `scrollWidth`**.
  - Trong cùng hàng → mũi tên ngang `→`
  - Cuối hàng (chưa phải máy cuối) → mũi tên rẽ xuống `↴`

#### b) Dọn thanh trượt trong toàn bộ component

| Trước | Sau |
|---|---|
| `.flow-scroll { overflow-x: auto }` | bỏ hẳn |
| `.rail-body { max-height: 260px; overflow-y: auto }` | bỏ `max-height`/`overflow` → rail cuộn theo trang |
| `.table-scroll { overflow: auto }` | bỏ; bảng dùng `table-layout: fixed` + `overflow-wrap: anywhere` |
| `.drawer` animation `translateX(24px)` tràn mép phải | đổi thành `translateX(-18px)` (trượt vào từ trong) + `overflow:hidden` |
| `.bell-count` tràn ra ngoài `.bell` | đặt `top:1px; right:1px` + viền 2px, nằm trong khung |

**Nguyên tắc đã chốt:** chỉ còn **1 thanh cuộn ở cấp TRANG**. Ngoại lệ duy nhất:
`.dr-body` của drawer (lớp phủ toàn màn hình — cuộn bên trong là chuẩn).

#### c) Sửa 5 lỗi dữ liệu mà `work.md` §1.2.C chỉ ra (quan trọng hơn giao diện)

| Lỗi | Nguyên nhân | Đã sửa |
|---|---|---|
| Timestamp lệch **7h** so với đồng hồ topbar | UI cắt chuỗi ISO **UTC** bằng `.slice(11,19)` | `domain/time.ts` mới — quy đổi giờ địa phương (`fmtClock`, `fmtHm`, `fmtDateTime`, `fmtAge`) |
| "**Còn 0 pcs**" khi đã vượt kế hoạch | không xử lý nhánh vượt kế hoạch | `domain/plan.ts` mới → `planProgress()` hiện `vượt X pcs` |
| **Performance = 100%** | `CurrentSpeed` dao động **quanh** design speed (±5%) | dao động trong khoảng **92–100%** (`wobble = 0.92 + 0.08·(0.5+0.5·sin)`) — máy thật không vượt thiết kế ổn định |
| Thiếu **connection state** & **data quality** | chỉ có 1 chiều machine state | `domain/quality.ts` mới — tách 3 chiều độc lập |
| Đơn vị `degC` / `uS/cm` thô | `unitOf()` trả `null` | `displayUnit()` + chuẩn hoá `*/min` → `*/ph` |

#### d) Tách 3 chiều trạng thái (theo `prompt.md` §4) — `domain/quality.ts`

| Chiều | Nguồn | Nơi hiển thị |
|---|---|---|
| **Machine state** | `MachineState` + `EmergencyStop`/`Starved`/`Blocked`/`AlarmCode` | Badge trạng thái, viền trái card, chip plant |
| **Connection state** | **KÊNH** (`channel`), không phải máy | Badge "Kết nối / Yếu / Mất kết nối" ở header line + card plant |
| **Data quality** | `quality` + `stale` + tuổi bản ghi | Chấm "Mới / Cũ / Không có" trên card & header drawer |

⚠ Không suy luận connection state từ machine state (và ngược lại).
⚠ Không biến missing data thành `0` — vẫn hiện `—`.

#### e) Thêm màn thứ 4: Alarm & Event Center — `pages/AlarmCenter.tsx`

Phân biệt 3 loại thông báo (có panel giải thích ngay trên trang):
- **Alarm** — đang tồn tại, cần xử lý. Nguồn: tag `AlarmCode`.
- **Event** — đã xảy ra. Nguồn: pipeline sự kiện downtime.
- **Notification** — thông báo vận hành. **Chưa có nguồn riêng trong middleware** → mới là mô tả.

Có bộ lọc (Tất cả / Alarm / Sự kiện), KPI tóm tắt, click để drill-down vào máy.

#### f) Layout & hierarchy theo `work.md` §2

- **Plant Overview**: 4 KPI (OEE nhà máy / Đạt kế hoạch ca / Máy đang chạy / Alarm đang mở) →
  3 line card (OEE là chỉ số chính, có progress + machine summary stacked bar + connection badge) →
  **Production Trend** (actual vs target) + **Sự kiện gần đây** (2 cột).
- **Line View**: header panel 4 OEE KPI + progress kế hoạch → **ProcessFlow lưới** → rail (Alarm /
  Máy theo trạng thái / Sự kiện) → **Xu hướng sản lượng** + **Các công đoạn** (danh sách 9 máy).
- **Machine Detail**: thêm connection + freshness + timestamp thật trong header; bảng tag dùng
  `table-layout: fixed`; thêm phím `Escape` đóng drawer.

#### g) Bảng màu / style

Giữ nguyên hệ token sẵn có (`tokens.css`). Đã đo màu ảnh tham khảo bằng Python:
- `Dashboard_sample.png`: nền `#0b1a2d` / `#011023`
- `Dashboard_sample_2.png`: nền `#0f172a` (slate-900) + `#1e293b` (slate-800) — 34% / 28.6%
- `mes_dashboard_2x2.html` (bản dựng lại từ ảnh): `--bg:#0a1224; --panel:#0e1a34; --card:#101f3d; --line:#1d3566`

→ Token hiện tại (`#0b1220` / `#111a2c`) **đã rất gần** các ảnh. Không cần đổi.

### 3.2 File đã tạo mới

| File | Vai trò |
|---|---|
| `src/mock/domain/quality.ts` | `ConnectionState`, `Freshness`, `freshnessOf()`, `CONNECTION_META`, `FRESHNESS_META` |
| `src/mock/domain/time.ts` | `fmtClock`, `fmtHm`, `fmtDateTime`, `ageSeconds`, `fmtAge` (giờ địa phương) |
| `src/mock/domain/plan.ts` | `planProgress()` → ratio/pct/delta/label ("còn X" / "vượt X") |
| `src/mock/components/ProcessFlow.tsx` | Sơ đồ dòng chảy dạng lưới, không thanh trượt |
| `src/mock/pages/AlarmCenter.tsx` | Màn 4 — Alarm & Event Center |
| `tests/mock-ui.spec.ts` | 13 test layout (xem §5) |
| `tests/mock-shots.spec.ts` | Script chụp ảnh 4 màn (tiện dụng để review) |

### 3.3 File đã sửa

| File | Thay đổi chính |
|---|---|
| `src/mock/store.ts` | thêm `connection`, `freshness` vào `MachineStateView`; thêm `connection`, `statusCounts` vào `LineView`; export `countByStatus()` |
| `src/mock/mock-simulator.ts` | `CurrentSpeed` dao động 92–100%; thêm `connection` theo channel; `receivedAt` có độ trễ (`LAG_SECONDS`) để demo freshness; `pushOutput()` / `outputHistoryOf()` |
| `src/mock/pages/LineView.tsx` | viết lại toàn bộ — dùng `ProcessFlow`, `planProgress`, `fmtClock`, `ConnectionBadge`, `OutputTrend`, `stage-list` |
| `src/mock/pages/PlantOverview.tsx` | viết lại — KPI mới, `PlantTrend`, line card theo work.md |
| `src/mock/pages/MachineDetail.tsx` | header có connection/freshness/timestamp; bảng tag không scroll; `Escape` đóng drawer; `displayUnit` cho cột đơn vị |
| `src/mock/App.tsx` | thêm route `alarms`; sidebar có mục "Alarm & Sự kiện"; chuông topbar click → Alarm Center; ghi lịch sử sản lượng theo line |
| `src/mock/app.css` | layout flow mới + ~200 dòng CSS cho các thành phần mới; bỏ các rule overflow cũ |
| `src/mock/domain/state.ts` | `displayUnit()` thêm case `*/min` → `*/ph` |
| `docs/MES_UI_Concept_v1.0.md` | thêm **§G** (G.1–G.9) ghi lại toàn bộ quyết định phiên này |

## 4. Quyết định thiết kế — và chỗ **KHÔNG** làm theo góp ý

| Góp ý trong `work.md` | Quyết định | Lý do |
|---|---|---|
| Thêm trạng thái luồng giữa các công đoạn (Blocked / Starved / Flow interrupted) | **KHÔNG thêm** | Chính góp ý cũng nói "không nên suy luận Blocked/Starved chỉ từ RUNNING/STOPPED; cần có dữ liệu đầu vào/đầu ra tương ứng". Catalog hiện **không có** tag đầu vào/đầu ra theo từng công đoạn → thêm vào lúc này là **bịa dữ liệu**. Cần bổ sung tag ở tầng middleware trước. |
| "Mini-map / danh sách toàn bộ máy để định vị nhanh" | **Thay bằng** panel "Các công đoạn" | Đã có sẵn trong rail, nay đưa thành panel rõ ràng (9 máy + trạng thái + thời điểm cập nhật) |
| "Đưa nhiều KPI hơn lên hàng đầu" | **Giữ 4 KPI**, phần còn lại xuống khu vực phân tích | Đúng góp ý §1.2.A |
| "Production Trend actual vs target" | **Đã thêm** ở Plant Overview + Line View | Yêu cầu của `prompt.md` §3 |
| "Thêm Role-based UI" | **Chưa làm** | Ngoài phạm vi mock giao diện; cần backend xác thực |

## 5. Kiểm chứng

```bash
cd Data-Integrate/dashboard/frontend
npx tsc --noEmit -p tsconfig.json          # → exit 0, sạch
npx playwright test tests/mock-ui.spec.ts   # → 13/13 pass
```

`tests/mock-ui.spec.ts` chạy ở **4 kích thước màn hình** (1920 / 1600 / 1280 / 1024) và kiểm tra:

1. Không phần tử nào có overflow ngang ở cả 4 màn hình.
2. 9 máy của line đều nằm trong khung nhìn (không bị cắt bên phải).
3. Số mũi tên nối = số máy − 1 (8).
4. Timestamp trên card khớp đồng hồ topbar (< 2 phút).
5. Vượt kế hoạch → hiện "vượt", **không** hiện "còn 0".
6. Performance ≤ 100%.
7. Machine Detail: đơn vị SI đúng (`°C`), không còn `degC`.
8. Alarm Center: phân biệt được alarm và sự kiện.

**Lưu ý môi trường:** cần dev server ở `:5173` và `npx playwright install chromium` (đã cài).
Nếu server tắt: `npm run dev` trong `dashboard/frontend`.

### 5.1 Đợt 12/11/2026 (phiên này) — đã thêm 6 test → **19 test, tất cả PASS**

9. Ca sản xuất khớp đồng hồ hệ thống (không ghim cứng "Ca A").
10. Mũi tên dòng chảy nối liền giữa 2 card liền kề (đo theo `getBoundingClientRect`).
11. Kết nối báo cáo theo **kênh**, không theo máy.
12. **Mọi chữ ≥ 11px** trên toàn trang.
13. Alarm Center: bảng có cấu trúc (8 cột) + tìm kiếm + lọc dây chuyền.
14. Sidebar không có nút chết (mọi nút hoạt động hoặc `disabled` tường minh).

## 6. Việc CÒN LẠI (cho phiên mới)

### 6.0 ĐÃ XỬA trong phiên 12/11/2026 (tham khảo, không cần làm lại)

| # | Vấn đề | Cách sửa |
|---|--------|----------|
| 1 | Mũi tên sơ đồ dòng chảy không nối vào card nào (rẽ xuống ở mép phải, card kế tiếp ở mép trái) | Chuyển sang bố cục **rắn (boustrophedon)** — hàng đảo chiều, mũi tên nối liền; thêm **số thứ tự công đoạn** trên card |
| 2 | Bộ cột lệch (6+3) | Thuật toán chọn số cột cân bằng (chênh lệch ≤ 1 máy giữa các hàng) |
| 3 | `direction: rtl` làm lưới tràn ngang | Dùng `flex-direction: row-reverse` |
| 4 | KPI báo "7 máy mất kết nối" (thực tế chỉ 1 kênh yếu) | Báo theo **kênh**: "1/4 kênh kết nối yếu" (connection thuộc kênh, không thuộc máy) |
| 5 | Ca ghim cứng "Ca A · 06:00–14:00" trong khi đồng hồ là 16:16 | Module `domain/shift.ts` — suy ca từ đồng hồ hệ thống |
| 6 | `Performance` tự tính (vi phạm §6) → kẹt ở 100% | Dùng đúng `(IdealCycleTime × TotalCount) / RunTime`; thêm `domain/runtime.ts` (`runFactorOf`) dùng chung simulator ↔ OEE |
| 7 | Mục sidebar "Phân tích" không có handler | Chuyển sang nhóm "Quản trị" với `disabled` + `title` giải thích; thêm khối người dùng |
| 8 | 62/113 chữ < 11px | Nâng toàn bộ `font-size` trong `app.css` lên ≥ 11px (63 khai báo) |
| 9 | Card SHARED mồ côi ở hàng 2 | Lưới 4 cột, 3 line + 1 CIP thành 1 hàng cân đối |
| 10 | Panel dưới lệch chiều cao (220 vs 400) | `align-items: stretch` + biểu đồ co giãn theo khung |
| 11 | Danh sách máy trùng ở 3 nơi (flow + rail + stage) | Rail đổi thành **tóm tắt đếm theo trạng thái** |
| 12 | Alarm list dạng row | **Bảng 8 cột** (Severity badge, Source, Description, Status) + ô tìm kiếm + lọc dây chuyền |
| 13 | "Đạt kế hoạch ca 35%" gây hiểu nhầm giữa ca | Thêm KPI **"Nhịp sản xuất"** (pace) so với kế hoạch tích luỹ tới giờ |

**Còn lại trong §6.1–6.3** (chưa làm vì bạn chọn phạm vi "sửa lỗi + bố trí lại"):
- Gauge tròn cho KPI OEE (ảnh tham khảo có, mock chưa dùng)
- Tabs thời gian 1h/8h/24h/7d
- Nút Acknowledge cho alarm (cần nguồn `alarm_ack` ở backend)
- Phân trang alarm
- Sidebar 7 mục kiểu ảnh tham khảo

### 6.1 Ưu tiên cao — đối chiếu với ảnh thật

1. **Mở 3 ảnh** và so sánh với mock hiện tại. Điểm cần kiểm chắc:
   - `mes_dashboard_2x2.html` mô tả **OEE dạng gauge tròn** (donut + kim) ở KPI đầu tiên —
     mock hiện dùng số + progress bar. Ảnh thật có dùng gauge không?
   - Mẫu có **"Production by Line"** dạng 3 thanh ngang (Line 01 86.2% / Line 02 78.5% / Line 03 80.1%)
     — mock hiện dùng line card + stacked bar.
   - Mẫu có **tabs 1h/8h/24h/7d** ở Line Monitoring — mock hiện chưa có bộ chọn khoảng thời gian.
   - Mẫu có **ảnh máy** (placeholder) + nút back ở Machine Detail — mock dùng drawer.
   - Mẫu có **bảng alarm đầy đủ** (Time / Severity / Source / Description / Status / Action)
     với nút **Acknowledge** + phân trang — mock hiện dùng danh sách dạng row.
   - Mẫu có **sidebar 7 mục** (Dashboard / Production / Equipment / Quality / Material / Analytics /
     Administration) + user "Thuận Phan / Admin" — mock hiện 5 mục, chưa có user block.
2. Sửa CSS token nếu ảnh thật lệch màu.

### 6.2 Câu hỏi đang chờ bạn trả lời

> *"NG Quantity / Defect Rate" có nên đưa lên KPI tổng nhà máy không?*
> Hiện tại: `Đạt kế hoạch ca` đã lên KPI; Yield/Defect mới ở mức card máy + Machine Detail.

### 6.3 Việc kỹ thuật còn lại

- [ ] Thêm bộ chọn khoảng thời gian (1h / 8h / 24h / 7d) — dữ liệu mock hiện chỉ giữ 90 điểm.
- [ ] Nếu thêm Acknowledgement cho alarm → cần nguồn `alarm_ack` ở backend (chưa có).
- [ ] `Notification` chưa có nguồn dữ liệu → cần bảng/signal từ middleware.
- [ ] Tag đầu vào/đầu ra cho flow state (Block/Starve) → cần thêm vào catalog tầng middleware.
- [ ] Chạy `npm run build` trước khi commit để chắc chắn `tsc -b` pass.

## 7. Bối cảnh dữ liệu mock (để không phá khi sửa)

- **Nguồn**: `catalog.gen.ts` — **auto-generate từ `IndustrialTelemetry.Middleware/metadata/catalog.json`**
  (26 máy, 404 tag). **KHÔNG sửa file này thủ công.**
- **Đơn vị đếm** khác nhau theo máy: `preform/min`, `bottles/min`, `caps/min`, `cans/min`,
  `pcs/min`, `cases/min`, `m/min`, `cycles` (CIP).
- **Bộ đếm đặc trưng**: 24/26 máy có `GoodCounter`; `DATE_CODER` chỉ có `PrintCount`;
  `BOTTLE_LABELER` → `LabelApplyCount`; `CAN_INSPECTION` → `InspectionCount`;
  `CIP_SKID` → `TotalCounter` (đơn vị `cycles`, KHÔNG phải sản lượng).
- **Bộ đếm theo ca**: seed = `rate × plannedElapsedMinutes × efficiency(0.82–0.98) × runFactor(trạng thái máy)`.
  - ⚠ **Đợt 12/11 (sửa)**: seed theo **thời gian SẢN XUẤT** (đã trừ giờ nghỉ) và nhân
    `runFactor` theo trạng thái máy — cùng mô hình thời gian với `computeLineOee`.
    Trước đó seed theo thời gian thô → sản lượng vượt kế hoạch → **Performance vượt 100%
    và bị kẹt ở trần**, OEE sai.
  - Ca hiện tại **suy ra từ đồng hồ hệ thống** (`domain/shift.ts`), KHÔNG ghim "Ca A".
- **Máy cố ý đặt trạng thái** (để demo có đủ tình huống):
  `L01_RINSER_01` STOPPED · `L01_CODER_01` FAULTED (alarm 417) · `L02_AIRCONV_01` MAINTENANCE ·
  `L03_CANFILLER_01` STARTING · `L03_CANDEPAL_01` STOPPED.
- **Demo data quality**: `L02_LABELER_01.LabelRollRemaining` = Bad ·
  `L03_CANCODER_01.InkLevel` + `MachineState` = stale ·
  `LINE_03` channel = degraded · `L03_CANCODER_01` lag 95s · `L02_LABELER_01` lag 12s.
- **Công thức OEE** (đã được duyệt, `docs/architecture.txt` §6):
  `Availability = RunTime / PlannedProductionTime` ·
  `Performance = (IdealCycleTime × TotalCount) / RunTime` ·
  `Quality = GoodCount / TotalCount` · `OEE = A × P × Q`.
  - ⚠ **Đợt 12/11 (sửa)**: `Performance` KHÔNG còn tự tính từ trung bình
    `CurrentSpeed/DesignSpeed` (vi phạm "không tự bịa công thức nghiệp vụ").
    Nay dùng đúng `(IdealCycleTime × TotalCount) / RunTime` với
    `IdealCycleTime = 60 / DesignSpeed` và `RunTime` của **máy tham chiếu**.
  - `RunTime` của line = TỔNG `plannedSec × runFactor(máy)`; mẫu số Availability =
    `plannedSec × số máy`.
- **Máy tham chiếu tính OEE của line** = công đoạn **CHIẾT** (`FILLING`), không phải máy đầu tiên.
- **OEE nhà máy** = trung bình **gia quyền theo sản lượng** từng line (không cộng trung bình cộng).
- **Mọi số liệu trong mock đều là MOCK** — UI phải giữ badge "MOCK" (đã có).

## 8. Quy ước code trong thư mục `src/mock`

- Comment tiếng Việt, dùng `/* */` cho CSS (⚠ **không dùng `//` trong CSS** — đã gây lỗi
  mất toàn bộ style ở phiên trước vì parser nuốt mất block `:root`).
- Business logic đặt ở `domain/` (pure function, không phụ thuộc React) — có thể test độc lập.
- Component dùng chung ở `components/`.
- **Không hard-code theo `machineId`** — profile theo `machineType` (`domain/metric-profiles.ts`).
- **Không suy diễn** alarm severity, machine state mapping, hay bịa công thức KPI.
- Đơn vị lấy từ **catalog tag**, không hard-code chuỗi trong JSX.

## 9. File quan trọng cần đọc lại

```
Data-Integrate/
├─ docs/
│  ├─ MES_UI_Concept_v1.0.md      ← §F (phiên trước) + §G (phiên này) — ĐỌC TRƯỚC
│  ├─ mes_dashboard_2x2.html      ← spec hình ảnh (bản dựng lại từ ảnh)
│  └─ screenshots/                ← 3 ảnh tham khảo (cần MỞ bằng mắt ở phiên mới)
├─ work.md                        ← góp ý review
├─ prompt.md                      ← design requirement
└─ dashboard/frontend/
   ├─ src/mock/
   │  ├─ App.tsx                  ← shell + route (plant / line / machine / alarms)
   │  ├─ store.ts                 ← state tổng hợp
   │  ├─ mock-simulator.ts        ← sinh dữ liệu giả
   │  ├─ catalog.gen.ts           ← AUTO-GENERATE, không sửa tay
   │  ├─ tokens.css               ← design tokens
   │  ├─ app.css                  ← toàn bộ style
   │  ├─ domain/                  ← state.ts, oee.ts, quality.ts, time.ts, plan.ts,
   │  │                              shift.ts (mới), runtime.ts (mới), metric-profiles.ts
   │  ├─ components/              ← common.tsx, ProcessFlow.tsx
   │  └─ pages/                   ← PlantOverview, LineView, MachineDetail, AlarmCenter
   └─ tests/mock-ui.spec.ts       ← 19 test layout + hành vi
```

### 9.1 Script kiểm chứng (chạy khi server đang chạy ở :5173)

| Script | Việc |
|--------|------|
| `node tools/verify_flow.mjs` | Đo ngữ nghĩa mũi tên dòng chảy (nằm đúng khe, đúng cột) |
| `node tools/check_values.mjs` | In giá trị KPI/OEE đang hiển thị ở cả 3 màn |
| `node tools/measure2.mjs 1920 1080` | Đo bố cục: kích thước card, panel, cỡ chữ, tràn ngang |
| `node tools/find_small_text.mjs` | Liệt kê mọi chữ < 11px còn sót |
| `node tools/shots.mjs` | Chụp ảnh 3 màn hình vào `shots/` |

> ⚠ **Ảnh trong phiên này KHÔNG hiển thị được** (harness cắt pixel) — phải kiểm chứng
> bằng **đo đạc chương trình** như trên, không đoán bằng mắt.

---

**Ngày hoàn tất phiên:** 2026-11-12 · **Trạng thái:** code hoàn chỉnh, 13/13 test pass,
`tsc` sạch · **Việc còn lại:** đối chiếu với ảnh thật (cần phiên có khả năng đọc ảnh) và
bổ sung các tính năng còn thiếu trong §6.
