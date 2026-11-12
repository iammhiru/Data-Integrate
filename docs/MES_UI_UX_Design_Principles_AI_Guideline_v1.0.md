# MES UI/UX Design Principles & AI Implementation Guideline

**Phiên bản:** 1.0\
**Ngày:** 12/11/2026\
**Phạm vi:** Web-based Manufacturing Execution System (MES), Smart
Factory, Industry 4.0\
**Mục đích:** Tài liệu quy chuẩn để AI assistant, UI/UX designer và
frontend developer thiết kế, triển khai, review và mở rộng giao diện MES
nhất quán.

------------------------------------------------------------------------

## 1. Mục tiêu và nguyên tắc nền tảng

Giao diện MES phải giúp đúng người dùng:

1.  Nhìn thấy đúng thông tin theo vai trò và ngữ cảnh.
2.  Hiểu đúng trạng thái sản xuất, thiết bị, chất lượng và dữ liệu.
3.  Thực hiện nhiệm vụ chính xác với ít thao tác và ít sai sót.
4.  Nhận biết dữ liệu mới, dữ liệu cũ, dữ liệu lỗi và tình trạng mất kết
    nối.
5.  Không nhầm lẫn giữa thông báo, cảnh báo, trạng thái thiết bị và
    trạng thái dữ liệu.
6.  Không tạo đường đi vòng qua cơ chế phân quyền, interlock hoặc biện
    pháp an toàn của OT.

**Định nghĩa chất lượng:** UI MES chuyên nghiệp không chỉ đẹp. UI phải
rõ ràng, nhất quán, dễ học, hiệu quả khi vận hành, đáng tin cậy và phù
hợp môi trường sử dụng thực tế.

### 1.1. Thứ tự ưu tiên khi có xung đột

Khi các mục tiêu thiết kế mâu thuẫn, áp dụng thứ tự ưu tiên:

1.  An toàn vận hành và tính đúng đắn của thông tin.
2.  Khả năng hoàn thành tác vụ và giảm lỗi người dùng.
3.  Khả năng đọc, nhận biết trạng thái và độ tin cậy dữ liệu.
4.  Tính nhất quán và khả năng bảo trì.
5.  Thẩm mỹ và hiệu ứng trang trí.

Không hy sinh khả năng nhận biết alarm, data quality hoặc trạng thái máy
để làm giao diện tối giản hơn.

------------------------------------------------------------------------

## 2. Phạm vi áp dụng và phân biệt loại giao diện

MES có nhiều loại màn hình. Không áp dụng một mẫu UI duy nhất cho tất
cả.

  -----------------------------------------------------------------------
  Loại giao diện          Mục đích                Định hướng
  ----------------------- ----------------------- -----------------------
  Operational HMI / Line  Theo dõi vận hành trực  Tham chiếu ISA-101; ưu
  Monitoring              tiếp                    tiên nhận biết trạng
                                                  thái, alarm và dữ liệu

  Production Execution    Thực hiện lệnh, xác     Task-oriented, rõ ràng,
                          nhận sản lượng, thao    ít bước, validation
                          tác công đoạn           chặt

  Quality Management      Inspection, NG,         Chính xác, truy xuất
                          disposition,            được, thể hiện rõ trạng
                          traceability            thái và lịch sử

  Equipment / Maintenance Theo dõi máy, downtime, Trạng thái thiết bị,
                          bảo trì                 lịch sử sự kiện, dữ
                                                  liệu theo thời gian

  Planning / Management   Kế hoạch, KPI, tổng     Tổng hợp, so sánh,
  Dashboard               quan nhà máy            drill-down, hỗ trợ
                                                  quyết định

  Administration          Người dùng, role, cấu   Bảo mật, kiểm soát thay
                          hình, audit             đổi, biểu mẫu rõ ràng
  -----------------------------------------------------------------------

**Lưu ý:** MES không đồng nghĩa với SCADA/HMI. ISA-101 là tham chiếu
mạnh cho màn hình giám sát/vận hành công nghiệp, nhưng không thay thế
toàn bộ nguyên tắc UX cho ERP-like forms, báo cáo, quản trị hay quy
trình chất lượng.

------------------------------------------------------------------------

## 3. User-centered và role-based design

### 3.1. Thiết kế theo vai trò và nhiệm vụ

Phải xác định nhóm người dùng trước khi thiết kế màn hình. Ví dụ:

  -----------------------------------------------------------------------
  Vai trò                 Nhiệm vụ thường gặp     Thông tin/ưu tiên
  ----------------------- ----------------------- -----------------------
  Operator                Thực hiện công đoạn,    Work instruction,
                          xác nhận thao tác và    order, machine state,
                          sản lượng               input nhanh

  Line Leader             Điều phối line, theo    Line status, output,
                          dõi tiến độ, xử lý vấn  manpower, downtime,
                          đề ban đầu              alarms

  Supervisor              Kiểm soát nhiều line/ca KPI, production plan vs
                                                  actual, exceptions

  Quality Engineer        Kiểm tra và xử lý chất  Inspection, NG,
                          lượng                   disposition,
                                                  traceability

  Maintenance Engineer    Xử lý sự cố và bảo trì  Equipment health,
                                                  alarms, downtime, work
                                                  orders

  Planner                 Lập và theo dõi kế      Schedule, order,
                          hoạch                   capacity, material
                                                  readiness

  Factory Manager         Đánh giá hoạt động nhà  OEE, output, quality,
                          máy                     delivery, trends

  Administrator           Quản trị hệ thống       Users, roles,
                                                  configuration, audit
  -----------------------------------------------------------------------

