/** Densidad de UI V1.31 — comfortable (default) | compact. */
export type UiDensity = "comfortable" | "compact";

export const UI_DENSITY_DEFAULT: UiDensity = "comfortable";

export function isUiDensity(value: unknown): value is UiDensity {
  return value === "comfortable" || value === "compact";
}

export function nextUiDensity(current: UiDensity): UiDensity {
  return current === "comfortable" ? "compact" : "comfortable";
}

export function applyUiDensityToDocument(density: UiDensity): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.density = density;
}
