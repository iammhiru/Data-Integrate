# Chay master-api (FastAPI :8001) — phuc vu MASTER DATA cho frontend.
#
# Master data = du lieu TINH (dong chay, SKU, work order, ke hoach san luong).
# Nguon: PostgreSQL (MASTER_DB_URL) neu co; khong co -> config/master_data.json.
#
# Usage:  .\scripts\run-master-api.ps1
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "env-local.ps1")

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"

# Neu co PostgreSQL thi tro MASTER_DB_URL vao day (comment de dung JSON fallback):
#   $env:MASTER_DB_URL = "postgres://smartfactory:smartfactory@192.168.179.176:5432/smartfactory"
if (-not $env:MASTER_DB_URL) {
    Write-Host "MASTER_DB_URL chua duoc dat -> dung config/master_data.json (fallback)" -ForegroundColor Yellow
}

Push-Location (Join-Path $Root "services\master-api")
try {
    & $Py -m uvicorn app:app --host 0.0.0.0 --port 8001
} finally {
    Pop-Location
}