Không giả định mọi nhà máy có cùng vai trò. Phải xác minh role, workflow
và trách nhiệm thực tế của dự án.

### 3.2. Quy tắc

-   Chỉ đưa thông tin và hành động phù hợp với nhiệm vụ của người dùng
    lên màn hình.
-   Phân biệt quyền xem, quyền tạo, quyền sửa, quyền xác nhận và quyền
    thực thi.
-   Không dùng việc ẩn nút ở frontend làm cơ chế bảo mật duy nhất;
    backend phải kiểm tra quyền.
-   Không tạo dashboard "one-size-fits-all".
-   Giữ ngữ cảnh làm việc (site, factory, area, line, shift, order) rõ
    ràng.
-   Khi thay đổi context/filter, phải thể hiện context hiện tại và tránh
    làm mất dữ liệu nhập dở.

### 3.3. User research

Trước khi chốt thiết kế, cần xác minh: - Ai sử dụng màn hình? - Người
dùng đứng/ngồi ở đâu, cách màn hình bao xa? - Thiết bị là desktop,
industrial PC, touchscreen, tablet hay wall display? - Môi trường có
găng tay, ánh sáng mạnh/yếu, tiếng ồn hoặc thời gian thao tác hạn chế
không? - Tác vụ thường xuyên nhất và tác vụ rủi ro cao nhất là gì? -
Điều gì xảy ra khi mạng hoặc nguồn dữ liệu bị gián đoạn?

Không tự suy diễn câu trả lời. Nếu thiếu dữ kiện, AI phải liệt kê giả
định và hỏi người dùng khi giả định ảnh hưởng đáng kể đến thiết kế.

------------------------------------------------------------------------

## 4. Information architecture và navigation

### 4.1. Cấu trúc thông tin

Tổ chức module theo nghiệp vụ thực tế, không theo cấu trúc database hoặc
tên service backend.

Cấu trúc tham khảo:

``` text
MES
├── Dashboard
│   ├── Factory Overview
│   ├── Production Overview
│   └── Line Monitoring
├── Production
│   ├── Production Orders
│   ├── Work Orders
│   ├── Dispatching
│   └── Production Tracking
├── Equipment
│   ├── Machine Monitoring
│   ├── Downtime
│   └── Maintenance
├── Quality
│   ├── Inspection
│   ├── Non-conformance
│   └── Traceability
├── Material
│   ├── Material Tracking
│   └── Consumption
├── Analytics
│   ├── OEE
│   ├── Production Reports
│   └── Quality Reports
└── Administration
    ├── Users & Roles
    ├── Configuration
    └── Audit Logs
```

Đây chỉ là cấu trúc khởi điểm. Chỉ giữ module thực sự nằm trong scope
sản phẩm.

### 4.2. Navigation rules

-   Duy trì App Shell, sidebar/top navigation, page header và breadcrumb
    nhất quán.
-   Thể hiện rõ menu đang được chọn.
-   Nhóm menu theo nghiệp vụ; tránh quá nhiều cấp lồng nhau.
-   Tên menu phải dùng thuật ngữ mà người dùng nhà máy hiểu.
-   Icon phải có ý nghĩa, đi kèm label khi ý nghĩa không hiển nhiên.
-   Không tạo navigation khác nhau tùy tiện giữa các module.
-   Hỗ trợ deep link khi phù hợp để người dùng mở trực tiếp một đối
    tượng hoặc màn hình.
-   Không dùng màu sắc đơn thuần để biểu thị menu active.

------------------------------------------------------------------------

## 5. Information hierarchy và bố cục màn hình

### 5.1. Ba tầng thông tin

1.  **Overview:** thông tin cần nhận biết nhanh (KPI chính, trạng thái
    tổng thể, cảnh báo quan trọng).
2.  **Operational details:** thông tin giải thích trạng thái và hỗ trợ
    hành động.
3.  **Deep details / history:** giao dịch, lịch sử, raw values, audit và
    phân tích chi tiết.

Ưu tiên overview trước, details sau; không hiển thị mọi trường dữ liệu
chỉ vì backend cung cấp.

### 5.2. Layout rules

-   Mỗi màn hình cần có một mục tiêu chính và một tiêu đề mô tả đúng mục
    tiêu.
-   Nhóm nội dung theo tác vụ hoặc đối tượng nghiệp vụ.
-   Dùng grid và spacing nhất quán.
-   Đặt hành động chính ở vị trí dễ tìm, không cạnh tranh với hành động
    nguy hiểm.
-   Dùng whitespace để phân tách nhóm; không bọc mọi thành phần bằng
    card hoặc border.
-   Không nhồi nhét quá nhiều KPI, chart hoặc bảng lên một màn hình.
-   Ưu tiên bố cục có thể quét nhanh bằng mắt.
-   Với dashboard, chỉ chọn chỉ số hỗ trợ quyết định; mỗi KPI cần định
    nghĩa, đơn vị, khoảng thời gian và nguồn dữ liệu rõ ràng.

