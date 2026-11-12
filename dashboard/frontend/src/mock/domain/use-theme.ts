// ============================================================================
//  Hook đổi theme sáng/tối.
//  - Mặc định SÁNG (phòng điều khiển sáng).
//  - Lưu lựa chọn vào localStorage để giữ qua các phiên.
//  - Áp dụng qua thuộc tính `data-theme` trên <html> → token trong tokens.css
//    đổi theo (không cần re-render).
// ============================================================================

import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "mes-theme";

function readTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "dark" || v === "light") return v;
  } catch {
    /* localStorage bị chặn → dùng mặc định */
  }
  return "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.setAttribute("data-theme", "dark");
    else root.removeAttribute("data-theme");
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* bỏ qua */
    }
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => (t === "light" ? "dark" : "light"));
  }, []);

  return { theme, toggle };
}
