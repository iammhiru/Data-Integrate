# ============================================================================
#  TRIỂN KHAI SPARK TRÊN MÁY SERVER 192.168.179.176
#  (thay cho chay Spark native tren Windows)
#
#  VÌ SAO CHUYỂN:
#    Spark chạy native trên Windows không ghi được Parquet ra MinIO:
#      java.lang.UnsatisfiedLinkError: NativeIO$Windows.access0
#        at org.apache.hadoop.fs.FileUtil.canRead(FileUtil.java:1249)
#        at org.apache.hadoop.util.DiskChecker.checkAccessByFileMethods(DiskChecker.java:160)
#        at org.apache.hadoop.fs.s3a.S3AFileSystem.createTmpFileForWrite(S3AFileSystem.java:1282)
#    Nguyên nhân: Hadoop tren Windows can native `hadoop.dll` de kiem tra
#    "dia local co ghi duoc khong" khi S3A staging block tam. May Windows
#    khong co binary nay (chi phat hanh tren GitHub) -> UnsatisfiedLinkError.
#    => Chay Spark trong Docker tren server Linux: co native san, va
#       co san Kafka + MinIO + PostgreSQL ngay canh.
#
#  KIEN TRUC SAU KHI CHUYEN:
#
#    [Windows]  Middleware ---> Kafka 192.168.179.176:29092
#    [Windows]  state-api (:8000) <--- Kafka topic `machine-state`
#    [Windows]  master-api (:8001) <--- PostgreSQL :5432
#    [Windows]  Frontend Vite (:5173)
#         |
#         | (server 192.168.179.176, tat ca trong Docker)
#         v
#    [Server]  spark-raw-ingest    Kafka -> MinIO s3a://smart-factory/raw/telemetry
#    [Server]  spark-batch-kpi     MinIO raw -> PostgreSQL machine_kpi_1m
#    [Server]  spark-machine-state Kafka -> Kafka `machine-state`
#
#  TAI NGUON CHAY:
#    · Kafka      : compose project `smart-factory-server`?? -> KHONG,
#                   Kafka chay bang compose rieng (docker-compose.kafka-fixed.yml),
#                   network `kafka-net`, 3 broker, publish 29092/39092/49092.
#    · MinIO      : compose project `smart-factory-datalake` (sf-minio-dl), port 4434/4435.
#    · PostgreSQL : compose project `smart-factory-server` (sf-postgres), port 5432.
#    Ba cai tren cung MOT may nhung KHAC network -> Spark dung IP HOST
#    (192.168.179.176) de noi den, KHONG dung ten service (minio:/postgres:/broker-1:).
#
# ------------------------------------------------------------------------------
#  BƯỚC 0 — KIỂM TRA PORT TRƯỚC KHI CHỐT CẤU HÌNH (BẮT BUỘC)
# ------------------------------------------------------------------------------
#
#  ⚠ Server da co dich vu khac chay port 8080/8081 -> KHONG dung cho Spark.
#    Cac port Spark da kiem tra TRONG (probe tu may Windows):
#       4040 / 4041 / 4042  -> FREE   (Spark UI: raw-ingest / machine-state / batch)
#       7077 / 7078         -> FREE   (khong dung - khong deploy master/worker)
#
#  Kiem tra lai tren SERVER (SSH vao), de chan doan chinh xac:
#
#    ssh dev@192.168.179.176
#
#    # 1) Port nao dang dung?
#    sudo ss -ltnp | grep -E ':(4040|4041|4042|7077|8080|8081|4434|4435|5432|29092)\b'
#
#    # 2) Container nao dang chay?
#    docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
#
#    # 3) Tai nguyen may (Spark 3 job can ~4GB RAM)
#    free -h
#    df -h /var/lib/docker          # can >= 8G (image Spark ~2.5GB + jars)
#    nproc                          # khuyen nghi >= 4 core
#
#    # 4) Firewall: KHONG can mo them port (Spark dung host network, noi bo)
#    #    Chi can cac port da dung cho Windows: 4434, 4435, 5432, 29092
#    sudo ufw status
#
#  NEU 4040/4041/4042 da bi dung -> doi trong docker-compose.spark-server.yml
#  (SPARK_UI_PORT + --conf spark.ui.port=...) roi build lai.
#
# ------------------------------------------------------------------------------
#  BƯỚC 1 — GOM JAR (chạy trên MÁY WINDOWS)
# ------------------------------------------------------------------------------
#
#   cd E:\Work\SFSVcongty\Laird\Code\Data-Integrate
#   .\scripts\prepare-spark-jars.ps1
#
#   -> Tao docker\spark\jars\ voi 7 file (~275 MB):
#        spark-sql-kafka-0-10_2.12-3.5.5.jar       (copy tu PySpark)
#        spark-token-provider-kafka-0-10_2.12-3.5.5.jar (copy tu PySpark)
#        kafka-clients-3.4.1.jar                   (copy tu PySpark)
#        commons-pool2-2.11.1.jar                  (copy tu PySpark)
#        hadoop-aws-3.3.4.jar                     (Maven)
#        aws-java-sdk-bundle-1.12.262.jar          (Maven, 267 MB)
#        postgresql-42.7.4.jar                    (Maven)
#
#   Build image OFFLINE (Dockerfile.server COPY jar) -> server KHONG can
#   truy cap repo1.maven.org khi build.
#
# ------------------------------------------------------------------------------
#  BƯỚC 2 — COPY FILE LÊN SERVER
# ------------------------------------------------------------------------------
#
#  ⚠ CÁCH NHANH NHẤT — dùng script (gom tar.gz 1 lan, chi nhap password 1 lan):
#
#   cd E:\Work\SFSVcongty\Laird\Code\Data-Integrate
#   .\scripts\deploy-spark-server.ps1
#
#  Script nay: gom `docker/spark` + `spark/apps` + `spark/conf` +
#  `docker-compose.spark-server.yml` vao `build/spark-server-bundle.tar.gz`
#  (247 MB) -> scp len server -> giai nen vao /home/dev/smart-factory/
#  -> in lenh can chay tiep.
#
#  ⚠ LAYOUT BẮT BUỘC trên server (compose file ở ROOT, KHÔNG trong docker/):
#
#     /home/dev/smart-factory/
#       docker-compose.spark-server.yml    <-- build context = ./docker/spark
#       docker/spark/{Dockerfile.server, jars/*.jar}
#       spark/apps/*.py                    <-- volume mount
#       spark/conf/spark-defaults-server.conf
#
#  NẾU tự làm từng lệnh:
#
#   ssh dev@192.168.179.176 "mkdir -p /home/dev/smart-factory/docker"
#
#   scp -r docker\spark            dev@192.168.179.176:/home/dev/smart-factory/docker/spark
#   scp -r spark\apps              dev@192.168.179.176:/home/dev/smart-factory/spark/apps
#   scp -r spark\conf              dev@192.168.179.176:/home/dev/smart-factory/spark/conf
#   scp docker\docker-compose.spark-server.yml dev@192.168.179.176:/home/dev/smart-factory/
#
#   ⚠ .env: dung chung voi MinIO Data Lake da tao. Kiem tra lai co dung
#      MINIO_ROOT_USER / MINIO_ROOT_PASSWORD / MINIO_BUCKET:
#
#   ssh dev@192.168.179.176 "grep -E 'MINIO_|KAFKA_BOOTSTRAP|POSTGRES_' /home/dev/smart-factory/.env"
#
#   Can co it nhat:
#     MINIO_ROOT_USER=minioadmin
#     MINIO_ROOT_PASSWORD=minioadmin123
#     MINIO_BUCKET=smart-factory
#     KAFKA_BOOTSTRAP=192.168.179.176:29092
#     POSTGRES_DB=smart_factory
#     POSTGRES_USER=sf_user
#     POSTGRES_PASSWORD=sf_password
#
# ------------------------------------------------------------------------------
#  BƯỚC 3 — BUILD IMAGE (trên SERVER)
# ------------------------------------------------------------------------------
#
#   ssh dev@192.168.179.176
#   cd /home/dev/smart-factory
#
#   docker compose -f docker-compose.spark-server.yml build
#
#   ⚠ Image apache/spark:3.5.5-...-ubuntu ~660MB (compressed) -> lau.
#      Neu Docker Hub bi chan -> xem muc "FALLBACK" cuoi file.
#
# ------------------------------------------------------------------------------
#  BƯỚC 4 — CHẠY (trên SERVER)
# ------------------------------------------------------------------------------
#
#   cd /home/dev/smart-factory
#   docker compose -f docker-compose.spark-server.yml up -d
#
#   # Theo doi:
#   docker compose -f docker-compose.spark-server.yml ps
#   docker compose -f docker-compose.spark-server.yml logs -f --tail=50
#
#   # Có 3 container:
#   #   spark-raw-ingest     -> ghi MinIO
#   #   spark-machine-state  -> ghi Kafka `machine-state`
#   #   spark-batch-kpi      -> ghi PostgreSQL (vong lap moi 300s)
#
# ------------------------------------------------------------------------------
#  BƯỚC 5 — KIỂM TRA FULL LUỒNG
# ------------------------------------------------------------------------------
#
#  5.1. Container healthy?
#
#    docker compose -f docker-compose.spark-server.yml ps
#    # Tat ca phai "Up", khong co "Restarting"
#
#  5.2. Raw ingest ghi duoc Parquet vao MinIO?
#
#    # Log can co dong JSON: {"batch":0,"rows":...,"invalid":0}
#    docker compose -f docker-compose.spark-server.yml logs spark-raw-ingest | grep '"batch"' | tail -5
#
#    # Kiem tra bucket (tu may Windows)
#    cd E:\Work\SFSVcongty\Laird\Code\Data-Integrate
#    .\.venv\Scripts\python.exe -c "import boto3; s=boto3.client('s3',endpoint_url='http://192.168.179.176:4434',aws_access_key_id='minioadmin',aws_secret_access_key='minioadmin123');print([(o['Key'],o['Size']) for o in s.list_objects_v2(Bucket='smart-factory').get('Contents',[])])"
#    # -> phai co raw/telemetry/ingest_date=.../ingest_hour=.../part-*.parquet
#
#  5.3. Batch KPI ghi duoc fact vao PostgreSQL?
#
#    docker compose -f docker-compose.spark-server.yml logs spark-batch-kpi | grep '"job"' | tail -5
#    # -> {"job":"incremental","range":[...],"events":...,"kpiRows":...}
#
#    # Query truc tiep (tu may Windows)
#    $env:PGPASSWORD="sf_password"
#    & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h 192.168.179.176 -U sf_user -d smart_factory -c "select count(*), min(ts_minute), max(ts_minute) from machine_kpi_1m;"
#    # (neu may Windows chua cai psql -> dung .\.venv\Scripts\python.exe voi psycopg)
#
#  5.4. Speed layer ghi Kafka `machine-state`?
#
#    .\.venv\Scripts\python.exe scripts\kafka_peek.py
#    # -> topic machine-state phai co message moi (timestamp gan)
#
#  5.5. Spark UI (tu trinh duyet)
#
#    http://192.168.179.176:4040   -> raw-ingest
#    http://192.168.179.176:4041   -> machine-state
#    http://192.168.179.176:4042   -> batch-kpi
#
#  5.6. API tren Windows van doc dung (khong can doi)
#
#    Invoke-WebRequest http://127.0.0.1:8000/api/analytics/freshness -UseBasicParsing
#    Invoke-WebRequest http://127.0.0.1:8000/api/analytics/overview   -UseBasicParsing
#
# ------------------------------------------------------------------------------
#  BƯỚC 6 — TẮT SPARK TRÊN WINDOWS (neu van con chay)
# ------------------------------------------------------------------------------
#
#   # Dung cac script Windows dang chay Spark:
#   Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
#     Where-Object { $_.CommandLine -like "*machine_state_stream.py*" -or
#                     $_.CommandLine -like "*raw_ingest.py*" -or
#                     $_.CommandLine -like "*batch_kpi.py*" } |
#     ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
#
#   # Xoa checkpoint Windows (khong dung nua, tranh doc trung):
#   Remove-Item -Recurse -Force .\.spark-checkpoints
#
#   ⚠ KHONG xoa volume Docker `smart-factory-spark_spark-checkpoints`:
#      no chua offset cua 3 job -> restart se doc lai tu dau.
#
# ------------------------------------------------------------------------------
#  VẤN ĐỀ THƯỜNG GẶP
# ------------------------------------------------------------------------------
#
#  · `docker compose ... build` that / loi mang
#      -> `docker pull apache/spark:3.5.5-scala2.12-java17-python3-ubuntu` thu truoc.
#         Neu that, xem FALLBACK cuoi file.
#
#  · `docker compose -f docker-compose.spark-server.yml` -> "no such file"
#      -> Compose file phai o ROOT cua /home/dev/smart-factory/ (KHONG trong docker/),
#         vi build context la `./docker/spark` va volume mount la `./spark/apps`.
#         Script deploy da lo ra dung layout; neu lam tay:
#           scp docker\docker-compose.spark-server.yml dev@192.168.179.176:/home/dev/smart-factory/
#
#  · `docker compose build` -> "Dockerfile.server not found" / "jars/... not found"
#      -> Thieu `docker/spark/jars/*.jar` tren server. Chay lai tren WINDOWS:
#           .\scripts\prepare-spark-jars.ps1
#           .\scripts\deploy-spark-server.ps1
#
#  · Container `spark-raw-ingest` restart lien tuc
#      -> `docker compose -f docker-compose.spark-server.yml logs spark-raw-ingest | tail -50`
#      -> 90% la endpoint sai (MinIO/PG/Kafka) hoac credential trong .env.
#
#  · `AccessDenied` khi ghi MinIO
#      -> MINIO_ROOT_USER/PASSWORD trong .env SERVER khac voi MinIO that.
#         Kiem tra: docker exec sf-minio-dl env | grep MINIO_ROOT
#
#  · `PSQLException: Connection refused` tu Spark
#      -> Postgres khong publish 5432 ra host, hoac firewall chua mo.
#         Kiem tra: docker ps | grep sf-postgres  (phai co 0.0.0.0:5432->5432)
#
#  · `Connection to node -1 could not be established` (Kafka)
#      -> KAFKA_BOOTSTRAP sai, hoac broker advertise IP cu (192.168.79.242).
#         Kiem tra tu Windows:
#           .\.venv\Scripts\python.exe -c "from kafka import KafkaAdminClient;print(KafkaAdminClient(bootstrap_servers='192.168.179.176:29092').describe_cluster())"
#         Neu host != 192.168.179.176 -> sua KAFKA_ADVERTISED_LISTENERS trong
#         docker-compose.kafka-fixed.yml tren server roi restart broker.
#
#  · Batch bao "chua co raw tai s3a://.../raw/telemetry"
#      -> raw-ingest chua ghi xong micro-batch dau tien (60s) -> cho them 1-2 phut.
#
#  · Ban muon chay lai tu dau (xoa offset):
#      docker compose -f docker-compose.spark-server.yml down
#      docker volume rm smart-factory-spark_spark-checkpoints
#      docker compose -f docker-compose.spark-server.yml up -d
#
# ------------------------------------------------------------------------------
#  FALLBACK — NEU SERVER KHONG PULL DUOC IMAGE SPARK
# ------------------------------------------------------------------------------
#
#  A) Docker Hub chan image apache/spark:
#      -> Build image Spark tren may Windows? Khong co Docker.
#      -> Hoac tai image tren may khac roi `docker save` / `docker load`:
#           docker pull apache/spark:3.5.5-scala2.12-java17-python3-ubuntu
#           docker save -o spark.tar apache/spark:3.5.5-scala2.12-java17-python3-ubuntu
#           scp spark.tar dev@192.168.179.176:/home/dev/smart-factory/
#           ssh dev@192.168.179.176 "docker load -i spark.tar"
#      -> Sua Dockerfile.server: FROM smart-factory/spark-local:3.5.5
#
#  B) Registry noi bo co image Spark:
#      -> doi FROM trong Dockerfile.server theo tag noi bo.
# ============================================================================