### 5.3. Progressive disclosure

Chỉ hiển thị mức thông tin cần thiết cho tác vụ hiện tại. Cho phép mở
rộng chi tiết qua tab, drawer, detail page hoặc drill-down. Không giấu
thông tin an toàn hoặc alarm quan trọng sau nhiều lớp tương tác.

------------------------------------------------------------------------

## 6. Design tokens và visual language

Phải tạo Design System dùng chung. Các giá trị dưới đây là **điểm khởi
đầu đề xuất**, không phải giá trị bắt buộc của ISA/ISO. Cần kiểm thử với
thiết bị và người dùng thực tế.

### 6.1. Typography

  Token                      Giá trị khởi điểm
  ------------------------ -------------------
  Page title                         24--28 px
  Section heading                    18--20 px
  Card title                         14--16 px
  Body                               14--16 px
  Table content                      13--14 px
  Supporting text                    12--13 px
  KPI                                28--36 px
  Large wall-display KPI             36--48 px

Quy tắc: - Dùng tối đa 1--2 font family nếu không có yêu cầu đặc biệt. -
Duy trì thang font-size và font-weight rõ ràng. - Không dùng supporting
text nhỏ cho dữ liệu vận hành quan trọng. - Không viết toàn bộ nội dung
bằng chữ in hoa. - Dùng tabular numerals cho số lượng, KPI, thời gian và
dữ liệu dạng cột. - Hiển thị đơn vị đo cạnh giá trị.

### 6.2. Spacing

Dùng hệ thống 4px hoặc 8px nhất quán. Ví dụ:

  Token     Giá trị
  ------- ---------
  xs           4 px
  sm           8 px
  md          12 px
  lg          16 px
  xl          24 px
  2xl         32 px
  3xl         48 px

### 6.3. Semantic colors

Màu phải có ý nghĩa nhất quán. Palette cụ thể cần được kiểm tra độ tương
phản và phù hợp với môi trường.

  Semantic token     Ý nghĩa                    Màu tham khảo
  ------------------ -------------------------- ---------------
  Success / Normal   Bình thường, hoàn tất      `#16A34A`
  Warning            Cần chú ý                  `#D97706`
  Critical / Error   Sự cố nghiêm trọng         `#DC2626`
  Information        Thông tin                  `#2563EB`
  Neutral            Trung tính/chưa xác định   `#64748B`

Quy tắc: - Không dùng màu đỏ làm màu trang trí phổ biến. - Không dùng
màu sắc làm tín hiệu duy nhất; kết hợp text, icon, shape hoặc pattern. -
Không gán màu cho trạng thái nếu chưa xác định ngữ nghĩa nghiệp vụ. -
Không mặc định mọi trạng thái STOP đều là lỗi; STOPPED, IDLE, OFFLINE và
FAULT phải phân biệt. - Không để cùng một màu mang ý nghĩa khác nhau ở
các module nếu không có lý do được ghi nhận. - Cần hỗ trợ light/dark
theme nếu scope yêu cầu; kiểm thử riêng từng theme.

### 6.4. Surface, border và effects

-   Hạn chế shadow nặng, gradient và hiệu ứng trang trí.
-   Dùng border và background để tạo phân cấp có chủ đích.
-   Border radius, elevation và icon size phải có token.
-   Tránh hiệu ứng nhấp nháy liên tục; chuyển động chỉ dùng khi giúp
    nhận biết thay đổi quan trọng.
-   Không dùng animation để biểu diễn trạng thái duy nhất.

------------------------------------------------------------------------

## 7. Trạng thái thiết bị và dữ liệu công nghiệp

Đây là yêu cầu đặc thù, phải được xem là một phần cốt lõi của UI MES.

### 7.1. Không đồng nhất trạng thái máy với trạng thái kết nối

Ít nhất cần phân biệt các khái niệm:

-   **RUNNING:** máy đang chạy theo định nghĩa nghiệp vụ/nguồn dữ liệu.
-   **IDLE:** máy sẵn sàng nhưng không sản xuất.
-   **STOPPED:** máy dừng có chủ đích hoặc trạng thái dừng được xác
    nhận.
-   **FAULT:** máy có lỗi được xác nhận.
-   **OFFLINE / DISCONNECTED:** mất kết nối hoặc không nhận được dữ liệu
    nguồn.
-   **UNKNOWN:** chưa đủ thông tin để kết luận.
-   **MAINTENANCE:** đang trong trạng thái bảo trì nếu nghiệp vụ có định
    nghĩa.

Không tự suy ra trạng thái máy từ một tag đơn lẻ nếu logic nghiệp vụ
chưa được xác nhận.

### 7.2. Data quality và freshness

Với dữ liệu công nghiệp, UI cần phân biệt:

  -----------------------------------------------------------------------
  Trường hợp              Ý nghĩa                 Cách thể hiện
  ----------------------- ----------------------- -----------------------
  Value = 0               Giá trị đo thực sự bằng Hiển thị `0`
                          0                       

  Null / Missing          Không có giá trị        Hiển thị `—` hoặc "No
                                                  data"

  Bad quality             Nguồn báo dữ liệu không Hiển thị quality state
                          đáng tin cậy            

  Stale                   Dữ liệu cũ hơn ngưỡng   Hiển thị stale
                          cho phép                indicator và thời điểm

  Disconnected            Mất kết nối nguồn       Hiển thị trạng thái kết
                                                  nối

  Loading                 Đang truy xuất          Loading state, không
                                                  giả lập giá trị

  Error                   Không thể lấy dữ liệu   Error state và khả năng
                                                  thử lại phù hợp
  -----------------------------------------------------------------------

