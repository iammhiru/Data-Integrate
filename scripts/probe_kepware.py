"""Kiem tra Kepware co chua cac node tag theo TAG_FOLDER khong (fix API)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\IndustrialTelemetry.Middleware")))

from opcua import Client

from core.tag_loader import load_all_tags

tags = load_all_tags()
print(f"Tags loaded: {len(tags)}")

client = Client("opc.tcp://127.0.0.1:49320", timeout=15)
client.connect()
root = client.get_root_node()

objects = root.get_child("0:Objects")
print("Objects children (channels):")
for ch in objects.get_children():
    bn = ch.get_browse_name()
    kids = ch.get_children()
    print(f"  {bn}  ({len(kids)} devices)")
    for d in kids[:2]:
        print(f"      {d.get_browse_name()}")

print("\n--- Doc 8 node dau ---")
ok = fail = 0
for t in tags[:8]:
    node = client.get_node(t.node_id)
    try:
        val = node.get_value()
        st = node.get_data_value().StatusCode
        print(f"  OK   {t.node_id} = {val!r} status={st}")
        ok += 1
    except Exception as e:
        print(f"  FAIL {t.node_id}: {type(e).__name__}: {e}")
        fail += 1
print(f"Probe: ok={ok} fail={fail}")
client.disconnect()
