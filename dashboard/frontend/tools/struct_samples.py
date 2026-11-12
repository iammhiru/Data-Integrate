"""Cấu trúc 2 ảnh Dashboard_sample*.png — so với mock Plant Overview."""
import numpy as np
from PIL import Image
from collections import Counter
import os

D = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots"


def report(fn):
    im = Image.open(os.path.join(D, fn)).convert("RGB")
    a = np.array(im)
    H, W, _ = a.shape
    lum = a.astype(np.float32).mean(axis=2)
    print("=" * 74)
    print(f"{fn} {W}x{H}")

    # tìm cột dọc dài (>=30% chiều cao) -> biên sidebar / panel
    col = (lum > 40).mean(axis=0)
    row = (lum > 40).mean(axis=1)
    print("  vertical boundaries:")
    i = 0
    while i < W:
        if col[i] > 0.30:
            j = i
            while j + 1 < W and col[j + 1] > 0.30:
                j += 1
            if j - i >= 1:
                print("    x=%4d..%4d  (w=%4d, %.0f%%)" % (i, j, j - i + 1, 100 * col[i:j + 1].mean()))
            i = j + 1
        else:
            i += 1
    print("  horizontal boundaries:")
    i = 0
    while i < H:
        if row[i] > 0.25:
            j = i
            while j + 1 < H and row[j + 1] > 0.25:
                j += 1
            if j - i >= 1:
                print("    y=%4d..%4d  (h=%4d, %.0f%%)" % (i, j, j - i + 1, 100 * row[i:j + 1].mean()))
            i = j + 1
        else:
            i += 1

    # vùng sáng (chữ/icon) theo dải ngang -> gợi ý các hàng nội dung
    txt = lum > 130
    rs = txt.sum(axis=1)
    print("  text bands:")
    i = 0
    while i < H:
        if rs[i] >= 5:
            j = i
            while j + 1 < H and rs[j + 1] >= 5:
                j += 1
            if j - i >= 3:
                cs = txt[i:j + 1].sum(axis=0)
                xs = np.nonzero(cs)[0]
                print("    y=%4d..%4d h=%3d  x=%4d..%4d" % (i, j, j - i + 1, xs[0], xs[-1]))
            i = j + 1
        else:
            i += 1


report("Dashboard_sample.png")
report("Dashboard_sample_2.png")