Không được thay null, bad quality, stale hoặc disconnected thành số 0.
Không được hiển thị dữ liệu cũ như dữ liệu realtime.

### 7.3. Metadata tối thiểu

Tùy loại dữ liệu, nên có: - Value và engineering unit. - Source
timestamp (thời điểm nguồn ghi nhận). - Received timestamp (thời điểm hệ
thống nhận). - Quality/status. - Source/equipment/tag identifier khi cần
truy vết. - Freshness threshold hoặc quy tắc xác định stale. -
Sampling/aggregation interval với dữ liệu định kỳ.

Phân biệt source timestamp và received timestamp. Không gọi cả hai là
"Last Updated" nếu người dùng có thể hiểu nhầm.

### 7.4. Realtime behavior

-   Chỉ cập nhật vùng dữ liệu bị thay đổi; tránh refresh toàn trang
    không cần thiết.
-   Không để cập nhật realtime làm mất focus, selection, nội dung form
    hoặc vị trí scroll.
-   Hiển thị trạng thái kết nối và thời điểm nhận dữ liệu gần nhất.
-   Có reconnect behavior và trạng thái khi reconnect.
-   Tránh animation gây mất tập trung khi giá trị thay đổi liên tục.
-   Có thể gom/throttle cập nhật hiển thị để giữ hiệu năng, nhưng không
    được làm sai lệch ý nghĩa dữ liệu hoặc che giấu alarm.
-   Ngưỡng stale phải phụ thuộc loại tag và chu kỳ cập nhật đã thống
    nhất; không dùng một timeout chung cho mọi tag.
-   Nếu dữ liệu được tổng hợp hoặc lấy mẫu, phải thể hiện khoảng thời
    gian/aggregation phù hợp.

------------------------------------------------------------------------

## 8. Alarm, event và notification

### 8.1. Phân biệt

-   **Alarm:** điều kiện bất thường cần người có trách nhiệm chú ý hoặc
    hành động theo quy trình.
-   **Event:** sự kiện được ghi nhận trong hệ thống.
-   **Notification:** thông tin được gửi đến người dùng, không nhất
    thiết yêu cầu hành động khẩn cấp.

Không biến mọi event thành alarm. Không dùng màu đỏ cho notification
thông thường.

### 8.2. Alarm UI

Một alarm record nên hỗ trợ các thông tin phù hợp với hệ thống: - Alarm
ID. - Severity/priority. - Source (site, area, line, machine,
process). - Description. - Trigger time. - Current state. -
Acknowledgement state. - Acknowledged by / time. -
Clear/return-to-normal time nếu có. - Hướng dẫn hoặc quy trình xử lý đã
được phê duyệt.

Quy tắc: - Alarm phải có phân cấp và cách sắp xếp dễ hiểu. - Có lọc theo
severity, source, thời gian và trạng thái. - Acknowledge không đồng
nghĩa với clear hoặc khắc phục. - Không tự động xóa lịch sử alarm sau
khi acknowledge. - Tránh alarm flood và duplicate notification. - Không
tự tạo recommended action mang tính an toàn nếu chưa được chuyên gia/nhà
máy phê duyệt. - Âm thanh, nhấp nháy và màu phải theo alarm philosophy
và tiêu chuẩn áp dụng của dự án.

------------------------------------------------------------------------

## 9. Data visualization và dashboard

### 9.1. Chọn biểu đồ theo câu hỏi nghiệp vụ

  Nhu cầu                              Thành phần phù hợp
  ------------------------------------ -------------------------------------
  Một KPI so với target                KPI card, bullet/progress indicator
  Xu hướng theo thời gian              Line chart
  So sánh line/machine/shift           Bar chart
  Phân tích nguyên nhân lỗi/downtime   Pareto chart
  Phân bố dữ liệu                      Histogram/box plot khi phù hợp
  Trạng thái nhiều thiết bị            Status matrix/list
  Trình tự sự kiện                     Timeline/event list

### 9.2. Chart rules

-   Tránh 3D chart và hiệu ứng không mang thông tin.
-   Có title mô tả nội dung, đơn vị, time range và legend khi cần.
-   Trục và scale phải trung thực; không cắt trục gây hiểu sai.
-   Màu series nhất quán giữa các màn hình.
-   Tooltip cung cấp giá trị chính xác và timestamp khi phù hợp.
-   Có empty/loading/error state.
-   Không dùng pie chart cho quá nhiều nhóm hoặc khi cần so sánh chính
    xác.
-   Cung cấp bảng hoặc dữ liệu thay thế khi chart không đủ khả năng truy
    cập.
-   Phân biệt actual, target, forecast và derived metric.
-   Mỗi KPI phải có công thức/định nghĩa nghiệp vụ, nguồn và phạm vi
    thời gian được thống nhất.

### 9.3. Drill-down

