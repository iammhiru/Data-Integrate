"""
Luong B - Realtime metrics: Kafka -> Spark Structured Streaming -> Kafka `realtime-metrics` + PostgreSQL.

3 streaming query chay song song trong cung mot app:

  status_5s      machine-telemetry, tumbling window 5s / may (trigger 5s)
                 -> Kafka realtime-metrics (metricType=machine.status.5s)
                 -> upsert machine_status_current (status, temperature, pressure, speed, energy)
  metric_1m      machine-telemetry, tumbling window 1 phut / may (trigger 30s)
                 -> Kafka realtime-metrics (metricType=machine.metric.1m)
                 -> upsert machine_metric_1m
  production_1m  production-events, tumbling window 1 phut / may (trigger 5s)
                 -> Kafka realtime-metrics (metricType=production.rate.1m)
                 -> upsert machine_status_current.production_rate

Xu ly chung: parse envelope -> bo event loi -> watermark theo event time
-> dropDuplicatesWithinWatermark(eventId) -> window aggregation (output mode update:
moi trigger phat lai gia tri moi nhat cua cac window dang mo).

Moi message realtime co emittedAt va maxIngestedAt -> do latency middleware -> UI.

Chay:
  spark-submit /opt/spark-apps/realtime_metrics.py                          # doc tu offset moi nhat
  spark-submit /opt/spark-apps/realtime_metrics.py --starting-offsets earliest
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime

from pyspark.sql import DataFrame, SparkSession, functions as F

TELEMETRY_FIELDS = {"temperature": "double", "pressure": "double", "speed": "double",
                    "energy": "double", "status": "string"}
PRODUCTION_FIELDS = {"productId": "string", "quantity": "long", "goodQuantity": "long",
                     "rejectQuantity": "long"}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))
    p.add_argument("--output-topic", default="realtime-metrics")
    p.add_argument("--starting-offsets", default="latest")
    p.add_argument("--watermark", default="30 seconds", help="do tre toi da chap nhan cho late event")
    p.add_argument("--status-trigger", default="5 seconds")
    p.add_argument("--metric-trigger", default="30 seconds")
    p.add_argument("--checkpoint-dir", default="/opt/spark-checkpoints/realtime")
    p.add_argument("--progress-interval", type=int, default=30,
                   help="giay; in throughput / thoi gian xu ly cua tung query (0 = tat)")
    p.add_argument("--jdbc-url", default=os.getenv("POSTGRES_JDBC_URL",
                                                   "jdbc:postgresql://postgres:5432/smart_factory"))
    p.add_argument("--db-user", default=os.getenv("POSTGRES_USER"))
    p.add_argument("--db-password", default=os.getenv("POSTGRES_PASSWORD"))
    return p.parse_args()


# ----------------------------------------------------------------------------- PostgreSQL
def sql_literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v) if v == v else "NULL"  # NaN -> NULL
    if isinstance(v, datetime):
        return f"'{v.isoformat()}+00'::timestamptz"  # session timezone = UTC
    return "'" + str(v).replace("'", "''") + "'"


class Postgres:
    """Ket qua aggregate nho (<= so may x so window) -> collect ve driver, upsert 1 cau SQL."""

    def __init__(self, spark: SparkSession, url: str, user: str, password: str):
        self.spark, self.url, self.user, self.password = spark, url, user, password

    def upsert(self, rows: list[dict], table: str, keys: list[str], update_cols: list[str],
               where: str | None = None):
        if not rows:
            return
        cols = list(rows[0].keys())
        values = ",\n".join("(" + ", ".join(sql_literal(r[c]) for c in cols) + ")" for r in rows)
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES {values} "
               f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {sets}"
               + (f" WHERE {where}" if where else ""))
        jvm = self.spark.sparkContext._jvm
        conn = jvm.java.sql.DriverManager.getConnection(self.url, self.user, self.password)
        try:
            conn.createStatement().executeUpdate(sql)
        finally:
            conn.close()


def latest_per_machine(rows: list[dict], ts_col: str) -> list[dict]:
    """Mot batch co the chua nhieu window cua cung mot may -> chi giu window moi nhat."""
    best = {}
    for r in rows:
        m = r["machine_id"]
        if m not in best or r[ts_col] > best[m][ts_col]:
            best[m] = r
    return list(best.values())


# ----------------------------------------------------------------------------- Streams
def read_events(spark, args, topic: str, fields: dict) -> DataFrame:
    v = F.col("value").cast("string")
    j = lambda path: F.get_json_object(v, path)  # noqa: E731
    df = (spark.readStream.format("kafka")
          .option("kafka.bootstrap.servers", args.bootstrap)
          .option("subscribe", topic)
          .option("startingOffsets", args.starting_offsets)
          .option("failOnDataLoss", "false")
          .load()
          .select(j("$.eventId").alias("eventId"),
                  j("$.machineId").alias("machineId"),
                  F.to_timestamp(j("$.timestamp")).alias("eventTime"),
                  F.to_timestamp(j("$.ingestedAt")).alias("ingestedAt"),
                  *[j(f"$.payload.{f}").cast(t).alias(f) for f, t in fields.items()]))
    return (df.filter(F.col("eventId").isNotNull() & F.col("machineId").isNotNull()
                      & F.col("eventTime").isNotNull())
              .withWatermark("eventTime", args.watermark)
              .dropDuplicatesWithinWatermark(["eventId"]))


def telemetry_agg(df: DataFrame, window: str) -> DataFrame:
    missing = F.lit(False)
    for f in TELEMETRY_FIELDS:
        missing = missing | F.col(f).isNull()
    return (df.groupBy(F.col("machineId"), F.window("eventTime", window))
              .agg(F.max_by("status", F.when(F.col("status").isNotNull(), F.col("eventTime")))
                     .alias("status"),
                   F.avg("temperature").alias("avgTemperature"),
                   F.max("temperature").alias("maxTemperature"),
                   F.avg("pressure").alias("avgPressure"),
                   F.avg("speed").alias("avgSpeed"),
                   F.sum("energy").alias("sumEnergy"),
                   F.count("*").alias("sampleCount"),
                   F.sum(missing.cast("long")).alias("missingCount"),
                   F.max("eventTime").alias("lastEventTime"),
                   F.max("ingestedAt").alias("maxIngestedAt"))
              .withColumn("windowStart", F.col("window.start"))
              .withColumn("windowEnd", F.col("window.end"))
              .drop("window"))


def production_agg(df: DataFrame) -> DataFrame:
    return (df.filter(F.col("quantity").isNotNull())
              .groupBy(F.col("machineId"), F.window("eventTime", "1 minute"))
              .agg(F.sum("quantity").alias("totalQty"),
                   F.sum("goodQuantity").alias("goodQty"),
                   F.sum("rejectQuantity").alias("rejectQty"),
                   F.max("eventTime").alias("lastEventTime"),
                   F.max("ingestedAt").alias("maxIngestedAt"))
              .withColumn("windowStart", F.col("window.start"))
              .withColumn("windowEnd", F.col("window.end"))
              .drop("window")
              # san pham / phut, tinh tren phan window da troi qua (window dang mo chua du 60s)
              .withColumn("productionRate", F.round(
                  F.col("totalQty") * 60.0 / F.greatest(
                      F.lit(1.0),
                      F.unix_timestamp("lastEventTime") - F.unix_timestamp("windowStart") + 1), 2)))


def to_kafka(df: DataFrame, metric_type: str, topic: str, bootstrap: str):
    (df.withColumn("metricType", F.lit(metric_type))
       .withColumn("emittedAt", F.current_timestamp())
       .withColumn("latencyMs", (F.col("emittedAt").cast("double")
                                 - F.col("maxIngestedAt").cast("double")) * 1000)
       .select(F.col("machineId").alias("key"),
               F.to_json(F.struct("*"),
                         {"timestampFormat": "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"}).alias("value"))
       .write.format("kafka")
       .option("kafka.bootstrap.servers", bootstrap)
       .option("topic", topic)
       .save())


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("realtime-metrics").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    pg = Postgres(spark, args.jdbc_url, args.db_user, args.db_password)

    telemetry = read_events(spark, args, "machine-telemetry", TELEMETRY_FIELDS)
    production = read_events(spark, args, "production-events", PRODUCTION_FIELDS)

    def sink_status(batch: DataFrame, batch_id: int):
        batch.persist()
        to_kafka(batch, "machine.status.5s", args.output_topic, args.bootstrap)
        rows = [dict(machine_id=r.machineId, status=r.status, temperature=r.avgTemperature,
                     pressure=r.avgPressure, speed=r.avgSpeed, energy=r.sumEnergy,
                     event_time=r.lastEventTime, updated_at=datetime.utcnow())
                for r in batch.collect()]
        rows = latest_per_machine(rows, "event_time")
        pg.upsert(rows, "machine_status_current", ["machine_id"],
                  ["status", "temperature", "pressure", "speed", "energy", "event_time", "updated_at"],
                  where="machine_status_current.event_time IS NULL "
                        "OR machine_status_current.event_time <= EXCLUDED.event_time")
        batch.unpersist()
        print(f"[status_5s] batch {batch_id}: {len(rows)} machines", flush=True)

    def sink_metric_1m(batch: DataFrame, batch_id: int):
        batch.persist()
        to_kafka(batch, "machine.metric.1m", args.output_topic, args.bootstrap)
        rows = [dict(machine_id=r.machineId, window_start=r.windowStart, window_end=r.windowEnd,
                     avg_temperature=r.avgTemperature, max_temperature=r.maxTemperature,
                     avg_pressure=r.avgPressure, avg_speed=r.avgSpeed, sum_energy=r.sumEnergy,
                     sample_count=r.sampleCount, missing_count=r.missingCount)
                for r in batch.collect()]
        pg.upsert(rows, "machine_metric_1m", ["machine_id", "window_start"],
                  [c for c in (rows[0] if rows else {}) if c not in ("machine_id", "window_start")])
        batch.unpersist()
        print(f"[metric_1m] batch {batch_id}: {len(rows)} windows", flush=True)

    def sink_production(batch: DataFrame, batch_id: int):
        batch.persist()
        to_kafka(batch, "production.rate.1m", args.output_topic, args.bootstrap)
        rows = [dict(machine_id=r.machineId, production_rate=r.productionRate,
                     window_start=r.windowStart)
                for r in batch.collect()]
        rows = [{"machine_id": r["machine_id"], "production_rate": r["production_rate"]}
                for r in latest_per_machine(rows, "window_start")]
        pg.upsert(rows, "machine_status_current", ["machine_id"], ["production_rate"])
        batch.unpersist()
        print(f"[production_1m] batch {batch_id}: {len(rows)} machines", flush=True)

    def start(df, name, sink, trigger):
        return (df.writeStream.queryName(name)
                  .outputMode("update")
                  .foreachBatch(sink)
                  .option("checkpointLocation", f"{args.checkpoint_dir}/{name}")
                  .trigger(processingTime=trigger)
                  .start())

    start(telemetry_agg(telemetry, "5 seconds"), "status_5s", sink_status, args.status_trigger)
    start(telemetry_agg(telemetry, "1 minute"), "metric_1m", sink_metric_1m, args.metric_trigger)
    start(production_agg(production), "production_1m", sink_production, args.status_trigger)
    log_progress(spark, args.progress_interval)


def log_progress(spark: SparkSession, interval: int):
    """In dinh ky tien do tung query: so event, throughput, thoi gian xu ly batch, so key trong state."""
    while True:
        if spark.streams.awaitAnyTermination(interval or None):
            return
        for q in spark.streams.active:
            p = q.lastProgress
            if not p:
                continue
            d = p.get("durationMs", {})
            state_rows = sum(op.get("numRowsTotal", 0) for op in p.get("stateOperators", []))
            print(json.dumps({
                "query": q.name, "batchId": p["batchId"], "inputRows": p["numInputRows"],
                "inputRowsPerSec": round(p.get("inputRowsPerSecond", 0) or 0, 1),
                "processedRowsPerSec": round(p.get("processedRowsPerSecond", 0) or 0, 1),
                "triggerMs": d.get("triggerExecution"), "addBatchMs": d.get("addBatch"),
                "walCommitMs": d.get("walCommit"), "commitOffsetsMs": d.get("commitOffsets"),
                "stateRows": state_rows}), flush=True)


if __name__ == "__main__":
    main()
