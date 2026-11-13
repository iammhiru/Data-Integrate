import re, collections, json, os

p = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\dashboard\frontend\src\mock\catalog.gen.ts"
src = open(p, encoding="utf-8").read()
lines = re.findall(r'"lineId": "([A-Z_0-9]+)"', src)
ch = re.findall(r'"channel": "([A-Z_0-9]+)"', src)
mt = re.findall(r'"machineType": "([A-Z_0-9]+)"', src)
pr = re.findall(r'"processId": "([A-Z_0-9]+)"', src)
print("lineId :", dict(collections.Counter(lines)))
print("channel:", dict(collections.Counter(ch)))
print("machineType:", dict(collections.Counter(mt)))
print("processId:", dict(collections.Counter(pr)))

# tag counts per machine
blocks = src.split('"machineId": "')[1:]
tot = 0
per = []
for b in blocks:
    mid = b[:b.index('"')]
    n = b.count('"tagType":')
    tot += n
    per.append((mid, n))
print("tổng tag:", tot, "| máy nhiều tag nhất:", sorted(per, key=lambda x: -x[1])[:5])
print("máy ít tag nhất:", sorted(per, key=lambda x: x[1])[:5])

# catalog.json chính thức
cj = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\IndustrialTelemetry.Middleware\metadata\catalog.json"
d = json.load(open(cj, encoding="utf-8"))
print("\ncatalog.json top-level keys:", list(d.keys())[:10])
if isinstance(d, dict):
    for k, v in d.items():
        if isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
        elif isinstance(v, dict):
            print(f"  {k}: dict[{len(v)}] keys={list(v.keys())[:6]}")
        else:
            print(f"  {k}: {v}")
