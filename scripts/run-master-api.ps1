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

# ─── Nap bien tu file .env (neu co) ───────────────────────────────────────────
# File .env o goc repo (bi git-ignore) chua MASTER_DB_URL / MINIO_*.
# Uu tien: bien trong .env > bien da set trong shell hien tai.
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Write-Host "Doc config tu $EnvFile" -ForegroundColor DarkGray
    foreach ($line in Get-Content $EnvFile -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        $i = $t.IndexOf("=")
        if ($i -lt 1) { continue }
        $name = $t.Substring(0, $i).Trim()
        $val = $t.Substring($i + 1).Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($name)) {
            Set-Item -Path "Env:$name" -Value $val
        }
    }
}

if ($env:MASTER_DB_URL) {
    Write-Host "MASTER_DB_URL = $env:MASTER_DB_URL" -ForegroundColor Green
} else {
    Write-Host "MASTER_DB_URL chua duoc dat -> dung config/master_data.json (fallback)" -ForegroundColor Yellow
    Write-Host "  (set trong .env o goc repo de doc PostgreSQL that)" -ForegroundColor DarkGray
}

Push-Location (Join-Path $Root "services\master-api")
try {
    & $Py -m uvicorn app:app --host 0.0.0.0 --port 8001
} finally {
    Pop-Location
}
