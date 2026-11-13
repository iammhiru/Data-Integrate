# Chay Middleware (doc Kepware qua OPC UA -> Kafka industrial.telemetry)
#
#   .\scripts\run-middleware.ps1            # dung .env (SIMULATION_MODE=false) -> doc Kepware that
#   .\scripts\run-middleware.ps1 -Simulation # bat simulation -> sinh du lieu lien tuc, khong can Kepware
#
# Luu y: file .env giu nguyen dung theo TichHopDuLieuLon_BaiTapLon/IndustrialTelemetry.Middleware/.env
# (KAFKA_BROKERS tro toi cluster that 192.168.179.176:29092).
param(
    [switch]$Simulation
)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "env-local.ps1")

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$Mw = Join-Path $Root "IndustrialTelemetry.Middleware"

$env:KAFKA_BROKERS = "192.168.179.176:29092"
$env:KAFKA_TOPIC = "industrial.telemetry"

if ($Simulation) {
    # Kepware tren may nay gia tri TINH (khong doi) -> change-detection dedup bo het,
    # khong co gi gui sang Kafka. Bat simulation de co du lieu lien tuc.
    $env:SIMULATION_MODE = "true"
    $env:SIMULATION_SPEED_FACTOR = "1.0"
    $env:SIMULATION_QUALITY_FAULT_RATE = "0.01"
    Write-Host ">>> SIMULATION_MODE=true (sinh du lieu gia lap)"
}

Push-Location $Mw
try {
    & $Py "$Mw\main.py"
} finally {
    Pop-Location
}
