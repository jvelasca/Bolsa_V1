/**
 * Membresía Estudio — SoT = lista API canónica (ADR-024).
 * Cache local: `estudio-membership-store` (no Visualizados).
 */

import type { InstrumentWithMetaDto } from '@bolsa/shared';
import { ESTUDIO_LIST_ID } from '@bolsa/shared';
import { api } from '@/lib/api';
import {
  useEstudioMembershipStore,
  type EstudioMemberEntry,
} from '@/stores/estudio-membership-store';

export type EstudioMemberMeta = {
  instrumentId: string;
  symbol: string;
  name: string;
};

/** Lee instrumentIds actuales de la lista API Estudio (crea/asegura vía GET lists). */
export async function fetchEstudioInstrumentIds(): Promise<string[]> {
  await api.getLists();
  const detail = await api.getList(ESTUDIO_LIST_ID);
  return detail.data.instrumentIds ?? [];
}

/**
 * Hidrata el cache Estudio desde API.
 * No toca Visualizados (pestañas / búsqueda).
 */
export async function hydrateEstudioMembershipFromApi(): Promise<void> {
  let apiIds: string[];
  try {
    apiIds = await fetchEstudioInstrumentIds();
  } catch {
    return;
  }

  let quotesById = new Map<string, { symbol: string; name: string }>();
  if (apiIds.length > 0) {
    try {
      const quotes = await api.getInstrumentQuotes(apiIds);
      quotesById = new Map(
        quotes.data.map((q) => [q.id, { symbol: q.symbol, name: q.name }]),
      );
    } catch {
      // stubs below
    }
  }

  const prev = useEstudioMembershipStore.getState().members;
  const byPrev = new Map(prev.map((m) => [m.instrumentId, m]));
  const next: EstudioMemberEntry[] = apiIds.map((id) => {
    const q = quotesById.get(id);
    const old = byPrev.get(id);
    return {
      instrumentId: id,
      symbol: q?.symbol ?? old?.symbol ?? id.slice(0, 8),
      name: q?.name ?? old?.name ?? id.slice(0, 8),
    };
  });
  useEstudioMembershipStore.getState().replaceMembers(next);
}

/** Añade instrumentos a Estudio (API + cache). */
export async function addToEstudioMembership(
  instruments: ReadonlyArray<InstrumentWithMetaDto | EstudioMemberMeta>,
): Promise<number> {
  if (instruments.length === 0) return 0;
  const current = await fetchEstudioInstrumentIds();
  const set = new Set(current);
  let added = 0;
  const metas: EstudioMemberEntry[] = [];
  for (const raw of instruments) {
    const id =
      'id' in raw && typeof (raw as InstrumentWithMetaDto).id === 'string'
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
  useEstudioMembershipStore.getState().upsertMembers(metas);
  return added;
}

/** Quita instrumentos de Estudio (API + cache). */
export async function removeFromEstudioMembership(
  instrumentIds: ReadonlyArray<string>,
): Promise<number> {
  if (instrumentIds.length === 0) return 0;
  const current = await fetchEstudioInstrumentIds();
  const removeSet = new Set(instrumentIds);
  const next = current.filter((id) => !removeSet.has(id));
  const removed = current.length - next.length;
  if (removed === 0) {
    useEstudioMembershipStore.getState().removeIds(instrumentIds);
    return 0;
  }
  await api.updateList(ESTUDIO_LIST_ID, { instrumentIds: next });
  useEstudioMembershipStore.getState().removeIds(instrumentIds);
  return removed;
}
