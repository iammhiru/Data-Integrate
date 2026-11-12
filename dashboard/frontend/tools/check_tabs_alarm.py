"""Kiểm tra tinh tế: tabs 1h/8h/24h/7d ở F2 và severity tag + nút ở F4."""
import numpy as np
from PIL import Image
from collections import Counter

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
a = np.array(Image.open(REF).convert("RGB"))

print("=== F2: vùng tabs (góc phải header frame2) ===")
reg = a[78:135, 898:1519].reshape(-1, 3)
cnt = Counter(map(tuple, reg[::3]))
for c, n in cnt.most_common(14):
    sat = max(c) - min(c)
    tag = " <-- MÀU" if sat > 45 and max(c) > 80 else ""
    print("   #%02X%02X%02X %5.2f%% sat=%3d%s" % (c[0], c[1], c[2], 100.0 * n / len(reg[::3]), sat, tag))

print("\n=== F4: bảng alarm — màu của tag severity & nút ===")
reg4 = a[560:849, 898:1519]
flat = reg4.reshape(-1, 3)
cnt4 = Counter(map(tuple, flat[::3]))
for c, n in cnt4.most_common(20):
    sat = max(c) - min(c)
    if sat > 40 and max(c) > 70:
        print("   #%02X%02X%02X %5.2f%% sat=%3d" % (c[0], c[1], c[2], 100.0 * n / len(flat[::3]), sat))

print("\n=== Quét ngang hàng để tìm các ô nút (vùng cột 531..596 trong F4) ===")
for y in [600, 640, 680, 720, 760]:
    row = a[y, 898:1519]
    cc = Counter(map(tuple, row))
    top = [("#%02X%02X%02X" % c, n) for c, n in cc.most_common(5) if max(c) - min(c) > 40]
    if top:
        print(f"   y={y}: {top}")
