# ============================================================================
#  CÀI MINIO DATA LAKE — máy Linux 192.168.179.176 (port 4434)
# ============================================================================
#
#  VÌ SAO TÁCH RIÊNG (không dùng `docker-compose.server.yml`):
#    · Máy 176 đã có 1 MinIO khác đang chạy → tránh trùng container/volume/port.
#    · PostgreSQL đã chạy ổn tằng từ `docker-compose.server.yml` → không đụng vào.
#    · Cổng riêng 4434 (S3 API) + 4435 (Web console) → không đụng MinIO cũ.
#
#  NHỚ: container MinIO vẫn nghe ở 9000/9001 BÊN TRONG compose network,
#  nên client cùng network dùng `http://minio:9000`; client ngoài (máy Windows)
#  dùng `http://192.168.179.176:4434`.
#
# ------------------------------------------------------------------------------
#  BƯỚC 1 — Copy file lên máy server (chạy trên MÁY WINDOWS)
# ------------------------------------------------------------------------------
#
#   cd E:\Work\SFSVcongty\Laird\Code\Data-Integrate
#
#   ssh dev@192.168.179.176 "mkdir -p /home/dev/smart-factory"
#   scp docker\docker-compose.minio-datalake.yml dev@192.168.179.176:/home/dev/smart-factory/
#   scp .env.example                             dev@192.168.179.176:/home/dev/smart-factory/
#
# ------------------------------------------------------------------------------
#  BƯỚC 2 — Kiểm tra môi trường máy server (SSH vào)
# ------------------------------------------------------------------------------
#
#   ssh dev@192.168.179.176
#
#   docker --version
#   docker compose version
#   df -h /var/lib/docker        # cần >= 2G cho MinIO
#   free -h                      # cần >= 1G RAM trống
#
#   # MinIO cũ của anh đang chiếm port nào? (để chắc chắn 4434/4435 còn trống)
#   sudo ss -ltnp | grep -E ':(4434|4435|9000|9001)'
#   docker ps --format '{{.Names}}\t{{.Ports}}'
#
# ------------------------------------------------------------------------------
#  BƯỚC 3 — Tạo .env trên server
# ------------------------------------------------------------------------------
#
#   cd /home/dev/smart-factory
#   cp .env.example .env
#   nano .env        # sửa MINIO_ROOT_USER / MINIO_ROOT_PASSWORD / MINIO_S3_PORT
#
#   Nội dung cần đảm bảo:
#     MINIO_ROOT_USER=minioadmin
#     MINIO_ROOT_PASSWORD=minioadmin123
#     MINIO_BUCKET=smart-factory
#     MINIO_S3_PORT=4434
#     MINIO_CONSOLE_PORT=4435
#     MINIO_IMAGE=alpine/minio:RELEASE.2025-10-15T17-29-55Z
#
# ------------------------------------------------------------------------------
#  BƯỚC 4 — Khởi động
# ------------------------------------------------------------------------------
#
#   cd /home/dev/smart-factory
#   docker compose -f docker-compose.minio-datalake.yml up -d
#
#   Theo dõi:
#     docker compose -f docker-compose.minio-datalake.yml logs -f
#   Ctrl+C để thoát log (không dừng container).
#
#   Kiểm tra:
#     docker compose -f docker-compose.minio-datalake.yml ps
#     # minio      : healthy
#     # minio-init : Exited (0)   <- bình thường, tạo bucket 1 lần rồi thoát
#
#   Nếu `minio-init` FAIL (không kết nối được) → xem log:
#     docker compose -f docker-compose.minio-datalake.yml logs minio-init
#
# ------------------------------------------------------------------------------
#  BƯỚC 5 — Mở firewall
# ------------------------------------------------------------------------------
#
#   # Ubuntu/Debian (ufw)
#     sudo ufw allow from 192.168.179.0/24 to any port 4434 proto tcp
#     sudo ufw allow from 192.168.179.0/24 to any port 4435 proto tcp
#     sudo ufw reload
#     sudo ufw status numbered
#
#   # CentOS/RHEL (firewalld)
#     sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.179.0/24" port protocol="tcp" port="4434" accept'
#     sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.179.0/24" port protocol="tcp" port="4435" accept'
#     sudo firewall-cmd --reload
#     sudo firewall-cmd --list-all
#
# ------------------------------------------------------------------------------
#  BƯỚC 6 — Kiểm tra từ máy Windows
# ------------------------------------------------------------------------------
#
#   # 1. Kết nối được?
#   Test-NetConnection -ComputerName 192.168.179.176 -Port 4434
#   Test-NetConnection -ComputerName 192.168.179.176 -Port 4435
#   # -> TcpTestSucceeded : True
#
#   # 2. Health endpoint
#   Invoke-WebRequest http://192.168.179.176:4434/minio/health/live -UseBasicParsing | Select StatusCode
#   # -> 200
#
#   # 3. Bucket đã tạo chưa? (dùng MinIO client trong container)
#   ssh dev@192.168.179.176 "docker compose -f /home/dev/smart-factory/docker-compose.minio-datalake.yml \
#       run --rm --no-deps --entrypoint sh minio -c 'ls -la /data'"
#
#   # 4. Web console: mở trình duyệt
#   #    http://192.168.179.176:4435  (đăng nhập minioadmin / minioadmin123)
#
# ------------------------------------------------------------------------------
#  BƯỚC 7 — Nạp schema BATCH vào PostgreSQL (chạy trên MÁY WINDOWS)
# ------------------------------------------------------------------------------
#
#   cd E:\Work\SFSVcongty\Laird\Code\Data-Integrate
#   .\scripts\apply-batch-schema.ps1
#   # -> OK: da chay 03_batch_schema.sql
#   # -> OK: partition ...
#
# ------------------------------------------------------------------------------
#  BƯỚC 8 — CHẠY SPARK (⚠ ĐÃ CHUYỂN SANG SERVER — xem docs/deploy-spark-server.md)
# ------------------------------------------------------------------------------
#
#  Spark KHÔNG chạy native trên Windows được (thiếu `hadoop.dll` ->
#  UnsatisfiedLinkError khi S3A ghi Parquet). Đã chuyển sang chạy Spark
#  trong Docker trên máy server 192.168.179.176 — cùng máy đang chạy
#  Kafka + MinIO + PostgreSQL.
#
#   Xem đầy đủ: docs/deploy-spark-server.md
#
#  Tóm tắt:
#   # Trên MÁY WINDOWS
#   .\scripts\prepare-spark-jars.ps1        # gom 7 jar vào docker\spark\jars\
#   scp -r docker\spark                    dev@192.168.179.176:/home/dev/smart-factory/docker/
#   scp -r spark\apps spark\conf           dev@192.168.179.176:/home/dev/smart-factory/spark/
#   scp docker\docker-compose.spark-server.yml dev@192.168.179.176:/home/dev/smart-factory/
#
#   # Trên SERVER
#   cd /home/dev/smart-factory
#   docker compose -f docker-compose.spark-server.yml build
#   docker compose -f docker-compose.spark-server.yml up -d
#
#  Sau đó 3 container chạy nền:
#   spark-raw-ingest     Kafka -> MinIO raw Parquet   (UI: :4040)
#   spark-machine-state  Kafka -> Kafka `machine-state` (UI: :4041)
#   spark-batch-kpi      MinIO -> PostgreSQL fact     (UI: :4042)
#
#  Kiểm tra dữ liệu:
#   Invoke-WebRequest http://127.0.0.1:8000/api/analytics/freshness -UseBasicParsing
#
# ============================================================================
