# Task: Refactor MES Smart Factory Dashboard UI/UX

Bạn là Senior Industrial UI/UX Designer và Senior Frontend Engineer, chuyên thiết kế hệ thống MES, SCADA và Smart Factory.

## 1. Context

Hiện tại dự án đã có:
- Factory Overview.
- Production Line Detail.
- Dark theme.
- Sidebar và top status bar.
- Production line cards.
- Machine status cards.
- Realtime telemetry và recent events (một phần đang sử dụng mock data).

Hãy xem các screenshot và ảnh design reference được cung cấp.

Mục tiêu là cải tiến giao diện hiện tại, không xây dựng lại dự án từ đầu.

## 2. Design requirements

Tuân thủ tài liệu MES_UI_UX_Design_Principles_AI_Guideline_v1.0.

Giữ lại:
- Dark industrial theme.
- Navigation structure.
- Factory → Line → Machine hierarchy.
- Semantic status colors.
- Các component hiện đang hoạt động tốt.

Cải tiến:
- Information hierarchy.
- KPI presentation.
- Production flow visualization.
- Machine status representation.
- Data freshness và data quality.
- Responsive layout.
- Alarm và event presentation.
- Spacing, typography và consistency.

## 3. Required screens

Triển khai bốn màn hình:

1. Factory Overview.
2. Production Line Detail.
3. Machine Detail.
4. Alarm & Event Center.

Các màn hình phải liên kết với nhau thông qua navigation và drill-down.

## 4. Industrial data requirements

Phải phân biệt:
- RUNNING
- IDLE
- STOPPED
- FAULT
- OFFLINE
- UNKNOWN
- MAINTENANCE

Phải phân biệt:
- Valid data.
- Null / Missing.
- Bad quality.
- Stale data.
- Disconnected.

Không được biến missing data thành 0.

Mọi KPI phải có định nghĩa và nguồn dữ liệu thống nhất. Không tự tạo công thức nghiệp vụ.

## 5. Implementation constraints

- Kiểm tra cấu trúc source code trước khi sửa.
- Tái sử dụng component hiện có.
- Không tự ý thay đổi backend/API contract.
- Không tạo mock data mới nếu đã có nguồn dữ liệu.
- Nếu cần mock, phải tách riêng và đánh dấu MOCK.
- Không tạo button không có chức năng.
- Không làm mất các chức năng hiện có.
- Không tự suy diễn alarm severity hoặc machine state mapping.

## 6. Expected result

Sau khi hoàn thành:
- Bốn màn hình có cùng Design System.
- Navigation và drill-down hoạt động.
- Responsive phù hợp desktop và industrial touchscreen mục tiêu.
- Các trạng thái dữ liệu được biểu diễn chính xác.
- Có loading, empty, error và offline states.
- Không có lỗi hiển thị hoặc dữ liệu không nhất quán.

Trước khi code, hãy phân tích source code và đề xuất kế hoạch thay đổi. Sau đó triển khai theo từng màn hình, kiểm tra ảnh hưởng của từng thay đổi và báo cáo những phần còn thiếu dữ liệu nghiệp vụ.

Ưu tiên tính chính xác, khả năng vận hành và tính nhất quán hơn hiệu ứng trang trí.