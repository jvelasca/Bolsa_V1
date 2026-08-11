import type { ChartDrawTool } from "@bolsa/shared";

/** Modos del grupo Cursor (mutuamente excluyentes; solo uno activo). */
export const CURSOR_GROUP_TOOLS: ChartDrawTool[] = [
  "select",
  "cross",
  "dot",
  "dot-halo",
  "arrow",
];

/** Estilo del crosshair del ratón (no crean dibujos persistentes). */
export const CURSOR_CROSSHAIR_STYLES: ChartDrawTool[] = [
  "cross",
  "dot",
  "dot-halo",
];

/** Herramientas de navegación global. */
export const NAVIGATION_DRAW_TOOLS: ChartDrawTool[] = ["select", "crosshair"];

/** Marcadores persistidos en el gráfico (grupo flechas, etc.). */
export const MARKER_DRAW_TOOLS: ChartDrawTool[] = [
  "arrow-circle",
  "arrow-up",
  "arrow-down",
];

export function isCursorGroupTool(tool: ChartDrawTool): boolean {
  return CURSOR_GROUP_TOOLS.includes(tool);
}

export function isCursorCrosshairStyle(tool: ChartDrawTool): boolean {
  return CURSOR_CROSSHAIR_STYLES.includes(tool);
}

export function isCursorArrowTool(tool: ChartDrawTool): boolean {
  return tool === "arrow";
}

/** Crosshair personalizado o flecha-cursor (oculta el crosshair nativo del chart). */
export function usesCustomChartCursor(tool: ChartDrawTool): boolean {
  return isCursorCrosshairStyle(tool) || isCursorArrowTool(tool);
}

/** Ocultar crosshair nativo LWC (puntero sin líneas, modos custom, regla). */
export function shouldHideNativeCrosshair(tool: ChartDrawTool): boolean {
  return (
    tool === "select" || tool === "crosshair" || usesCustomChartCursor(tool)
  );
}

export function isNavigationDrawTool(tool: ChartDrawTool): boolean {
  return NAVIGATION_DRAW_TOOLS.includes(tool);
}

export function isMarkerDrawTool(tool: ChartDrawTool): boolean {
  return MARKER_DRAW_TOOLS.includes(tool);
}

export function isShapeDrawTool(tool: ChartDrawTool): boolean {
  return !isNavigationDrawTool(tool) && !isCursorGroupTool(tool);
}

/** Puntero o cruz: seleccionar, anclajes y doble clic en dibujos existentes. */
export function canInteractWithDrawings(tool: ChartDrawTool): boolean {
  return tool === "select" || tool === "cross";
}

export function blocksChartPan(tool: ChartDrawTool): boolean {
  if (isNavigationDrawTool(tool) || isCursorGroupTool(tool)) return false;
  return true;
}

export function capturesDrawingPointer(
  tool: ChartDrawTool,
  _selectedDrawingId: string | null,
): boolean {
  if (tool === "crosshair") return false;
  if (tool === "select" || tool === "cross") return false;
  if (isShapeDrawTool(tool)) return true;
  return false;
}

/** Bloquea pan/zoom del gráfico (distinto de capturar puntero en la capa de dibujos). */
export function blocksChartPointerPan(
  tool: ChartDrawTool,
  _selectedDrawingId: string | null,
): boolean {
  if (tool === "crosshair") return true;
  if (isShapeDrawTool(tool)) return true;
  return false;
}

/** Separadores precio/indicadores inactivos mientras se dibuja o mide en el gráfico. */
export function shouldDisablePanelResize(tool: ChartDrawTool): boolean {
  return blocksChartPointerPan(tool, null);
}

/** Puntero sobre un dibujo: priorizar edición frente a pan del gráfico. */
export function shouldCaptureDrawingPointer(
  tool: ChartDrawTool,
  hoveringDrawing: boolean,
  interactionDragging: boolean,
): boolean {
  if (interactionDragging) return true;
  if ((tool === "select" || tool === "cross") && hoveringDrawing) return true;
  return capturesDrawingPointer(tool, null);
}
