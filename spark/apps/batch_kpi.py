"""
L1/L2 - Batch KPI: MinIO raw (Parquet) -> PostgreSQL (fact cong duoc, do min 1 phut).

Che do (--mode):
    incremental  khoang [data_until_truoc - lookback, now - delay)  (mac dinh moi 5 phut)
    daily        tinh lai tron 1 ngay dia phuong (--date, mac dinh hom qua) -> bat event tre
    backfill     chay daily lan luot cho --from .. --to (ngay dia phuong)
    auto         incremental; neu da qua --daily-at ma chua co daily cho hom qua -> chay daily

Moi lan tinh 1 khoang [rs, re) (UTC, canh phut):
    1. Doc raw partition ingest phu hop, loc event_ts trong [rs, re), dedup theo event_id.
    2. Lay "snapshot cuoi phut" (state, bo dem, design speed) cua phut truoc rs tu machine_kpi_1m
       -> diem bat dau (middleware chi gui khi gia tri DOI nen can biet trang thai dau khoang).
    3. Tinh:
       - khoang trang thai MachineState -> giay/trang thai/phut + machine_state_interval
       - delta bo dem Total/Good/DefectCounter (xu ly reset) -> san luong/phut, ideal_time_sec
       - tong hop tag so/phut (n, sum, min, max, last)
       - chat luong du lieu/phut (received, invalid, duplicate, missing, late, bad quality)
    4. Ghi PG: staging (JDBC) -> 1 transaction DELETE [rs, re) + INSERT -> chay lai idempotent.
       Rollup machine_kpi_1h cho cac gio bi anh huong. Ghi nhat ky batch_run.
"""
from __future__ import annotations

import argparse
import json
import os
import traceback
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from pyspark.sql import DataFrame, SparkSession, Window, functions as F
from pyspark.sql.utils import AnalysisException

STATE_COLS = {0: "off_sec", 1: "starting_sec", 2: "run_sec", 3: "stopped_sec", 4: "faulted_sec", 5: "maint_sec"}
NO_DATA = -1   # trang thai gia: may im lang qua --max-silence-sec (mat ket noi / pipeline dung)
STATE_NAMES = {-1: "NO_DATA", 0: "OFF", 1: "STARTING", 2: "RUNNING", 3: "STOPPED", 4: "FAULTED", 5: "MAINTENANCE"}
STOP_STATES = [3, 4]
COUNTERS = {"TotalCounter": "total", "GoodCounter": "good", "DefectCounter": "defect"}

KPI_COLS = ["machine_id", "ts_minute", "line_id", "product_id", "shift_id", "shift_date",
            "run_sec", "starting_sec", "stopped_sec", "faulted_sec", "maint_sec", "off_sec", "nodata_sec",
            "stop_events", "total_count", "good_count", "defect_count", "ideal_time_sec", "counter_reset",
            "design_speed", "state_end", "state_since", "total_end", "good_end", "defect_end"]
INTERVAL_COLS = ["machine_id", "start_ts", "end_ts", "state", "state_name", "duration_sec", "is_open",
                 "line_id", "shift_id", "shift_date"]
