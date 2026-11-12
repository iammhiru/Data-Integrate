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
    GET /ui                                  trang test realtime (HTML nhan WebSocket)
    WS  /ws/machines?machineId=&lineId=      day realtime: snapshot luc ket noi, sau do patch thay doi

WebSocket (server -> client):
    {"type":"snapshot","ready":bool,"serverTime":..,"machines":[<giong GET /api/machines/{id}>]}
    {"type":"patch","serverTime":..,"machines":[<summary may> + "tags": {chi cac tag vua doi}]}
    {"type":"heartbeat","serverTime":..,"ready":bool}      khi khong co gi gui trong WS_HEARTBEAT_SEC
client -> server (tuy chon):
    {"action":"subscribe","machineIds":["L01_FILLER_01"],"lineId":null}  doi bo loc -> nhan snapshot moi
    {"action":"ping"}  -> {"type":"pong"}
Thay doi duoc gom va gui moi WS_FLUSH_MS (mac dinh 250ms); nhieu lan doi cung 1 tag trong 1 nhip
chi gui ban moi nhat. Chi co 1 coroutine (broadcaster) gui snapshot/patch -> thu tu luon dung.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError, TopicPartition, OFFSET_BEGINNING
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("STATE_TOPIC", "machine-state")
STALE_AFTER_SEC = float(os.getenv("STALE_AFTER_SEC", "60"))
SUMMARY_TAGS = ["MachineState", "MachineMode", "AlarmCode", "EmergencyStop", "CurrentSpeed",
                "DesignSpeed", "TotalCounter", "GoodCounter", "DefectCounter", "Starved", "Blocked"]
WS_FLUSH_SEC = float(os.getenv("WS_FLUSH_MS", "250")) / 1000
WS_HEARTBEAT_SEC = float(os.getenv("WS_HEARTBEAT_SEC", "15"))
WS_SEND_TIMEOUT_SEC = float(os.getenv("WS_SEND_TIMEOUT_SEC", "5"))

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

    def apply(self, rec: dict) -> tuple[str, str, dict] | None:
        """Tra ve (machineId, tagName, entry) neu trang thai thay doi, None neu bo qua."""
        mid, tag = rec.get("machineId"), rec.get("tagName")
        if not mid or not tag:
            return None
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
                return None
            m["tags"][tag] = entry
            m["meta"] = {k: rec.get(k) for k in
                         ("machineId", "plantId", "lineId", "processId", "machineType", "equipmentCode",
                          "sourceSystem")}
        return mid, tag, dict(entry)

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


class WsClient:
    def __init__(self, ws: WebSocket, machine_ids: set[str] | None, line_id: str | None) -> None:
        self.ws = ws
        self.machine_ids = machine_ids
        self.line_id = line_id
        self.need_snapshot = True      # broadcaster se gui snapshot o nhip ke tiep
        self.last_sent = 0.0
        self.lock = asyncio.Lock()

    def wants(self, mid: str, line_id: str | None) -> bool:
        return (not self.machine_ids or mid in self.machine_ids) and (not self.line_id or line_id == self.line_id)

    async def send(self, msg: dict) -> bool:
        try:
            async with self.lock:
                await asyncio.wait_for(self.ws.send_text(json.dumps(msg, default=str)), WS_SEND_TIMEOUT_SEC)
            self.last_sent = time.time()
            return True
        except Exception:  # noqa: BLE001 - client cham / da dong -> loai bo
            return False


