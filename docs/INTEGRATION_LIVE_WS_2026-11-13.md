# Tích hợp LIVE — React UI ↔ `state-api` (FastAPI) qua WebSocket

> Cập nhật: 2026-11-13 · Phạm vi: **realtime-first** (trạng thái máy, tag, KPI thời gian thực).

---

## 1. Quyết định thiết kế

| Hạng mục | Quyết định | Lý do |
|---|---|---|
| Đường kết nối | **`direct-ws`** — UI mở WebSocket thẳng tới `state-api` | Không phụ thuộc backend .NET cũ (SignalR); đúng như "hướng dẫn compose + websocket tạm qua Python với UI" của đồng đội |
| Phạm vi | **realtime-first** | Trạng thái + tag + KPI sống. Lịch sử trend/alarm **tích luỹ ở client**, chưa đọc từ DB (chưa có aggregator) |
| Nguồn dữ liệu | Giao diện `TelemetrySource` (`src/mock/telemetry-source.ts`) | 2 lớp cài đặt, UI không đổi dòng nào khi đổi nguồn |

## 2. Kiến trúc

```
Kepware/OPC-UA  (hoặc middleware-sim)
      ↓ industrial.telemetry (Kafka)
Spark  spark/apps/machine_state_stream.py   → topic `machine-state` (compacted)
      ↓
FastAPI  services/state-api/app.py          → giữ trạng thái trong RAM
      ↓  WS /ws/machines
React  src/mock/live-source.ts               → TelemetrySource
      ↓
UI    src/mock/store.ts → domain/* → pages/*
```

## 3. Giao thức WebSocket (`services/state-api/app.py`)

| Frame | Nội dung |
|---|---|
| `snapshot` | `{"type":"snapshot","ready":bool,"serverTime":str,"machines":[…]}` — gửi ngay khi client kết nối. Mỗi máy có `meta` + `summary` + `tags` (đủ 404 tag) |
| `patch` | `{"type":"patch","serverTime":str,"machines":[…]}` — chỉ tag vừa đổi, gom mỗi 250 ms |
| `heartbeat` | `{"type":"heartbeat","serverTime":str,"ready":bool}` — mỗi 15 s khi rảnh |

Client → server: `{"action":"ping"}` (giữ kết nối qua proxy) · `{"action":"subscribe","machineIds":[…],"lineId":…}` (đổi bộ lọc).

## 4. Chạy thử

### 4.1 Backend (compose)

```bash
cd Data-Integrate
docker compose --profile telemetry up -d --build
# state-api      → http://localhost:8000/docs
# state-api WS   → ws://localhost:8000/ws/machines
```

Kiểm tra nhanh:

```bash
curl http://localhost:8000/health
# {"status":"ok","ready":true,"machines":26,"tags":404,...}
```

### 4.2 Frontend

```bash
cd Data-Integrate/dashboard/frontend
npm install
npm run dev
```

- **MOCK (mặc định)**: <http://127.0.0.1:5173/>
- **LIVE**: <http://127.0.0.1:5173/?source=live>
- Nút `MOCK ⇄` trên topbar để chuyển nhanh giữa hai nguồn.

Proxy của Vite (`vite.config.ts`) chuyển tiếp `/state-api/*` → `http://localhost:8000/*`
(có `rewrite` bóc tiền tố vì FastAPI không có prefix này) — nên không dính CORS.

### 4.3 Deploy Docker

Khi build production không có proxy Vite → đặt biến môi trường build-time:

```bash
VITE_STATE_API_WS=ws://localhost:8000/ws/machines npm run build
```

## 5. Xử lý khác biệt giữa MOCK và LIVE

