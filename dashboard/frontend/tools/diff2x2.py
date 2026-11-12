"""So khớp pixel giữa bản render HTML (2x2) và ảnh gốc UI2x2.png."""
import numpy as np
from PIL import Image
import os

S = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\dashboard\frontend\tools"
REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"

ref = np.array(Image.open(REF).convert("RGB")).astype(np.int16)
ren = np.array(Image.open(os.path.join(S, "_2x2_render.png")).convert("RGB")).astype(np.int16)
print("ref", ref.shape, "render", ren.shape)

H = min(ref.shape[0], ren.shape[0])
W = min(ref.shape[1], ren.shape[1])
r = ref[:H, :W]
g = ren[:H, :W]

d = np.abs(r - g).mean(axis=2)
print("mean abs diff: %.2f   pixels<20: %.1f%%" % (d.mean(), 100 * (d < 20).mean()))

# Thử các ca lệch (dx,dy) nhỏ để tìm alignment tốt nhất
best = None
for dy in range(-14, 15):
    for dx in range(-14, 15):
        ay0, ax0 = max(0, -dy), max(0, -dx)
        by0, bx0 = max(0, dy), max(0, dx)
        hh = H - abs(dy)
        ww = W - abs(dx)
        if hh <= 0 or ww <= 0:
            continue
        a = ref[ay0:ay0 + hh, ax0:ax0 + ww]
        b = ren[by0:by0 + hh, bx0:bx0 + ww]
        dd = np.abs(a - b).mean()
        if best is None or dd < best[0]:
            best = (dd, dx, dy)
print("best alignment: mean=%.2f at dx=%d dy=%d" % best)

# So khớp vùng khung: so 2 ảnh đã căn
dd, dx, dy = best
hh, ww = H - abs(dy), W - abs(dx)
a = ref[max(0, -dy):max(0, -dy) + hh, max(0, -dx):max(0, -dx) + ww]
b = ren[max(0, dy):max(0, dy) + hh, max(0, dx):max(0, dx) + ww]
diff = np.abs(a - b).mean(axis=2)
# in "bản đồ nhiệt" 16x16
gh, gw = 32, 32
print("\nheat map (mean diff per cell, lower = closer):")
for i in range(gh):
    row = ""
    for j in range(gw):
        v = diff[i * H // gh:(i + 1) * H // gh, j * W // gw:(j + 1) * W // gw].mean()
        row += " .:-=+*#%@"[min(9, int(v / 6))]
    print("   " + row)
