"""Kiểm tra: card KPI đầu của frame1 trong ảnh gốc có gauge tròn không?
Tìm mọi cung màu bão hoà trong vùng card (không chỉ xanh lá)."""
import numpy as np
from PIL import Image
from collections import Counter

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
a = np.array(Image.open(REF).convert("RGB"))

print("Frame1 KPI card 1: x=159..314, y=115..200")
reg = a[115:200, 159:315].astype(np.int16)
mx = reg.max(axis=2); mn = reg.min(axis=2)
sat = mx - mn
print("  pixel bão hoà (sat>45):", int(((sat > 45) & (mx > 90)).sum()))
flat = reg.reshape(-1, 3)
cnt = Counter(map(tuple, flat[::3]))
for c, n in cnt.most_common(12):
    print("    #%02X%02X%02X %5.1f%%  sat=%d" % (c[0], c[1], c[2], 100.0 * n / len(flat[::3]), max(c) - min(c)))

# Vẽ bản ascii của card1 để nhìn cấu trúc (mỗi ký tự = 2px x 2px)
print("\nASCII card1 (mỗi ký tự ~ 2x2 px):")
lum = reg.mean(axis=2)
h, w = lum.shape
chars = " .:-=+*#%@"
for y in range(0, h, 3):
    line = ""
    for x in range(0, w, 2):
        v = lum[y:y + 3, x:x + 2].mean()
        line += chars[min(9, int(v / 26))]
    print("   " + line)
