# Tai ve cac JAR bat buoc cho Spark chay NATIVE tren Windows (khong dung Docker).
#
#   .\scripts\fetch-jars.ps1
#
# PySpark 3.5.5 di kem 257 jar nhung THIEU 3 jar bat buoc cho duong batch:
#   1. hadoop-aws           : S3A filesystem (doc/ghi Parquet tren MinIO)
#   2. aws-java-sdk-bundle  : SDK S3 cho S3A
#   3. postgresql           : JDBC driver (batch_kpi.py ghi PostgreSQL qua JDBC)
#
# Docker image `smart-factory/spark` (docker/spark/Dockerfile) da ADD sẵn 3 jar này;
# khi chay native tren Windows thi phải tải về như script này làm.
#
# Idempotent: jar đã tồn tại + đúng size → bỏ qua.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$JarDir = Join-Path $PSScriptRoot "jars"
New-Item -ItemType Directory -Force -Path $JarDir | Out-Null

$Jars = @(
    @{ Name = "hadoop-aws-3.3.4.jar"
       Url  = "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar" },
    @{ Name = "aws-java-sdk-bundle-1.12.262.jar"
       Url  = "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar" },
    @{ Name = "postgresql-42.7.4.jar"
       Url  = "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar" }
)

foreach ($j in $Jars) {
    $dest = Join-Path $JarDir $j.Name
    if (Test-Path $dest) {
        Write-Host "  = $($j.Name) (da co)" -ForegroundColor DarkGray
        continue
    }
    Write-Host "  > $($j.Name) ..." -ForegroundColor Cyan
    $tmp = "$dest.part"
    Invoke-WebRequest -Uri $j.Url -OutFile $tmp -UseBasicParsing -TimeoutSec 900
    Move-Item $tmp $dest -Force
    $mb = [math]::Round((Get-Item $dest).Length / 1MB, 1)
    Write-Host "    xong ($mb MB)" -ForegroundColor Green
}

Write-Host "`nJAR trong $JarDir :" -ForegroundColor Cyan
Get-ChildItem $JarDir -Filter *.jar | ForEach-Object {
    "    {0,-38} {1,8} MB" -f $_.Name, [math]::Round($_.Length / 1MB, 1)
}
