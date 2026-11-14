# Apply schema BATCH (03_batch_schema.sql) vao PostgreSQL tren may server.
#
#   .\scripts\apply-batch-schema.ps1
#
# Script nay:
#   1. Doc postgres/init/03_batch_schema.sql
#   2. Chay qua psycopg (multi-statement, tuong thich psql -f)
#   3. Tao partition cho cac ngay gan nhat (batch_ensure_partitions)
#   4. In bang ket qua + so dong du lieu
#
# Idempotent: chay lai nhieu lan deu an toan (CREATE TABLE IF NOT EXISTS).
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$SqlFile = Join-Path $Root "postgres\init\03_batch_schema.sql"

if (-not (Test-Path $SqlFile)) { throw "khong tim thay $SqlFile" }

# DSN: lay tu .env goc repo, fallback theo may server mac dinh.
$EnvFile = Join-Path $Root ".env"
$dsn = $null
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match '^\s*MASTER_DB_URL\s*=\s*(.+)$') { $dsn = $Matches[1].Trim().Trim('"').Trim("'") }
    }
}
if (-not $dsn) { $dsn = "postgresql://sf_user:sf_password@192.168.179.176:5432/smart_factory" }

$env:SF_APPLY_SQL_FILE = $SqlFile
$env:SF_APPLY_DSN = $dsn

& $Py -c @"
import os, sys, datetime
import psycopg

sql = open(os.environ['SF_APPLY_SQL_FILE'], encoding='utf-8').read()
dsn = os.environ['SF_APPLY_DSN']

with psycopg.connect(dsn, autocommit=True) as c:
    with c.cursor() as cur:
        cur.execute(sql)
    print('OK: da chay 03_batch_schema.sql')

    # Partition cho 7 ngay gan nhat + 2 ngay truoc (de backfill co cho)
    today = datetime.date.today()
    frm = today - datetime.timedelta(days=2)
    to = today + datetime.timedelta(days=1)
    with c.cursor() as cur:
        cur.execute('SELECT batch_ensure_partitions(%s::date, %s::date)', (frm, to))
    print(f'OK: partition {frm} .. {to}')

    tables = ('machine_kpi_1m', 'machine_kpi_1h', 'machine_state_interval',
              'tag_metric_1m', 'data_quality_1m', 'batch_run')
    with c.cursor() as cur:
        for t in tables:
            cur.execute(f'SELECT count(*) FROM {t}')
            print(f'  {t:26} rows={cur.fetchone()[0]}')
        cur.execute('SELECT data_until, last_success_at FROM batch_freshness')
        print('  batch_freshness:', cur.fetchone())
"@