TAG_COLS = ["machine_id", "tag_name", "ts_minute", "n", "sum", "min", "max", "last"]
DQ_COLS = ["machine_id", "ts_minute", "received", "invalid", "duplicate", "missing_value", "late",
           "bad_quality", "valid"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["incremental", "daily", "backfill", "auto"], default="auto")
    ap.add_argument("--date", help="daily: ngay dia phuong YYYY-MM-DD (mac dinh hom qua)")
    ap.add_argument("--from", dest="date_from", help="backfill: ngay dia phuong bat dau")
    ap.add_argument("--to", dest="date_to", help="backfill: ngay dia phuong ket thuc (bao gom)")
    ap.add_argument("--bucket", default=os.getenv("MINIO_BUCKET", "smart-factory"))
    ap.add_argument("--tz", default=os.getenv("PLANT_TZ", "Asia/Ho_Chi_Minh"))
    ap.add_argument("--lookback-min", type=int, default=30, help="tinh lai N phut truoc de nhan event tre")
    ap.add_argument("--delay-min", type=int, default=3, help="chi tinh toi now - N phut (cho raw-ingest ghi xong)")
    ap.add_argument("--first-run-min", type=int, default=60, help="lan incremental dau tien: tinh N phut gan nhat")
    ap.add_argument("--max-range-hours", type=int, default=6, help="incremental toi da N gio; xa hon -> dung daily/backfill")
    ap.add_argument("--max-silence-sec", type=int, default=120,
                    help="may khong co event nao qua N giay -> NO_DATA (khong keo dai trang thai cu)")
    ap.add_argument("--late-sec", type=int, default=30, help="event tre = kafka_ts - event_ts > N giay")
    ap.add_argument("--daily-at", default="00:30", help="auto: gio dia phuong bat dau duoc chay daily cho hom qua")
    ap.add_argument("--pg-url", default=os.getenv("PG_JDBC_URL", "jdbc:postgresql://postgres:5432/"
                                                                + os.getenv("POSTGRES_DB", "smart_factory")))
    ap.add_argument("--pg-user", default=os.getenv("POSTGRES_USER", "sf_user"))
    ap.add_argument("--pg-password", default=os.getenv("POSTGRES_PASSWORD", ""))
    return ap.parse_args()


def floor_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")


class Pg:
    """PostgreSQL qua JDBC (jar co san trong image) - doc bang Spark, ghi/DDL bang java.sql."""

    def __init__(self, spark: SparkSession, args: argparse.Namespace) -> None:
        self.spark, self.url = spark, args.pg_url
        self.props = {"user": args.pg_user, "password": args.pg_password, "driver": "org.postgresql.Driver"}

    def read(self, sql: str) -> DataFrame:
        return self.spark.read.jdbc(self.url, f"({sql}) q", properties=self.props)

    def _conn(self):
        jvm = self.spark.sparkContext._jvm
        p = jvm.java.util.Properties()
        p.setProperty("user", self.props["user"])
        p.setProperty("password", self.props["password"])
        return jvm.java.sql.DriverManager.getConnection(self.url, p)

    def execute(self, statements: list[str]) -> None:
        """Chay nhieu cau lenh trong MOT transaction."""
        c = self._conn()
        try:
            c.setAutoCommit(False)
            st = c.createStatement()
            for s in statements:
                st.execute(s)
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def scalar(self, sql: str):
        c = self._conn()
        try:
            rs = c.createStatement().executeQuery(sql)
            return rs.getString(1) if rs.next() else None
        finally:
            c.close()

    def stage(self, df: DataFrame, table: str) -> None:
        (df.write.mode("overwrite").option("truncate", "true").option("batchsize", 5000)
         .jdbc(self.url, table, properties=self.props))


# ============================================================================ doc du lieu
def read_parquet(spark: SparkSession, path: str, ingest_from: datetime, ingest_to: datetime) -> DataFrame | None:
    """Doc raw theo partition ingest_date/ingest_hour (UTC) trong [ingest_from, ingest_to]."""
    lo = ingest_from.astimezone(timezone.utc).strftime("%Y-%m-%d %H")
    hi = ingest_to.astimezone(timezone.utc).strftime("%Y-%m-%d %H")
    try:
        df = spark.read.option("basePath", path).parquet(path)
    except AnalysisException:
        return None   # chua co du lieu raw
    key = F.concat_ws(" ", F.col("ingest_date"), F.col("ingest_hour"))
    return df.filter((key >= lo) & (key <= hi))


