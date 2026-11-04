import type { ChartDrawTool, DrawingToolGroupId } from "@bolsa/shared";

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

/** Cursor neutro de último recurso cuando no hay un cursor previo recordado. */
export const CHART_CURSOR_TOOL: ChartDrawTool = "select";

/**
 * Cursores *puros*: no crean objetos al hacer clic. Son el único destino válido
 * de `Escape`. `arrow` queda fuera a propósito aunque viva en el grupo Cursor:
 * deja flechas fijas, así que es un modo de dibujo y debe poder abandonarse.
 */
export const PURE_CURSOR_TOOLS: ChartDrawTool[] = [
  "select",
  "cross",
  "dot",
  "dot-halo",
];

export function isPureCursorTool(tool: ChartDrawTool): boolean {
  return PURE_CURSOR_TOOLS.includes(tool);
}

/**
 * `Escape` sale del modo de dibujo. No actúa si ya se está en un cursor puro
 * (Puntero, Cruz, Punto, Punto resaltado): no hay nada de lo que salir.
 */
export function shouldExitDrawModeOnEscape(tool: ChartDrawTool): boolean {
  return !isPureCursorTool(tool);
}

/**
 * Herramienta a la que vuelve `Escape`: el **último cursor puro usado**
 * (p. ej. Cruz), no el puntero por defecto. Si no hay cursor recordado válido,
 * cae a `CHART_CURSOR_TOOL`.
 */
export function resolveEscapeDrawTool(input: {
  currentTool: ChartDrawTool;
  lastDrawToolByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
}): ChartDrawTool {
  if (isPureCursorTool(input.currentTool)) return input.currentTool;
  const remembered = input.lastDrawToolByGroup.cursor;
  if (remembered && isPureCursorTool(remembered)) return remembered;
  return CHART_CURSOR_TOOL;
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
