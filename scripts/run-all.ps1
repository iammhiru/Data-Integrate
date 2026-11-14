# ============================================================================
#  CHAY TOAN BO PIPELINE (khong Docker) tren Windows, chay nen.
#
#   .\scripts\run-all.ps1 -Mode Simulation   # middleware gia lap (SIMULATION_MODE=true)
#   .\scripts\run-all.ps1 -Mode Real         # middleware doc Kepware that (SIMULATION_MODE=false)
#   .\scripts\run-all.ps1 -Mode Simulation -SkipSpark   # bo Spark local (mac dinh: BO)
#
#  ⚠ MAC DINH -SkipSpark = TRUE:
#    Spark da chay trong Docker tren server 192.168.179.176
#    (spark-raw-ingest / spark-machine-state / spark-batch-kpi).
#    Chay them Spark local se bi 2 job ghi cung topic `machine-state` ->
#    gia tri trong UI nhay nhay. Dung -SkipSpark:$false neu muon chay local
#    (chi khi server chua co Spark).
#
#  Chuoi du lieu:
#    Middleware -> Kafka `industrial.telemetry` -> [Spark tren server] ->
#    Kafka `machine-state` (compacted) -> state-api (FastAPI :8000) ->
#    WebSocket -> Frontend (Vite :5173)
#
#  Master data (dong chay, SKU, work order, ke hoach) -> master-api (:8001) -> Frontend
#
#  Kafka: cluster that 192.168.179.176:29092 (KAFKA_BROKERS trong .env)
#
#  Script chuyen rieng (de doc):
#    .\scripts\run-sim.ps1    # gia lap, khong Spark
#    .\scripts\run-real.ps1   # Kepware that, khong Spark
# ============================================================================
param(
    [ValidateSet("Simulation", "Real")]
    [string]$Mode = "Simulation",
    [switch]$NoFrontend,
    # -SkipSpark:$false -> CHAY Spark local tren may nay (mac dinh: KHONG chay).
    [switch]$SkipSpark = $true,
    [double]$SpeedFactor = 1.0,
    [double]$FaultRate = 0.01
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Scripts = $PSScriptRoot
$Logs = Join-Path $Root "logs"

New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Start-Step {
    param([string]$Name, [string]$Script, [string[]]$ExtraArgs = @())
    Write-Host "==> Bat $Name" -ForegroundColor Cyan
    $out = Join-Path $Logs "$Name.out"
    $err = Join-Path $Logs "$Name.err"
    Remove-Item $out, $err -ErrorAction SilentlyContinue
    $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Scripts $Script)) + $ExtraArgs
    Start-Process -FilePath "powershell.exe" -ArgumentList $args `
        -RedirectStandardOutput $out -RedirectStandardError $err `
        -WindowStyle Hidden -WorkingDirectory $Root | Out-Null
}

function Stop-Step {
    param([string]$Pattern)
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like $Pattern } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

# --- Dung phien ban cu (neu co) ---
Write-Host "`n=== [0/4] Dung phien cu ===" -ForegroundColor Yellow
Stop-Step "*machine_state_stream.py*"
Stop-Step "*raw_ingest.py*"
Stop-Step "*batch_kpi.py*"
Stop-Step "*IndustrialTelemetry.Middleware*main.py*"
Stop-Step "*uvicorn app:app*"

Write-Host "`n=== [0b/4] Tao topic `machine-state` ===" -ForegroundColor Yellow
& (Join-Path $Root ".venv\Scripts\python.exe") (Join-Path $Scripts "kafka_create_topics.py")

if ($SkipSpark) {
    Write-Host "`n=== [1/4] Spark: BO QUA (dang chay tren server 192.168.179.176) ===" -ForegroundColor DarkGray
} else {
    Write-Host "`n=== [1/4] Spark Structured Streaming (LOCAL tren may nay) ===" -ForegroundColor Yellow
    Start-Step "spark" "run-spark.ps1"
    Start-Sleep -Seconds 40
}

Write-Host "`n=== [2/4] state-api (:8000) ===" -ForegroundColor Yellow
Start-Step "state-api" "run-state-api.ps1"
Start-Sleep -Seconds 15

Write-Host "`n=== [2b/4] master-api (:8001) — master data + Work Order ===" -ForegroundColor Yellow
Start-Step "master-api" "run-master-api.ps1"
Start-Sleep -Seconds 8

Write-Host "`n=== [3/4] Middleware (Mode=$Mode) ===" -ForegroundColor Yellow
Start-Step "middleware" "run-middleware.ps1" @("-Mode", $Mode, "-SpeedFactor", "$SpeedFactor", "-FaultRate", "$FaultRate")
Start-Sleep -Seconds 30

if (-not $NoFrontend) {
    Write-Host "`n=== [4/4] Frontend Vite (:5173) ===" -ForegroundColor Yellow
    $fe = Join-Path $Root "dashboard\frontend"
    $existing = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Vite da chay tren :5173 — bo qua" -ForegroundColor DarkGray
    } else {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
            -RedirectStandardOutput (Join-Path $Logs "frontend.out") `
            -RedirectStandardError (Join-Path $Logs "frontend.err") `
            -WindowStyle Hidden -WorkingDirectory $fe | Out-Null
    }
}

Write-Host "`n=== KET QUA ===" -ForegroundColor Green
Start-Sleep -Seconds 20
try {
    $h = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 10).Content
    Write-Host "  state-api :8000  -> $h" -ForegroundColor Green
} catch {
    Write-Host "  state-api :8000  -> CHUA SAN SANG ($($_.Exception.Message))" -ForegroundColor Red
}
try {
    $m = (Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -UseBasicParsing -TimeoutSec 10).Content
    Write-Host "  master-api :8001 -> $m" -ForegroundColor Green
} catch {
    Write-Host "  master-api :8001 -> CHUA SAN SANG ($($_.Exception.Message))" -ForegroundColor Red
}
Write-Host "  Frontend  :5173  -> http://127.0.0.1:5173/?source=live" -ForegroundColor Green
Write-Host "  state-api :8000  -> http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "`nLog: $Logs\{state-api,master-api,middleware}.err" -ForegroundColor DarkGray
