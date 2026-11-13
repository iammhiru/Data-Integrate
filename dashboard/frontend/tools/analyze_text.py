"""Phân tích sâu: tìm khung (card) bằng màu viền + vùng chữ, theo từng ảnh."""
import numpy as np
from PIL import Image
from collections import Counter
import os, sys

D = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots"


def load(fn):
    return Image.open(os.path.join(D, fn)).convert("RGB")


def palette(a, n=24):
    flat = a.reshape(-1, 3)[::13]
    return Counter(map(tuple, flat)).most_common(n)


def report(fn):
    im = load(fn)
    a = np.array(im)
    H, W, _ = a.shape
    print("=" * 74)
    print(f"{fn}  {W}x{H}")

    pal = palette(a)
    print("  palette:")
    for c, n in pal:
        print("    #%02X%02X%02X  %5.2f%%" % (c[0], c[1], c[2], 100.0 * n / (H * W / 13)))

    # --- tìm màu viền (dùng để dò khung) ---
    # viền là màu có độ bão hoà cao hơn nền nhiều, ví dụ #1E3A5F, #1D3566
    lum = a.astype(np.float32).mean(axis=2)
    # chữ: pixel rất sáng (>140)
    text = lum > 140
    print("  text rows (>=8 bright px runs):")
    rs = text.sum(axis=1)
    i = 0
    lines = []
    while i < H:
        if rs[i] >= 8:
            j = i
            while j + 1 < H and rs[j + 1] >= 8:
                j += 1
            if j - i >= 4:
                lines.append((i, j))
            i = j + 1
        else:
            i += 1
    for s in lines[:80]:
        cs = text[s[0]:s[1] + 1].sum(axis=0)
        xs = [x for x, v in enumerate(cs) if v >= 1]
        x0, x1 = (xs[0], xs[-1]) if xs else (0, 0)
        print("    y=%4d..%4d h=%3d  x=%4d..%4d" % (s[0], s[1], s[1] - s[0] + 1, x0, x1))
    print("    (tổng %d dòng chữ)" % len(lines))


for f in sys.argv[1:] or ["Dashboard_sample_2.png"]:
    report(f)
