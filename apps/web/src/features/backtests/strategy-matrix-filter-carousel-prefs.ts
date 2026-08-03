/**
 * Preferencias del carrusel de filtros de la matriz (Probar).
 * Visible + favoritos (★ al frente), como columnas de la matriz / listas Trading.
 */

import type { StrategyMatrixFilter } from '@/features/backtests/backtest-strategy-matrix';
import {
  STRATEGY_MATRIX_FILTER_IDS,
  STRATEGY_MATRIX_FILTER_LABELS,
} from '@/features/backtests/backtest-strategy-matrix';

export const STRATEGY_MATRIX_FILTER_CAROUSEL_PREFS_KEY =
  'bolsa-strategy-matrix-filter-carousel-v1';

export type StrategyMatrixFilterCarouselPrefs = {
  /** Chips visibles en el carrusel (al menos 1). */
  visibleIds: StrategyMatrixFilter[];
  /** Favoritos: aparecen primero entre los visibles. */
  favoriteIds: StrategyMatrixFilter[];
};

export { STRATEGY_MATRIX_FILTER_LABELS };

export const DEFAULT_STRATEGY_MATRIX_FILTER_VISIBLE: StrategyMatrixFilter[] = [
  ...STRATEGY_MATRIX_FILTER_IDS,
];

export const DEFAULT_STRATEGY_MATRIX_FILTER_FAVORITES: StrategyMatrixFilter[] = [
  'all',
  'preset',
  'finalists',
];

function isFilterId(raw: unknown): raw is StrategyMatrixFilter {
  return (
    typeof raw === 'string' &&
    (STRATEGY_MATRIX_FILTER_IDS as readonly string[]).includes(raw)
  );
}

/** Legacy `saved` → Mis estrategias. */
export function normalizeStrategyMatrixFilter(raw: unknown): StrategyMatrixFilter {
  if (raw === 'saved') return 'mine';
  if (isFilterId(raw)) return raw;
  return 'all';
}

function normalizeIdList(
  raw: unknown,
  fallback: StrategyMatrixFilter[],
): StrategyMatrixFilter[] {
  if (!Array.isArray(raw)) return [...fallback];
  const out: StrategyMatrixFilter[] = [];
  const seen = new Set<StrategyMatrixFilter>();
  for (const item of raw) {
    if (item !== 'saved' && !isFilterId(item)) continue;
    const id = normalizeStrategyMatrixFilter(item);
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out.length > 0 ? out : [...fallback];
}

export function defaultStrategyMatrixFilterCarouselPrefs(): StrategyMatrixFilterCarouselPrefs {
  return {
    visibleIds: [...DEFAULT_STRATEGY_MATRIX_FILTER_VISIBLE],
    favoriteIds: [...DEFAULT_STRATEGY_MATRIX_FILTER_FAVORITES],
  };
}

export function normalizeStrategyMatrixFilterCarouselPrefs(
  raw: unknown,
): StrategyMatrixFilterCarouselPrefs {
  const d = defaultStrategyMatrixFilterCarouselPrefs();
  if (!raw || typeof raw !== 'object') return d;
  const o = raw as Partial<StrategyMatrixFilterCarouselPrefs>;
  let visibleIds = normalizeIdList(o.visibleIds, d.visibleIds);
  if (visibleIds.length === 0) visibleIds = [...d.visibleIds];
  const favoriteIds = normalizeIdList(o.favoriteIds, d.favoriteIds).filter((id) =>
    visibleIds.includes(id),
  );
  return { visibleIds, favoriteIds };
}

export function loadStrategyMatrixFilterCarouselPrefs(): StrategyMatrixFilterCarouselPrefs {
  try {
    const raw = localStorage.getItem(STRATEGY_MATRIX_FILTER_CAROUSEL_PREFS_KEY);
    if (!raw) return defaultStrategyMatrixFilterCarouselPrefs();
    return normalizeStrategyMatrixFilterCarouselPrefs(JSON.parse(raw));
  } catch {
    return defaultStrategyMatrixFilterCarouselPrefs();
  }
}

export function saveStrategyMatrixFilterCarouselPrefs(
  prefs: StrategyMatrixFilterCarouselPrefs,
): void {
  const n = normalizeStrategyMatrixFilterCarouselPrefs(prefs);
  localStorage.setItem(STRATEGY_MATRIX_FILTER_CAROUSEL_PREFS_KEY, JSON.stringify(n));
}

export function toggleStrategyMatrixFilterVisible(
  prefs: StrategyMatrixFilterCarouselPrefs,
  id: StrategyMatrixFilter,
): StrategyMatrixFilterCarouselPrefs {
  const has = prefs.visibleIds.includes(id);
  if (has) {
    if (prefs.visibleIds.length <= 1) return prefs;
    return {
      visibleIds: prefs.visibleIds.filter((x) => x !== id),
      favoriteIds: prefs.favoriteIds.filter((x) => x !== id),
    };
  }
  const visibleIds = STRATEGY_MATRIX_FILTER_IDS.filter(
    (x) => x === id || prefs.visibleIds.includes(x),
  );
  return { ...prefs, visibleIds };
}

export function toggleStrategyMatrixFilterFavorite(
  prefs: StrategyMatrixFilterCarouselPrefs,
  id: StrategyMatrixFilter,
): StrategyMatrixFilterCarouselPrefs {
  if (!prefs.visibleIds.includes(id)) return prefs;
  const has = prefs.favoriteIds.includes(id);
  return {
    ...prefs,
    favoriteIds: has
      ? prefs.favoriteIds.filter((x) => x !== id)
      : [...prefs.favoriteIds, id],
  };
}

/** Orden de chips: favoritos (orden canónico) + resto visibles (orden canónico). */
export function orderedVisibleStrategyMatrixFilters(
  prefs: StrategyMatrixFilterCarouselPrefs,
): StrategyMatrixFilter[] {
  const visible = new Set(prefs.visibleIds);
  const fav = new Set(prefs.favoriteIds.filter((id) => visible.has(id)));
  const favorites = STRATEGY_MATRIX_FILTER_IDS.filter((id) => fav.has(id));
  const rest = STRATEGY_MATRIX_FILTER_IDS.filter(
    (id) => visible.has(id) && !fav.has(id),
  );
  return [...favorites, ...rest];
}
