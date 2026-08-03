import { useEffect, useMemo, useRef } from 'react';
import type { InstrumentWithMetaDto } from '@bolsa/shared';

import {
  useVisualizationStore,
  type VisualizationSessionEntry,
} from '@/stores/visualization-store';
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

function sameIdSet(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const id of a) {
    if (!b.has(id)) return false;
  }
  return true;
}

/**
 * Lista virtual «En estudio» = instrumentos con pestaña de gráfico abierta.
 * Escrituras al store solo cuando cambia el conjunto de pestañas o el foco.
 * No carga el catálogo completo (las pestañas ya llevan symbol/label).
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

  const openKey = useMemo(
    () => openTabs.map((tab) => `${tab.id}:${tab.instrumentId}`).join('|'),
    [openTabs],
  );

  const lastOpenKeyRef = useRef<string | null>(null);
  const lastBumpKeyRef = useRef<string | null>(null);

  // Conjunto = pestañas abiertas (sin setState si no hay cambios de IDs).
  useEffect(() => {
    const openIds = new Set(openTabs.map((tab) => tab.instrumentId));
    const store = useVisualizationStore.getState();
    const currentIds = new Set(store.entries.map((entry) => entry.instrumentId));

    if (lastOpenKeyRef.current === openKey && sameIdSet(openIds, currentIds)) {
      return;
    }
    lastOpenKeyRef.current = openKey;

    if (sameIdSet(openIds, currentIds)) {
      return;
    }

    const now = new Date().toISOString();
    // Una entrada por instrumento (puede haber habido pestañas duplicadas legacy).
    const byInstrument = new Map<string, (typeof openTabs)[number]>();
    for (const tab of openTabs) {
      if (!byInstrument.has(tab.instrumentId)) {
        byInstrument.set(tab.instrumentId, tab);
      }
      if (tab.id === activeChartId) {
        byInstrument.set(tab.instrumentId, tab);
      }
    }
    const next: VisualizationSessionEntry[] = [...byInstrument.values()].map((tab) => {
      const existing = store.entries.find((entry) => entry.instrumentId === tab.instrumentId);
      const instrument = instrumentFromTab(tab.instrumentId, tab.label);
      if (existing) {
        return {
          ...existing,
          symbol: instrument.symbol,
          name: instrument.name,
        };
      }
      return {
        instrumentId: tab.instrumentId,
        symbol: instrument.symbol,
        name: instrument.name,
        firstViewedAt: now,
        lastViewedAt: now,
        viewCount: 1,
      };
    });

    const prevFingerprint = store.entries
      .map((entry) => `${entry.instrumentId}:${entry.symbol}:${entry.name}`)
      .join('|');
    const nextFingerprint = next
      .map((entry) => `${entry.instrumentId}:${entry.symbol}:${entry.name}`)
      .join('|');
    if (prevFingerprint === nextFingerprint) {
      return;
    }

    store.replaceEntries(next);
  }, [openKey, openTabs, activeChartId]);

  // Bump «visto N×» solo al cambiar de pestaña activa (una vez por foco).
  useEffect(() => {
    if (!activeChartId) return;
    const tab = openTabs.find((item) => item.id === activeChartId);
    if (!tab) return;

    const bumpKey = `${activeChartId}:${tab.instrumentId}`;
    if (lastBumpKeyRef.current === bumpKey) return;
    lastBumpKeyRef.current = bumpKey;

    const store = useVisualizationStore.getState();
    if (!store.contains(tab.instrumentId)) return;

    store.addInstrument(instrumentFromTab(tab.instrumentId, tab.label), {
      source: 'list',
    });
  }, [activeChartId, openTabs]);
}
