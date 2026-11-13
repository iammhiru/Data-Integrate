"""Thêm `hint` (mô tả ý nghĩa) cho từng trạng thái trong STATUS_META."""
import io, re

p = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\dashboard\frontend\src\mock\domain\state.ts"
src = io.open(p, encoding="utf-8").read()

# Mô tả ý nghĩa — dùng cho bảng chú giải (component StatusSummary).
HINTS = {
    "FAULT": "Máy đang lỗi — cần người phụ trách xử lý",
    "MAINTENANCE": "Đang bảo trì theo kế hoạch, không tính vào thời gian chạy",
    "BLOCKED": "Bị tắc nghẽn — máy không thể đưa sản phẩm đi tiếp",
    "STARVED": "Thiếu nguyên liệu đầu vào — máy dừng vì không có nguyên liệu",
    "WARNING": "Có alarm nhưng máy vẫn chạy — cần theo dõi",
    "STOPPED": "Máy dừng có chủ ý — chờ nguyên liệu hoặc chờ lệnh",
    "STARTING": "Đang khởi động — chưa đạt tốc độ thiết kế",
    "RUNNING": "Đang chạy bình thường trong chế độ tự động",
    "OFF": "Máy tắt — không tham gia sản xuất",
    "NO_DATA": "Không đọc được trạng thái — kiểm tra kết nối hoặc chất lượng dữ liệu",
}

count = 0
for key, hint in HINTS.items():
    # chèn `hint` ngay sau `severity: N,` của block tương ứng
    pat = re.compile(
        r'(  ' + key + r': \{\n(?:.*\n)*?    severity: \d+,\n)',
    )
    def repl(m):
        global count
        count += 1
        return m.group(1) + f'    hint: "{hint}",\n'
    src, n = pat.subn(repl, src, count=1)
    if n == 0:
        print("KHONG khop:", key)

# thêm field vào type StatusMeta
src = src.replace(
    "  /** Mức ưu tiên: số nhỏ hơn = nghiêm trọng hơn. */\n  severity: number;",
    "  /** Mức ưu tiên: số nhỏ hơn = nghiêm trọng hơn. */\n"
    "  severity: number;\n"
    "  /** Mô tả ý nghĩa — dùng cho bảng chú giải trạng thái. */\n"
    "  hint?: string;",
)

io.open(p, "w", encoding="utf-8").write(src)
print(f"da them hint cho {count} trang thai")
