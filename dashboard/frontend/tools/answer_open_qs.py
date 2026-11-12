"""Xác định chính xác 3 câu hỏi còn mở trong handoff §6.1:
  Q1: KPI 1 có gauge tròn không?        -> đã trả lời: KHÔNG (chữ, không phải vòng tròn)
  Q2: có "Production by Line" 3 thanh ngang không?
  Q3: có tabs 1h/8h/24h/7d không?
"""
import numpy as np
from PIL import Image
from collections import Counter

REF = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\docs\screenshots\UI2x2.png"
a = np.array(Image.open(REF).convert("RGB"))

PAL = {
    "green  #22c55e": (0x22, 0xC5, 0x5E),
    "amber  #f59e0b": (0xF5, 0x9E, 0x0B),
    "blue   #3b82f6": (0x3B, 0x82, 0xF6),
    "red    #ef4444": (0xEF, 0x44, 0x44),
    "slate-blue #2563eb": (0x25, 0x63, 0xEB),
}


def near(c, t, tol=42):
    return sum(abs(int(c[i]) - t[i]) for i in range(3)) <= tol


def scan(name, x0, y0, x1, y1):
    reg = a[y0:y1, x0:x1]
    h, w, _ = reg.shape
    print(f"\n{name}  [{x0},{y0}->{x1},{y1}]  {w}x{h}")
    for label, t in PAL.items():
        m = np.zeros((h, w), bool)
        for y in range(h):
            for x in range(w):
                if near(reg[y, x], t):
                    m[y, x] = True
        n = int(m.sum())
        if n < 12:
            print(f"   {label:22s} {n:5d} px  (không đáng kể)")
            continue
        ys, xs = np.nonzero(m)
        print(f"   {label:22s} {n:5d} px  bbox y={ys.min()}..{ys.max()} x={xs.min()}..{xs.max()}")
        # cụm ngang (thanh)
        rows = m.sum(axis=1)
        idx = np.nonzero(rows > 25)[0]
        if len(idx):
            print(f"        dải ngang dày (bar): y={idx.min()}..{idx.max()}  (rộng {idx.max()-idx.min()+1})")
        # cụm dọc
        cols = m.sum(axis=0)
        idx2 = np.nonzero(cols > 25)[0]
        if len(idx2):
            print(f"        cột dày: x={idx2.min()}..{idx2.max()}")


# Frame 1: card phải = "Production by Line" theo spec HTML
scan("F1 card phải (Production by Line?)", 465, 190, 761, 456)
scan("F1 card trái (OEE Trend)", 140, 190, 465, 456)
# Frame 2: vùng header có tabs 1h/8h/24h/7d + 3 thẻ line
scan("F2 header + tabs", 898, 78, 1519, 135)
scan("F2 dải 3 thẻ line", 898, 135, 1519, 215)
scan("F2 line status panel", 898, 215, 1250, 456)
# Frame 3: ảnh máy placeholder
scan("F3 ảnh máy", 140, 520, 300, 660)
# Frame 4: bảng alarm
scan("F4 bảng alarm", 898, 560, 1519, 849)
