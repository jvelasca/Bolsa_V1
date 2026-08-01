/**
 * Al quitar un valor de una lista persistente: si tiene pestaña de gráfico abierta,
 * la cierra. La lista virtual «Visualización» se actualiza sola (espejo de pestañas).
 */

import { useWorkspaceStore } from '@/stores/workspace-store';

export function closeOpenChartsForInstrument(instrumentId: string): void {
  if (!instrumentId) return;
  const { workspace, closeChartTab } = useWorkspaceStore.getState();
  const open = workspace.charts.filter((tab) => tab.instrumentId === instrumentId);
  for (const tab of open) {
    closeChartTab(tab.id);
  }
}

export function closeOpenChartsForInstruments(instrumentIds: Iterable<string>): void {
  const seen = new Set<string>();
  for (const id of instrumentIds) {
    if (!id || seen.has(id)) continue;
    seen.add(id);
    closeOpenChartsForInstrument(id);
  }
}
