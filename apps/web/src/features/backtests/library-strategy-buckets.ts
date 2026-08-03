/**
 * Cajones de Biblioteca (L0 2026-08-03).
 *
 * - Genéricas: presets del catálogo (no filas BD).
 * - Genéricas optimizadas: clones / Lab adopt (origin preset).
 * - Mis estrategias: autoría (manual sin preset, assisted, ai_generated, imported).
 * - Finalistas: TOP del valor (sin cambio).
 */

import type { StrategyOrigin } from '@bolsa/shared';

export type StrategiesListFilter = 'all' | 'generics' | 'optimized' | 'mine' | 'finalists';

export type LibrarySavedBucket = 'optimized' | 'mine';

export const LIBRARY_FILTER_LABELS: Record<StrategiesListFilter, string> = {
  all: 'Todas',
  generics: 'Genéricas',
  optimized: 'Optimizadas',
  mine: 'Mis estrategias',
  finalists: 'Finalistas',
};

/** Copy corto para chips / tooltips. */
export const LIBRARY_FILTER_TITLES: Record<StrategiesListFilter, string> = {
  all: 'Catálogo + optimizadas + mis autorías',
  generics: 'Plantillas del catálogo (no guardadas)',
  optimized: 'Clones y ajustes Lab sobre genéricas',
  mine: 'Autoría propia (manual, prompt IA, asistida, import)',
  finalists: 'TOP del valor seleccionado en Probar',
};

export type LibraryBucketable = {
  origin: string;
  presetKey?: string | null;
};

/**
 * Clasifica una estrategia guardada.
 * `preset` → optimizada. Legacy Lab (`manual` + presetKey) también → optimizada.
 */
export function librarySavedBucket(s: LibraryBucketable): LibrarySavedBucket {
  if (s.origin === 'preset') return 'optimized';
  // Lab adoptaba como manual + presetKey antes de L0.
  if (s.origin === 'manual' && s.presetKey) return 'optimized';
  return 'mine';
}

export function filterStrategiesByLibraryBucket<T extends LibraryBucketable>(
  strategies: T[],
  filter: StrategiesListFilter,
): T[] {
  if (filter === 'generics' || filter === 'finalists') return [];
  if (filter === 'all') return strategies;
  const want: LibrarySavedBucket = filter === 'optimized' ? 'optimized' : 'mine';
  return strategies.filter((s) => librarySavedBucket(s) === want);
}

export function countLibraryBuckets(strategies: LibraryBucketable[]): {
  optimized: number;
  mine: number;
} {
  let optimized = 0;
  let mine = 0;
  for (const s of strategies) {
    if (librarySavedBucket(s) === 'optimized') optimized += 1;
    else mine += 1;
  }
  return { optimized, mine };
}

/** Etiquetas de origen alineadas a L0. */
export const LIBRARY_ORIGIN_LABELS: Record<StrategyOrigin, string> = {
  manual: 'Manual',
  assisted: 'Asistida',
  ai_generated: 'Prompt IA',
  imported: 'Importada',
  preset: 'Optimizada',
};

export function normalizeStrategiesListFilter(raw: unknown): StrategiesListFilter {
  if (
    raw === 'all' ||
    raw === 'generics' ||
    raw === 'optimized' ||
    raw === 'mine' ||
    raw === 'finalists'
  ) {
    return raw;
  }
  return 'all';
}
