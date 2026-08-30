/** Tema de UI V1.31.1 — dark (default) | light | system. */

export type UiTheme = "dark" | "light" | "system";

export type ResolvedUiTheme = "dark" | "light";

export const UI_THEME_DEFAULT: UiTheme = "dark";

export function isUiTheme(value: unknown): value is UiTheme {
  return value === "dark" || value === "light" || value === "system";
}

export function nextUiTheme(current: UiTheme): UiTheme {
  if (current === "dark") return "light";
  if (current === "light") return "system";
  return "dark";
}

export function resolveUiTheme(
  theme: UiTheme,
  prefersDark = true,
): ResolvedUiTheme {
  if (theme === "light") return "light";
  if (theme === "dark") return "dark";
  return prefersDark ? "dark" : "light";
}

export function readSystemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Aplica tema resuelto en `<html data-theme="…">` (tokens CSS + variante `dark:`). */
export function applyUiThemeToDocument(theme: UiTheme): ResolvedUiTheme {
  const resolved = resolveUiTheme(theme, readSystemPrefersDark());
  if (typeof document === "undefined") return resolved;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  return resolved;
}
