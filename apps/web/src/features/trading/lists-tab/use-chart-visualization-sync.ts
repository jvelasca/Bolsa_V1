/**
 * Sync ligero: abrir/enfocar pestaña de gráfico → añade a lista Estudio si falta.
 * Cerrar pestaña NO saca de Estudio (membresía explícita).
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import { useEffect, useMemo, useRef } from 'react';
import type { InstrumentWithMetaDto } from '@bolsa/shared';

import { useVisualizationStore } from '@/stores/visualization-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

function instrumentFromTab(instrumentId: string, label: string): InstrumentWithMetaDto {
  return {
    id: instrumentId,
    symbol: label,
    yahooSymbol: label,
    name: label,
    exchange: '—',
    country: '—',
    currency: 'EUR',
    sector: null,
    isActive: true,
    meta: {
      barCount: 0,
      lastSync: null,
      lastClose: null,
      changePct: null,
    },
  };
}

/**
 * Lista virtual «Estudio»: membresía explícita (store + workspace).
 * Abrir gráfico suma; quitar solo vía lista / membresía / bulk.
 */
export function useChartVisualizationSync() {
  const charts = useWorkspaceStore((state) => state.workspace.charts);
  const activeChartId = useWorkspaceStore((state) => state.workspace.activeChartId);

  const openTabs = useMemo(
    () =>
      charts
        .filter((tab) => Boolean(tab.instrumentId))
        .map((tab) => ({
          id: tab.id,
          instrumentId: tab.instrumentId as string,
          label: tab.label,
        })),
    [charts],
  );

  const openInstrumentKey = useMemo(
    () =>
      [...new Set(openTabs.map((tab) => tab.instrumentId))]
        .sort()
        .join('|'),
    [openTabs],
  );

  const lastSeedKeyRef = useRef<string | null>(null);
  const lastBumpKeyRef = useRef<string | null>(null);

  // Sembrar / ampliar Estudio con pestañas abiertas (nunca sustituir el conjunto).
  useEffect(() => {
    if (lastSeedKeyRef.current === openInstrumentKey) return;
    lastSeedKeyRef.current = openInstrumentKey;

    for (const tab of openTabs) {
      const live = useVisualizationStore.getState();
      if (!live.contains(tab.instrumentId)) {
        live.addInstrument(instrumentFromTab(tab.instrumentId, tab.label), {
          source: 'list',
        });
      }
    }
  }, [openInstrumentKey, openTabs]);

  // Bump «visto N×» al cambiar de pestaña activa (solo si ya está en Estudio).
  useEffect(() => {
    if (!activeChartId) return;
    const tab = openTabs.find((item) => item.id === activeChartId);
    if (!tab) return;

    const bumpKey = `${activeChartId}:${tab.instrumentId}`;
    if (lastBumpKeyRef.current === bumpKey) return;
    lastBumpKeyRef.current = bumpKey;

    const store = useVisualizationStore.getState();
    if (!store.contains(tab.instrumentId)) {
      store.addInstrument(instrumentFromTab(tab.instrumentId, tab.label), {
        source: 'list',
      });
      return;
    }

    store.addInstrument(instrumentFromTab(tab.instrumentId, tab.label), {
      source: 'list',
    });
  }, [activeChartId, openTabs]);
}
