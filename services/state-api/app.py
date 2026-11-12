"""
Machine State API - tra trang thai moi nhat cua tung may.

Nguon: Kafka topic `machine-state` (compacted, key = "machineId|tagName", do Spark job
spark/apps/machine_state_stream.py ghi). Khi khoi dong, consumer doc topic TU DAU
(assign + OFFSET_BEGINNING, khong dung offset cua consumer group) de dung lai toan bo
trang thai trong RAM, sau do tiep tuc nhan cap nhat moi.

Endpoints:
    GET /health                              trang thai consumer (da nap xong chua, so key, offset)
    GET /api/machines?lineId=&machineType=   danh sach may + trang thai tom tat
    GET /api/machines/{machineId}            toan bo tag moi nhat cua 1 may
    GET /api/machines/{machineId}/tags/{tagName}
    GET /api/lines                           tong hop so may theo line / trang thai
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError, TopicPartition, OFFSET_BEGINNING
from fastapi import FastAPI, HTTPException, Query

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("STATE_TOPIC", "machine-state")
STALE_AFTER_SEC = float(os.getenv("STALE_AFTER_SEC", "60"))
SUMMARY_TAGS = ["MachineState", "MachineMode", "AlarmCode", "EmergencyStop", "CurrentSpeed",
                "DesignSpeed", "TotalCounter", "GoodCounter", "DefectCounter", "Starved", "Blocked"]

log = logging.getLogger("state-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class StateStore:
    """machineId -> {"meta": {...}, "tags": {tagName: record}} ; thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._machines: dict[str, dict] = {}
        self.ready = False            # da doc toi high watermark luc khoi dong chua
        self.messages = 0
        self.ignored_older = 0
        self.last_message_at: float | None = None
        self.offsets: dict[int, int] = {}

    def apply(self, rec: dict) -> None:
        mid, tag = rec.get("machineId"), rec.get("tagName")
        if not mid or not tag:
            return
        value = next((rec.get(k) for k in ("valueNum", "valueBool", "valueText") if rec.get(k) is not None), None)
        if value is not None and rec.get("valueType") in ("Int32", "Int64", "UInt16", "UInt32"):
            value = int(value)
        entry = {
            "value": value, "valueType": rec.get("valueType"), "unit": rec.get("unit"),
            "statusCode": rec.get("statusCode"), "isGood": rec.get("isGood"),
            "tagCode": rec.get("tagCode"), "tagType": rec.get("tagType"),
            "eventTime": rec.get("eventTime"), "eventId": rec.get("eventId"),
            "emittedAt": rec.get("emittedAt"),
        }
        if rec.get("stateName"):
            entry["stateName"] = rec["stateName"]
        with self._lock:
            m = self._machines.setdefault(mid, {"meta": {}, "tags": {}})
            old = m["tags"].get(tag)
            # phong thu: bo ban cu hon (vd doc lai phan chua compact cua topic)
            if old and (old["eventTime"] or "") > (entry["eventTime"] or ""):
                self.ignored_older += 1
                return
            m["tags"][tag] = entry
            m["meta"] = {k: rec.get(k) for k in
                         ("machineId", "plantId", "lineId", "processId", "machineType", "equipmentCode",
                          "sourceSystem")}

    def machine_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._machines)

    def get(self, mid: str) -> dict | None:
        with self._lock:
            m = self._machines.get(mid)
            return None if m is None else {"meta": dict(m["meta"]), "tags": {k: dict(v) for k, v in m["tags"].items()}}

    def tag_count(self) -> int:
        with self._lock:
            return sum(len(m["tags"]) for m in self._machines.values())


store = StateStore()


def summarize(m: dict) -> dict:
    tags = m["tags"]
    now = datetime.now(timezone.utc)
    last_raw = max((x["eventTime"] for x in tags.values() if x.get("eventTime")), default=None)
    last = _ts(last_raw)
    st = tags.get("MachineState", {})
    return {
        **m["meta"],
        "state": st.get("stateName"),
        "stateSince": st.get("eventTime"),
        "summary": {k: tags[k]["value"] for k in SUMMARY_TAGS if k in tags},
        "tagCount": len(tags),
        "lastEventTime": last_raw,
        "ageSeconds": round((now - last).total_seconds(), 1) if last else None,
        "stale": last is None or (now - last).total_seconds() > STALE_AFTER_SEC,
    }


