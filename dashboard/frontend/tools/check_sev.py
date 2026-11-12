"""Xác định màu severity tag + nút trong bảng alarm của ảnh gốc (F4)."""
import numpy as np
from PIL import Image
from collections import Counter

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
a = np.array(Image.open(REF).convert("RGB"))
reg = a[560:849, 898:1519]

flat = reg.reshape(-1, 3)
print("màu bão hoà (sat>55) trong F4:")
c = Counter(map(tuple, flat))
hits = [(col, n) for col, n in c.items() if max(col) - min(col) > 55 and max(col) > 80]
hits.sort(key=lambda x: -x[1])
for col, n in hits[:15]:
    print("   #%02X%02X%02X n=%d" % (col[0], col[1], col[2], n))

# Tìm các hình chữ nhật nhỏ màu đậm (tag/nút) bằng cách quét cột trong vùng bảng
print("\nQuét hàng y=640..820, tìm cụm ngang màu đậm:")
regi = reg.astype(np.int16)
for y in range(20, 270, 12):
    row = regi[y]
    mx = row.max(axis=1); mn = row.min(axis=1)
    dark = (mx - mn > 55) & (mx > 70)
    xs = np.nonzero(dark)[0]
    if len(xs) > 5:
        # gom cụm
        cl = []
        for x in xs:
            if cl and x - cl[-1][1] <= 3:
                cl[-1][1] = x
            else:
                cl.append([x, x])
        big = [s for s in cl if s[1] - s[0] >= 12]
        if big:
            print(f"   y={y+560}: " + ", ".join(f"x{s[0]}-{s[1]}" for s in big))