def load_master(pg: Pg, tz: str):
    machines = pg.read("SELECT m.machine_id, m.line AS line_id, l.product_id, m.ideal_speed "
                       "FROM machine m LEFT JOIN line l ON l.line_id = m.line")
    shifts = pg.read("SELECT shift_id, start_time::text AS st, end_time::text AS et FROM shift").collect()

    def shift_cols(ts_col: str) -> tuple:
        local = F.from_utc_timestamp(F.col(ts_col), tz)
        sec = F.hour(local) * 3600 + F.minute(local) * 60 + F.second(local)
        sid, sdate = None, None
        for s in shifts:
            st = sum(int(x) * m for x, m in zip(s.st.split(":")[:3], (3600, 60, 1)))
            et = sum(int(x) * m for x, m in zip(s.et.split(":")[:3], (3600, 60, 1)))
            if st < et:
                cond, d = (sec >= st) & (sec < et), F.to_date(local)
            else:   # ca qua dem: phan sau 0h thuoc ngay bat dau ca
                cond = (sec >= st) | (sec < et)
                d = F.when(sec < et, F.date_sub(F.to_date(local), 1)).otherwise(F.to_date(local))
            sid = F.when(cond, F.lit(s.shift_id)) if sid is None else sid.when(cond, F.lit(s.shift_id))
            sdate = F.when(cond, d) if sdate is None else sdate.when(cond, d)
        if sid is None:
            return F.lit(None).cast("string"), F.lit(None).cast("date")
        return sid, sdate

    return machines, shift_cols


