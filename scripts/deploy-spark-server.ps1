# Deploy Spark (server) tu may WINDOWS len may Linux 192.168.179.176.
#
#   .\scripts\deploy-spark-server.ps1
#   .\scripts\deploy-spark-server.ps1 -Server 192.168.179.176 -User dev
#
# Lam gi (tu dong):
#   1. Gom docker\spark, spark\apps, spark\conf, docker-compose.spark-server.yml
#      vao 1 file tar.gz (tranh nhap password nhieu lan).
#   2. scp len server.
#   3. ssh giai nen vao /home/dev/smart-factory/ (giai nen de an toan).
#   4. Hien lenh can chay tiep tren server (build + up) — KHONG tu chay
#      vi can quyet dinh thoi diem build/up.
param(
    [string]$Server = "192.168.179.176",
    [string]$User = "dev",
    [string]$RemoteDir = "/home/dev/smart-factory",
    [switch]$SkipTar
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BundleDir = Join-Path $Root "build"
$Stage = Join-Path $BundleDir "stage"
$Bundle = Join-Path $BundleDir "spark-server-bundle.tar.gz"
$RemoteBundle = "$RemoteDir/spark-server-bundle.tar.gz"

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null

# --- 1. Gom file --------------------------------------------------------------
if (-not $SkipTar) {
    Write-Host "==> [1/3] Gom file vao bundle..." -ForegroundColor Cyan

    # Docker image build context: docker/spark (Dockerfile.server + jars/)
    $ctx = Join-Path $Root "docker\spark"
    if (-not (Test-Path (Join-Path $ctx "jars\aws-java-sdk-bundle-1.12.262.jar"))) {
        Write-Warning "Thieu jar trong docker\spark\jars — chay .\scripts\prepare-spark-jars.ps1 truoc!"
    }

    # STAGING: compose file phai o ROOT cua remote dir (no no la build context
    # `./docker/spark` + volume mount `./spark/apps`), KHONG nam trong `docker/`.
    Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path (Join-Path $Stage "docker") | Out-Null
    # Copy-Item dich TEN thu muc -> phai tao thu muc dich truoc, neu khong
    # `docker\spark` se bi copy thanh `docker/` (mat duong dan `docker/spark`).
    Copy-Item (Join-Path $Root "docker\spark") (Join-Path $Stage "docker\spark") -Recurse -Force
    Copy-Item (Join-Path $Root "spark")         (Join-Path $Stage "spark") -Recurse -Force
    Copy-Item (Join-Path $Root "docker\docker-compose.spark-server.yml") (Join-Path $Stage "docker-compose.spark-server.yml") -Force

    Remove-Item $Bundle -Force -ErrorAction SilentlyContinue
    Push-Location $Stage
    try {
        # -C staging de duong dan trong bundle giong het layout tren server:
        #   docker/spark/...  spark/apps/...  spark/conf/...  docker-compose.spark-server.yml
        tar -czf $Bundle -C $Stage docker spark docker-compose.spark-server.yml
        if ($LASTEXITCODE -ne 0) { throw "tar that bai (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
    $mb = [math]::Round((Get-Item $Bundle).Length / 1MB, 1)
    Write-Host "    bundle: $Bundle ($mb MB)" -ForegroundColor Green
    Write-Host "    noi dung:" -ForegroundColor DarkGray
    tar -tzf $Bundle | ForEach-Object { "      $_" }
}

# --- 2. Copy len server -------------------------------------------------------
Write-Host "==> [2/3] Copy len $Server ..." -ForegroundColor Cyan
ssh -o StrictHostKeyChecking=no $User@$Server "mkdir -p $RemoteDir"
if ($LASTEXITCODE -ne 0) { throw "ssh that bai — check user/pass" }

scp -o StrictHostKeyChecking=no $Bundle "${User}@${Server}:$RemoteBundle"
if ($LASTEXITCODE -ne 0) { throw "scp that bai" }

# --- 3. Giai nen tren server ---------------------------------------------------
Write-Host "==> [3/3] Giai nen tren server..." -ForegroundColor Cyan
$remoteCmd = @"
cd $RemoteDir && \
rm -rf docker/Dockerfile docker/Dockerfile.server docker/jars && \
tar -xzf spark-server-bundle.tar.gz && rm -f spark-server-bundle.tar.gz && \
echo '--- layout tren server ---' && \
ls -1 docker/spark/jars/ && \
ls -1 spark/apps/ && \
ls -1 spark/conf/ && \
ls -1 docker-compose.spark-server.yml
"@
ssh -o StrictHostKeyChecking=no $User@$Server $remoteCmd
if ($LASTEXITCODE -ne 0) { throw "giai nen that bai" }

Write-Host "`n=== Xong. Tren SERVER chay tiep: ===" -ForegroundColor Green
Write-Host @"
  ssh $User@$Server
  cd $RemoteDir

  # 0. KIEM TRA PORT truoc khi chot (bat buoc)
  sudo ss -ltnp | grep -E ':(4040|4041|4042|7077|8080|8081)\b'
  free -h
  df -h /var/lib/docker

  # 1. Kiem tra .env co dung credential khong
  grep -E 'MINIO_|KAFKA_BOOTSTRAP|POSTGRES_' .env

  # 2. Build image (offline, jar da COPY trong image)
  docker compose -f docker-compose.spark-server.yml build

  # 3. Chay 3 job
  docker compose -f docker-compose.spark-server.yml up -d
  docker compose -f docker-compose.spark-server.yml ps

  # 4. Theo doi log
  docker compose -f docker-compose.spark-server.yml logs -f --tail=50
"@ -ForegroundColor Gray

Write-Host "`nSau khi len server xong, quay lai may WINDOWS de verify:" -ForegroundColor Cyan
Write-Host "  .\scripts\verify-full-flow.ps1" -ForegroundColor Gray
