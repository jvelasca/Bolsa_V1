/**
 * Modelo cliente del hub Instrumentos (I0–I5).
 * Filtro + ordenación de catálogo BD (+ listas / cartera / Estudio / IO).
 *
 * @see docs/engineering/instruments-hub-2026-07-31.md
 * @see docs/engineering/instruments-hub-narrative-2026-08-04.md
 */

import type { InstrumentWithMetaDto, PositionDto } from '@bolsa/shared';
import type { HubListMembership } from '@/features/instruments/instruments-hub-enrichment';
import type { HubFaScore, HubTaScore } from '@/features/instruments/instruments-hub-scores';
import type { HubTrackerChip } from '@/features/instruments/instruments-hub-trackers';

export type InstrumentsHubSortKey =
  | 'symbol'
  | 'name'
  | 'lastClose'
  | 'changePct'
  | 'barCount'
  | 'listCount'
  | 'unrealizedPnl'
  | 'scoreFa'
  | 'scoreTa'
  | 'scoreIo'
  | 'trackerCount'
  | 'lastBar';

export type InstrumentsHubSortDir = 'asc' | 'desc';

/** Alcance rápido de la barra de filtros. */
export type InstrumentsHubScopeFilter = 'all' | 'estudio' | 'portfolio' | 'list';

export type InstrumentsHubEnrichment = {
  membershipsByInstrument?: Map<string, HubListMembership[]>;
  positionsByInstrument?: Map<string, PositionDto>;
  faByInstrument?: Map<string, HubFaScore>;
  taByInstrument?: Map<string, HubTaScore>;
  /** Índice Operativo (Recomendación) 0–100. */
  ioByInstrument?: Map<string, number | null>;
  trackersByInstrument?: Map<string, HubTrackerChip[]>;
};

export function normalizeInstrumentsHubQuery(q: string): string {
  return q.trim().toLowerCase();
}

export function instrumentMatchesHubQuery(
  instrument: InstrumentWithMetaDto,
  rawQuery: string,
  memberships?: HubListMembership[],
): boolean {
  const q = normalizeInstrumentsHubQuery(rawQuery);
  if (!q) return true;
  const hay = [
    instrument.symbol,
    instrument.name,
    instrument.yahooSymbol,
    instrument.isin ?? '',
    instrument.sector ?? '',
    instrument.exchange ?? '',
    ...(memberships ?? []).map((m) => m.listName),
  ]
    .join(' ')
    .toLowerCase();
  return hay.includes(q);
}

function cmpNullableNumber(
  a: number | null | undefined,
  b: number | null | undefined,
  dir: InstrumentsHubSortDir,
): number {
  const av = a == null || !Number.isFinite(a) ? null : a;
  const bv = b == null || !Number.isFinite(b) ? null : b;
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const d = av - bv;
  return dir === 'asc' ? d : -d;
}

function cmpString(a: string, b: string, dir: InstrumentsHubSortDir): number {
  const d = a.localeCompare(b, undefined, { sensitivity: 'base' });
  return dir === 'asc' ? d : -d;
}

