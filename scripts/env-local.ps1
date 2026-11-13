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
