/**
 * Política: como máximo una pestaña de gráfico por instrumento.
 * Un valor puede estar en varias listas; la pestaña es única y se reutiliza al abrir.
 */

import type { ChartTabState } from "@bolsa/shared";

export function dedupeChartTabsByInstrument(
  charts: ChartTabState[],
  activeChartId: string | null,
): { charts: ChartTabState[]; activeChartId: string | null } {
  const kept: ChartTabState[] = [];
  const seen = new Map<string, number>(); // instrumentId → index in kept

  for (const tab of charts) {
    const instrumentId = tab.instrumentId?.trim() ?? "";
    if (!instrumentId) {
      kept.push(tab);
      continue;
    }
    const existingIndex = seen.get(instrumentId);
    if (existingIndex === undefined) {
      seen.set(instrumentId, kept.length);
      kept.push(tab);
      continue;
    }
    // Preferir la pestaña activa si hay duplicado
    if (activeChartId && tab.id === activeChartId) {
      kept[existingIndex] = tab;
    }
  }

  const nextActive =
    activeChartId && kept.some((tab) => tab.id === activeChartId)
      ? activeChartId
      : (kept[0]?.id ?? null);

  return { charts: kept, activeChartId: nextActive };
}