Thiết kế đường đi phân tích hợp lý, ví dụ:

`Factory → Area → Line → Machine → Tag / Event`

Drill-down phải giữ context (thời gian, ca, line, product/order) khi phù
hợp và cho phép người dùng quay lại cấp trước.

------------------------------------------------------------------------

## 10. Form, table và data entry

### 10.1. Forms

-   Label rõ ràng; placeholder không thay thế label.
-   Đánh dấu required/optional nhất quán.
-   Validation gần trường nhập và giải thích cách sửa.
-   Giữ lại dữ liệu hợp lệ khi có lỗi.
-   Dùng input type và format đúng với dữ liệu.
-   Kiểm soát đơn vị, precision và giới hạn giá trị.
-   Tránh bắt người dùng nhập lại dữ liệu đã có.
-   Có trạng thái saving/saved/failed khi lưu bất đồng bộ.
-   Với thao tác ảnh hưởng sản xuất/chất lượng, cần xác nhận theo mức
    rủi ro và workflow đã duyệt.
-   Không yêu cầu xác nhận cho mọi hành động nhỏ; tránh confirmation
    fatigue.

### 10.2. Tables

Cân nhắc hỗ trợ: - Sorting và filtering. - Pagination hoặc
virtualization cho dataset lớn. - Sticky header khi bảng dài. - Column
visibility/resizing khi cần. - Row selection và bulk action có kiểm
soát. - Export theo quyền và giới hạn dữ liệu. - Empty, loading, error
và no-result state riêng biệt. - Định dạng ngày giờ, số, đơn vị và trạng
thái nhất quán.

Không render hàng nghìn dòng DOM cùng lúc nếu ảnh hưởng hiệu năng. Không
mặc định dùng pagination nếu tác vụ cần quét liên tục; chọn theo
workflow.

### 10.3. Destructive / high-impact actions

-   Dùng label mô tả hậu quả cụ thể (ví dụ "Cancel production order"),
    không dùng label mơ hồ.
-   Phân biệt primary action và destructive action.
-   Xác nhận khi hành động khó hoàn tác hoặc ảnh hưởng vận hành.
-   Hiển thị đối tượng và hậu quả trước khi xác nhận.
-   Backend phải xác thực quyền và trạng thái nghiệp vụ tại thời điểm
    thực thi.
-   Ghi audit trail cho hành động quan trọng.

------------------------------------------------------------------------

## 11. Responsive, adaptive và môi trường công nghiệp

Không chỉ thiết kế cho một kích thước desktop.

  -----------------------------------------------------------------------
  Thiết bị/ngữ cảnh                   Định hướng
  ----------------------------------- -----------------------------------
  Office desktop                      Dashboard, bảng, phân tích nhiều
                                      cột

  Industrial PC                       Nội dung dễ đọc, thao tác ổn định

  Touchscreen station                 Target lớn, thao tác đơn giản,
                                      không phụ thuộc hover

  Tablet                              Card/layout thích ứng, thao tác tại
                                      hiện trường

  Mobile                              Quick status, notification, tác vụ
                                      ngắn

  Wall display                        KPI lớn, trạng thái tổng quan, xem
                                      từ xa
  -----------------------------------------------------------------------

Quy tắc: - Thiết kế theo thiết bị và ngữ cảnh sử dụng, không chỉ co giãn
layout. - Không phụ thuộc hover. - Touch target phải đủ lớn cho môi
trường thực tế; WCAG 2.2 AA có tiêu chí tối thiểu 24×24 CSS px với các
ngoại lệ. Với touchscreen công nghiệp, cân nhắc mục tiêu lớn hơn (ví dụ
40--48 CSS px) và kiểm thử với găng tay/khoảng cách thao tác. - Đảm bảo
chữ và trạng thái đọc được ở khoảng cách sử dụng thực tế. - Không đặt
thao tác nguy hiểm cạnh nút thường dùng. - Kiểm thử ở độ phân giải,
browser và thiết bị mục tiêu đã thống nhất.

------------------------------------------------------------------------

## 12. Accessibility

Hướng đến WCAG 2.2 Level AA cho phần giao diện web trong phạm vi phù
hợp.

-   Độ tương phản chữ/nền đáp ứng tiêu chí WCAG.
-   Không dùng màu sắc làm phương tiện duy nhất truyền đạt trạng thái.
-   Có focus indicator rõ ràng.
-   Hỗ trợ keyboard navigation cho tác vụ phù hợp.
-   Label và accessible name cho controls.
-   Lỗi form được mô tả bằng text, không chỉ bằng màu.
-   Không dùng animation gây khó chịu; tôn trọng reduced-motion
    preference khi phù hợp.
-   Không tự động chuyển trang hoặc mất nội dung nhập khi người dùng
    chưa chủ động.
-   Kiểm thử accessibility bằng công cụ và thao tác thực tế; không chỉ
    dựa vào kiểm tra tự động.

Không tuyên bố "WCAG compliant" nếu chưa có đánh giá đủ phạm vi.

------------------------------------------------------------------------

## 13. Security, permissions và auditability

-   Frontend chỉ hỗ trợ trải nghiệm quyền; backend là nơi thực thi
    authorization.
-   Phân biệt view/create/edit/approve/execute/delete/export.
-   Không đưa secret, token nhạy cảm hoặc thông tin xác thực vào UI/log
    client.
