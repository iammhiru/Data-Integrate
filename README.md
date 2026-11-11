# Smart Manufacturing - Big Data Pipeline (Nhóm 18)

Kepware/OPC UA → Middleware → **Kafka** → **Spark Structured Streaming** → **MinIO** (raw) → **Spark Batch** → **PostgreSQL** → .NET / Dashboard

Thiết kế chi tiết: [`docs/architecture.txt`](docs/architecture.txt)

## Dashboard

Backend, Kafka Consumer, SignalR và frontend nằm trong [`dashboard/`](dashboard/README.md).
Dashboard đọc topic **`realtime-metrics`** từ Spark và các bảng PostgreSQL.

```bash
docker compose up -d --build --wait dashboard   # http://localhost:5080
docker compose --profile streaming up -d       # bật producer Spark theo hướng dẫn bên dưới
```

Mock độc lập: `docker compose -f dashboard/compose.mock.yaml up -d --build --wait`, mở http://localhost:5082.

## Khởi động

```bash
cp .env.example .env          # lần đầu
docker compose up -d --build  # build image Spark (kèm jar Kafka/S3A/JDBC) và chạy toàn bộ
docker compose ps
```

`kafka-init` (tạo topic) và `minio-init` (tạo bucket) chạy một lần rồi thoát (`Exited (0)` là bình thường).
PostgreSQL tự tạo schema và master data từ `postgres/init/*.sql` khi volume còn trống.

| Service | Trong mạng docker | Từ máy host |
|---|---|---|
| Kafka | `kafka:9092` | `localhost:9094` |
| Kafka UI (xem topic, message, consumer group) | | http://localhost:8082 |
| MinIO S3 API / Console | `http://minio:9000` | http://localhost:9000 / http://localhost:9001 |
| PostgreSQL | `postgres:5432` | `localhost:5432` |
| Spark master | `spark://spark-master:7077` | UI http://localhost:8080 |
| Spark worker UI | | http://localhost:8081 |
| Spark UI job raw ingest / realtime | | http://localhost:4041 / http://localhost:4042 |

Tài khoản mặc định nằm trong `.env`.

## Streaming jobs (chạy nền)

```bash
docker compose --profile streaming up -d     # stream-raw-ingest (luồng A) + stream-realtime (luồng B)
docker compose logs -f stream-realtime       # mỗi 30s in throughput / thời gian xử lý từng query
./scripts/live_producer.sh                   # phát event realtime (MACHINES=50 RATE=2 SECONDS_=120)
```

Luồng B (`spark/apps/realtime_metrics.py`) đọc `machine-telemetry` + `production-events`, gom theo window
5s / 1 phút, ghi ra topic **`realtime-metrics`** (cho backend .NET đẩy WebSocket) và upsert
`machine_status_current`, `machine_metric_1m` trong PostgreSQL.

Message trên `realtime-metrics` (key = machineId):

```json
{"machineId":"M001","status":"RUNNING","avgTemperature":72.4,"avgPressure":5.5,"avgSpeed":1450.2,
 "sumEnergy":10.3,"sampleCount":10,"missingCount":0,"lastEventTime":"...","maxIngestedAt":"...",
 "windowStart":"...","windowEnd":"...","metricType":"machine.status.5s","emittedAt":"...","latencyMs":2350.1}
```

`metricType`: `machine.status.5s` | `machine.metric.1m` | `production.rate.1m`.

Đo latency: `docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic realtime-metrics --from-beginning --max-messages 5000 --timeout-ms 10000 | python3 scripts/measure_latency.py`

## Chạy Spark job thủ công

```bash
# Luồng A: Kafka -> MinIO (raw Parquet). Chạy liên tục, trigger 1 phút (đã có service stream-raw-ingest):
docker compose exec spark-master spark-submit /opt/spark-apps/kafka_to_minio.py
#   --available-now : xử lý hết dữ liệu đang có rồi dừng;  --trigger "10 seconds"

# Luồng C: MinIO -> PostgreSQL (production/quality/data quality metric), upsert idempotent
docker compose exec spark-master spark-submit /opt/spark-apps/minio_to_postgres.py [--date 2026-11-11 [--hour 8]]
```

## Smoke test end-to-end

```bash
./scripts/smoke_test.sh     # CẢNH BÁO: dừng streaming service, reset topic, bucket, checkpoint và các bảng metric
```

Script sinh event test (có chèn duplicate / missing / invalid / late), đẩy vào Kafka, chạy cả hai job,
in bảng `data_quality_metric` rồi đối chiếu tổng sản lượng giữa Spark và một phép tính Python độc lập.

## Cấu trúc

```
docker-compose.yml          Kafka, MinIO, PostgreSQL, Spark master + worker
docker/spark/Dockerfile     apache/spark 3.5.5 + jar connector
docker/kafka/create-topics.sh
spark/conf/spark-defaults.conf   cấu hình S3A -> MinIO
spark/apps/                 PySpark job (mount vào /opt/spark-apps)
postgres/init/              DDL + seed master data
scripts/                    generator event test, smoke test
```

## Ghi chú

- Image `minio/minio` đã bị gỡ khỏi Docker Hub/quay.io nên dùng `alpine/minio` (build tự động từ source chính thức, tag cố định).
- Tài nguyên: worker 6 core / 3 GB. raw ingest dùng 1 core, realtime 3 core, job batch tối đa 2 core.
- Thêm worker: `docker compose up -d --scale spark-worker=2` (cần bỏ `container_name` và port của worker).
- Xoá sạch dữ liệu: `docker compose down -v`.
