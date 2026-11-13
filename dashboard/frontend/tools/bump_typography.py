"""Nâng cỡ chữ tối thiểu trong app.css lên 11px (WCAG + work.md §1.3).

Bảng nâng:
  9px, 9.5px  → 11px    (nhãn rất nhỏ, eyebrow)
  10px, 10.5px → 11.5px (chữ phụ)
  11px        → 11.5px  (chữ phụ)
Các cỡ ≥ 11.5px giữ nguyên.
"""
import re, io, sys

p = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\dashboard\frontend\src\mock\app.css"
src = io.open(p, encoding="utf-8").read()

MAP = {
    "9px": "11px",
    "9.5px": "11px",
    "10px": "11.5px",
    "10.5px": "11.5px",
    "11px": "11.5px",
}

# chỉ thay trong khai báo font-size: Xpx
def repl(m):
    val = m.group(1)
    return f"font-size: {MAP.get(val, val)}"

out = re.sub(r"font-size:\s*([0-9.]+px)", repl, src)

n = sum(1 for a, b in zip(re.findall(r"font-size:\s*([0-9.]+px)", src),
                          re.findall(r"font-size:\s*([0-9.]+px)", out)) if a != b)
io.open(p, "w", encoding="utf-8").write(out)
print(f"đã nâng {n} khai báo font-size trong app.css")

# Kiểm tra còn sót cỡ < 11px
left = sorted(set(x for x in re.findall(r"font-size:\s*([0-9.]+px)", out)
                   if float(x.replace("px", "")) < 11))
print("còn sót cỡ < 11px:", left or "không")
