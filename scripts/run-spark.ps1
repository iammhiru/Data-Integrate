# Chay Spark Structured Streaming job (industrial.telemetry -> machine-state compacted)
# Local mode tren Windows (khong co Docker/Spark cluster).
# Usage:  .\scripts\run-spark.ps1
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "env-local.ps1")

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$App = Join-Path $Root "spark\apps\machine_state_stream.py"
$Checkpoint = Join-Path $Root ".spark-checkpoints\machine-state"

New-Item -ItemType Directory -Force -Path (Split-Path $Checkpoint -Parent) | Out-Null

# spark-submit.cmd doc spark-defaults.conf tu %SPARK_CONF_DIR%
$env:SPARK_CONF_DIR = Join-Path $PSScriptRoot "spark-conf"

# PYSPARK_SUBMIT_ARGS phai GIU ten script cuoi cung (pyspark-shell) — pyspark tu them vao.
# --jars: patch Hadoop LocalFileSystem cho Windows (bo native hadoop.dll).
$PatchJar = Join-Path $PSScriptRoot "hadoop-patch\hadoop-localfs-patch.jar"
$env:PYSPARK_SUBMIT_ARGS = "--conf spark.driver.host=127.0.0.1 --conf spark.driver.bindAddress=127.0.0.1 --jars `"$PatchJar`" pyspark-shell"

& $Py $App `
    --bootstrap "192.168.179.176:29092" `
    --input-topic "industrial.telemetry" `
    --output-topic "machine-state" `
    --starting-offsets "latest" `
    --trigger "1 second" `
    --checkpoint-dir "$Checkpoint"
