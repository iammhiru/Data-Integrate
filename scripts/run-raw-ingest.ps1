# Chay RAW INGEST (L0) native tren Windows: Kafka `industrial.telemetry` -> MinIO Parquet.
#
#   .\scripts\run-raw-ingest.ps1                 # doc tu dau (earliest)
#   .\scripts\run-raw-ingest.ps1 -Latest         # chi doc event moi
#
# GHI vao MinIO:  s3a://<MINIO_BUCKET>/raw/telemetry/ingest_date=YYYY-MM-DD/ingest_hour=HH/
#
# Can: 3 jar S3A/PG (scripts\fetch-jars.ps1) + spark-defaults.conf tro dung endpoint MinIO.
param(
    [switch]$Latest,
    [int]$TriggerSec = 60
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "env-local.ps1")

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$App = Join-Path $Root "spark\apps\raw_ingest.py"
$Checkpoint = Join-Path $Root ".spark-checkpoints\raw-ingest"
$JarDir = Join-Path $PSScriptRoot "jars"

New-Item -ItemType Directory -Force -Path (Split-Path $Checkpoint -Parent) | Out-Null

# --- Bien MinIO tu .env goc repo ---
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
        if ($k -match '^(MINIO_|AWS_)') { Set-Item -Path "env:$k" -Value $v }
    }
}
if (-not $env:MINIO_BUCKET) { $env:MINIO_BUCKET = "smart-factory" }
if (-not $env:MINIO_ROOT_USER) { $env:MINIO_ROOT_USER = "minioadmin" }
if (-not $env:MINIO_ROOT_PASSWORD) { $env:MINIO_ROOT_PASSWORD = "minioadmin123" }
# S3A lay credential tu bien moi truong
$env:AWS_ACCESS_KEY_ID = $env:MINIO_ROOT_USER
$env:AWS_SECRET_ACCESS_KEY = $env:MINIO_ROOT_PASSWORD
$env:AWS_REGION = "us-east-1"

# --- Spark conf (S3A endpoint + PG JDBC) ---
$env:SPARK_CONF_DIR = Join-Path $PSScriptRoot "spark-conf"

$PatchJar = Join-Path $PSScriptRoot "hadoop-patch\hadoop-localfs-patch.jar"
$Jars = @($PatchJar)
foreach ($n in @("hadoop-aws-3.3.4.jar", "aws-java-sdk-bundle-1.12.262.jar", "postgresql-42.7.4.jar")) {
    $p = Join-Path $JarDir $n
    if (Test-Path $p) { $Jars += $p } else { Write-Warning "thieu jar: $n (chay scripts\fetch-jars.ps1)" }
}
$JarArg = ($Jars | ForEach-Object { "`"$_`"" }) -join ","

$env:PYSPARK_SUBMIT_ARGS = "--conf spark.driver.host=127.0.0.1 --conf spark.driver.bindAddress=127.0.0.1 --jars $JarArg pyspark-shell"

$offsets = if ($Latest) { "latest" } else { "earliest" }

Write-Host "raw-ingest: Kafka $($env:KAFKA_BOOTSTRAP) -> s3a://$($env:MINIO_BUCKET)/raw (offsets=$offsets, trigger=${TriggerSec}s)" -ForegroundColor Cyan
& $Py $App `
    --bootstrap $env:KAFKA_BOOTSTRAP `
    --topic "industrial.telemetry" `
    --bucket $env:MINIO_BUCKET `
    --starting-offsets $offsets `
    --trigger "$TriggerSec seconds" `
    --checkpoint-dir $Checkpoint
