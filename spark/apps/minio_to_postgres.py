"""
Luong C - Batch analytics: MinIO (raw Parquet) -> Spark Batch -> PostgreSQL.

Tinh va upsert:
  - production_metric   (machine, product, shift, date, hour)
  - quality_metric      (machine, product, shift, date, hour, defect_type)
  - data_quality_metric (event_type, date, hour)

Ghi PostgreSQL theo kieu staging table + INSERT ... ON CONFLICT DO UPDATE
-> chay lai job nhieu lan khong sinh trung du lieu (idempotent).

Chay (trong container spark-master):
  spark-submit /opt/spark-apps/minio_to_postgres.py                    # toan bo du lieu raw
  spark-submit /opt/spark-apps/minio_to_postgres.py --date 2026-11-11  # mot ngay
  spark-submit /opt/spark-apps/minio_to_postgres.py --date 2026-11-11 --hour 8
"""
from __future__ import annotations

import argparse
import os

from pyspark.sql import DataFrame, SparkSession, functions as F, Window
from pyspark.sql.utils import AnalysisException

RAW_DIRS = {
    "machine.telemetry": "machine_telemetry",
    "production.event": "production",
    "quality.event": "quality",
}
TOPIC_TO_EVENT_TYPE = {
    "machine-telemetry": "machine.telemetry",
    "production-events": "production.event",
    "quality-events": "quality.event",
}
# Truong bat buoc trong payload cua tung loai event -> thieu = missing-field event
REQUIRED_PAYLOAD_FIELDS = {
    "machine.telemetry": ["temperature", "pressure", "speed", "energy", "status"],
    "production.event": ["productId", "quantity", "goodQuantity", "rejectQuantity", "shift"],
    "quality.event": ["productId", "result", "quantity", "rejectQuantity"],
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=os.getenv("MINIO_BUCKET", "smart-factory"))
    p.add_argument("--date", help="YYYY-MM-DD; bo trong = xu ly tat ca")
    p.add_argument("--hour", type=int, help="0-23; chi dung kem --date")
    p.add_argument("--late-threshold-sec", type=int, default=30,
                   help="ingestedAt - eventTime > nguong nay (giay) = late event")
    p.add_argument("--jdbc-url", default=os.getenv("POSTGRES_JDBC_URL",
                                                   "jdbc:postgresql://postgres:5432/smart_factory"))
    p.add_argument("--db-user", default=os.getenv("POSTGRES_USER"))
    p.add_argument("--db-password", default=os.getenv("POSTGRES_PASSWORD"))
    return p.parse_args()


class Postgres:
    def __init__(self, spark: SparkSession, url: str, user: str, password: str):
        self.spark, self.url = spark, url
        self.props = {"user": user, "password": password, "driver": "org.postgresql.Driver"}

    def query(self, sql: str) -> DataFrame:
        return (self.spark.read.format("jdbc").option("url", self.url).option("query", sql)
                .options(**self.props).load())

    def execute(self, sql: str):
        jvm = self.spark.sparkContext._jvm
        conn = jvm.java.sql.DriverManager.getConnection(self.url, self.props["user"], self.props["password"])
        try:
            conn.createStatement().execute(sql)
        finally:
            conn.close()

    def upsert(self, df: DataFrame, table: str, keys: list):
        cols = df.columns
        stg = f"stg_{table}"
        df.write.jdbc(self.url, stg, mode="overwrite", properties=self.props)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in keys)
        col_list = ", ".join(cols)
        self.execute(
            f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {stg} "
            f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}, updated_at = now(); "
            f"DROP TABLE {stg};"
        )
        print(f"upsert {table}: {df.count()} rows")


def read_parquet(spark, path, args) -> DataFrame | None:
    try:
        df = spark.read.parquet(path)
    except AnalysisException as e:
        if "PATH_NOT_FOUND" in str(e) or "Path does not exist" in str(e):
            print(f"skip: {path} chua co du lieu")
            return None
        raise
    if args.date:
        df = df.filter(F.col("date").cast("string") == args.date)
        if args.hour is not None and "hour" in df.columns:
            df = df.filter(F.col("hour").cast("int") == args.hour)
    return df


def payload_field(name, dtype="string"):
    return F.get_json_object("payload", f"$.{name}").cast(dtype)


def dedup(df: DataFrame) -> DataFrame:
    """Giu ban ghi den Kafka som nhat cho moi eventId."""
    w = Window.partitionBy("eventId").orderBy("kafkaTimestamp", "kafkaOffset")
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


def shift_expr(shifts: DataFrame):
    """Map gio cua event time -> shift_id theo bang master shift (ho tro ca qua dem)."""
    h = F.hour("eventTime")
    expr = None
    for r in shifts.collect():
        s, e = r.start_hour, r.end_hour
        cond = (h >= s) & (h < e) if s < e else (h >= s) | (h < e)
        expr = F.when(cond, F.lit(r.shift_id)) if expr is None else expr.when(cond, F.lit(r.shift_id))
    return expr.otherwise(F.lit("UNKNOWN"))


def time_cols(df):
    return (df.withColumn("date", F.to_date("eventTime"))
              .withColumn("hour", F.hour("eventTime")))


