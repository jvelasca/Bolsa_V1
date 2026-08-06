/**
 * Membresía Estudio — SoT = lista API canónica (ADR-024).
 * El visualization-store actúa como cache local para IO / gate SEMI / carrusel.
 */

import type { InstrumentWithMetaDto, VisualizationPersistedEntry } from '@bolsa/shared';
import { ESTUDIO_LIST_ID } from '@bolsa/shared';
import { api } from '@/lib/api';
import { useVisualizationStore } from '@/stores/visualization-store';

export type EstudioMemberMeta = {
  instrumentId: string;
  symbol: string;
  name: string;
};

function entryFromMeta(meta: EstudioMemberMeta, now: string): VisualizationPersistedEntry {
  return {
    instrumentId: meta.instrumentId,
    symbol: meta.symbol,
    name: meta.name,
    firstViewedAt: now,
    lastViewedAt: now,
    viewCount: 1,
  };
}

/** Lee instrumentIds actuales de la lista API Estudio (crea/asegura vía GET lists). */
export async function fetchEstudioInstrumentIds(): Promise<string[]> {
  await api.getLists();
  const detail = await api.getList(ESTUDIO_LIST_ID);
  return detail.data.instrumentIds ?? [];
}

/**
 * Hidrata el store desde API. Si API vacía y hay entradas locales, las sube (migración).
 */
export async function hydrateEstudioMembershipFromApi(): Promise<void> {
  const store = useVisualizationStore.getState();
  const local = store.entries;
  let apiIds: string[];
  try {
    apiIds = await fetchEstudioInstrumentIds();
  } catch {
    return;
  }

  if (apiIds.length === 0 && local.length > 0) {
    const ids = local.map((e) => e.instrumentId);
    await api.updateList(ESTUDIO_LIST_ID, { instrumentIds: ids });
    apiIds = ids;
  }

  const now = new Date().toISOString();
  const byLocal = new Map(local.map((e) => [e.instrumentId, e]));
  const next: VisualizationPersistedEntry[] = apiIds.map((id) => {
    const prev = byLocal.get(id);
    if (prev) return prev;
    return entryFromMeta({ instrumentId: id, symbol: id.slice(0, 8), name: id.slice(0, 8) }, now);
  });
  store.replaceEntries(next);
}

/** Añade instrumentos a Estudio (API + cache). */
export async function addToEstudioMembership(
  instruments: ReadonlyArray<InstrumentWithMetaDto | EstudioMemberMeta>,
): Promise<number> {
  if (instruments.length === 0) return 0;
  const store = useVisualizationStore.getState();
  const current = await fetchEstudioInstrumentIds();
  const set = new Set(current);
  let added = 0;
  const metas: EstudioMemberMeta[] = [];
  for (const raw of instruments) {
    const id = 'id' in raw && typeof (raw as InstrumentWithMetaDto).id === 'string'
      ? (raw as InstrumentWithMetaDto).id
      : (raw as EstudioMemberMeta).instrumentId;
    const symbol =
      'symbol' in raw ? String(raw.symbol) : (raw as EstudioMemberMeta).symbol;
    const name = 'name' in raw ? String(raw.name) : (raw as EstudioMemberMeta).name;
    if (!id || set.has(id)) continue;
    set.add(id);
    metas.push({ instrumentId: id, symbol, name });
    added += 1;
  }
  if (added === 0) return 0;
  await api.updateList(ESTUDIO_LIST_ID, { instrumentIds: [...set] });
  for (const m of metas) {
    const asDto = {
      id: m.instrumentId,
      symbol: m.symbol,
      yahooSymbol: m.symbol,
      name: m.name,
      exchange: '—',
      country: '—',
      currency: 'EUR',
      sector: null,
      isActive: true,
      meta: { barCount: 0, lastSync: null, lastClose: null, changePct: null },
    } satisfies InstrumentWithMetaDto;
    store.addInstrument(asDto, { source: 'list' });
  }
  return added;
}

/** Quita instrumentos de Estudio (API + cache). */
export async function removeFromEstudioMembership(
  instrumentIds: ReadonlyArray<string>,
): Promise<number> {
  if (instrumentIds.length === 0) return 0;
  const store = useVisualizationStore.getState();
  const current = await fetchEstudioInstrumentIds();
  const removeSet = new Set(instrumentIds);
  const next = current.filter((id) => !removeSet.has(id));
  const removed = current.length - next.length;
  if (removed === 0) {
    for (const id of instrumentIds) store.removeInstrument(id);
    return 0;
  }
  await api.updateList(ESTUDIO_LIST_ID, { instrumentIds: next });
  for (const id of instrumentIds) store.removeInstrument(id);
  return removed;
}
