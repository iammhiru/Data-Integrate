"""Thống kê dataType / tagType / coverage của catalog.gen.ts."""
import re
import collections
import io

p = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\dashboard\frontend\src\mock\catalog.gen.ts"
src = io.open(p, encoding="utf-8").read()

dt = collections.Counter(re.findall(r'"dataType":\s*"(\w+)"', src))
tt = collections.Counter(re.findall(r'"tagType":\s*"(\w+)"', src))
print("dataType:", dict(dt))
print("tagType :", dict(tt))

names = sorted(set(re.findall(r'"name":\s*"(\w+)"', src)))
print("distinct tag names:", len(names))
print(names)

# Mọi tag có dataType nào chưa được simulator xử lý?
print("\n--- tag name -> dataType ---")
pairs = re.findall(r'"name":\s*"(\w+)",\s*"dataType":\s*"(\w+)"', src)
byname = collections.defaultdict(set)
for n, d in pairs:
    byname[n].add(d)
for n in sorted(byname):
    print(f"  {n:26s} {sorted(byname[n])}")
