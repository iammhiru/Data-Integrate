"""Kiểm tra vùng 'Production by Line' (3 thanh ngang) trong ảnh gốc frame1."""
import numpy as np
from PIL import Image
from collections import Counter

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
a = np.array(Image.open(REF).convert("RGB"))

# vùng card phải của frame1
reg = a[190:456, 465:761]
flat = reg.reshape(-1, 3)
cnt = Counter(map(tuple, flat[::5]))
print("màu chính trong card phải frame1:")
for c, n in cnt.most_common(10):
    print("   #%02X%02X%02X %5.1f%%" % (c[0], c[1], c[2], 100.0 * n / len(flat[::5])))

# tìm các thanh ngang: pixel bão hoà cao (xanh/amber/green) tạo thành hàng dài
regi = reg.astype(np.int16)
mx = regi.max(axis=2); mn = regi.min(axis=2)
sat = mx - mn
colored = (sat > 45) & (mx > 90)
print("\npixel màu bão hoà trong card phải:", int(colored.sum()))
ys, xs = np.nonzero(colored)
if len(xs):
    print("  bbox y=%d..%d  x=%d..%d" % (ys.min(), ys.max(), xs.min(), xs.max()))
    # gom theo cụm y
    rows = sorted(set(ys.tolist()))
    clusters = []
    for y in rows:
        if clusters and y - clusters[-1][1] <= 3:
            clusters[-1][1] = y
        else:
            clusters.append([y, y])
    print("  các dải ngang màu (bar):")
    for c in clusters:
        m = colored[c[0]:c[1] + 1]
        cx = np.nonzero(m.any(axis=0))[0]
        print("    y=%d..%d  x=%d..%d  (rộng %d, dày %d)" % (c[0], c[1], cx.min(), cx.max(), cx.max() - cx.min() + 1, c[1] - c[0] + 1))

# tương tự cho card trái (biểu đồ OEE trend)
reg2 = a[190:456, 140:465].astype(np.int16)
mx2 = reg2.max(axis=2); mn2 = reg2.min(axis=2)
sat2 = mx2 - mn2
col2 = (sat2 > 45) & (mx2 > 90)
print("\npixel màu bão hoà trong card trái (OEE trend):", int(col2.sum()))
ys2, xs2 = np.nonzero(col2)
if len(xs2):
    print("  bbox y=%d..%d x=%d..%d" % (ys2.min(), ys2.max(), xs2.min(), xs2.max()))
    cc = Counter(map(tuple, reg2.reshape(-1, 3)[::7]))
    print("  màu chính:")
    for c, n in cc.most_common(8):
        print("    #%02X%02X%02X %5.1f%%" % (c[0], c[1], c[2], 100.0 * n / len(reg2.reshape(-1, 3)[::7])))

# frame4: bảng alarm — có nút màu xanh (Acknowledge)?
reg3 = a[471:849, 898:1519].astype(np.int16)
mx3 = reg3.max(axis=2); mn3 = reg3.min(axis=2)
sat3 = mx3 - mn3
btn = (sat3 > 70) & (mx3 > 100)
ys3, xs3 = np.nonzero(btn)
print("\nframe4 pixel màu đậm (nút/tag):", len(xs3))
if len(xs3):
    cc = Counter(map(tuple, reg3.reshape(-1, 3)[::7]))
    for c, n in cc.most_common(10):
        if max(c) - min(c) > 50:
            print("    #%02X%02X%02X %5.2f%%" % (c[0], c[1], c[2], 100.0 * n / len(reg3.reshape(-1, 3)[::7])))
