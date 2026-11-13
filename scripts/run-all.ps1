# Chay TOAN BO pipeline (khong Docker) tren Windows, chay nen.
#
#   .\scripts\run-all.ps1                # middleware o che do SIMULATION (co du lieu lien tuc)
#   .\scripts\run-all.ps1 -RealKepware   # middleware doc Kepware that (chi dung khi gia tri tag doi)
#
# Chuoi du lieu:
#   Middleware -> Kafka `industrial.telemetry` -> Spark -> Kafka `machine-state` (compact)
#              -> state-api (FastAPI :8000) -> WebSocket -> Frontend (Vite :5173)
#
# Kafka: cluster that 192.168.179.176:29092 (KAFKA_BROKERS trong .env)
param(
    [switch]$RealKepware,
    [switch]$NoFrontend
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
Stop-Step "*machine_state_stream.py*"
Stop-Step "*IndustrialTelemetry.Middleware*main.py*"
Stop-Step "*uvicorn app:app*"

Write-Host "`n=== [0/4] Tao topic `machine-state` ===" -ForegroundColor Yellow
& (Join-Path $Root ".venv\Scripts\python.exe") (Join-Path $Scripts "kafka_create_topics.py")

Write-Host "`n=== [1/4] Spark Structured Streaming ===" -ForegroundColor Yellow
Start-Step "spark" "run-spark.ps1"
Start-Sleep -Seconds 40

Write-Host "`n=== [2/4] state-api (:8000) ===" -ForegroundColor Yellow
Start-Step "state-api" "run-state-api.ps1"
Start-Sleep -Seconds 20

Write-Host "`n=== [3/4] Middleware ===" -ForegroundColor Yellow
if ($RealKepware) {
    Start-Step "middleware" "run-middleware.ps1"
} else {
    Start-Step "middleware" "run-middleware.ps1" @("-Simulation")
}
Start-Sleep -Seconds 35

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
Write-Host "  Frontend  :5173  -> http://127.0.0.1:5173/?source=live" -ForegroundColor Green
Write-Host "  state-api :8000  -> http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "`nLog: $Logs\{spark,state-api,middleware}.err" -ForegroundColor DarkGray