| Vấn đề | MOCK | LIVE | Cách xử lý |
|---|---|---|---|
| Tag chưa từng có giá trị | luôn có số | **không có trong `tags`** | `values[tag] = null` + quality `Unknown` — **không** coi là `0` |
| `statusCode` | `Good`/`Present` | `Good`/`Uncertain`/`Bad` | `Good`/`Present` → `Good`; còn lại giữ nguyên để hiện đúng nhãn |
| Bộ đếm sản phẩm | seed theo ca | **tích luỹ từ lúc thiết bị bật**, không reset theo ca | Lưu `baseline` lúc kết nối → OEE dùng phần **tăng thêm** |
| Planned Production Time | theo ca (§6) | **số giây đã trôi kể từ lúc kết nối** | `LiveSource.plannedSec()` |
| Run Time | `planned × runFactorOf(status)` | **tích phân** theo trạng thái RUNNING từ luồng | `LiveSource.runTimeSecOf()` |
| Trạng thái kết nối theo channel | có sẵn | `state-api` không trả | Suy ra từ độ tươi dữ liệu của các máy trong kênh |
| Sự kiện (alarm/state) | simulator sinh | **chỉ** từ đổi trạng thái + bật/tắt `AlarmCode` | `LiveSource.detectEvents()` |

> ⚠ **Hợp đồng OEE**: cả 3 đại lượng (Planned / Run Time / Total Count) phải cùng MỘT cửa sổ quan sát, nếu không Performance sẽ vượt 100%. Vì vậy ở chế độ LIVE ta chọn cửa sổ = *từ lúc mở kết nối*.
> Khi có job ghi lịch sử vào PostgreSQL, chỉ cần đổi `plannedSec()` / `runTimeSecOf()` của `LiveSource` — UI không đổi.

## 6. Bản đồ mã nguồn

| File | Vai trò |
|---|---|
| `src/mock/telemetry-source.ts` | Interface `TelemetrySource` + `MockSource` (bọc `MockSimulator`) |
| `src/mock/live-source.ts` | `LiveSource` — WebSocket client, chuẩn hóa payload, tích phân OEE, phát sự kiện |
| `src/mock/store.ts` | `buildStore(source)` — dựng view từ nguồn; `computeLineOee` dùng `source.*` |
| `src/mock/App.tsx` | Chọn nguồn theo `?source=live|mock`, quản lý vòng cập nhật, badge LIVE/MOCK |
| `src/mock/components/common.tsx` | `SourceBadge` (LIVE = xanh, MOCK = hổ phách) |
| `tests/live-ws.spec.ts` | Kiểm thử adapter LIVE với server WebSocket giả (Playwright `routeWebSocket`) |

## 7. Kiểm thử

```bash
cd Data-Integrate/dashboard/frontend
npx playwright test tests/mock-ui.spec.ts tests/live-ws.spec.ts
```

`tests/live-ws.spec.ts` mock 100% WebSocket (snapshot / patch / heartbeat / mất kết nối) nên **không cần** backend chạy.

> `tests/dashboard.spec.ts` là test của trang **chẩn đoán** (`/diagnostics.html`) — cần backend .NET cũ ở `:5080`.
> Khi backend không chạy, nhóm này **tự động skip** (không tính là fail). Không liên quan tích hợp này.

Chạy toàn bộ:

```bash
npx playwright test
# → 29 passed, 7 skipped (nhóm chẩn đoán), 0 failed
```

## 8. Việc còn lại (để tích hợp "full")

1. **Lịch sử theo ca** — cần aggregator ghi `machine-state` → PostgreSQL và API truy vấn theo ca; hiện UI mới chỉ có lịch sử trong phiên.
2. **Dữ liệu master** — `sku`, `productName`, `plannedQty`, `idealCycleTime` hiện mock trong `store.ts`; cần đọc từ PG master (`production_run.idealCycleTime`).
3. **Alarm lịch sử** — hiện chỉ suy ra từ luồng `AlarmCode`; cần bảng alarm để xem lại sự kiện đã qua.
4. **Đồng bộ ca (shift rollover)** — `LiveSource` hiện giữ nguyên cửa sổ kể từ lúc kết nối; khi có ca thật phải reset baseline + run time tại mốc ca.
