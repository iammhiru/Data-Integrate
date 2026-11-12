"""Đếm card/bố cục trong từng vùng của ảnh gốc bằng cách phân đoạn màu nền card."""
import numpy as np
from PIL import Image
from collections import Counter

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
im = Image.open(REF).convert("RGB")
a = np.array(im)

CARD = np.array([0x15, 0x1F, 0x34])   # #151F34 - nền card trong ảnh
PANEL = np.array([0x0D, 0x15, 0x25])  # #0D1525 - nền panel


def seg_rows(x0, x1, y0, y1, label):
    """Chia các cột 'đậm' (card) trong dải ngang."""
    strip = a[y0:y1, x0:x1].astype(np.int16)
    # phân đoạn theo cột trung bình
    prof = strip.reshape(strip.shape[1], -1, 3).mean(axis=1)
    isCard = np.abs(prof - CARD).sum(axis=1) < 26
    out = []
    i = 0
    while i < len(isCard):
        if isCard[i]:
            j = i
            while j + 1 < len(isCard) and isCard[j + 1]:
                j += 1
            if j - i >= 20:
                out.append((x0 + i, x0 + j))
            i = j + 1
        else:
            i += 1
    print(f"  {label}: {len(out)} vùng card")
    for s in out:
        print(f"      x={s[0]}..{s[1]}  (w={s[1]-s[0]})")


print("UI2x2.png — phân đoạn card theo từng dải")
print("FRAME 1 (Factory Overview), main x=140..761")
seg_rows(140, 761, 78, 115, "topbar")
seg_rows(140, 761, 115, 200, "KPI row")
seg_rows(140, 761, 200, 460, "chart + right card")
print("FRAME 2 (Line Monitoring), main x=898..1519")
seg_rows(898, 1519, 78, 115, "topbar")
seg_rows(898, 1519, 115, 200, "tabs/line cards")
seg_rows(898, 1519, 200, 460, "panels")
print("FRAME 3 (Machine Detail), main x=140..761")
seg_rows(140, 761, 471, 520, "header")
seg_rows(140, 761, 520, 660, "image + status + params")
seg_rows(140, 761, 660, 849, "events + temp trend")
print("FRAME 4 (Alarm List), main x=898..1519")
seg_rows(898, 1519, 471, 520, "header")
seg_rows(898, 1519, 520, 570, "filters")
seg_rows(898, 1519, 570, 849, "table")
print("BOTTOM band")
seg_rows(18, 1519, 858, 1014, "5 panels")

# đếm số card trong dải KPI chính xác bằng cách xem 1 hàng cụ thể
print("\nDải KPI frame1 — quét từng cột ở y=190 (giữa dải card):")
row = a[190, 140:761].astype(np.int16)
runs = []
cur = None
for x in range(row.shape[0]):
    isc = abs(row[x] - CARD).sum() < 30
    if isc and cur is None:
        cur = x
    elif not isc and cur is not None:
        if x - cur >= 15:
            runs.append((140 + cur, 140 + x - 1))
        cur = None
if cur is not None:
    runs.append((140 + cur, 761))
print("  card runs @y=190:", runs)
print("  => số KPI card:", len(runs))
