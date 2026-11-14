"""
L0 - Raw ingest: Kafka `industrial.telemetry` -> MinIO (Data Lake, Parquet).

    s3a://<bucket>/raw/telemetry/ingest_date=YYYY-MM-DD/ingest_hour=HH/part-*.parquet
    s3a://<bucket>/raw/_invalid/ingest_date=YYYY-MM-DD/ingest_hour=HH/part-*.parquet

Nguyen tac:
  * Partition theo INGEST time (timestamp Kafka, UTC) chu khong theo eventTime:
    chi append vao partition moi -> batch doc tang dan theo partition, event tre tu nam o partition moi.
  * KHONG dedup / KHONG tong hop: raw giu nguyen ban de tai xu ly. Giu ca `raw_json` goc.
  * Message hong (JSON loi, thieu machineId/tagName/eventTime, eventTime o tuong lai) -> `_invalid`
    kem `invalid_reason`, de batch dem duoc Invalid / Missing cho Data Quality.
  * At-least-once (foreachBatch co the ghi lai khi retry) -> batch dedup theo eventId.
"""
from __future__ import annotations

import argparse
import json
import os

from pyspark.sql import DataFrame, SparkSession, functions as F, types as T

TELEMETRY_SCHEMA = T.StructType([
    T.StructField("eventId", T.StringType()),
    T.StructField("eventType", T.StringType()),
    T.StructField("schemaVersion", T.StringType()),
    T.StructField("eventTime", T.StringType()),
    T.StructField("source", T.StructType([
        T.StructField("system", T.StringType()),
        T.StructField("channel", T.StringType()),
        T.StructField("device", T.StringType()),
        T.StructField("nodeId", T.StringType()),
        T.StructField("serverTimestamp", T.StringType()),
    ])),
    T.StructField("plant", T.StructType([
        T.StructField("plantId", T.StringType()),
        T.StructField("lineId", T.StringType()),
        T.StructField("processId", T.StringType()),
    ])),
    T.StructField("machine", T.StructType([
        T.StructField("machineId", T.StringType()),
        T.StructField("machineType", T.StringType()),
        T.StructField("equipmentCode", T.StringType()),
    ])),
    T.StructField("tag", T.StructType([
        T.StructField("tagName", T.StringType()),
        T.StructField("tagCode", T.StringType()),
        T.StructField("tagType", T.StringType()),
    ])),
    T.StructField("measurement", T.StructType([
        T.StructField("value", T.StringType()),     # number | bool | string | null -> ep kieu theo valueType
        T.StructField("valueType", T.StringType()),
        T.StructField("unit", T.StringType()),
    ])),
    T.StructField("quality", T.StructType([
        T.StructField("statusCode", T.StringType()),
        T.StructField("isGood", T.BooleanType()),
    ])),
])

NUMERIC_TYPES = ["Int16", "Int32", "Int64", "UInt16", "UInt32", "UInt64", "Float", "Double"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))
    ap.add_argument("--topic", default="industrial.telemetry")
    ap.add_argument("--bucket", default=os.getenv("MINIO_BUCKET", "smart-factory"))
    ap.add_argument("--starting-offsets", default="earliest", help="chi dung khi chua co checkpoint")
    ap.add_argument("--max-offsets-per-trigger", type=int, default=200000)
    ap.add_argument("--trigger", default="1 minute")
    ap.add_argument("--max-future-sec", type=int, default=300)
    ap.add_argument("--checkpoint-dir", default="/opt/spark-checkpoints/raw-ingest")
    return ap.parse_args()


