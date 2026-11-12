"""Kiểm tra KPI đầu tiên của frame 1 trong ảnh gốc: có gauge tròn không?"""
import numpy as np
from PIL import Image

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
im = Image.open(REF).convert("RGB")
a = np.array(im)

# KPI card 1: x=159..314. Tìm vùng có màu xanh lá (gauge arc #22c55e) trong card đó
reg = a[115:200, 159:315].astype(np.int16)
r, g, b = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
green = (g > 120) & (g > r + 40) & (g > b + 40)
ys, xs = np.nonzero(green)
print("card1 pixels xanh lá:", len(xs))
if len(xs):
    print("  bbox x=%d..%d  y=%d..%d" % (xs.min(), xs.max(), ys.min(), ys.max()))
    # phân bố theo cột -> nếu là gauge tròn, các pixel nằm rải rác theo vòng
    colcount = green.sum(axis=0)
    nz = np.nonzero(colcount)[0]
    print("  số cột có xanh lá:", len(nz), "trong", green.shape[1])
    print("  histogram cột (mẫu):", colcount[::12].tolist())

# So với card 2 (không gauge)
reg2 = a[115:200, 325:467].astype(np.int16)
r2, g2, b2 = reg2[:, :, 0], reg2[:, :, 1], reg2[:, :, 2]
green2 = (g2 > 120) & (g2 > r2 + 40) & (g2 > b2 + 40)
print("card2 pixels xanh lá:", int(green2.sum()))

# Tìm mọi hình tròn/arc xanh lá trong toàn ảnh frame1
reg3 = a[78:456, 140:761].astype(np.int16)
r3, g3, b3 = reg3[:, :, 0], reg3[:, :, 1], reg3[:, :, 2]
gr = (g3 > 110) & (g3 > r3 + 35) & (g3 > b3 + 35)
ys, xs = np.nonzero(gr)
print("\nframe1 toàn bộ pixel xanh lá:", len(xs))
if len(xs):
    print("  bbox x=%d..%d y=%d..%d" % (xs.min(), xs.max(), ys.min(), ys.max()))
    # histogram theo cột, tìm cụm rộng
    from collections import Counter
    hist = Counter((xs // 10) * 10)
    print("  cột có mật độ cao:", sorted([k for k, v in hist.items() if v > 8]))