def production_metric(raw: DataFrame) -> DataFrame:
    df = time_cols(dedup(raw)).select(
        "machineId", "date", "hour",
        payload_field("productId").alias("product_id"),
        payload_field("shift").alias("shift_id"),
        payload_field("quantity", "long").alias("qty"),
        payload_field("goodQuantity", "long").alias("good"),
        payload_field("rejectQuantity", "long").alias("reject"),
    ).filter(F.col("product_id").isNotNull() & F.col("qty").isNotNull())
    return (df.groupBy(F.col("machineId").alias("machine_id"), "product_id",
                       F.coalesce("shift_id", F.lit("UNKNOWN")).alias("shift_id"), "date", "hour")
              .agg(F.sum("qty").alias("total_qty"),
                   F.sum("good").alias("good_qty"),
                   F.sum("reject").alias("reject_qty"))
              .withColumn("reject_rate",
                          F.when(F.col("total_qty") > 0, F.col("reject_qty") / F.col("total_qty") * 100))
              .withColumn("production_rate", F.col("total_qty") / F.lit(60.0)))  # san pham / phut


def quality_metric(raw: DataFrame, shift_of) -> DataFrame:
    df = time_cols(dedup(raw)).select(
        "machineId", "date", "hour", shift_of.alias("shift_id"),
        payload_field("productId").alias("product_id"),
        F.coalesce(payload_field("defectType"), F.lit("NONE")).alias("defect_type"),
        payload_field("quantity", "long").alias("qty"),
        payload_field("rejectQuantity", "long").alias("reject"),
    ).filter(F.col("product_id").isNotNull() & F.col("qty").isNotNull())
    return (df.groupBy(F.col("machineId").alias("machine_id"), "product_id", "shift_id",
                       "date", "hour", "defect_type")
              .agg(F.sum("qty").alias("inspected_qty"), F.sum("reject").alias("reject_qty"))
              .withColumn("defect_rate",
                          F.when(F.col("inspected_qty") > 0,
                                 F.col("reject_qty") / F.col("inspected_qty") * 100)))


def data_quality_metric(raws: dict, invalid: DataFrame | None, late_sec: int) -> DataFrame | None:
    parts = []
    for event_type, raw in raws.items():
        missing = F.lit(False)
        for f in REQUIRED_PAYLOAD_FIELDS[event_type]:
            missing = missing | payload_field(f).isNull()
        w = Window.partitionBy("eventId").orderBy("kafkaTimestamp", "kafkaOffset")
        parts.append(
            time_cols(raw)
            .withColumn("is_dup", F.row_number().over(w) > 1)
            .withColumn("is_missing", missing)
            .withColumn("is_late",
                        F.unix_timestamp(F.coalesce("ingestedAt", "kafkaTimestamp"))
                        - F.unix_timestamp("eventTime") > late_sec)
            .select(F.lit(event_type).alias("event_type"), "date", "hour",
                    "is_dup", "is_missing", "is_late", F.lit(False).alias("is_invalid"))
        )
    if invalid is not None:
        mapping = F.create_map(*[F.lit(x) for kv in TOPIC_TO_EVENT_TYPE.items() for x in kv])
        ts = F.coalesce("eventTime", "kafkaTimestamp")
        parts.append(invalid.select(
            mapping[F.col("kafkaTopic")].alias("event_type"),
            F.to_date(ts).alias("date"), F.hour(ts).alias("hour"),
            F.lit(False).alias("is_dup"), F.lit(False).alias("is_missing"),
            F.lit(False).alias("is_late"), F.lit(True).alias("is_invalid")))
    if not parts:
        return None

    all_events = parts[0]
    for p in parts[1:]:
        all_events = all_events.unionByName(p)

    cnt = lambda c: F.sum(F.col(c).cast("long"))  # noqa: E731
    valid_cond = ~(F.col("is_dup") | F.col("is_missing") | F.col("is_invalid"))
    return (all_events.groupBy("event_type", "date", "hour")
            .agg(F.count("*").alias("total_events"),
                 F.sum(valid_cond.cast("long")).alias("valid_events"),
                 cnt("is_invalid").alias("invalid_events"),
                 cnt("is_dup").alias("duplicate_events"),
                 cnt("is_missing").alias("missing_field_events"),
                 cnt("is_late").alias("late_events"))
            .withColumn("data_quality_rate", F.col("valid_events") / F.col("total_events") * 100))


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("batch-minio-to-postgres").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    pg = Postgres(spark, args.jdbc_url, args.db_user, args.db_password)
    base = f"s3a://{args.bucket}"

    raws = {}
    for event_type, dirname in RAW_DIRS.items():
        df = read_parquet(spark, f"{base}/raw/{dirname}", args)
        if df is not None:
            raws[event_type] = df.cache()

    if "production.event" in raws:
        pg.upsert(production_metric(raws["production.event"]), "production_metric",
                  ["machine_id", "product_id", "shift_id", "date", "hour"])

    if "quality.event" in raws:
        shift_of = shift_expr(pg.query(
            "SELECT shift_id, extract(hour FROM start_time)::int AS start_hour, "
            "extract(hour FROM end_time)::int AS end_hour FROM shift"))
        pg.upsert(quality_metric(raws["quality.event"], shift_of), "quality_metric",
                  ["machine_id", "product_id", "shift_id", "date", "hour", "defect_type"])

    invalid = read_parquet(spark, f"{base}/invalid", args)
    if invalid is not None and args.hour is not None:
        invalid = invalid.filter(F.hour(F.coalesce("eventTime", "kafkaTimestamp")) == args.hour)
    dq = data_quality_metric(raws, invalid, args.late_threshold_sec)
    if dq is not None:
        pg.upsert(dq, "data_quality_metric", ["event_type", "date", "hour"])

    spark.stop()


if __name__ == "__main__":
    main()
