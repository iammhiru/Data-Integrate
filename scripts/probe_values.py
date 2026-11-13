"""Poll gia tri tag tu Kepware 2 lan, cach nhau N giay, de kiem tra du lieu co THAY DOI khong."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\IndustrialTelemetry.Middleware")))

from opcua import Client

from core.tag_loader import load_all_tags

tags = load_all_tags()
client = Client("opc.tcp://127.0.0.1:49320", timeout=15)
client.connect()

sample = [t for t in tags if t.tag_name in ("MachineState", "CurrentSpeed", "TotalCounter", "TankLevel", "FillingPressure")][:25]

def read():
    out = {}
    for t in sample:
        try:
            out[t.node_id] = client.get_node(t.node_id).get_value()
        except Exception as e:
            out[t.node_id] = f"<err {type(e).__name__}>"
    return out

a = read()
print("=== LAN 1 ===")
for k, v in a.items():
    print(f"  {k} = {v!r}")

time.sleep(8)

b = read()
print("\n=== LAN 2 (sau 8s) ===")
changed = 0
for k, v in b.items():
    mark = ""
    if a.get(k) != v:
        mark = "   <-- THAY DOI"
        changed += 1
    print(f"  {k} = {v!r}{mark}")
print(f"\nChanged: {changed}/{len(sample)}")

client.disconnect()
