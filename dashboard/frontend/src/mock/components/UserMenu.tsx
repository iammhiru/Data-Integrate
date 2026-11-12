// ============================================================================
//  UserMenu — khối người dùng ở GÓC TRÊN BÊN PHẢI header, sổ xuống dropdown.
//
//  Tham chiếu: Laird.System.UI/src/lib/components/UserInfoMenu.svelte
//    - Avatar tròn + badge mũi tên nhỏ ở góc dưới phải (caret rotate khi mở)
//    - Backdrop phủ toàn màn khi menu mở → chặn click ra ngoài
//    - Panel trắng, bo góc lớn, đổ bóng
//    - Đóng bằng click ra ngoài hoặc phím Escape
//
//  ⚠ YÊU CẦU (12/11): KHÔNG làm các chức năng nâng cao (phân quyền, đổi mật
//    khẩu, đăng xuất) — mục tiêu dự án là tích hợp dữ liệu, UI đẹp và nhanh.
//    Vì vậy menu chỉ hiển thị THÔNG TIN (không có nút chết, không có mục
//    disabled trông như lỗi).
// ============================================================================

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Clock, ShieldCheck, UserRound } from "lucide-react";
import { shiftLabel } from "../domain/shift";

export function UserMenu() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Đóng khi click ra ngoài.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="user-menu" ref={wrapRef}>
      <button
        className="user-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Thông tin tài khoản người dùng"
        title="Nguyễn Văn A — Trưởng ca PLANT_01"
      >
        <span className="user-avatar" aria-hidden="true">
          <UserRound size={16} />
        </span>
        <span className="user-trigger-name">Nguyễn Văn A</span>
        <span className="user-caret" aria-hidden="true">
          <ChevronDown size={14} style={{ transform: open ? "rotate(180deg)" : undefined }} />
        </span>
      </button>

      {open && (
        <>
          {/* Backdrop chặn click xuống UI bên dưới khi menu đang mở */}
          <div className="user-menu-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="user-menu-panel" role="menu" aria-label="Thông tin người dùng">
            <div className="user-menu-head">
              <span className="user-avatar user-avatar-lg" aria-hidden="true">
                <UserRound size={22} />
              </span>
              <div className="user-menu-id">
                <b>Nguyễn Văn A</b>
                <span>Trưởng ca · PLANT_01</span>
              </div>
            </div>
            <div className="user-menu-sep" />
            {/*
              ⚠ YÊU CẦU (12/11): bỏ toàn bộ nút chết (Profile / Change password
              / Log out) và các mục `disabled`. Menu giờ CHỈ hiển thị thông tin
              đang có thật — không gợi ý tính năng chưa triển khai.
            */}
            <UserMenuInfo icon={<ShieldCheck size={15} />} label="Vai trò" value="Trưởng ca" />
            <UserMenuInfo icon={<Clock size={15} />} label="Ca hiện tại" value={shiftLabel()} />
            <UserMenuInfo icon={<UserRound size={15} />} label="Phạm vi" value="PLANT_01 · 3 line" />
          </div>
        </>
      )}
    </div>
  );
}

function UserMenuInfo({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="user-menu-info" role="menuitem">
      <span className="user-menu-item-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="user-menu-info-label">{label}</span>
      <b className="user-menu-info-value">{value}</b>
    </div>
  );
}
