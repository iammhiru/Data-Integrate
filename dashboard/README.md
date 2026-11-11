# Dashboard — Backend, Kafka Consumer, SignalR và Frontend

ASP.NET Core 10, Confluent.Kafka, Npgsql, React/TypeScript. Không chứa code middleware hay xử lý Spark; dashboard đọc đầu ra của các phần đó.

## Chạy cùng hệ thống nhóm

Từ gốc repo, tạo `.env` từ `.env.example` nếu chưa có rồi chạy:

```powershell
docker compose up -d --build --wait dashboard
docker compose --profile streaming up -d
```

Mở **http://localhost:5080**. Lệnh thứ nhất chạy dashboard/Kafka/PostgreSQL; lệnh thứ hai bật các Spark job đã có trong repo. Cần nguồn gửi sự kiện theo hướng dẫn README gốc để Spark phát dữ liệu. Khi chưa có trạng thái, UI hiển thị “— / Chưa rõ”, không coi máy là dừng.

Mock độc lập (không cần Kafka/Spark/PostgreSQL):

```powershell
docker compose -f dashboard/compose.mock.yaml up -d --build --wait
```

Mở **http://localhost:5082**. Mock được gắn nhãn rõ, mô phỏng đúng cấu trúc metric; không sinh dữ liệu OEE giả. `localhost` chỉ truy cập từ máy chạy Docker. Không chạy hai ứng dụng chiếm cùng cổng.

## Kafka đầu vào

Mặc định topic `realtime-metrics`, group riêng `dashboard-metrics-v1`, broker nội bộ Docker `kafka:9092`. Chạy backend trên host dùng `localhost:9094`. Key là machineId. Schema lấy từ `spark/apps/realtime_metrics.py`:

| metricType | Dữ liệu dùng trên giao diện |
|---|---|
| machine.status.5s | status, avgTemperature, avgPressure, avgSpeed, sumEnergy |
| machine.metric.1m | avg/max temperature, avgPressure, avgSpeed, sumEnergy, sampleCount, missingCount |
| production.rate.1m | productionRate, totalQty, goodQty, rejectQty |

`lastEventTime`, `windowStart`, `windowEnd`, `emittedAt` là UTC. Cửa sổ đang mở có thể được Spark phát lại: cùng lastEventTime nhưng emittedAt mới hơn được cập nhật. Clock được giữ riêng từng trường; production metric không ghi đè trạng thái máy và aggregate 1 phút dùng trường riêng. Giá trị null/thiếu giữ nguyên, không thay bằng 0. Cache chống lặp tối đa 50.000 event và biểu đồ 180 điểm/trường trong RAM.

Chế độ tương thích telemetry envelope v1 vẫn có thể bật bằng `Kafka__Format=Telemetry`, `Kafka__Topic=machine-telemetry` và group riêng. Compose mặc định dùng Metrics đúng luồng sau Spark.

## PostgreSQL / API

Backend đọc master `machine` và bootstrap trạng thái từ `machine_status_current` mỗi 30 giây. Danh mục dự phòng khớp SQL seed M001–M100; master DB thay thế khi có kết nối. Bảng latest chưa có dữ liệu thì backend đợi event, không bịa snapshot.

| Endpoint | Nội dung |
|---|---|
| GET /health | Trạng thái backend, Kafka và PostgreSQL; không chứng minh PLC đang online |
| GET /api/catalog | Danh mục máy và trường hiển thị |
| GET /api/snapshot | Giá trị mới nhất, mode, topic, trạng thái nguồn |
| GET /api/diagnostics | Thống kê nhánh dashboard trong phiên |
| GET /api/machines/M001/series?tagCode=speed | Biểu đồ trong phiên, tối đa 180 điểm |
| GET /api/analytics?from=2026-11-11&to=2026-11-11&machineId=M001 | Các bảng phân tích PostgreSQL |
| /hubs/telemetry | SignalR event Snapshot, định kỳ 1 giây |

API phân tích đọc production_metric, quality_metric, data_quality_metric, oee_metric, downtime_event và machine_metric_1m. Truy vấn có tham số, lọc tối đa 31 ngày UTC, tối đa 1.000 dòng/bảng và cờ truncated. data_quality_metric không có machine_id nên bộ lọc máy không áp dụng; UI ghi rõ. Bảng rỗng khác với số 0; lỗi truy vấn trả 503. Không tính lại OEE hay thay đổi schema database.

## Cấu hình và phát triển

Compose truyền thông tin Kafka và `ConnectionStrings__Postgres` từ `.env` của nhóm. Backend cho phép ghi đè qua biến môi trường hoặc appsettings.Local.json (Git ignore). Không đưa mật khẩu thật vào Git. Frontend gọi cùng origin qua API/SignalR, không chứa thông tin đăng nhập Kafka/DB.

Phát triển cần .NET SDK 10 và Node.js LTS: `dotnet run --project dashboard/backend/Factory.Api.csproj`; trong dashboard/frontend chạy `npm ci` rồi `npm run dev` (cổng 5173, proxy tới backend 5080).

## Kiểm thử

```powershell
dotnet run --project dashboard/tests/Factory.Tests.csproj
cd dashboard/frontend
npm.cmd ci
npx.cmd playwright install chromium
$env:PREVIEW_URL='http://localhost:5082'
npm.cmd run test:browser
```

Các test trực tiếp kiểm tra adapter dữ liệu, sửa cửa sổ Spark, phân biệt chưa có dữ liệu với số 0, giao diện mobile và reconnect SignalR. Không cần chạy script reset dữ liệu để kiểm tra dashboard.

Đây là prototype local, một backend instance; state/biểu đồ không lưu bền. Sau restart, trạng thái được nạp từ latest DB hoặc event mới. Hệ thống chưa có đăng nhập/TLS để mở ra Internet. Đơn vị và định nghĩa metric theo nguồn Spark; OEE/downtime cần upstream ghi kết quả trước khi có số liệu hiển thị.
