# Chay BATCH KPI (L1/L2) native tren Windows: MinIO raw Parquet -> PostgreSQL fact 1 phut.
#
#   .\scripts\run-batch-kpi.ps1                          # incremental (mac dinh: 30 phut lookback)
#   .\scripts\run-batch-kpi.ps1 -Mode daily -Date 2026-11-13
#   .\scripts\run-batch-kpi.ps1 -Mode backfill -From 2026-11-12 -To 2026-11-13
#
# Can: scripts\fetch-jars.ps1 (S3A + PG JDBC) + MinIO + PostgreSQL deu truy cap duoc.
param(
    [ValidateSet("incremental", "daily", "backfill", "auto")]
    [string]$Mode = "incremental",
    [string]$Date,
    [string]$From,
    [string]$To,
    [int]$LookbackMin = 30,
    [int]$DelayMin = 3
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "env-local.ps1")

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$App = Join-Path $Root "spark\apps\batch_kpi.py"
$JarDir = Join-Path $PSScriptRoot "jars"

# --- Bien MinIO + PG tu .env goc repo ---
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
        if ($k -match '^(MINIO_|AWS_|POSTGRES_|PG_)') { Set-Item -Path "env:$k" -Value $v }
    }
}
if (-not $env:MINIO_BUCKET) { $env:MINIO_BUCKET = "smart-factory" }
if (-not $env:MINIO_ROOT_USER) { $env:MINIO_ROOT_USER = "minioadmin" }
if (-not $env:MINIO_ROOT_PASSWORD) { $env:MINIO_ROOT_PASSWORD = "minioadmin123" }
$env:AWS_ACCESS_KEY_ID = $env:MINIO_ROOT_USER
$env:AWS_SECRET_ACCESS_KEY = $env:MINIO_ROOT_PASSWORD
$env:AWS_REGION = "us-east-1"

if (-not $env:PG_JDBC_URL) {
    $env:PG_JDBC_URL = "jdbc:postgresql://192.168.179.176:5432/smart_factory"
}
if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = "sf_user" }
if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = "sf_password" }
$env:PLANT_TZ = "Asia/Ho_Chi_Minh"

# --- Spark conf ---
$env:SPARK_CONF_DIR = Join-Path $PSScriptRoot "spark-conf"

$PatchJar = Join-Path $PSScriptRoot "hadoop-patch\hadoop-localfs-patch.jar"
$Jars = @($PatchJar)
foreach ($n in @("hadoop-aws-3.3.4.jar", "aws-java-sdk-bundle-1.12.262.jar", "postgresql-42.7.4.jar")) {
    $p = Join-Path $JarDir $n
    if (Test-Path $p) { $Jars += $p } else { Write-Warning "thieu jar: $n (chay scripts\fetch-jars.ps1)" }
}
$JarArg = ($Jars | ForEach-Object { "`"$_`"" }) -join ","
$env:PYSPARK_SUBMIT_ARGS = "--conf spark.driver.host=127.0.0.1 --conf spark.driver.bindAddress=127.0.0.1 --jars $JarArg pyspark-shell"

$argList = @($App, "--mode", $Mode, "--pg-url", $env:PG_JDBC_URL,
             "--pg-user", $env:POSTGRES_USER, "--pg-password", $env:POSTGRES_PASSWORD,
             "--bucket", $env:MINIO_BUCKET, "--tz", $env:PLANT_TZ,
             "--lookback-min", $LookbackMin, "--delay-min", $DelayMin)
if ($Date) { $argList += @("--date", $Date) }
if ($From) { $argList += @("--from", $From) }
if ($To)   { $argList += @("--to", $To) }

Write-Host "batch-kpi: mode=$Mode  MinIO=$($env:MINIO_BUCKET)  PG=$($env:PG_JDBC_URL)" -ForegroundColor Cyan
& $Py @argList