-   Không để UI bỏ qua interlock, safety logic hoặc quy trình điều khiển
    OT.
-   Xác nhận danh tính/quyền theo cơ chế hệ thống.
-   Session timeout và re-authentication phải phù hợp chính sách bảo
    mật.
-   Ghi nhận actor, timestamp, action, target và kết quả cho thao tác
    quan trọng.
-   Không cho phép sửa/xóa audit record trái với chính sách lưu trữ.
-   Áp dụng phân quyền theo site/area/line/object khi nghiệp vụ yêu cầu.
-   Thiết kế UI phải phù hợp kiến trúc phân vùng IT/OT và chính sách OT
    security.

------------------------------------------------------------------------

## 14. Performance và reliability

-   Tối ưu thời gian tải trang và phản hồi thao tác theo SLA dự án.
-   Tránh tải dữ liệu không cần thiết; hỗ trợ pagination, virtualization
    hoặc lazy loading phù hợp.
-   Tránh re-render toàn bộ màn hình khi một tag thay đổi.
-   Có loading state nhưng không nhấp nháy hoặc skeleton quá mức.
-   Có retry/reconnect có kiểm soát; không gửi lặp thao tác ghi gây side
    effect.
-   Với thao tác ghi, xử lý idempotency hoặc chống double-submit ở tầng
    phù hợp.
-   Không hiển thị trạng thái thành công trước khi server xác nhận.
-   Khi API lỗi, giữ lại dữ liệu nhập hợp lệ và thông báo rõ trạng thái.
-   Phân biệt lỗi UI, lỗi mạng, lỗi server, lỗi validation và lỗi nghiệp
    vụ.
-   Đo hiệu năng trên dữ liệu và thiết bị gần với production.

------------------------------------------------------------------------

## 15. Component architecture và Design System

Xây dựng Design System dùng chung trước khi phát triển nhiều module.

### 15.1. Design tokens

-   Colors và semantic status.
-   Typography.
-   Spacing.
-   Radius.
-   Elevation/shadow.
-   Breakpoints.
-   Icon sizes.
-   Motion/duration.

### 15.2. Core components

-   Button, Input, Select, Checkbox, Radio.
-   Modal, Drawer, Tabs, Tooltip, Popover.
-   Badge, Alert, Toast.
-   Card, Breadcrumb, Sidebar, PageHeader.
-   DataTable, Pagination, FilterBar.
-   Loading, EmptyState, ErrorState.

### 15.3. Industrial components

-   MachineStatus.
-   ProductionLineOverview.
-   OEEKPI.
-   AlarmPanel.
-   DowntimeTimeline.
-   ProductionProgress.
-   EquipmentHierarchy.
-   DataQualityIndicator.
-   ConnectionStatus.
-   RealtimeValue.
-   TraceabilityTimeline.

### 15.4. Component rules

-   Component phải có API, variants và states được định nghĩa.
-   Không tạo component trùng chức năng chỉ vì khác module.
-   Không hard-code màu/spacing trong từng page khi đã có token.
-   Component phải hỗ trợ loading, disabled, error và empty state khi
    phù hợp.
-   Tài liệu hóa ví dụ sử dụng và trường hợp không nên sử dụng.
-   Thay đổi component dùng chung phải kiểm tra ảnh hưởng toàn hệ thống.

------------------------------------------------------------------------

## 16. AI-specific implementation rules

Phần này là chỉ dẫn bắt buộc cho AI khi tạo hoặc chỉnh sửa UI MES.

### 16.1. Trước khi code

AI phải: 1. Đọc cấu trúc dự án, framework, routing, component library và
coding conventions hiện tại. 2. Xác định loại màn hình và vai trò người
dùng. 3. Xác định workflow chính và hành động có rủi ro. 4. Kiểm tra
Design System/token/component đã có trước khi tạo mới. 5. Xác định dữ
liệu thật, API contract, loading/error/empty states. 6. Nêu rõ giả định
nếu yêu cầu nghiệp vụ chưa đủ. 7. Không tự tạo KPI, công thức OEE,
machine state mapping, alarm severity hoặc business rule khi chưa có
nguồn xác nhận.

### 16.2. Khi triển khai

-   Ưu tiên tái sử dụng component và token hiện có.
-   Giữ nhất quán App Shell và navigation.
-   Tách component theo trách nhiệm; tránh page component quá lớn.
-   Không nhúng dữ liệu giả vào production path.
-   Mock data phải được đánh dấu rõ và tách khỏi API thật.
-   Không tự ý thay đổi API contract, database schema hoặc business
    logic khi chỉ được yêu cầu chỉnh UI.
-   Không tự thêm chức năng hoặc trường dữ liệu chưa được yêu cầu.
-   Không hiển thị dữ liệu công nghiệp thiếu quality/freshness như dữ
    liệu hợp lệ.
-   Không dùng màu sắc, animation hoặc icon thay thế thông tin trạng
    thái.
-   Đảm bảo mọi nút đều có hành vi thực; không tạo control trang trí giả
    tương tác.
-   Xử lý permission, disabled state và error state đúng.
-   Không tuyên bố đã tích hợp realtime nếu chỉ polling/mock hoặc chưa
    xác minh luồng dữ liệu.

