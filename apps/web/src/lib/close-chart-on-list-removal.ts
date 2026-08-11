/**
 * Al quitar un valor de una lista persistente: si tiene pestaña de gráfico abierta,
 * la cierra. La lista virtual «Visualizados» se actualiza sola (espejo de pestañas).
 */

import { useWorkspaceStore } from "@/stores/workspace-store";

export function closeOpenChartsForInstrument(instrumentId: string): void {
  if (!instrumentId) return;
  useWorkspaceStore.getState().closeChartTabsForInstruments([instrumentId]);
}

export function closeOpenChartsForInstruments(
  instrumentIds: Iterable<string>,
): void {
  const ids = [...new Set([...instrumentIds].filter(Boolean))];
  if (ids.length === 0) return;
  useWorkspaceStore.getState().closeChartTabsForInstruments(ids);
}