# ============================================================================ tinh toan
def compute(spark: SparkSession, pg: Pg, args: argparse.Namespace, rs: datetime, re: datetime,
            ingest_to: datetime) -> dict:
    base = f"s3a://{args.bucket}/raw"
    machines, shift_cols = load_master(pg, args.tz)
    machines = machines.cache()
    rs_l, re_l = F.lit(rs).cast("timestamp"), F.lit(re).cast("timestamp")

    raw = read_parquet(spark, f"{base}/telemetry", rs - timedelta(minutes=10), ingest_to)
    if raw is None:
        raise RuntimeError(f"chua co raw tai {base}/telemetry - raw-ingest da chay chua?")
    # chi lay cot can thiet (bo raw_json - chiem phan lon dung luong) truoc khi cache
    ev = (raw.select("event_id", "event_ts", "machine_id", "tag_name", "value_num", "value_bool", "value_str",
                     "is_good", "kafka_ts")
          .filter((F.col("event_ts") >= rs_l) & (F.col("event_ts") < re_l)).cache())
    d = ev.dropDuplicates(["event_id"]).withColumn("ts_minute", F.date_trunc("minute", "event_ts")).cache()

    # ---- diem bat dau: snapshot cuoi phut gan nhat truoc rs (trong 1 ngay)
    carry = pg.read(
        "SELECT DISTINCT ON (machine_id) machine_id, state_end, state_since, total_end, good_end, "
        "defect_end, design_speed FROM machine_kpi_1m "
        f"WHERE ts_minute < '{iso(rs)}' AND ts_minute >= '{iso(rs - timedelta(days=1))}' "
        "AND state_end IS NOT NULL ORDER BY machine_id, ts_minute DESC").cache()

    grid = (machines.select("machine_id", "line_id", "product_id", "ideal_speed")
            .crossJoin(spark.range(1).select(F.explode(F.sequence(
                rs_l, re_l - F.expr("INTERVAL 1 MINUTE"), F.expr("INTERVAL 1 MINUTE"))).alias("ts_minute"))))

    # ------------------------------------------------------------------ trang thai
    s_ev = (d.filter((F.col("tag_name") == "MachineState") & F.col("value_num").isNotNull())
            .select("machine_id", F.col("event_ts").alias("ts"), F.col("value_num").cast("int").alias("state"),
                    F.lit(None).cast("timestamp").alias("since"), F.lit(False).alias("is_carry")))
    s_carry = carry.filter(F.col("state_end").isNotNull()).select(
        "machine_id", rs_l.alias("ts"), F.col("state_end").cast("int").alias("state"),
        F.col("state_since").alias("since"), F.lit(True).alias("is_carry"))
    # NO_DATA: khoang im lang > max-silence (moi tag) -> chen su kien gia state=-1 tai (event cuoi + silence)
    silence = args.max_silence_sec
    alive = (d.select("machine_id", F.col("event_ts").alias("ts"))
             .unionByName(carry.select("machine_id", rs_l.alias("ts"))))
    wa = Window.partitionBy("machine_id").orderBy("ts")
    gaps = (alive.withColumn("nxt", F.coalesce(F.lead("ts").over(wa), re_l))
            .filter((F.unix_micros("nxt") - F.unix_micros("ts")) > silence * 1_000_000)
            .select("machine_id", (F.col("ts") + F.expr(f"INTERVAL {silence} SECONDS")).alias("ts"),
                    F.lit(NO_DATA).alias("state"), F.lit(None).cast("timestamp").alias("since"),
                    F.lit(False).alias("is_carry")))
    w = Window.partitionBy("machine_id").orderBy(F.col("ts"), F.col("is_carry").desc())
    seg = (s_ev.unionByName(s_carry).unionByName(gaps)
           .withColumn("chg", F.when(F.lag("state").over(w).isNull()
                                     | (F.lag("state").over(w) != F.col("state")), 1).otherwise(0))
           .withColumn("grp", F.sum("chg").over(w.rowsBetween(Window.unboundedPreceding, 0)))
           .withColumn("next_ts", F.coalesce(F.lead("ts").over(w), re_l)))
    intervals = (seg.groupBy("machine_id", "grp").agg(
        F.min("ts").alias("seg_start"), F.max("next_ts").alias("end_ts"),
        F.first("state").alias("state"), F.max("is_carry").alias("from_carry"),
        F.first("since", ignorenulls=True).alias("since"))
        .withColumn("start_ts", F.when(F.col("from_carry"), F.coalesce("since", "seg_start"))
                    .otherwise(F.col("seg_start")))
        .filter(F.col("end_ts") > F.col("seg_start"))
        .cache())

    # giay theo trang thai / phut
    per_min = (intervals
               .withColumn("ts_minute", F.explode(F.sequence(
                   F.date_trunc("minute", "seg_start"),
                   F.date_trunc("minute", F.col("end_ts") - F.expr("INTERVAL 1 MILLISECOND")),
                   F.expr("INTERVAL 1 MINUTE"))))
               .withColumn("m_end", F.col("ts_minute") + F.expr("INTERVAL 1 MINUTE"))
               .withColumn("sec", (F.unix_micros(F.least("end_ts", "m_end"))
                                   - F.unix_micros(F.greatest("seg_start", "ts_minute"))) / 1e6))
    state_sec = per_min.groupBy("machine_id", "ts_minute").pivot("state", list(STATE_COLS)).agg(F.sum("sec"))
    for k, c in STATE_COLS.items():
        state_sec = state_sec.withColumnRenamed(str(k), c)
    state_end = per_min.groupBy("machine_id", "ts_minute").agg(
        F.max_by("state", "end_ts").alias("state_end"), F.max_by("start_ts", "end_ts").alias("state_since"))
    stop_ev = (intervals.filter(~F.col("from_carry") & F.col("state").isin(STOP_STATES))
               .groupBy("machine_id", F.date_trunc("minute", "seg_start").alias("ts_minute"))
               .agg(F.count("*").cast("int").alias("stop_events")))

    # ------------------------------------------------------------------ bo dem
    c_ev = (d.filter(F.col("tag_name").isin(list(COUNTERS)) & F.col("value_num").isNotNull())
            .select("machine_id", "tag_name", F.col("event_ts").alias("ts"), F.col("value_num").alias("v"),
                    F.lit(False).alias("is_carry")))
    c_carry = None
    for tag, short in COUNTERS.items():
        part = carry.filter(F.col(f"{short}_end").isNotNull()).select(
            "machine_id", F.lit(tag).alias("tag_name"), (rs_l - F.expr("INTERVAL 1 SECOND")).alias("ts"),
            F.col(f"{short}_end").alias("v"), F.lit(True).alias("is_carry"))
        c_carry = part if c_carry is None else c_carry.unionByName(part)
    wc = Window.partitionBy("machine_id", "tag_name").orderBy("ts")
    prev = F.lag("v").over(wc)
    deltas = (c_ev.unionByName(c_carry)
              .withColumn("delta", F.when(prev.isNull(), 0.0)
                          .when(F.col("v") >= prev, F.col("v") - prev).otherwise(F.col("v")))
              .withColumn("reset", prev.isNotNull() & (F.col("v") < prev))
              .filter(~F.col("is_carry"))
              .withColumn("ts_minute", F.date_trunc("minute", "ts")))
    cnt = deltas.groupBy("machine_id", "ts_minute").agg(
        *[F.sum(F.when(F.col("tag_name") == t, F.col("delta"))).alias(f"{s}_d") for t, s in COUNTERS.items()],
        *[F.max_by(F.when(F.col("tag_name") == t, F.col("v")),
                   F.when(F.col("tag_name") == t, F.col("ts"))).alias(f"{s}_last") for t, s in COUNTERS.items()],
        F.max(F.col("reset").cast("int")).cast("boolean").alias("counter_reset"))
    # may khong co GoodCounter (vd CODER) -> good = total - defect
    has_good = (d.filter(F.col("tag_name") == "GoodCounter").select("machine_id")
                .unionByName(carry.filter(F.col("good_end").isNotNull()).select("machine_id"))
                .distinct().withColumn("has_good", F.lit(True)))

    # design speed (sp/phut): tag DesignSpeed -> carry -> machine.ideal_speed
    ds = (d.filter((F.col("tag_name") == "DesignSpeed") & F.col("value_num").isNotNull())
          .groupBy("machine_id", "ts_minute").agg(F.max_by("value_num", "event_ts").alias("ds_last")))

    # ------------------------------------------------------------------ ghep vao luoi phut + forward fill
    wf = Window.partitionBy("machine_id").orderBy("ts_minute").rowsBetween(Window.unboundedPreceding, 0)
    kpi = (grid.join(state_sec, ["machine_id", "ts_minute"], "left")
           .join(state_end, ["machine_id", "ts_minute"], "left")
           .join(stop_ev, ["machine_id", "ts_minute"], "left")
           .join(cnt, ["machine_id", "ts_minute"], "left")
           .join(ds, ["machine_id", "ts_minute"], "left")
           .join(carry.select("machine_id", F.col("total_end").alias("c_total"), F.col("good_end").alias("c_good"),
                              F.col("defect_end").alias("c_defect"), F.col("design_speed").alias("c_ds")),
                 "machine_id", "left")
           .join(has_good, "machine_id", "left"))
    for c in STATE_COLS.values():
        kpi = kpi.withColumn(c, F.coalesce(F.col(c), F.lit(0.0)))
    known = sum(F.col(c) for c in STATE_COLS.values())
    kpi = (kpi.withColumn("nodata_sec", F.greatest(F.lit(0.0), F.lit(60.0) - known))
           .withColumn("stop_events", F.coalesce("stop_events", F.lit(0)))
           .withColumn("counter_reset", F.coalesce("counter_reset", F.lit(False))))
    for s in COUNTERS.values():
        kpi = kpi.withColumn(f"{s}_end", F.coalesce(F.last(f"{s}_last", ignorenulls=True).over(wf), F.col(f"c_{s}")))
    kpi = kpi.withColumn("design_speed", F.coalesce(F.last("ds_last", ignorenulls=True).over(wf),
                                                    F.col("c_ds"), F.col("ideal_speed")))
    total = F.coalesce(F.col("total_d"), F.lit(0.0))
    defect = F.coalesce(F.col("defect_d"), F.lit(0.0))
    good = F.when(F.col("has_good"), F.coalesce(F.col("good_d"), F.lit(0.0))) \
            .otherwise(F.greatest(total - defect, F.lit(0.0)))
    sid, sdate = shift_cols("ts_minute")
    kpi = (kpi.withColumn("total_count", total.cast("long"))
           .withColumn("good_count", good.cast("long"))
           .withColumn("defect_count", defect.cast("long"))
           .withColumn("ideal_time_sec", F.when(F.col("design_speed") > 0, total * 60.0 / F.col("design_speed"))
                       .otherwise(F.lit(0.0)))
           .withColumn("shift_id", sid).withColumn("shift_date", sdate)
           .withColumn("state_end", F.col("state_end").cast("short"))
           .select(*KPI_COLS))

    # ------------------------------------------------------------------ khoang trang thai (bang downtime)
    state_name = F.create_map(*[x for k, n in STATE_NAMES.items() for x in (F.lit(k), F.lit(n))])
    isid, isdate = shift_cols("start_ts")
    intervals_out = (intervals.join(machines.select("machine_id", "line_id"), "machine_id", "left")
                     .withColumn("state_name", F.coalesce(state_name[F.col("state")], F.lit("UNKNOWN")))
                     .withColumn("duration_sec", (F.unix_micros("end_ts") - F.unix_micros("start_ts")) / 1e6)
                     .withColumn("is_open", F.col("end_ts") >= re_l)
                     .withColumn("state", F.col("state").cast("short"))
                     .withColumn("shift_id", isid).withColumn("shift_date", isdate)
                     .select(*INTERVAL_COLS))

    # ------------------------------------------------------------------ tag so / phut
    tags = (d.filter(F.col("value_num").isNotNull())
            .groupBy("machine_id", "tag_name", "ts_minute")
            .agg(F.count("*").cast("int").alias("n"), F.sum("value_num").alias("sum"),
                 F.min("value_num").alias("min"), F.max("value_num").alias("max"),
                 F.max_by("value_num", "event_ts").alias("last"))
            .select(*TAG_COLS))

    # ------------------------------------------------------------------ chat luong du lieu / phut
    recv = (ev.groupBy("machine_id", F.date_trunc("minute", "event_ts").alias("ts_minute"))
            .agg(F.count("*").alias("recv_valid"), F.countDistinct("event_id").alias("distinct_ev")))
    missing = F.col("value_num").isNull() & F.col("value_bool").isNull() & F.col("value_str").isNull()
    dq_d = d.groupBy("machine_id", "ts_minute").agg(
        F.sum(missing.cast("int")).alias("missing_value"),
        F.sum(((F.unix_micros("kafka_ts") - F.unix_micros("event_ts")) > args.late_sec * 1_000_000).cast("int"))
        .alias("late"),
        F.sum((F.col("is_good") == F.lit(False)).cast("int")).alias("bad_quality"))
    inv_raw = read_parquet(spark, f"{base}/_invalid", rs, re)
    if inv_raw is not None:
        inv = (inv_raw.filter((F.col("kafka_ts") >= rs_l) & (F.col("kafka_ts") < re_l))
               .groupBy(F.coalesce(F.col("machine_id"), F.lit("UNKNOWN")).alias("machine_id"),
                        F.date_trunc("minute", "kafka_ts").alias("ts_minute"))
               .agg(F.count("*").alias("invalid")))
    else:
        inv = spark.createDataFrame([], "machine_id string, ts_minute timestamp, invalid long")
    dq = (recv.join(dq_d, ["machine_id", "ts_minute"], "left").join(inv, ["machine_id", "ts_minute"], "full")
          .na.fill(0, ["recv_valid", "distinct_ev", "missing_value", "late", "bad_quality", "invalid"])
          .withColumn("received", F.col("recv_valid") + F.col("invalid"))
          .withColumn("duplicate", F.col("recv_valid") - F.col("distinct_ev"))
          .withColumn("valid", F.col("distinct_ev") - F.col("missing_value"))
          .select(*DQ_COLS))

    # ------------------------------------------------------------------ ghi PostgreSQL
    pg.execute([f"SELECT batch_ensure_partitions('{rs.astimezone(timezone.utc).date()}'::date, "
                f"'{(re - timedelta(microseconds=1)).astimezone(timezone.utc).date()}'::date)"]
               + [f"CREATE UNLOGGED TABLE IF NOT EXISTS stg_{t} (LIKE {t})"
                  for t in ("machine_kpi_1m", "machine_state_interval", "tag_metric_1m", "data_quality_1m")])
    pg.stage(kpi, "stg_machine_kpi_1m")
    pg.stage(intervals_out, "stg_machine_state_interval")
    pg.stage(tags, "stg_tag_metric_1m")
    pg.stage(dq, "stg_data_quality_1m")

    a, b = iso(rs), iso(re)
    h0 = iso(rs.replace(minute=0))
    h1 = iso((re - timedelta(microseconds=1)).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    ic = ", ".join(INTERVAL_COLS)
    pg.execute([
        f"DELETE FROM machine_kpi_1m WHERE ts_minute >= '{a}' AND ts_minute < '{b}'",
        f"INSERT INTO machine_kpi_1m ({', '.join(KPI_COLS)}) SELECT {', '.join(KPI_COLS)} FROM stg_machine_kpi_1m",
        f"DELETE FROM tag_metric_1m WHERE ts_minute >= '{a}' AND ts_minute < '{b}'",
        f"INSERT INTO tag_metric_1m ({', '.join(TAG_COLS)}) SELECT {', '.join(TAG_COLS)} FROM stg_tag_metric_1m",
        f"DELETE FROM data_quality_1m WHERE ts_minute >= '{a}' AND ts_minute < '{b}'",
        f"INSERT INTO data_quality_1m ({', '.join(DQ_COLS)}) SELECT {', '.join(DQ_COLS)} FROM stg_data_quality_1m",
        # khoang bat dau trong [rs, re): thay the; khoang noi tiep tu truoc rs: upsert (keo dai neu dang mo)
        f"DELETE FROM machine_state_interval WHERE start_ts >= '{a}' AND start_ts < '{b}'",
        f"""INSERT INTO machine_state_interval AS t ({ic}) SELECT {ic} FROM stg_machine_state_interval
            ON CONFLICT (machine_id, start_ts) DO UPDATE SET
              end_ts = CASE WHEN EXCLUDED.is_open THEN GREATEST(t.end_ts, EXCLUDED.end_ts) ELSE EXCLUDED.end_ts END,
              is_open = CASE WHEN EXCLUDED.is_open AND t.end_ts > EXCLUDED.end_ts THEN t.is_open
                             ELSE EXCLUDED.is_open END,
              duration_sec = EXTRACT(EPOCH FROM (CASE WHEN EXCLUDED.is_open
                               THEN GREATEST(t.end_ts, EXCLUDED.end_ts) ELSE EXCLUDED.end_ts END) - t.start_ts),
              state = EXCLUDED.state, state_name = EXCLUDED.state_name""",
        # rollup gio cho cac gio bi anh huong
        f"DELETE FROM machine_kpi_1h WHERE ts_hour >= '{h0}' AND ts_hour < '{h1}'",
        f"""INSERT INTO machine_kpi_1h
            SELECT machine_id, date_trunc('hour', ts_minute), max(line_id), max(product_id), max(shift_id),
                   max(shift_date), count(*), sum(run_sec), sum(starting_sec), sum(stopped_sec), sum(faulted_sec),
                   sum(maint_sec), sum(off_sec), sum(nodata_sec), sum(stop_events), sum(total_count),
                   sum(good_count), sum(defect_count), sum(ideal_time_sec)
            FROM machine_kpi_1m WHERE ts_minute >= '{h0}' AND ts_minute < '{h1}'
            GROUP BY machine_id, date_trunc('hour', ts_minute)""",
        # staging chi dung trong lan chay -> don sach (khong giu ban sao du lieu)
        "TRUNCATE stg_machine_kpi_1m, stg_machine_state_interval, stg_tag_metric_1m, stg_data_quality_1m",
    ])
    stats = {"events": ev.count(), "deduped": d.count(), "kpiRows": kpi.count(),
             "intervals": intervals_out.count(), "tagRows": tags.count()}
    for x in (ev, d, intervals, carry, machines):
        x.unpersist()
    return stats


# ============================================================================ dieu phoi
def run_range(spark, pg, args, job: str, rs: datetime, re: datetime, ingest_to: datetime) -> None:
    run_id = pg.scalar(f"INSERT INTO batch_run (job, range_start, range_end, status) "
                       f"VALUES ('{job}', '{iso(rs)}', '{iso(re)}', 'RUNNING') RETURNING run_id")
    t0 = datetime.now(timezone.utc)
    try:
        stats = compute(spark, pg, args, rs, re, ingest_to)
        stats["seconds"] = round((datetime.now(timezone.utc) - t0).total_seconds(), 1)
        pg.execute([f"UPDATE batch_run SET status='SUCCESS', finished_at=now(), "
                    f"stats='{json.dumps(stats)}'::jsonb WHERE run_id={run_id}"])
        print(json.dumps({"job": job, "range": [iso(rs), iso(re)], **stats}), flush=True)
    except Exception as exc:
        err = (str(exc)[:2000]).replace("'", "''")
        pg.execute([f"UPDATE batch_run SET status='FAILED', finished_at=now(), error='{err}' WHERE run_id={run_id}"])
        traceback.print_exc()
        raise


def local_day_range(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    rs = datetime.combine(day, time(0), tzinfo=tz).astimezone(timezone.utc)
    re = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz).astimezone(timezone.utc)
    return rs, re


def run_incremental(spark, pg, args) -> None:
    now = datetime.now(timezone.utc)
    re = floor_minute(now - timedelta(minutes=args.delay_min))
    prev = pg.scalar("SELECT to_char(max(range_end) AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS') "
                     "FROM batch_run WHERE job='incremental' AND status='SUCCESS'")
    if prev:
        prev_dt = datetime.fromisoformat(prev).replace(tzinfo=timezone.utc)
        rs = min(prev_dt, re) - timedelta(minutes=args.lookback_min)
    else:
        rs = re - timedelta(minutes=args.first_run_min)
    if re - rs > timedelta(hours=args.max_range_hours):
        print(f"WARN: khoang {iso(rs)}..{iso(re)} qua dai, cat con {args.max_range_hours}h "
              f"(phan cu hon -> chay daily/backfill)", flush=True)
        rs = re - timedelta(hours=args.max_range_hours)
    run_range(spark, pg, args, "incremental", floor_minute(rs), re, now)


def run_daily(spark, pg, args, day: date, job: str = "daily") -> None:
    tz = ZoneInfo(args.tz)
    rs, re = local_day_range(day, tz)
    safe_end = floor_minute(datetime.now(timezone.utc) - timedelta(minutes=args.delay_min))
    if rs >= safe_end:
        print(f"bo qua {day}: chua toi ngay nay", flush=True)
        return
    run_range(spark, pg, args, job, rs, min(re, safe_end), re + timedelta(days=1))


def main() -> None:
    args = parse_args()
    spark = (SparkSession.builder.appName(f"batch-kpi-{args.mode}")
             .config("spark.sql.sources.partitionColumnTypeInference.enabled", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    pg = Pg(spark, args)
    tz = ZoneInfo(args.tz)
    today = datetime.now(tz).date()

    if args.mode == "incremental":
        run_incremental(spark, pg, args)
    elif args.mode == "daily":
        run_daily(spark, pg, args, date.fromisoformat(args.date) if args.date else today - timedelta(days=1))
    elif args.mode == "backfill":
        d0, d1 = date.fromisoformat(args.date_from), date.fromisoformat(args.date_to or args.date_from)
        while d0 <= d1:   # tuan tu: ngay sau dung snapshot cuoi ngay truoc
            run_daily(spark, pg, args, d0, job="backfill")
            d0 += timedelta(days=1)
    else:  # auto
        run_incremental(spark, pg, args)
        hh, mm = (int(x) for x in args.daily_at.split(":"))
        yesterday = today - timedelta(days=1)
        rs, re = local_day_range(yesterday, tz)
        done = pg.scalar(f"SELECT count(*) FROM batch_run WHERE job IN ('daily','backfill') AND status='SUCCESS' "
                         f"AND range_start='{iso(rs)}' AND range_end='{iso(re)}'")
        if datetime.now(tz).time() >= time(hh, mm) and done == "0":
            has_raw = pg.scalar(f"SELECT count(*) FROM machine_kpi_1m WHERE ts_minute >= '{iso(rs)}' "
                                f"AND ts_minute < '{iso(re)}'")
            if has_raw != "0":   # chi doi soat ngay da co du lieu
                run_daily(spark, pg, args, yesterday)
    spark.stop()


if __name__ == "__main__":
    main()
