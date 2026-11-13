# Chay state-api (FastAPI: Kafka machine-state -> REST + WebSocket :8000)
# Usage:  .\scripts\run-state-api.ps1
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "env-local.ps1")

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"

$env:KAFKA_BOOTSTRAP = "192.168.179.176:29092"
$env:STATE_TOPIC = "machine-state"

Push-Location (Join-Path $Root "services\state-api")
try {
    & $Py -m uvicorn app:app --host 0.0.0.0 --port 8000
} finally {
    Pop-Location
}
