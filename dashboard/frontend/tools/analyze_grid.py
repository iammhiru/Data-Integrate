import numpy as np
from PIL import Image
import os

D = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots"

def grid_report(fn, bright_thr=45, frac_thr=0.35):
    im = Image.open(os.path.join(D, fn)).convert("RGB")
    a = np.array(im).astype(np.float32)
    lum = a.mean(axis=2)
    H, W = lum.shape
    print("=" * 70)
    print(fn, im.size)

    # cột dọc: tỉ lệ pixel sáng theo cột
    col = (lum > bright_thr).mean(axis=0)
    rows = (lum > bright_thr).mean(axis=1)

    def segs(idx, vals):
        out = []
        for i in idx:
            if out and i - out[-1][1] <= 3:
                out[-1][1] = i
            else:
                out.append([i, i])
        return out

    ci = [i for i, v in enumerate(col) if v > frac_thr]
    ri = [i for i, v in enumerate(rows) if v > frac_thr]
    print("  vertical rules (>=%.0f%% bright):" % (frac_thr * 100))
    for s in segs(ci, col):
        print("    x=%4d..%4d  (%.2f%%)" % (s[0], s[1], 100 * col[s[0]:s[1] + 1].mean()))
    print("  horizontal rules:")
    for s in segs(ri, rows):
        print("    y=%4d..%4d  (%.2f%%)" % (s[0], s[1], 100 * rows[s[0]:s[1] + 1].mean()))


grid_report("UI2x2.png")
grid_report("Dashboard_sample.png")
grid_report("Dashboard_sample_2.png")
