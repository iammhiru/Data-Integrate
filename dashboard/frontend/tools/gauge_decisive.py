"""Xác định chính xác: KPI card 1 trong ảnh gốc có gauge tròn không?"""
import numpy as np
from PIL import Image
from collections import Counter

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
a = np.array(Image.open(REF).convert("RGB"))

# Tìm pixel bão hoà trong card1 và in vị trí + màu
reg = a[115:200, 159:315].astype(np.int16)
mx = reg.max(axis=2); mn = reg.min(axis=2)
sat = mx - mn
m = (sat > 45) & (mx > 90)
ys, xs = np.nonzero(m)
print("card1: %d pixel bão hoà" % len(xs))
if len(xs):
    print("  bbox y=%d..%d x=%d..%d" % (ys.min(), ys.max(), xs.min(), xs.max()))
    cc = Counter(map(tuple, reg[ys, xs]))
    print("  màu bão hoà:")
    for c, n in cc.most_common(8):
        print("    #%02X%02X%02X  n=%d" % (c[0], c[1], c[2], n))
    # phân bố theo cột (gauge tròn = các cột giữa ít pixel hơn mép)
    hist = np.bincount(xs, minlength=reg.shape[1])
    print("  histogram theo cột (mọi 5 cột):")
    print("   ", hist[::5].tolist())

print()
# So sánh: một gauge tròn đường kính 54px sẽ tạo ~170 pixel trên 1 vòng tròn
# Đếm pixel theo vòng tròn (distance transform đơn giản) tại tâm bbox
if len(xs):
    cy = (ys.min() + ys.max()) / 2
    cx = (xs.min() + xs.max()) / 2
    r = np.hypot(ys - cy, xs - cx)
    hist_r = np.histogram(r, bins=12, range=(0, 40))[0]
    print("  histogram theo bán kính (0..40px):", hist_r.tolist())
    print("  => gauge tròn sẽ có đỉnh rõ ở 1 giá trị r")

# Cả 4 KPI card: tìm mọi pixel bão hoà mạn tính theo card
print("\nTất cả pixel bão hoà trong dải KPI (y=115..200, x=140..761) theo card:")
reg2 = a[115:200, 140:761].astype(np.int16)
mx2 = reg2.max(axis=2); mn2 = reg2.min(axis=2)
m2 = (mx2 - mn2 > 45) & (mx2 > 90)
for x0, x1, name in [(159, 314, "card1"), (325, 466, "card2"), (475, 608, "card3"), (619, 748, "card4")]:
    sub = m2[:, x0 - 140:x1 - 140 + 1]
    ys2, xs2 = np.nonzero(sub)
    cc = Counter(map(tuple, reg2[ys2, xs2])) if len(xs2) else {}
    print("  %s: %d px bão hoà  %s" % (name, len(xs2),
          ("màu: " + ", ".join("#%02X%02X%02X(%d)" % (c[0], c[1], c[2], n) for c, n in cc.most_common(3))) if cc else ""))
