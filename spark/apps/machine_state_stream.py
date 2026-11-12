"""
Luong realtime trang thai may: Kafka `industrial.telemetry` -> Kafka `machine-state` (compacted).

Input (contract IndustrialTelemetry.Middleware, schemaVersion 1.0):
    1 message = 1 tag doi gia tri, key = machineId, JSON long nhau
    {eventId, eventTime, source{...}, plant{...}, machine{...}, tag{...}, measurement{...}, quality{...}}

Xu ly:
    1. Parse theo schema, bo message hong (thieu machineId/tagName/eventTime) va event co
       eventTime o tuong lai qua --max-future-sec.
    2. Loc source.system (mac dinh nhan ca kepware + simulator; --source-systems de gioi han).
    3. groupBy(machineId, tagName) + max_by(record, eventTime), output mode UPDATE:
         - state = gia tri moi nhat cua tung tag (26 may x 404 tag -> 404 key, rat nho)
         - moi micro-batch chi phat ra cac tag vua co thay doi
         - event den muon (eventTime cu hon) KHONG ghi de gia tri moi: max_by van tra ban moi nhat
         - duplicate (cung eventId) cho ra cung ket qua -> idempotent, khong can dedup rieng
    4. Ghi Kafka `machine-state`, key = "machineId|tagName" -> topic compacted giu ban cuoi moi tag.

Khoi dong lai: offset Kafka + state nam trong checkpoint -> doc tiep tu cho da dung, khong mat event.
"""
from __future__ import annotations

import argparse
import json
import os

from pyspark.sql import SparkSession, functions as F, types as T

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
        # value co the la number | bool | string | null -> doc dang text, ep kieu theo valueType o duoi
        T.StructField("value", T.StringType()),
        T.StructField("valueType", T.StringType()),
        T.StructField("unit", T.StringType()),
    ])),
    T.StructField("quality", T.StructType([
        T.StructField("statusCode", T.StringType()),
        T.StructField("isGood", T.BooleanType()),
    ])),
])

