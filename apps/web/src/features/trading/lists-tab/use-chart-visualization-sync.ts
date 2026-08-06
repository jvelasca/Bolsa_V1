/**
 * **Visualizados** = instrumentos con pestaña de gráfico abierta ahora.
 * SoT = `workspace.charts` (add + prune; no dump legacy ni Estudio).
 * Cerrar pestaña → sale. ADR-024: no toca Estudio API.
 *
 * @see docs/engineering/visualizados-list-ux-2026-08-06.md
 * @see docs/adr/024-estudio-supervision-universe.md
 */

import { useEffect, useMemo, useRef } from 'react';

import {
  useVisualizationStore,
  type VisualizationSessionEntry,
} from '@/stores/visualization-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

function entriesKey(entries: ReadonlyArray<{ instrumentId: string }>): string {
  return [...new Set(entries.map((e) => e.instrumentId))].sort().join('|');
}

/**
 * Reconcilia el store al conjunto exacto de pestañas abiertas (add + prune).
 */
export function reconcileVisualizadosToOpenCharts(): void {
  const charts = useWorkspaceStore.getState().workspace.charts;
  const openTabs = charts.filter((tab) => Boolean(tab.instrumentId));
  const now = new Date().toISOString();
  const store = useVisualizationStore.getState();
  const prevById = new Map(store.entries.map((e) => [e.instrumentId, e]));

  const seen = new Set<string>();
  const next: VisualizationSessionEntry[] = [];
  for (const tab of openTabs) {
    const id = tab.instrumentId as string;
    if (seen.has(id)) continue;
    seen.add(id);
    const prev = prevById.get(id);
    if (prev) {
      next.push({
        ...prev,
        symbol: tab.label || prev.symbol,
        name: prev.name && prev.name !== prev.symbol ? prev.name : tab.label || prev.name,
        lastViewedAt: now,
      });
    } else {
      next.push({
        instrumentId: id,
        symbol: tab.label,
        name: tab.label,
        firstViewedAt: now,
        lastViewedAt: now,
        viewCount: 1,
      });
    }
  }

  if (entriesKey(store.entries) === entriesKey(next)) {
    // Solo refrescar labels si cambió el texto de pestaña
    const labelsMatch = next.every((n) => {
      const p = prevById.get(n.instrumentId);
      return p && p.symbol === n.symbol;
    });
    if (labelsMatch && store.entries.length === next.length) return;
  }
  store.replaceEntries(next);
}

export function useChartVisualizationSync() {
  const charts = useWorkspaceStore((state) => state.workspace.charts);
  const activeChartId = useWorkspaceStore((state) => state.workspace.activeChartId);
  const hydrated = useWorkspaceStore((state) => state.hydrated);

  const openInstrumentKey = useMemo(
    () =>
      [...new Set(charts.filter((t) => t.instrumentId).map((t) => t.instrumentId as string))]
        .sort()
        .join('|'),
    [charts],
  );

  const lastKeyRef = useRef<string | null>(null);
  const lastBumpKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (!hydrated) return;
    if (lastKeyRef.current === openInstrumentKey) return;
    lastKeyRef.current = openInstrumentKey;
    reconcileVisualizadosToOpenCharts();
  }, [hydrated, openInstrumentKey]);

  useEffect(() => {
    if (!hydrated || !activeChartId) return;
    const tab = charts.find((item) => item.id === activeChartId);
    if (!tab?.instrumentId) return;

    const bumpKey = `${activeChartId}:${tab.instrumentId}`;
    if (lastBumpKeyRef.current === bumpKey) return;
    lastBumpKeyRef.current = bumpKey;

    const store = useVisualizationStore.getState();
    if (!store.contains(tab.instrumentId)) {
      reconcileVisualizadosToOpenCharts();
      return;
    }
    // Bump viewCount al enfocar pestaña ya abierta
    const now = new Date().toISOString();
    store.replaceEntries(
      store.entries.map((e) =>
        e.instrumentId === tab.instrumentId
          ? {
              ...e,
              symbol: tab.label || e.symbol,
              lastViewedAt: now,
              viewCount: e.viewCount + 1,
            }
          : e,
      ),
    );
  }, [activeChartId, charts, hydrated]);
}
