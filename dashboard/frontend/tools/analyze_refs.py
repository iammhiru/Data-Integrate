import numpy as np
from PIL import Image
from collections import Counter
import os

D = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots"

for fn in ["UI2x2.png", "Dashboard_sample.png", "Dashboard_sample_2.png"]:
    p = os.path.join(D, fn)
    im = Image.open(p).convert("RGB")
    a = np.array(im)
    print("=" * 70)
    print(fn, im.size)

    # 1. histogram màu tổng thể
    flat = a.reshape(-1, 3)
    # lấy mẫu
    samp = flat[::7]
    cnt = Counter(map(tuple, samp))
    total = len(samp)
    print("  top 12 màu:")
    for c, n in cnt.most_common(12):
        print("    #%02X%02X%02X  %5.1f%%" % (c[0], c[1], c[2], 100.0 * n / total))

    # 2. số dòng / cột "vân" sáng (border) -> suy ra lưới panel
    lum = a.astype(np.float32).mean(axis=2)
    # cột có nhiều pixel khác nền tập trung -> vertical rules
    print("  dòng ngang đáng chú ý (tỉ lệ pixel sáng > 60):")
    rows = (lum > 60).mean(axis=1)
    idx = [i for i, v in enumerate(rows) if v > 0.6]
    # gom các đoạn liên tiếp
    segs = []
    for i in idx:
        if segs and i - segs[-1][1] <= 2:
            segs[-1][1] = i
        else:
            segs.append([i, i])
    for s in segs:
        if s[1] - s[0] >= 1:
            print("    y=%d..%d" % (s[0], s[1]))