### 16.3. Khi review

AI phải tự kiểm tra: - Có đúng mục tiêu màn hình và role không? - Có
đúng design token không? - Có đủ loading/empty/error/success state
không? - Có phân biệt null/zero/stale/bad quality/offline không? - Có
nguy cơ nhầm lẫn trạng thái hoặc hành động không? - Có keyboard/touch
interaction phù hợp không? - Có gây mất dữ liệu nhập khi
refresh/re-render không? - Có tạo thêm component trùng lặp không? - Có
ảnh hưởng màn hình khác không? - Có dùng dữ liệu hoặc quy tắc nghiệp vụ
chưa được xác nhận không?

### 16.4. Khi thiếu thông tin

AI không được bịa: - Công thức KPI/OEE. - Mapping tag → machine
status. - Alarm severity và response procedure. - Ngưỡng
stale/freshness. - Permission matrix. - Quy trình
approve/release/disposition. - Quy tắc chất lượng và truy xuất.

AI phải ghi `[NEEDS CONFIRMATION]` hoặc hỏi người dùng nếu thiếu thông
tin ảnh hưởng đến tính đúng đắn.

------------------------------------------------------------------------

## 17. Quy trình thiết kế và nghiệm thu

1.  **Discovery:** xác định người dùng, nhiệm vụ, môi trường và thiết
    bị.
2.  **Information Architecture:** module, navigation, hierarchy và
    context.
3.  **Design System:** tokens, core components, industrial components.
4.  **Wireframe:** xác minh workflow và bố cục trước visual design.
5.  **Prototype:** mô phỏng trạng thái bình thường, loading, error,
    offline và alarm.
6.  **Usability Test:** thử với người dùng đại diện trên thiết bị thực
    tế.
7.  **Implementation:** phát triển theo component và API contract.
8.  **Verification:** kiểm thử chức năng, accessibility, performance,
    data correctness và security.
9.  **Continuous Improvement:** đo task completion, task time, error
    rate và feedback.

### 17.1. Tiêu chí nghiệm thu

  Nhóm            Tiêu chí
  --------------- --------------------------------------------------------
  Usability       Task completion rate, time on task
  Accuracy        User error rate, data interpretation errors
  Consistency     Design system compliance
  Data trust      Correct freshness, quality and status representation
  Performance     Page load, interaction latency, update cost
  Accessibility   Contrast, keyboard, focus, target size
  Reliability     Error handling, reconnect, duplicate action prevention
  Security        Permission enforcement, auditability

Mỗi dự án phải xác định ngưỡng nghiệm thu bằng yêu cầu và đo đạc thực
tế. Không tự đặt số liệu đạt chuẩn nếu chưa có SLA hoặc kết quả test.

------------------------------------------------------------------------

## 18. Checklist review nhanh

### Visual & consistency

-   [ ] Color, typography, spacing và component nhất quán.
-   [ ] Có hierarchy rõ ràng.
-   [ ] Không lạm dụng màu, shadow, border hoặc animation.
-   [ ] Nội dung quan trọng đọc được trên thiết bị mục tiêu.

### Navigation & workflow

-   [ ] Menu đúng nghiệp vụ và role.
-   [ ] Tác vụ chính dễ tìm.
-   [ ] Context/filter được thể hiện rõ.
-   [ ] Không có bước hoặc popup không cần thiết.

### Industrial data

-   [ ] Có unit và timestamp phù hợp.
-   [ ] Phân biệt zero, null, bad quality, stale và offline.
-   [ ] Phân biệt RUNNING, IDLE, STOPPED, FAULT, OFFLINE, UNKNOWN.
-   [ ] Có trạng thái loading/error/reconnect.
-   [ ] KPI có định nghĩa, phạm vi và nguồn.

### Alarm & safety

-   [ ] Phân biệt alarm, event và notification.
-   [ ] Có severity và acknowledgement state.
-   [ ] Acknowledge không bị hiểu là clear.
-   [ ] Không bypass interlock hoặc safety control.

### Interaction & security

-   [ ] Form validation rõ.
-   [ ] Destructive action có kiểm soát.
-   [ ] Backend enforce authorization.
-   [ ] Hành động quan trọng có audit.
-   [ ] Nút và control có hành vi thật.

### Responsive & accessibility

-   [ ] Test trên thiết bị thực tế.
-   [ ] Không phụ thuộc hover.
-   [ ] Touch target phù hợp.
-   [ ] Keyboard/focus/contrast được kiểm tra.

------------------------------------------------------------------------

## 19. Tài liệu tham khảo và cách áp dụng

Các tài liệu dưới đây là nguồn tham chiếu. Cần kiểm tra edition,
amendment, trạng thái hiệu lực và quyền truy cập chính thức trước khi
đưa vào hồ sơ tuân thủ của dự án. Không coi guideline này là chứng nhận
tuân thủ tiêu chuẩn.

### 19.1. Tiêu chuẩn công nghiệp

1.  **ISA-101 -- Human Machine Interfaces for Process Automation
    Systems**\
    Website tổ chức: https://www.isa.org/\
    Phạm vi tham chiếu: HMI philosophy, lifecycle, design,
    implementation, operation và maintenance.\
    Áp dụng mạnh cho màn hình giám sát/vận hành công nghiệp; không áp
    dụng máy móc cho mọi form quản trị MES.