class Hub:
    """Gom thay doi tu thread Kafka; broadcaster (asyncio) lay ra moi WS_FLUSH_SEC."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[tuple[str, str], dict] = {}
        self.clients: set[WsClient] = set()
        self.patches_sent = 0

    def publish(self, mid: str, tag: str, entry: dict) -> None:   # goi tu thread consumer
        with self._lock:
            self._pending[(mid, tag)] = entry                        # trung key -> giu ban moi nhat

    def drain(self) -> dict[tuple[str, str], dict]:
        with self._lock:
            p, self._pending = self._pending, {}
        return p


hub = Hub()


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
                        changed = store.apply(json.loads(msg.value()))
                        if changed and store.ready:   # luc dang nap snapshot khong can gom patch
                            hub.publish(*changed)
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _snapshot(c: WsClient) -> dict:
    machines = []
    for mid in store.machine_ids():
        m = store.get(mid)
        if m and c.wants(mid, m["meta"].get("lineId")):
            machines.append({**summarize(m), "tags": dict(sorted(m["tags"].items()))})
    return {"type": "snapshot", "ready": store.ready, "serverTime": _now_iso(), "machines": machines}


async def broadcaster() -> None:
    """Coroutine DUY NHAT gui snapshot/patch -> client khong bao gio nhan patch cu sau snapshot moi.
    Moi nhip: drain pending truoc, roi moi dung snapshot -> snapshot da bao gom moi thay doi da drain,
    thay doi sau do nam trong pending cua nhip sau -> khong mat, khong lui."""
    was_ready = store.ready
    while True:
        await asyncio.sleep(WS_FLUSH_SEC)
        try:
            if store.ready and not was_ready:          # vua nap xong -> gui lai snapshot day du
                was_ready = True
                for c in hub.clients:
                    c.need_snapshot = True
            pending = hub.drain()
            by_m: dict[str, dict] = {}
            for (mid, tag), e in pending.items():
                by_m.setdefault(mid, {})[tag] = e
            summaries = {}
            for mid in by_m:
                m = store.get(mid)
                if m:
                    summaries[mid] = summarize(m)
            now = time.time()
            jobs = []
            for c in list(hub.clients):
                if c.need_snapshot:
                    c.need_snapshot = False
                    jobs.append((c, _snapshot(c)))
                    continue
                ms = [{**summaries[mid], "tags": dict(sorted(tags.items()))}
                      for mid, tags in by_m.items() if mid in summaries and c.wants(mid, summaries[mid].get("lineId"))]
                if ms:
                    jobs.append((c, {"type": "patch", "serverTime": _now_iso(), "machines": ms}))
                    hub.patches_sent += 1
                elif now - c.last_sent >= WS_HEARTBEAT_SEC:
                    jobs.append((c, {"type": "heartbeat", "serverTime": _now_iso(), "ready": store.ready}))
            if jobs:
                results = await asyncio.gather(*(c.send(msg) for c, msg in jobs))
                for (c, _), ok in zip(jobs, results):
                    if not ok:
                        hub.clients.discard(c)
                        log.info("ws client bi loai (cham/da dong), con %d", len(hub.clients))
                        try:
                            await c.ws.close()
                        except Exception:  # noqa: BLE001
                            pass
        except Exception as exc:  # noqa: BLE001 - khong de broadcaster chet
            log.exception("broadcaster loi: %s", exc)


def _parse_ids(v) -> set[str] | None:
    if v is None:
        return None
    items = v.split(",") if isinstance(v, str) else v
    ids = {str(x).strip() for x in items if str(x).strip()}
    return ids or None


@app.on_event("startup")
async def _start() -> None:
    threading.Thread(target=consume_forever, name="kafka-consumer", daemon=True).start()
    asyncio.create_task(broadcaster())


@app.websocket("/ws/machines")
async def ws_machines(ws: WebSocket, machineId: str | None = None, lineId: str | None = None):
    await ws.accept()
    c = WsClient(ws, _parse_ids(machineId), lineId or None)
    hub.clients.add(c)
    log.info("ws client ket noi (machineId=%s lineId=%s), tong %d", machineId, lineId, len(hub.clients))
    try:
        while True:
            try:
                req = json.loads(await ws.receive_text())
            except ValueError:
                await c.send({"type": "error", "message": "message phai la JSON"})
                continue
            action = req.get("action") if isinstance(req, dict) else None
            if action == "subscribe":
                c.machine_ids = _parse_ids(req.get("machineIds"))
                c.line_id = req.get("lineId") or None
                c.need_snapshot = True
            elif action == "ping":
                await c.send({"type": "pong", "serverTime": _now_iso()})
            else:
                await c.send({"type": "error", "message": "action hop le: subscribe | ping"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(c)
        log.info("ws client ngat, con %d", len(hub.clients))


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/ui")


@app.get("/ui", include_in_schema=False)
def ui():
    """Trang test don gian: nhan WebSocket /ws/machines va hien thi realtime."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok" if store.ready else "loading", "topic": TOPIC, "ready": store.ready,
            "machines": len(store.machine_ids()), "tags": store.tag_count(),
            "messagesConsumed": store.messages, "ignoredOlder": store.ignored_older,
            "wsClients": len(hub.clients), "wsPatchesSent": hub.patches_sent,
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