def split(raw: DataFrame, max_future_sec: int) -> tuple[DataFrame, DataFrame]:
    j = F.col("raw_json")
    e = raw.withColumn("e", F.from_json(j, TELEMETRY_SCHEMA))
    event_ts = F.to_timestamp(F.col("e.eventTime"))
    reason = (F.when(F.col("e").isNull() | F.col("e.eventId").isNull(), F.lit("MALFORMED_OR_NO_EVENT_ID"))
              .when(F.col("e.machine.machineId").isNull(), F.lit("MISSING_MACHINE_ID"))
              .when(F.col("e.tag.tagName").isNull(), F.lit("MISSING_TAG_NAME"))
              .when(event_ts.isNull(), F.lit("MISSING_OR_BAD_EVENT_TIME"))
              .when(event_ts > F.col("kafka_ts") + F.expr(f"INTERVAL {max_future_sec} SECONDS"),
                    F.lit("EVENT_TIME_IN_FUTURE")))
    e = e.withColumn("invalid_reason", reason)

    vt = F.col("e.measurement.valueType")
    v = F.col("e.measurement.value")
    valid = (e.filter(F.col("invalid_reason").isNull()).select(
        F.col("e.eventId").alias("event_id"),
        F.col("e.eventType").alias("event_type"),
        F.col("e.schemaVersion").alias("schema_version"),
        event_ts.alias("event_ts"),
        F.col("e.machine.machineId").alias("machine_id"),
        F.col("e.machine.machineType").alias("machine_type"),
        F.col("e.machine.equipmentCode").alias("equipment_code"),
        F.col("e.plant.plantId").alias("plant_id"),
        F.col("e.plant.lineId").alias("line_id"),
        F.col("e.plant.processId").alias("process_id"),
        F.col("e.tag.tagName").alias("tag_name"),
        F.col("e.tag.tagCode").alias("tag_code"),
        F.col("e.tag.tagType").alias("tag_type"),
        vt.alias("value_type"),
        F.when(vt.isin(NUMERIC_TYPES), v.cast("double")).alias("value_num"),
        F.when(vt == "Boolean", v.cast("boolean")).alias("value_bool"),
        F.when(~vt.isin(NUMERIC_TYPES + ["Boolean"]), v).alias("value_str"),
        F.col("e.measurement.unit").alias("unit"),
        F.col("e.quality.statusCode").alias("status_code"),
        F.col("e.quality.isGood").alias("is_good"),
        F.col("e.source.system").alias("source_system"),
        F.col("e.source.nodeId").alias("node_id"),
        F.to_timestamp(F.col("e.source.serverTimestamp")).alias("server_ts"),
        "kafka_partition", "kafka_offset", "kafka_ts", "raw_json", "ingest_date", "ingest_hour",
    ))
    invalid = (e.filter(F.col("invalid_reason").isNotNull()).select(
        F.col("e.eventId").alias("event_id"),
        F.col("e.machine.machineId").alias("machine_id"),
        F.col("e.tag.tagName").alias("tag_name"),
        F.col("e.eventTime").alias("event_time_raw"),
        "invalid_reason", "kafka_partition", "kafka_offset", "kafka_ts", "raw_json",
        "ingest_date", "ingest_hour",
    ))
    return valid, invalid


def main() -> None:
    args = parse_args()
    spark = SparkSession.builder.appName("raw-ingest").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    base = f"s3a://{args.bucket}/raw"

    raw = (spark.readStream.format("kafka")
           .option("kafka.bootstrap.servers", args.bootstrap)
           .option("subscribe", args.topic)
           .option("startingOffsets", args.starting_offsets)
           .option("maxOffsetsPerTrigger", args.max_offsets_per_trigger)
           .option("failOnDataLoss", "false")
           .load()
           .select(F.col("value").cast("string").alias("raw_json"),
                   F.col("partition").alias("kafka_partition"),
                   F.col("offset").alias("kafka_offset"),
                   F.col("timestamp").alias("kafka_ts"))
           .withColumn("ingest_date", F.date_format("kafka_ts", "yyyy-MM-dd"))
           .withColumn("ingest_hour", F.date_format("kafka_ts", "HH")))

    def write_batch(df: DataFrame, batch_id: int) -> None:
        df = df.persist()
        valid, invalid = split(df, args.max_future_sec)
        # 1 file / partition gio / micro-batch -> tranh qua nhieu file nho
        (valid.repartition("ingest_date", "ingest_hour").write.mode("append")
         .partitionBy("ingest_date", "ingest_hour").parquet(f"{base}/telemetry"))
        n_invalid = invalid.count()
        if n_invalid:
            (invalid.coalesce(1).write.mode("append")
             .partitionBy("ingest_date", "ingest_hour").parquet(f"{base}/_invalid"))
        print(json.dumps({"batch": batch_id, "rows": df.count(), "invalid": n_invalid}), flush=True)
        df.unpersist()

    q = (raw.writeStream.queryName("raw_ingest")
         .foreachBatch(write_batch)
         .option("checkpointLocation", args.checkpoint_dir)
         .trigger(processingTime=args.trigger)
         .start())
    print(f"raw_ingest: {args.topic} -> {base}/telemetry (trigger {args.trigger})", flush=True)
    q.awaitTermination()


if __name__ == "__main__":
    main()
