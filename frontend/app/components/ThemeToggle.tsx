"use client";

import { useEffect, useState } from "react";
import styles from "./ThemeToggle.module.css";

export const THEME_STORAGE_KEY = "acae-theme";

/** Inline, blocking init script — injected into <head> from layout.tsx so
 *  the correct theme is painted on the very first frame (no flash of the
 *  wrong theme). Runs before React hydrates; kept here so the toggle
 *  component and the init logic can't drift out of sync with each other. */
export const themeInitScript = `
(function () {
  try {
    var key = ${JSON.stringify(THEME_STORAGE_KEY)};
    var stored = localStorage.getItem(key);
    var theme =
      stored === "light" || stored === "dark"
        ? stored
        : window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark";
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
})();
`;

type Theme = "light" | "dark";

export default function ThemeToggle() {
  // null until mounted — avoids rendering an icon that might not match
  // whatever the init script already put on <html>.
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "light" ? "light" : "dark");
  }, []);

  function toggle() {
    const next: Theme = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch (e) {
      // localStorage unavailable (private mode, disabled) — the toggle
      // still works for the session, it just won't persist.
    }
  }

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={toggle}
      aria-label={
        theme === null
          ? "Toggle color theme"
          : theme === "dark"
          ? "Switch to light theme"
          : "Switch to dark theme"
      }
      // Keep the button's presence stable during hydration; only the
      // icon inside swaps once we know the real theme.
      suppressHydrationWarning
    >
      {theme !== "light" && (
        <svg
          className={styles.icon}
          viewBox="0 0 20 20"
          fill="none"
          aria-hidden="true"
        >
          <circle cx="10" cy="10" r="4.25" stroke="currentColor" strokeWidth="1.6" />
          <path
            d="M10 1.75v2.1M10 16.15v2.1M18.25 10h-2.1M3.85 10h-2.1M15.66 4.34l-1.48 1.48M5.82 14.18l-1.48 1.48M15.66 15.66l-1.48-1.48M5.82 5.82 4.34 4.34"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      )}
      {theme === "light" && (
        <svg
          className={styles.icon}
          viewBox="0 0 20 20"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M17.2 11.4A7.3 7.3 0 0 1 8.6 2.8a7.3 7.3 0 1 0 8.6 8.6Z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}