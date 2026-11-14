# Common environment cho khi chay pipeline truc tiep tren Windows (khong dung Docker).
# Dung:  . .\scripts\env-local.ps1  hoac  & .\scripts\env-local.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

# --- Java 17 (Spark) ---
$JavaHome = "C:\Program Files\Eclipse Adoptium\jdk-17.0.21.9-hotspot"
if (-not (Test-Path $JavaHome)) {
    $found = Get-ChildItem "C:\Program Files\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($found) { $JavaHome = $found.FullName }
}

# --- HADOOP_HOME: chi can de Hadoop tim thay winutils.exe tren Windows ---
$HadoopHome = Join-Path $PSScriptRoot "winutils"
New-Item -ItemType Directory -Force -Path (Join-Path $HadoopHome "bin") | Out-Null
if (-not (Test-Path (Join-Path $HadoopHome "bin\winutils.exe"))) {
    $src = Join-Path $PSScriptRoot "winutils\winutils.exe"
    if (Test-Path $src) { Copy-Item $src (Join-Path $HadoopHome "bin\winutils.exe") -Force }
}

# --- Kafka cluster that ---
$env:KAFKA_BOOTSTRAP = "192.168.179.176:29092"
$env:KAFKA_BROKERS   = "192.168.179.176:29092"
$env:STATE_TOPIC     = "machine-state"
$env:TELEMETRY_TOPIC = "industrial.telemetry"

# --- Nap .env goc repo (MASTER_DB_URL, PG_DSN, MINIO_*, KEPWARE_*, ...) ---
# Services doc config tu bien moi truong; .env la noi duy nang chua gia tri that.
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $k, $v = $line -split '=', 2
        $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
        if ($k) { Set-Item -Path "env:$k" -Value $v }
    }
}

# state-api / master-api doc PG_DSN; .env co the chi co MASTER_DB_URL -> map sang PG_DSN
if (-not $env:PG_DSN -and $env:MASTER_DB_URL) {
    $env:PG_DSN = $env:MASTER_DB_URL
}
if ($env:PG_DSN) { Write-Host "PG_DSN          = $env:PG_DSN" }

# --- Python ---
$env:PYSPARK_PYTHON        = $Py
$env:PYSPARK_DRIVER_PYTHON = $Py

# --- Spark ---
if ($JavaHome -and (Test-Path $JavaHome)) {
    $env:JAVA_HOME = $JavaHome
    $env:PATH = "$JavaHome\bin;$env:PATH"
}
$env:SPARK_HOME = Join-Path $Venv "Lib\site-packages\pyspark"

# --- Hadoop (Spark goi winutils.exe de chmod khi tao checkpoint dir) ---
$env:HADOOP_HOME = $HadoopHome
$env:PATH = "$HadoopHome\bin;$env:PATH"

Write-Host "JAVA_HOME       = $env:JAVA_HOME"
Write-Host "SPARK_HOME      = $env:SPARK_HOME"
Write-Host "HADOOP_HOME     = $env:HADOOP_HOME"
Write-Host "KAFKA_BOOTSTRAP = $env:KAFKA_BOOTSTRAP"
Write-Host "PY              = $Py"
