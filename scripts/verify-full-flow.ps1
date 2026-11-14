# Verify full luong du lieu sau khi chuyen Spark sang server 192.168.179.176.
#
#   .\scripts\verify-full-flow.ps1
#
# Kiem tra (tu may Windows, khong can SSH):
#   1. Port tren server (Kafka / MinIO / Postgres / Spark UI)
#   2. Kafka: topic + so message `industrial.telemetry` va `machine-state`
#   3. MinIO: bucket co Parquet trong raw/telemetry/
#   4. PostgreSQL: machine_kpi_1m co du lieu
#   5. Spark UI tren 4040/4041/4042 phan hoi
#   6. API local (state-api :8000, master-api :8001) neu dang chay
param(
    [string]$Server = "192.168.179.176",
    [string]$MinioEndpoint = "http://192.168.179.176:4434",
    [string]$KafkaBootstrap = "192.168.179.176:29092",
    [string]$Bucket = "smart-factory"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$Pass = 0
$Fail = 0

function Ok($msg)   { Write-Host "  [ OK ] $msg" -ForegroundColor Green; $script:Pass++ }
function No($msg)   { Write-Host "  [FAIL] $msg" -ForegroundColor Red;   $script:Fail++ }
function Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Head($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 1. Port
Head "1. Port tren server $Server"
foreach ($p in @(29092, 4434, 4435, 5432, 4040, 4041, 4042)) {
    $open = Test-NetConnection -ComputerName $Server -Port $p -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($open) { Ok "$p dang mo" } else { No "$p KHONG ket noi duoc" }
}

# ---------------------------------------------------------------- 2. Kafka
Head "2. Kafka ($KafkaBootstrap)"
& $Py (Join-Path $PSScriptRoot "kafka_peek.py") 2>&1 | Select-Object -First 30 | ForEach-Object { "    $_" }
if ($LASTEXITCODE -eq 0) { Ok "kafka_peek thanh cong" } else { No "kafka_peek that bai" }

# ---------------------------------------------------------------- 3. MinIO
Head "3. MinIO ($MinioEndpoint)"
& $Py -c @"
import boto3, sys
s = boto3.client('s3', endpoint_url='$MinioEndpoint',
    aws_access_key_id='minioadmin', aws_secret_access_key='minioadmin123',
    region_name='us-east-1')
try:
    r = s.list_objects_v2(Bucket='$Bucket')
    objs = r.get('Contents', [])
    pq = [o for o in objs if o['Key'].endswith('.parquet')]
    print(f'    tong object: {len(objs)}   parquet: {len(pq)}')
    for o in objs[:12]:
        print(f\"    {o['Key']}  {o['Size']}B\")
    print('    VERDICT=' + ('HAS_PARQUET' if pq else 'EMPTY'))
except Exception as e:
    print('    VERDICT=ERROR', e)
"@
if ($LASTEXITCODE -eq 0) { Ok "MinIO phan hoi" } else { No "MinIO loi" }

# ---------------------------------------------------------------- 4. PostgreSQL
Head "4. PostgreSQL fact (machine_kpi_1m)"
& $Py -c @"
import os, sys
sys.path.insert(0, os.path.join(r'$Root', '.venv', 'Lib', 'site-packages'))
try:
    import psycopg
except ImportError:
    print('    psycopg chua cai -> bo qua'); sys.exit(0)
try:
    with psycopg.connect('host=$Server port=5432 dbname=smart_factory user=sf_user password=sf_password', connect_timeout=8) as c:
        with c.cursor() as cur:
            cur.execute('select count(*), min(ts_minute), max(ts_minute) from machine_kpi_1m')
            n, lo, hi = cur.fetchone()
            print(f'    machine_kpi_1m: rows={n}  {lo} .. {hi}')
            cur.execute(\"select count(*) from machine_state_interval\")
            print('    machine_state_interval rows =', cur.fetchone()[0])
            cur.execute(\"select count(*) from data_quality_1m\")
            print('    data_quality_1m rows       =', cur.fetchone()[0])
            cur.execute(\"select job, status, range_start, range_end, finished_at from batch_run order by run_id desc limit 5\")
            print('    batch_run gan nhat:')
            for r in cur.fetchall():
                print('      ', r)
            print('    VERDICT=' + ('HAS_DATA' if n and n > 0 else 'EMPTY'))
except Exception as e:
    print('    VERDICT=ERROR', e)
"@

# ---------------------------------------------------------------- 5. Spark UI
Head "5. Spark UI tren server"
foreach ($p in @(4040, 4041, 4042)) {
    try {
        $r = Invoke-WebRequest "http://${Server}:$p" -UseBasicParsing -TimeoutSec 8
        Ok "Spark UI :$p -> HTTP $($r.StatusCode)"
    } catch {
        Warn "Spark UI :$p -> $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------- 6. API local
Head "6. API local (Windows)"
foreach ($api in @(@("state-api", 8000, "/api/analytics/freshness"), @("master-api", 8001, "/health"))) {
    $name, $port, $path = $api
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$port$path" -UseBasicParsing -TimeoutSec 8
        Ok "$name :$port$path -> HTTP $($r.StatusCode)"
        if ($r.Content) { "        $($r.Content.Substring(0, [Math]::Min(300, $r.Content.Length)))" }
    } catch {
        Warn "$name :$port$path -> $($_.Exception.Message)"
    }
}

Head "KET QUA"
Write-Host "  OK: $Pass    FAIL: $Fail" -ForegroundColor $(if ($Fail -eq 0) { "Green" } else { "Red" })
