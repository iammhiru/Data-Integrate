"""
Luong A - Raw ingest: Kafka -> Spark Structured Streaming -> MinIO (Parquet).

- Doc 3 topic machine-telemetry / production-events / quality-events.
- Parse event envelope, validate cac truong bat buoc.
- Event hop le  -> s3a://<bucket>/raw/<type>/date=YYYY-MM-DD/hour=HH/*.parquet
- Event loi     -> s3a://<bucket>/invalid/date=YYYY-MM-DD/*.parquet
- Khong dedup o day: raw giu nguyen de co the tai xu ly (batch se dedup theo eventId).
- Mot streaming query + foreachBatch (moi micro-batch doc Kafka 1 lan, tach ra nhieu thu muc).
  Checkpoint luu offset Kafka; neu job loi giua batch, batch do duoc chay lai -> co the
  ghi trung (at-least-once). Batch job dedup theo eventId nen ket qua cuoi van dung.

Chay (trong container spark-master):
  spark-submit /opt/spark-apps/kafka_to_minio.py                 # chay lien tuc, trigger 1 phut
  spark-submit /opt/spark-apps/kafka_to_minio.py --available-now # xu ly het du lieu dang co roi dung
"""
import argparse
import os

from pyspark.sql import SparkSession, functions as F

TOPIC_TO_DIR = {
    "machine-telemetry": "machine_telemetry",
    "production-events": "production",
    "quality-events": "quality",
}
TOPIC_TO_EVENT_TYPE = {
    "machine-telemetry": "machine.telemetry",
    "production-events": "production.event",
    "quality-events": "quality.event",
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))
    p.add_argument("--bucket", default=os.getenv("MINIO_BUCKET", "smart-factory"))
    p.add_argument("--trigger", default="1 minute", help="processing-time trigger, vd '10 seconds'")
    p.add_argument("--available-now", action="store_true",
                   help="xu ly toan bo du lieu dang co trong Kafka roi dung (dung cho test/backfill)")
    p.add_argument("--starting-offsets", default="earliest")
    p.add_argument("--max-offsets-per-trigger", type=int, default=200_000)
    return p.parse_args()


def parse_envelope(raw_df):
    """Kafka value (JSON) -> cot envelope. payload duoc giu nguyen dang JSON string."""
    v = F.col("value").cast("string")
    j = lambda path: F.get_json_object(v, path)  # noqa: E731

    event_time = F.to_timestamp(j("$.timestamp"))
    return (
        raw_df.select(
            j("$.eventId").alias("eventId"),
            j("$.eventType").alias("eventType"),
            j("$.source").alias("source"),
            j("$.machineId").alias("machineId"),
            event_time.alias("eventTime"),
            F.to_timestamp(j("$.ingestedAt")).alias("ingestedAt"),
            j("$.schemaVersion").cast("int").alias("schemaVersion"),
            j("$.payload").alias("payload"),
            F.col("topic").alias("kafkaTopic"),
            F.col("partition").alias("kafkaPartition"),
            F.col("offset").alias("kafkaOffset"),
            F.col("timestamp").alias("kafkaTimestamp"),
            v.alias("rawValue"),
        )
        .withColumn("processedAt", F.current_timestamp())
    )


def with_validation(df):
    expected_type = F.create_map(*[F.lit(x) for kv in TOPIC_TO_EVENT_TYPE.items() for x in kv])
    reasons = F.concat_ws(",",
        F.when(F.col("eventId").isNull(), F.lit("missing_eventId")),
        F.when(F.col("machineId").isNull(), F.lit("missing_machineId")),
        F.when(F.col("eventTime").isNull(), F.lit("invalid_timestamp")),
        F.when(F.col("payload").isNull(), F.lit("missing_payload")),
        F.when(F.col("eventType") != expected_type[F.col("kafkaTopic")], F.lit("wrong_eventType")),
    )
    return df.withColumn("invalidReason", F.when(reasons != "", reasons))


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("raw-ingest-kafka-to-minio").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    base = f"s3a://{args.bucket}"

    source = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", args.bootstrap)
        .option("subscribe", ",".join(TOPIC_TO_DIR))
        .option("startingOffsets", args.starting_offsets)
        .option("maxOffsetsPerTrigger", args.max_offsets_per_trigger)
        .option("failOnDataLoss", "false")
        .load()
    )
    events = with_validation(parse_envelope(source))

    valid_cond = F.col("invalidReason").isNull()
    partition_cols = (F.date_format("eventTime", "yyyy-MM-dd").alias("date"),
                      F.date_format("eventTime", "HH").alias("hour"))

    def write_batch(batch_df, batch_id):
        """Mot micro-batch: tach theo topic, ghi Parquet append vao tung thu muc raw."""
        batch_df.persist()
        counts = {}
        valid = batch_df.filter(valid_cond).drop("invalidReason", "rawValue").select("*", *partition_cols)
        for topic, dirname in TOPIC_TO_DIR.items():
            part = valid.filter(F.col("kafkaTopic") == topic)
            counts[dirname] = part.count()
            if counts[dirname]:
                part.write.mode("append").partitionBy("date", "hour").parquet(f"{base}/raw/{dirname}")
        invalid = (batch_df.filter(~valid_cond)
                   .withColumn("date", F.date_format(F.coalesce("eventTime", "kafkaTimestamp"), "yyyy-MM-dd")))
        counts["invalid"] = invalid.count()
        if counts["invalid"]:
            invalid.write.mode("append").partitionBy("date").parquet(f"{base}/invalid")
        batch_df.unpersist()
        print(f"batch {batch_id}: {counts}", flush=True)

    w = (events.writeStream.queryName("raw_ingest")
         .foreachBatch(write_batch)
         .option("checkpointLocation", f"{base}/checkpoints/raw-ingest"))
    w = w.trigger(availableNow=True) if args.available_now else w.trigger(processingTime=args.trigger)
    w.start().awaitTermination()
    spark.stop()


if __name__ == "__main__":
    main()