export function compareInstrumentsForHub(
  a: InstrumentWithMetaDto,
  b: InstrumentWithMetaDto,
  key: InstrumentsHubSortKey,
  dir: InstrumentsHubSortDir,
  enrichment?: InstrumentsHubEnrichment,
): number {
  switch (key) {
    case 'name':
      return cmpString(a.name, b.name, dir) || cmpString(a.symbol, b.symbol, 'asc');
    case 'lastClose':
      return (
        cmpNullableNumber(a.meta.lastClose, b.meta.lastClose, dir) ||
        cmpString(a.symbol, b.symbol, 'asc')
      );
    case 'changePct':
      return (
        cmpNullableNumber(a.meta.changePct, b.meta.changePct, dir) ||
        cmpString(a.symbol, b.symbol, 'asc')
      );
    case 'barCount':
      return (
        cmpNullableNumber(a.meta.barCount, b.meta.barCount, dir) ||
        cmpString(a.symbol, b.symbol, 'asc')
      );
    case 'listCount': {
      const ac = enrichment?.membershipsByInstrument?.get(a.id)?.length ?? 0;
      const bc = enrichment?.membershipsByInstrument?.get(b.id)?.length ?? 0;
      return cmpNullableNumber(ac, bc, dir) || cmpString(a.symbol, b.symbol, 'asc');
    }
    case 'unrealizedPnl': {
      const ap = enrichment?.positionsByInstrument?.get(a.id)?.unrealizedPnl ?? null;
      const bp = enrichment?.positionsByInstrument?.get(b.id)?.unrealizedPnl ?? null;
      return cmpNullableNumber(ap, bp, dir) || cmpString(a.symbol, b.symbol, 'asc');
    }
    case 'scoreFa': {
      const af = enrichment?.faByInstrument?.get(a.id)?.scoreDisplay100 ?? null;
      const bf = enrichment?.faByInstrument?.get(b.id)?.scoreDisplay100 ?? null;
      return cmpNullableNumber(af, bf, dir) || cmpString(a.symbol, b.symbol, 'asc');
    }
    case 'scoreTa': {
      const at = enrichment?.taByInstrument?.get(a.id)?.technicalDisplay100 ?? null;
      const bt = enrichment?.taByInstrument?.get(b.id)?.technicalDisplay100 ?? null;
      return cmpNullableNumber(at, bt, dir) || cmpString(a.symbol, b.symbol, 'asc');
    }
    case 'scoreIo': {
      const ai = enrichment?.ioByInstrument?.get(a.id) ?? null;
      const bi = enrichment?.ioByInstrument?.get(b.id) ?? null;
      return cmpNullableNumber(ai, bi, dir) || cmpString(a.symbol, b.symbol, 'asc');
    }
    case 'trackerCount': {
      const ac = enrichment?.trackersByInstrument?.get(a.id)?.length ?? 0;
      const bc = enrichment?.trackersByInstrument?.get(b.id)?.length ?? 0;
      return cmpNullableNumber(ac, bc, dir) || cmpString(a.symbol, b.symbol, 'asc');
    }
    case 'lastBar': {
      const ad = a.meta.lastBarDate ?? a.meta.lastSync?.syncedAt ?? null;
      const bd = b.meta.lastBarDate ?? b.meta.lastSync?.syncedAt ?? null;
      if (!ad && !bd) return cmpString(a.symbol, b.symbol, 'asc');
      if (!ad) return 1;
      if (!bd) return -1;
      return cmpString(ad, bd, dir) || cmpString(a.symbol, b.symbol, 'asc');
    }
    case 'symbol':
    // fall through
    default:
      return cmpString(a.symbol, b.symbol, dir);
  }
}

export function filterAndSortInstrumentsHub(
  instruments: InstrumentWithMetaDto[],
  opts: {
    query?: string;
    sortKey?: InstrumentsHubSortKey;
    sortDir?: InstrumentsHubSortDir;
    /** @deprecated prefer scopeFilter === 'portfolio' */
    onlyInPortfolio?: boolean;
    scopeFilter?: InstrumentsHubScopeFilter;
    /** Cuando scopeFilter === 'list'. */
    listId?: string | null;
    /** Membresía Estudio (lista virtual). */
    estudioIds?: ReadonlySet<string>;
    enrichment?: InstrumentsHubEnrichment;
  } = {},
): InstrumentWithMetaDto[] {
  const sortKey = opts.sortKey ?? 'symbol';
  const sortDir = opts.sortDir ?? 'asc';
  const enrichment = opts.enrichment;
  const scope: InstrumentsHubScopeFilter =
    opts.scopeFilter ?? (opts.onlyInPortfolio ? 'portfolio' : 'all');

  const filtered = instruments.filter((i) => {
    if (scope === 'portfolio') {
      const pos = enrichment?.positionsByInstrument?.get(i.id);
      if (!pos || pos.quantity === 0) return false;
    } else if (scope === 'estudio') {
      if (!opts.estudioIds?.has(i.id)) return false;
    } else if (scope === 'list') {
      const listId = opts.listId?.trim();
      if (!listId) return false;
      const memberships = enrichment?.membershipsByInstrument?.get(i.id) ?? [];
      if (!memberships.some((m) => m.listId === listId)) return false;
    }
    const memberships = enrichment?.membershipsByInstrument?.get(i.id);
    return instrumentMatchesHubQuery(i, opts.query ?? '', memberships);
  });
  return [...filtered].sort((a, b) =>
    compareInstrumentsForHub(a, b, sortKey, sortDir, enrichment),
  );
}

export function toggleInstrumentsHubSort(
  currentKey: InstrumentsHubSortKey,
  currentDir: InstrumentsHubSortDir,
  nextKey: InstrumentsHubSortKey,
): { sortKey: InstrumentsHubSortKey; sortDir: InstrumentsHubSortDir } {
  if (currentKey === nextKey) {
    return { sortKey: currentKey, sortDir: currentDir === 'asc' ? 'desc' : 'asc' };
  }
  const numericDesc: InstrumentsHubSortKey[] = [
    'changePct',
    'lastClose',
    'barCount',
    'listCount',
    'unrealizedPnl',
    'scoreFa',
    'scoreTa',
    'scoreIo',
    'trackerCount',
    'lastBar',
  ];
  return {
    sortKey: nextKey,
    sortDir: numericDesc.includes(nextKey) ? 'desc' : 'asc',
  };
}
