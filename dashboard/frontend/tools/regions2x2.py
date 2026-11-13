"""Phân tích vùng cụ thể của ảnh gốc UI2x2.png để đối chiếu từng khối."""
import numpy as np
from PIL import Image
from collections import Counter
import os

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
im = Image.open(REF).convert("RGB")
a = np.array(im)
H, W, _ = a.shape


def region(name, x0, y0, x1, y1):
    sub = a[y0:y1, x0:x1]
    lum = sub.astype(np.float32).mean(axis=2)
    flat = sub.reshape(-1, 3)[::5]
    cnt = Counter(map(tuple, flat)).most_common(4)
    print(f"  {name:34s} [{x0},{y0}->{x1},{y1}]  lum mean={lum.mean():6.1f} max={lum.max():5.1f}  bright%={100*(lum>45).mean():5.1f}")
    for c, n in cnt:
        print(f"        #{c[0]:02X}{c[1]:02X}{c[2]:02X} {100.0*n/len(flat):5.1f}%")


print("UI2x2.png 1536x1024 — khảo sát vùng")
print("HEADER")
region("header logo", 18, 15, 80, 70)
region("header title", 90, 15, 700, 60)
region("header pill right", 1150, 15, 1520, 60)
print("FRAME 1 (x 18..761, y 78..456) — Factory Overview")
region("f1 sidebar", 18, 78, 134, 456)
region("f1 main", 140, 78, 761, 456)
region("f1 topbar", 140, 78, 761, 110)
region("f1 kpi row", 140, 110, 761, 190)
region("f1 chart area", 140, 190, 460, 456)
region("f1 right card", 465, 190, 761, 456)
print("FRAME 2 (x 776..1519, y 78..456)")
region("f2 sidebar", 776, 78, 892, 456)
region("f2 main", 898, 78, 1519, 456)
print("FRAME 3 (y 471..849)")
region("f3 sidebar", 18, 471, 134, 849)
region("f3 main", 140, 471, 761, 849)
print("FRAME 4")
region("f4 sidebar", 776, 471, 892, 849)
region("f4 main", 898, 471, 1519, 849)
print("BOTTOM BAND (y 858..1024)")
region("bottom full", 18, 858, 1519, 1024)
region("bottom col1", 18, 858, 280, 1024)
region("bottom col2", 293, 858, 580, 1024)
region("bottom col5", 1193, 858, 1519, 1024)
print("BEYOND 1024?")
region("row 1000..1024", 18, 1000, 1519, 1024)