def consume_forever() -> None:
    conf = {"bootstrap.servers": BOOTSTRAP, "group.id": "state-api",  # group chi de dinh danh, khong commit
            "enable.auto.commit": False, "auto.offset.reset": "earliest"}
    while True:
        try:
            c = Consumer(conf)
            md = c.list_topics(TOPIC, timeout=10).topics.get(TOPIC)
            if md is None or md.error is not None or not md.partitions:
                raise RuntimeError(f"topic {TOPIC} chua san sang")
            parts = sorted(md.partitions)
            c.assign([TopicPartition(TOPIC, p, OFFSET_BEGINNING) for p in parts])
            # high watermark luc khoi dong -> doc toi day thi coi la da nap xong snapshot
            hw = {p: c.get_watermark_offsets(TopicPartition(TOPIC, p), timeout=10)[1] for p in parts}
            pending = {p for p, h in hw.items() if h > 0}
            log.info("assigned %s, high watermarks %s", parts, hw)
            if not pending:
                store.ready = True
            while True:
                msg = c.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        log.warning("kafka error: %s", msg.error())
                    continue
                if msg.value():
                    try:
                        store.apply(json.loads(msg.value()))
                    except (ValueError, TypeError) as exc:
                        log.warning("bo message hong offset=%s: %s", msg.offset(), exc)
                store.messages += 1
                store.last_message_at = time.time()
                store.offsets[msg.partition()] = msg.offset()
                if not store.ready:
                    if msg.offset() + 1 >= hw.get(msg.partition(), 0):
                        pending.discard(msg.partition())
                    if not pending:
                        store.ready = True
                        log.info("snapshot loaded: %d machines, %d tags, %d messages",
                                 len(store.machine_ids()), store.tag_count(), store.messages)
        except Exception as exc:  # noqa: BLE001 - mat ket noi Kafka -> thu lai
            log.error("consumer loi, thu lai sau 5s: %s", exc)
            time.sleep(5)


app = FastAPI(title="Machine State API", version="1.0")


@app.on_event("startup")
def _start() -> None:
    threading.Thread(target=consume_forever, name="kafka-consumer", daemon=True).start()


@app.get("/health")
def health():
    return {"status": "ok" if store.ready else "loading", "topic": TOPIC, "ready": store.ready,
            "machines": len(store.machine_ids()), "tags": store.tag_count(),
            "messagesConsumed": store.messages, "ignoredOlder": store.ignored_older,
            "lastMessageAgoSec": round(time.time() - store.last_message_at, 1) if store.last_message_at else None,
            "offsets": store.offsets}


@app.get("/api/machines")
def list_machines(lineId: str | None = Query(None), machineType: str | None = Query(None),
                  state: str | None = Query(None)):
    out = []
    for mid in store.machine_ids():
        s = summarize(store.get(mid))
        if (lineId and s.get("lineId") != lineId) or (machineType and s.get("machineType") != machineType) \
                or (state and s.get("state") != state.upper()):
            continue
        out.append(s)
    return {"count": len(out), "ready": store.ready, "machines": out}


@app.get("/api/machines/{machine_id}")
def get_machine(machine_id: str):
    m = store.get(machine_id)
    if m is None:
        raise HTTPException(404, f"khong co trang thai cho may '{machine_id}'"
                                 + ("" if store.ready else " (API dang nap snapshot, thu lai sau)"))
    return {**summarize(m), "tags": dict(sorted(m["tags"].items()))}


@app.get("/api/machines/{machine_id}/tags/{tag_name}")
def get_tag(machine_id: str, tag_name: str):
    m = store.get(machine_id)
    if m is None or tag_name not in m["tags"]:
        raise HTTPException(404, f"khong co tag '{tag_name}' cua may '{machine_id}'")
    return {"machineId": machine_id, "tagName": tag_name, **m["tags"][tag_name]}


@app.get("/api/lines")
def lines():
    agg: dict[str, dict] = {}
    for mid in store.machine_ids():
        s = summarize(store.get(mid))
        line = agg.setdefault(s.get("lineId") or "UNKNOWN", {"machines": 0, "states": {}})
        line["machines"] += 1
        key = s.get("state") or "UNKNOWN"
        line["states"][key] = line["states"].get(key, 0) + 1
    return dict(sorted(agg.items()))
