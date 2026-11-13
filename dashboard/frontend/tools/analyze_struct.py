"""Phân tích cấu trúc panel (khung) trong ảnh tham khảo bằng phát hiện cạnh + hộp chữ nhật."""
import numpy as np
from PIL import Image
import os

D = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots"


def analyze(fn):
    im = Image.open(os.path.join(D, fn)).convert("RGB")
    a = np.array(im)
    H, W, _ = a.shape
    lum = a.astype(np.float32).mean(axis=2)
    print("=" * 72)
    print(f"{fn}  {W}x{H}")

    # 1) Tìm các đường thẳng dọc ngang dài (>= 25% chiều cao/rộng)
    def lines(score, minlen, axis):
        out = []
        i = 0
        n = len(score)
        while i < n:
            if score[i] > 0.3:
                j = i
                while j + 1 < n and score[j + 1] > 0.3:
                    j += 1
                if j - i + 1 >= minlen:
                    out.append((i, j, float(score[i:j + 1].mean())))
                i = j + 1
            else:
                i += 1
        return out

    colscore = (lum > 40).mean(axis=0)
    rowscore = (lum > 40).mean(axis=1)
    print("  VERTICAL lines:")
    for s in lines(colscore, int(H * 0.25), 0):
        print("    x=%4d..%4d  len=%4d  mean=%.2f" % (s[0], s[1], s[1] - s[0] + 1, s[2]))
    print("  HORIZONTAL lines:")
    for s in lines(rowscore, int(W * 0.25), 1):
        print("    y=%4d..%4d  len=%4d  mean=%.2f" % (s[0], s[1], s[1] - s[0] + 1, s[2]))

    # 2) Vùng "panel" đậm hơn nền: dùng ngưỡng tương phản cục bộ
    #    nền = màu phổ biến nhất
    from collections import Counter
    flat = a.reshape(-1, 3)[::11]
    bg = Counter(map(tuple, flat)).most_common(1)[0][0]
    dist = np.abs(a.astype(np.int16) - np.array(bg, dtype=np.int16)).sum(axis=2)
    panel = dist > 26
    print("  panel-ish rows (>=40%% of width):")
    rs = panel.mean(axis=1)
    i = 0
    while i < H:
        if rs[i] > 0.40:
            j = i
            while j + 1 < H and rs[j + 1] > 0.40:
                j += 1
            if j - i >= 8:
                print("    y=%4d..%4d  h=%4d" % (i, j, j - i + 1))
            i = j + 1
        else:
            i += 1
    print("  panel-ish cols (>=40%% of height):")
    cs = panel.mean(axis=0)
    i = 0
    while i < W:
        if cs[i] > 0.40:
            j = i
            while j + 1 < W and cs[j + 1] > 0.40:
                j += 1
            if j - i >= 8:
                print("    x=%4d..%4d  w=%4d" % (i, j, j - i + 1))
            i = j + 1
        else:
            i += 1


for f in ["UI2x2.png", "Dashboard_sample.png", "Dashboard_sample_2.png"]:
    analyze(f)
