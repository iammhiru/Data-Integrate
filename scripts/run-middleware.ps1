# Chay Middleware (doc Kepware qua OPC UA -> Kafka industrial.telemetry)
#
#   .\scripts\run-middleware.ps1 -Mode Simulation  # SIMULATION_MODE=true  -> sinh du lieu gia lap
#   .\scripts\run-middleware.ps1 -Mode Real        # SIMULATION_MODE=false -> doc Kepware that
#
# Mac dinh: -Mode Real (giong .env cua IndustrialTelemetry.Middleware).
#
# ⚠ Bien moi truong set o day LUON THANG bien trong file .env, nen khong can
#   sua .env khi doi che do. `settings.py` dung `os.getenv()` nen bien moi
#   truong da co se duoc dung, khong bi .env ghi de.
#
# Luu y: file .env giu nguyen dung theo TichHopDuLieuLon_BaiTapLon/IndustrialTelemetry.Middleware/.env
# (KAFKA_BROKERS tro toi cluster that 192.168.179.176:29092).
param(
    [ValidateSet("Simulation", "Real")]
    [string]$Mode = "Real",
    # He so toc do mo phong (chi dung o che do Simulation).
    [double]$SpeedFactor = 1.0,
    # Ty le phat loi chat luong gia lap (chi dung o che do Simulation).
    [double]$FaultRate = 0.01
)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "env-local.ps1")

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$Mw = Join-Path $Root "IndustrialTelemetry.Middleware"

$env:KAFKA_BROKERS = "192.168.179.176:29092"
$env:KAFKA_TOPIC = "industrial.telemetry"

if ($Mode -eq "Simulation") {
    # Kepware tren may nay gia tri TINH (khong doi) -> change-detection dedup bo het,
    # khong co gi gui sang Kafka. Bat simulation de co du lieu lien tuc.
    $env:SIMULATION_MODE = "true"
    $env:SIMULATION_SPEED_FACTOR = "$SpeedFactor"
    $env:SIMULATION_QUALITY_FAULT_RATE = "$FaultRate"
    Write-Host ">>> SIMULATION_MODE=true (sinh du lieu gia lap, speed x$SpeedFactor, fault rate $FaultRate)" -ForegroundColor Green
} else {
    $env:SIMULATION_MODE = "false"
    Write-Host ">>> SIMULATION_MODE=false (doc Kepware that qua OPC UA)" -ForegroundColor Cyan
}

Push-Location $Mw
try {
    & $Py "$Mw\main.py"
} finally {
    Pop-Location
}
