/**
 * Puente entre workspace-store y ui-store (H3).
 *
 * Evita import circular: workspace no importa ui-store directamente.
 * El registro ocurre una vez al arrancar (`WorkspaceUiBridgeRegister`).
 */
import type { ChartInspectorNavigateRequest } from '@/features/charts/chart-inspector-nav';

export interface WorkspaceUiBridge {
  getOpenDrawingEditorId: () => string | null;
  getChartInspectorActiveShortcutKey: () => string | null;
  setChartInspectorActiveShortcutKey: (key: string | null) => void;
  setChartInspectorNav: (request: ChartInspectorNavigateRequest | null) => void;
  focusDrawing: (drawingId: string) => void;
  setOpenDrawingEditorId: (id: string | null) => void;
}

const noopBridge: WorkspaceUiBridge = {
  getOpenDrawingEditorId: () => null,
  getChartInspectorActiveShortcutKey: () => null,
  setChartInspectorActiveShortcutKey: () => {},
  setChartInspectorNav: () => {},
  focusDrawing: () => {},
  setOpenDrawingEditorId: () => {},
};

let bridge: WorkspaceUiBridge | null = null;

/** Registra implementación real (desde ui-store al montar la app). */
export function registerWorkspaceUiBridge(next: WorkspaceUiBridge): void {
  bridge = next;
}

/** Acceso seguro desde workspace-store sin dependencia estática de ui-store. */
export function getWorkspaceUiBridge(): WorkspaceUiBridge {
  return bridge ?? noopBridge;
}
