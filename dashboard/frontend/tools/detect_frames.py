"""Dò khung (frame) trong ảnh bằng viền sáng — để đối chiếu với mes_dashboard_2x2.html."""
import numpy as np
from PIL import Image
import os, sys

D = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots"


def detect(fn, thr=45, frac=0.55):
    im = Image.open(os.path.join(D, fn)).convert("RGB")
    a = np.array(im)
    H, W, _ = a.shape
    lum = a.astype(np.float32).mean(axis=2)
    bright = lum > thr

    # đường ngang: hàng có >= frac số pixel sáng
    rows = bright.mean(axis=1)
    cols = bright.mean(axis=0)

    def runs(score, minlen):
        out = []
        i = 0
        n = len(score)
        while i < n:
            if score[i] >= frac:
                j = i
                while j + 1 < n and score[j + 1] >= frac:
                    j += 1
                if j - i + 1 >= minlen:
                    out.append((i, j))
                i = j + 1
            else:
                i += 1
        return out

    print("=" * 70)
    print(fn, f"{W}x{H}")
    print("  h-lines (>=%.0f%% bright, len>=60):" % (frac * 100))
    for s in runs(rows, 60):
        print("    y=%4d..%4d  (h=%4d)" % (s[0], s[1], s[1] - s[0] + 1))
    print("  v-lines:")
    for s in runs(cols, 60):
        print("    x=%4d..%4d  (w=%4d)" % (s[0], s[1], s[1] - s[0] + 1))

    # Thử khớp: tìm cặp đường ngang cách nhau ~D và cặp dọc cách nhau ~D
    print("  -- grid candidates --")
    hl = runs(rows, 60)
    vl = runs(cols, 60)
    for i in range(len(hl) - 1):
        d = hl[i + 1][0] - hl[i][0]
        if 200 < d < 700:
            print(f"    h-gap y={hl[i][1]}..{hl[i+1][0]}  Δ={d}")
    for i in range(len(vl) - 1):
        d = vl[i + 1][0] - vl[i][0]
        if 200 < d < 900:
            print(f"    v-gap x={vl[i][1]}..{vl[i+1][0]}  Δ={d}")


for f in sys.argv[1:] or ["UI2x2.png"]:
    detect(f)