2.  **ISA-18.2 -- Management of Alarm Systems for the Process
    Industries**\
    Website tổ chức: https://www.isa.org/\
    Phạm vi tham chiếu: alarm philosophy, rationalization,
    prioritization, presentation, response, lifecycle và performance
    monitoring.\
    Áp dụng khi MES/HMI hiển thị hoặc quản lý alarm. Cần phân biệt alarm
    với event/notification.

3.  **ISA-95 / IEC 62264 -- Enterprise-Control System Integration**\
    Website tổ chức: https://www.isa.org/\
    IEC Webstore: https://webstore.iec.ch/\
    Phạm vi tham chiếu: mô hình và tích hợp giữa enterprise systems và
    manufacturing/control operations; terminology và information
    models.\
    Dùng để tổ chức ngữ cảnh và thông tin nghiệp vụ MES, không phải bộ
    quy tắc visual UI.

4.  **ISO 9241-210:2019 -- Ergonomics of human-system interaction ---
    Human-centred design for interactive systems**\
    https://www.iso.org/standard/77520.html\
    Phạm vi tham chiếu: human-centred design, hiểu người dùng/nhiệm
    vụ/ngữ cảnh, đánh giá và lặp cải tiến.

5.  **W3C -- Web Content Accessibility Guidelines (WCAG) 2.2**\
    https://www.w3.org/TR/WCAG22/\
    Phạm vi tham chiếu: perceivable, operable, understandable, robust;
    contrast, keyboard, focus, target size và accessibility.\
    Mục tiêu khuyến nghị cho web UI là WCAG 2.2 Level AA trong phạm vi
    áp dụng; cần audit thực tế trước khi tuyên bố compliance.

6.  **NIST SP 800-82 Rev. 3 -- Guide to Operational Technology (OT)
    Security**\
    https://csrc.nist.gov/pubs/sp/800/82/r3/final\
    Phạm vi tham chiếu: OT architecture, security controls,
    availability, safety, segmentation và risk management.\
    Đây là tài liệu bảo mật OT, không phải UI design standard.

### 19.2. Tài liệu bổ trợ

7.  **Nielsen Norman Group -- 10 Usability Heuristics for User Interface
    Design**\
    https://www.nngroup.com/articles/ten-usability-heuristics/\
    Tham chiếu: visibility of system status, match with real world,
    consistency, error prevention, recognition over recall và minimalist
    design.

8.  **Material Design 3**\
    https://m3.material.io/\
    Tham khảo component behavior, accessibility, layout và design
    tokens. Chỉ dùng như nguồn tham khảo; không bắt buộc MES phải mang
    phong cách Material.

9.  **Microsoft Fluent 2 Design System**\
    https://fluent2.microsoft.design/\
    Tham khảo design tokens, components, accessibility và enterprise
    application patterns.

### 19.3. Nguyên tắc về bản quyền và tuân thủ

-   Một số tiêu chuẩn ISA, ISO và IEC là tài liệu có bản quyền và có thể
    yêu cầu mua/đăng ký để xem toàn văn.
-   Website tổ chức tiêu chuẩn là điểm bắt đầu để xác minh edition và
    phạm vi; không suy diễn nội dung chi tiết từ trang giới thiệu.
-   Không ghi "compliant with ISA-101/ISA-18.2/ISO 9241/WCAG" chỉ vì đã
    áp dụng một số khuyến nghị trong tài liệu này.
-   Nếu dự án có yêu cầu tuân thủ chính thức, cần xác định tiêu
    chuẩn/edition áp dụng, phạm vi, bằng chứng kiểm thử và người có thẩm
    quyền phê duyệt.

------------------------------------------------------------------------

## 20. Prompt vận hành dành cho AI

Khi giao nhiệm vụ thiết kế hoặc phát triển UI MES, hãy tuân thủ tài liệu
này như guideline mặc định.

**AI MUST:** - Understand user role, task, screen type and operating
context before proposing UI. - Reuse the existing design system and
project conventions. - Prioritize operational correctness, readability,
consistency, safety and data trust. - Distinguish machine state from
connection state and data quality. - Provide loading, empty, error,
stale, offline and success states where relevant. - Preserve user
context and entered data during realtime updates. - Use only confirmed
business rules, KPI formulas, thresholds and permission definitions. -
Identify assumptions and mark unresolved requirements as
`[NEEDS CONFIRMATION]`. - Explain meaningful design decisions and list
any deviations from this guideline.

**AI MUST NOT:** - Invent business logic, OEE formulas, alarm
priorities, tag mappings or operational procedures. - Treat missing,
stale or bad-quality data as zero or valid current data. - Use color as
the only status indicator. - Add decorative charts, excessive gradients,
shadows or animations. - Create non-functional buttons or fake realtime
behavior. - Change backend contracts or business rules when asked only
to modify UI. - Claim standards compliance without evidence.

**Expected output for a UI implementation task:** 1. Brief
interpretation of the user role and screen objective. 2. Proposed layout
and component reuse. 3. Key states and interaction behavior. 4.
Assumptions / items requiring confirmation. 5. Implementation. 6. Short
verification checklist and known limitations.

------------------------------------------------------------------------

**End of guideline**
