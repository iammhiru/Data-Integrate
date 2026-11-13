"""So khớp mặt nạ chữ (text mask) giữa ảnh gốc UI2x2.png và bản render HTML.

Nếu nội dung chữ giống nhau, mặt nạ phải trùng khớp ở cùng vị trí.
Dùng để kiểm chứng: bản dựng lại HTML có THỰC SỰ tái tạo ảnh, hay chỉ "giống ý tưởng".
"""
import numpy as np
from PIL import Image
import os

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
REN = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\dashboard\frontend\tools\_2x2_render.png"

ref = np.array(Image.open(REF).convert("L")).astype(np.float32)
ren = np.array(Image.open(REN).convert("L")).astype(np.float32)
H = min(ref.shape[0], ren.shape[0]); W = min(ref.shape[1], ren.shape[1])
ref, ren = ref[:H, :W], ren[:H, :W]

# mặt nạ chữ: pixel sáng, đã loãi nhẹ để chịu sai lệch 1px
def mask(img, thr):
    m = (img > thr).astype(np.float32)
    # loãi 3x3
    p = np.pad(m, 1)
    out = np.zeros_like(m)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out += p[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]]
    return (out > 0).astype(np.float32)

for thr in (110, 150):
    A = mask(ref, thr); B = mask(ren, thr)
    inter = (A * B).sum(); union = ((A + B) > 0).sum()
    print(f"thr={thr}: IoU toàn ảnh = {inter/union:.3f}   (chữ ref={int(A.sum())}, chữ render={int(B.sum())})")

print("\nIoU theo vùng (thr=130):")
A = mask(ref, 130); B = mask(ren, 130)
regions = {
    "header (0..70)": (0, 0, W, 70),
    "frame1 (18..761, 78..456)": (18, 78, 761, 456),
    "frame2 (776..1519, 78..456)": (776, 78, 1519, 456),
    "frame3 (18..761, 471..849)": (18, 471, 761, 849),
    "frame4 (776..1519, 471..849)": (776, 471, 1519, 849),
    "bottom band (18..1519, 858..1014)": (18, 858, 1519, 1014),
}
for name, (x0, y0, x1, y1) in regions.items():
    a = A[y0:y1, x0:x1]; b = B[y0:y1, x0:x1]
    inter = (a * b).sum(); union = ((a + b) > 0).sum()
    print(f"  {name:36s} IoU={inter/union if union else 0:.3f}  refpx={int(a.sum()):6d} renpx={int(b.sum()):6d}")

# thử dịch tối ưu cho từng vùng
print("\nDịch tối ưu (vùng frame1):")
a0 = A[78:456, 18:761]
best = None
for dy in range(-12, 13):
    for dx in range(-12, 13):
        b = B[78 + dy:456 + dy, 18 + dx:761 + dx]
        inter = (a0 * b).sum(); union = ((a0 + b) > 0).sum()
        v = inter / union if union else 0
        if best is None or v > best[0]:
            best = (v, dx, dy)
print("  best IoU=%.3f tại dx=%d dy=%d" % best)