MACHINE_STATE_NAMES = {0: "OFF", 1: "STARTING", 2: "RUNNING", 3: "STOPPED", 4: "FAULTED", 5: "MAINTENANCE"}
NUMERIC_TYPES = ["Int32", "Int64", "UInt16", "UInt32", "Float", "Double"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"))
    ap.add_argument("--input-topic", default="industrial.telemetry")
    ap.add_argument("--output-topic", default="machine-state")
    ap.add_argument("--starting-offsets", default="earliest",
                    help="chi dung khi CHUA co checkpoint; earliest de khong bo sot tag on dinh")
    ap.add_argument("--max-offsets-per-trigger", type=int, default=50000)
    ap.add_argument("--trigger", default="1 second")
    ap.add_argument("--source-systems", default="",
                    help="vd 'kepware' de bo du lieu gia lap; rong = nhan tat ca")
    ap.add_argument("--max-future-sec", type=int, default=300,
                    help="bo event co eventTime vuot qua now + N giay")
    ap.add_argument("--checkpoint-dir", default="/opt/spark-checkpoints/machine-state")
    ap.add_argument("--progress-interval", type=int, default=30)
    return ap.parse_args()


def build(spark: SparkSession, args: argparse.Namespace):
    raw = (spark.readStream.format("kafka")
           .option("kafka.bootstrap.servers", args.bootstrap)
           .option("subscribe", args.input_topic)
           .option("startingOffsets", args.starting_offsets)
           .option("maxOffsetsPerTrigger", args.max_offsets_per_trigger)
           .option("failOnDataLoss", "false")
           .load())

    e = (raw.select(F.from_json(F.col("value").cast("string"), TELEMETRY_SCHEMA).alias("e"),
                    F.col("timestamp").alias("kafkaTimestamp"))
         .select("e.*", "kafkaTimestamp")
         .withColumn("eventTs", F.to_timestamp("eventTime"))
         .filter(F.col("machine.machineId").isNotNull()
                 & F.col("tag.tagName").isNotNull()
                 & F.col("eventTs").isNotNull()
                 # chan eventTime o tuong lai (lech dong ho): neu khong, max_by se "khoa" tag do
                 # vi moi event that sau do deu bi coi la cu hon
                 & (F.col("eventTs") <= F.current_timestamp() + F.expr(f"INTERVAL {args.max_future_sec} SECONDS"))))
    if args.source_systems:
        e = e.filter(F.col("source.system").isin([s.strip() for s in args.source_systems.split(",")]))

    vt = F.col("measurement.valueType")
    v = F.col("measurement.value")
    state_name = F.create_map(*[x for k, n in MACHINE_STATE_NAMES.items() for x in (F.lit(k), F.lit(n))])

    rec = F.struct(
        F.col("eventId"),
        F.col("eventTime"),
        F.col("plant.plantId").alias("plantId"),
        F.col("plant.lineId").alias("lineId"),
        F.col("plant.processId").alias("processId"),
        F.col("machine.machineType").alias("machineType"),
        F.col("machine.equipmentCode").alias("equipmentCode"),
        F.col("tag.tagCode").alias("tagCode"),
        F.col("tag.tagType").alias("tagType"),
        # 3 cot typed: dung 1 trong 3 theo valueType, cot con lai null
        F.when(vt.isin(NUMERIC_TYPES), v.cast("double")).alias("valueNum"),
        F.when(vt == "Boolean", v.cast("boolean")).alias("valueBool"),
        F.when(vt == "String", v).alias("valueText"),
        vt.alias("valueType"),
        F.col("measurement.unit").alias("unit"),
        F.col("quality.statusCode").alias("statusCode"),
        F.col("quality.isGood").alias("isGood"),
        F.col("source.system").alias("sourceSystem"),
        F.col("source.serverTimestamp").alias("serverTimestamp"),
        F.col("kafkaTimestamp"),
    )

    latest = (e.groupBy(F.col("machine.machineId").alias("machineId"), F.col("tag.tagName").alias("tagName"))
              .agg(F.max_by(rec, F.col("eventTs")).alias("r"))
              .select("machineId", "tagName", "r.*"))

    out = (latest
           .withColumn("stateName", F.when(F.col("tagName") == "MachineState",
                                          state_name[F.col("valueNum").cast("int")]))
           .withColumn("emittedAt", F.date_format(F.current_timestamp(), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"))
           .withColumn("latencyMs", (F.unix_millis(F.current_timestamp())
                                     - F.unix_millis(F.col("kafkaTimestamp"))).cast("long"))
           .drop("kafkaTimestamp"))

    return (out.select(F.concat_ws("|", "machineId", "tagName").alias("key"),
                       F.to_json(F.struct("*")).alias("value"))
            .writeStream.format("kafka")
            .queryName("machine_state")
            .option("kafka.bootstrap.servers", args.bootstrap)
            .option("topic", args.output_topic)
            .option("checkpointLocation", args.checkpoint_dir)
            .outputMode("update")
            .trigger(processingTime=args.trigger)
            .start())


def main() -> None:
    args = parse_args()
    spark = SparkSession.builder.appName("machine-state-stream").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    q = build(spark, args)
    print(f"machine_state: {args.input_topic} -> {args.output_topic} (trigger {args.trigger})", flush=True)
    while not q.awaitTermination(args.progress_interval):
        p = q.lastProgress
        if p:
            sp = p["stateOperators"][0] if p.get("stateOperators") else {}
            print(json.dumps({
                "batch": p["batchId"], "inputRows": p["numInputRows"],
                "inputRowsPerSec": round(p.get("inputRowsPerSecond") or 0, 1),
                "processedRowsPerSec": round(p.get("processedRowsPerSecond") or 0, 1),
                "triggerMs": p["durationMs"].get("triggerExecution"),
                "stateRows": sp.get("numRowsTotal"), "updatedRows": sp.get("numRowsUpdated"),
            }), flush=True)


if __name__ == "__main__":
    main()
