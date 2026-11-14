# Gom JAR cho image Spark chay tren SERVER (docker/spark/Dockerfile.server).
#
#   .\scripts\prepare-spark-jars.ps1
#
# Ket qua: docker\spark\jars\*.jar  (7 file, ~275 MB)
#
# Nguon:
#   - 4 jar Kafka  : copy tu PySpark distribution (.venv\...\pyspark\jars)
#   - hadoop-aws   : tai tu Maven Central
#   - aws-sdk-bundle: tai tu Maven Central (267 MB - lon nhat)
#   - postgresql   : tai tu Maven Central
#
# Idempotent: file da ton tai + dung size -> bo qua.
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$JarDir = Join-Path $Root "docker\spark\jars"
$PySparkJars = Join-Path $Root ".venv\Lib\site-packages\pyspark\jars"

New-Item -ItemType Directory -Force -Path $JarDir | Out-Null

# --- 1. Jar co san trong PySpark -> copy -------------------------------------
$FromPySpark = @(
    "spark-sql-kafka-0-10_2.12-3.5.5.jar",
    "spark-token-provider-kafka-0-10_2.12-3.5.5.jar",
    "kafka-clients-3.4.1.jar",
    "commons-pool2-2.11.1.jar"
)
foreach ($n in $FromPySpark) {
    $src = Join-Path $PySparkJars $n
    $dst = Join-Path $JarDir $n
    if ((Test-Path $dst) -and -not $Force) {
        Write-Host "  = $n (da co)" -ForegroundColor DarkGray
        continue
    }
    if (-not (Test-Path $src)) {
        Write-Warning "thieu $n trong PySpark (can cai pyspark trong .venv)"
        continue
    }
    Copy-Item $src $dst -Force
    Write-Host "  > $n (copy tu pyspark)" -ForegroundColor Cyan
}

# --- 2. Jar tai tu Maven Central ---------------------------------------------
$FromMaven = @(
    @{ Name = "hadoop-aws-3.3.4.jar"
       Url  = "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar" },
    @{ Name = "aws-java-sdk-bundle-1.12.262.jar"
       Url  = "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar" },
    @{ Name = "postgresql-42.7.4.jar"
       Url  = "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar" }
)
foreach ($j in $FromMaven) {
    $dest = Join-Path $JarDir $j.Name
    if ((Test-Path $dest) -and -not $Force) {
        Write-Host "  = $($j.Name) (da co)" -ForegroundColor DarkGray
        continue
    }
    Write-Host "  > $($j.Name) ..." -ForegroundColor Cyan
    $tmp = "$dest.part"
    Invoke-WebRequest -Uri $j.Url -OutFile $tmp -UseBasicParsing -TimeoutSec 900
    Move-Item $tmp $dest -Force
    Write-Host "    xong ($([math]::Round((Get-Item $dest).Length / 1MB, 1)) MB)" -ForegroundColor Green
}

Write-Host "`nJAR trong $JarDir :" -ForegroundColor Cyan
Get-ChildItem $JarDir -Filter *.jar | ForEach-Object {
    "    {0,-46} {1,8} MB" -f $_.Name, [math]::Round($_.Length / 1MB, 1)
}
Write-Host "`nTiep theo: scp -r docker\spark dev@192.168.179.176:/home/dev/smart-factory/" -ForegroundColor Green
