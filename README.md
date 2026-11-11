# Smart Manufacturing - Big Data Pipeline (Nhóm 18)

Kepware/OPC UA → Middleware → **Kafka** → **Spark Structured Streaming** → **MinIO** (raw) → **Spark Batch** → **PostgreSQL** → .NET / Dashboard

Thiết kế chi tiết: [`docs/architecture.txt`](docs/architecture.txt)

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
| MinIO S3 API / Console | `http://minio:9000` | http://localhost:9000 / http://localhost:9001 |
| PostgreSQL | `postgres:5432` | `localhost:5432` |
| Spark master | `spark://spark-master:7077` | UI http://localhost:8080 |
| Spark worker UI / App UI | | http://localhost:8081 / http://localhost:4040 |

Tài khoản mặc định nằm trong `.env`.

## Chạy Spark job

```bash
# Luồng A: Kafka -> MinIO (raw Parquet). Chạy liên tục, trigger 1 phút:
docker compose exec spark-master spark-submit /opt/spark-apps/kafka_to_minio.py
#   --available-now : xử lý hết dữ liệu đang có rồi dừng;  --trigger "10 seconds"

# Luồng C: MinIO -> PostgreSQL (production/quality/data quality metric), upsert idempotent
docker compose exec spark-master spark-submit /opt/spark-apps/minio_to_postgres.py [--date 2026-11-11 [--hour 8]]
```

## Smoke test end-to-end

```bash
./scripts/smoke_test.sh     # CẢNH BÁO: reset topic, bucket và các bảng *_metric
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
- Thêm worker: `docker compose up -d --scale spark-worker=2` (cần bỏ `container_name` và port của worker).
- Xoá sạch dữ liệu: `docker compose down -v`.
