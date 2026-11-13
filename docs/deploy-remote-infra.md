# ============================================================================
#  CÀI HẠ TẦNG SERVER (PostgreSQL + MinIO) — máy Linux 192.168.179.176
#  Ngày: 13/11/2026
#
#  Máy server đã có Kafka chạy trong Docker (xem `docker-compose.kafka-fixed.yml`
#  ở thư mục gốc workspace). Hướng dẫn này bổ sung PostgreSQL + MinIO theo
#  ĐÚNG CÁCH ĐÓ — chỉ cần copy file rồi chạy `docker compose up -d`.
#
#  ⚠ Bạn tự SSH vào máy server và tự chạy lệnh. Tài liệu này là kịch bản
#    (copy/paste từng lệnh theo thứ tự).
# ============================================================================

 -------------------------------------------------------------------------------
 0. THÔNG TIN KẾT NỐI (dùng lại cho toàn bộ tài liệu)
 -------------------------------------------------------------------------------
   HOST          : 192.168.179.176
   SSH user      : <user> của bạn (ví dụ: dev)
   THƯ MỤC LÀM   : /home/dev/smart-factory     (đổi nếu bạn dùng thư mục khác)

   Sau khi cài xong, từ máy Windows sẽ dùng:
     PostgreSQL : 192.168.179.176:5432
                  db=smart_factory  user=sf_user  password=sf_password
     MinIO S3   : http://192.168.179.176:9000
                  access=minioadmin  secret=minioadmin123
                  bucket=smart-factory
     MinIO UI   : http://192.168.179.176:9001

   ⚠ Mật khẩu mặc định ở trên là cho môi trường DEV. Khi đưa lên production
     PHẢI đổi — xem mục 8.

 -------------------------------------------------------------------------------
 1. KIỂM TRA MÁY SERVER (SSH vào, chạy từng lệnh)
 -------------------------------------------------------------------------------
   docker --version
   docker compose version
   df -h /var/lib/docker          # can >= 5G trong cho postgres + minio
   free -h                        # can >= 4G RAM

   Nếu `docker compose version` loi → Docker daemon chua chay:
     sudo systemctl start docker
     sudo systemctl enable docker

 -------------------------------------------------------------------------------
 2. TẠO THƯ MỤC & COPY FILE TỪ MÁY WINDOWS
 -------------------------------------------------------------------------------
 2.1. Trên MÁY WINDOWS (PowerShell), chạy ở thư mục
      E:\Work\SFSVcongty\Laird\Code\Data-Integrate

      ssh <user>@192.168.179.176 "mkdir -p /home/dev/smart-factory/postgres"

      scp docker\docker-compose.server.yml <user>@192.168.179.176:/home/dev/smart-factory/docker-compose.server.yml

      scp -r postgres\init <user>@192.168.179.176:/home/dev/smart-factory/postgres/

      scp .env.example <user>@192.168.179.176:/home/dev/smart-factory/.env.example

 2.2. Kiểm tra trên máy server:
      ls -la /home/dev/smart-factory/
      ls -la /home/dev/smart-factory/postgres/init/

      Phải thấy:
        docker-compose.server.yml
        .env.example
        postgres/init/01_schema.sql
        postgres/init/02_seed_master_data.sql

 -------------------------------------------------------------------------------
 3. TẠO FILE .env TRÊN MÁY SERVER
 -------------------------------------------------------------------------------
   Trên máy server:

     cd /home/dev/smart-factory
     cp .env.example .env
     nano .env          # (hoac vi + xemay)

   Sửa `.env` cho đúng:

     # --- PostgreSQL ---
     POSTGRES_DB=smart_factory
     POSTGRES_USER=sf_user
     POSTGRES_PASSWORD=sf_password

     # --- MinIO ---
     MINIO_ROOT_USER=minioadmin
     MINIO_ROOT_PASSWORD=minioadmin123
     MINIO_BUCKET=smart-factory

   ⚠ KHÔNG cần (va KHONG nen) sua cac bien Kafka trong file nay — Kafka
     chay bang compose rieng (`docker-compose.kafka-fixed.yml`), khong dung
     file .env nay.

 -------------------------------------------------------------------------------
 4. KHỞI ĐỘNG
 -------------------------------------------------------------------------------
   cd /home/dev/smart-factory
   docker compose -f docker-compose.server.yml up -d

   Theo dõi:
     docker compose -f docker-compose.server.yml logs -f

   Thoát Ctrl+C (khong dung container) → ket thuc.

   Kiem tra trang thai:
     docker compose -f docker-compose.server.yml ps
     # PostgreSQL: healthy
     # MinIO     : healthy
     # minio-init: Exited (0)  <- binh thuong, chay 1 lan roi thoat

 -------------------------------------------------------------------------------
 5. KIỂM TRA SCHEMA + SEED
 -------------------------------------------------------------------------------
 5.1. Bảng đã tạo chưa:
     docker compose -f docker-compose.server.yml exec postgres \
       psql -U sf_user -d smart_factory -c '\dt'

   Phai thay 16 bang:
     counter_baseline, data_quality_metric, downtime_event, line,
     machine, machine_id_mapping, machine_metric_1m, machine_status_current,
     oee_metric, pipeline_latency_metric, product, production_metric,
     production_plan, quality_metric, shift, work_order

 5.2. Master data đã seed chưa:
     docker compose -f docker-compose.server.yml exec postgres \
       psql -U sf_user -d smart_factory -c "SELECT count(*) AS may FROM machine;"
     docker compose -f docker-compose.server.yml exec postgres \
       psql -U sf_user -d smart_factory -c "SELECT product_id, ideal_cycle_time_sec FROM product;"
     docker compose -f docker-compose.server.yml exec postgres \
       psql -U sf_user -d smart_factory -c "SELECT line_id, shift_id, planned_qty FROM production_plan ORDER BY line_id, shift_id;"
     docker compose -f docker-compose.server.yml exec postgres \
       psql -U sf_user -d smart_factory -c "SELECT wo_id, wo_code, status FROM work_order ORDER BY wo_id;"

   Kiem tra so lieu:
     may     = 26
     product = 3
     work_order = 9
     production_plan = 9

 5.3. NẠP LẠI SEED (khi master data thay đổi — KHÔNG xoá volume):
     docker compose -f docker-compose.server.yml exec -T postgres \
       psql -U sf_user -d smart_factory \
       -f /docker-entrypoint-initdb.d/02_seed_master_data.sql

 -------------------------------------------------------------------------------
 6. MO FIREWALL
 -------------------------------------------------------------------------------
   (Ubuntu/Debian — ufw)
     sudo ufw allow from 192.168.179.0/24 to any port 5432 proto tcp
     sudo ufw allow from 192.168.179.0/24 to any port 9000 proto tcp
     sudo ufw allow from 192.168.179.0/24 to any port 9001 proto tcp
     sudo ufw reload
     sudo ufw status numbered

   (CentOS/RHEL — firewalld)
     sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.179.0/24" port protocol="tcp" port="5432" accept'
     sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.179.0/24" port protocol="tcp" port="9000" accept'
     sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.179.0/24" port protocol="tcp" port="9001" accept'
     sudo firewall-cmd --reload
     sudo firewall-cmd --list-all

   ⚠ Neu may server co SELinux, them context cho thu muc data:
     sudo semanage fcontext -a -t container_file_t "/var/lib/docker/volumes/sf-smart-factory-server_postgres-data/_data(/.*)?"
     sudo restorecon -Rv /var/lib/docker/volumes/sf-smart-factory-server_postgres-data/_data

 -------------------------------------------------------------------------------
 7. KIỂM TRA TỪ MÁY WINDOWS
 -------------------------------------------------------------------------------
   PowerShell:
     Test-NetConnection -ComputerName 192.168.179.176 -Port 5432
     Test-NetConnection -ComputerName 192.168.179.176 -Port 9000
     Test-NetConnection -ComputerName 192.168.179.176 -Port 9001

   Ket qua mong doi: True / True / True

   Ket noi truc tiep (neu co psql):
     psql "postgresql://sf_user:sf_password@192.168.179.176:5432/smart_factory" -c '\dt'

 -------------------------------------------------------------------------------
 8. TRO `master-api` VAO POSTGRESQL
 -------------------------------------------------------------------------------
 8.1. Trên máy Windows, sua `scripts/run-master-api.ps1`:
       (dong dang COMMENT — chuyen thanh de chay that)
         $env:MASTER_DB_URL = "postgres://sf_user:sf_password@192.168.179.176:5432/smart_factory"

 8.2. Restart master-api:
       Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
         Where-Object { $_.CommandLine -like "*uvicorn*8001*" } |
         ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
       cd E:\Work\SFSVcongty\Laird\Code\Data-Integrate
       Start-Process powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","scripts\run-master-api.ps1" `
         -RedirectStandardOutput "logs\master-api.out" `
         -RedirectStandardError  "logs\master-api.err" -WindowStyle Hidden

 8.3. Kiem tra:
       Invoke-WebRequest http://127.0.0.1:8001/health | Select -Expand Content
       # -> {"status":"ok","source":"postgres", ...}   <-- PHẢI là "postgres"

 8.4. (Tuỳ chọn) Tạo file `.env` riêng cho chay native tren Windows:
       Trong repo, `Data-Integrate/.env` dang bi git-ignore. Tao file do voi:
         MASTER_DB_URL=postgres://sf_user:sf_password@192.168.179.176:5432/smart_factory
         MINIO_ENDPOINT=http://192.168.179.176:9000
         MINIO_ACCESS_KEY=minioadmin
         MINIO_SECRET_KEY=minioadmin123
         MINIO_BUCKET=smart-factory

 -------------------------------------------------------------------------------
 9. DUY TRÌ (backup + upgrade)
 -------------------------------------------------------------------------------
 9.1. BACKUP PostgreSQL (nen dat cron hang ngay):
       docker compose -f /home/dev/smart-factory/docker-compose.server.yml exec -T postgres \
         pg_dump -U sf_user -d smart_factory -Fc > /home/dev/backup/smart_factory_$(date +%F).dump
       # Don dep file backup cu hon 14 ngay:
       find /home/dev/backup -name 'smart_factory_*.dump' -mtime +14 -delete

 9.2. Nang cap image:
       cd /home/dev/smart-factory
       docker compose -f docker-compose.server.yml pull
       docker compose -f docker-compose.server.yml up -d

 -------------------------------------------------------------------------------
 10. XOA HET (can lam lai tu dau)
 -------------------------------------------------------------------------------
   ⚠ XOA TOAN BO DU LIEU postgres + minio:
       cd /home/dev/smart-factory
       docker compose -f docker-compose.server.yml down -v
       # -v xoa named volume -> DB rong, script init chay lai tu dau

 -------------------------------------------------------------------------------
 11. XU LY SU CO
 -------------------------------------------------------------------------------
 11.1. PostgreSQL khong len / unhealthy:
       docker compose -f docker-compose.server.yml logs postgres | tail -50
       # Thuong do: volume da co du lieu cu tu lan chay truoc → script init KHONG
       # chay lai. Kiem tra bang:
       docker compose -f docker-compose.server.yml exec postgres \
         psql -U sf_user -d smart_factory -c '\dt'

 11.2. "password authentication failed" tu may Windows:
       - Sai ten database/user → xem lai `.env` tren server
       - `pg_hba.conf` tu choi `scram-sha-256`/`md5` cho host LAN → kiem tra:
           docker compose -f docker-compose.server.yml exec postgres \
             cat /var/lib/postgresql/data/pg_hba.conf | grep -v '^#'
       - Firewall chua mo port 5432

 11.3. Port 5432 bi CHIEM tren may Windows (Postgres local):
       Dung port khac tren server, vi du 15432:
         docker-compose.server.yml:  ports: - "15432:5432"
         va ket noi: postgres://sf_user:sf_password@192.168.179.176:15432/smart_factory

 11.4. MinIO khong tao duoc bucket:
       docker compose -f docker-compose.server.yml logs minio-init
       # Neu image alpine/minio khong pull duoc → doi sang minio/minio:latest
       # (can internet + Docker Hub)

 11.5. Docker compose version loi → dung `docker-compose` (co dau gach):
       docker-compose -f docker-compose.server.yml up -d
