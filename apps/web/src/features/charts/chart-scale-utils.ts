export const MIN_SCALE_ZOOM = 0.5;
export const MAX_SCALE_ZOOM = 3;
export const PRICE_SCALE_HIT_WIDTH_PX = 76;
/** Ancho mínimo fijo de la escala Y para evitar parpadeo al cambiar etiquetas del crosshair. */
export const PRICE_SCALE_MIN_WIDTH_PX = 76;

export function clampScaleZoom(value: number): number {
  return Math.min(MAX_SCALE_ZOOM, Math.max(MIN_SCALE_ZOOM, value));
}

export function marginsForZoom(zoom: number): { top: number; bottom: number } {
  const margin = Math.max(0.02, 0.12 / zoom);
  return { top: margin, bottom: margin };
}

export function clampMargin(value: number): number {
  return Math.min(0.88, Math.max(0.02, value));
}

export function clampPricePanOffset(value: number): number {
  return Math.min(0.45, Math.max(-0.45, value));
}

export function priceMarginsForZoom(
  zoom: number,
  hasVolume: boolean,
  topMarginPct: number,
  panOffset = 0,
): { top: number; bottom: number } {
  const zoomedTop = Math.max(topMarginPct / 100, 0.12 / zoom);
  const baseBottom = hasVolume ? 0.25 : 0.05;
  const panShift = panOffset * 0.35;
  return {
    top: clampMargin(zoomedTop + panShift),
    bottom: clampMargin(baseBottom - panShift),
  };
}

export function volumeMarginsForZoom(zoom: number): { top: number; bottom: number } {
  const height = 0.2 / zoom;
  return {
    top: Math.min(0.92, Math.max(0.48, 1 - height)),
    bottom: 0,
  };
}

export function stepScaleZoom(current: number, direction: 'in' | 'out'): number {
  const delta = direction === 'in' ? 0.12 : -0.12;
  return clampScaleZoom(current + delta);
}
