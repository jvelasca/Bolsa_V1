/** Preferencias de zona Backtesting (localStorage). */

import type { StrategyMatrixFilter } from '@/features/backtests/backtest-strategy-matrix';
import {
  DEFAULT_STRATEGY_MATRIX_COLUMN_LAYOUT,
  DEFAULT_STRATEGY_MATRIX_FAVORITE_COLUMN_IDS,
  normalizeStrategyMatrixFavorites,
  normalizeStrategyMatrixLayout,
  normalizeStrategyMatrixSort,
  type StrategyMatrixColumnId,
  type StrategyMatrixColumnLayoutItem,
  type StrategyMatrixSortState,
} from '@/features/backtests/strategy-matrix-column-layout';

export const BACKTEST_ZONE_PREFS_KEY = 'bolsa-backtest-zone-prefs-v1';

export const BACKTEST_HISTORY_MAX_DEFAULT = 20;
export const BACKTEST_HISTORY_MAX_MIN = 5;
export const BACKTEST_HISTORY_MAX_MAX = 100;

export const MATRIX_SELECT_BATCH_DEFAULT = 8;
export const MATRIX_SELECT_BATCH_MIN = 1;
export const MATRIX_SELECT_BATCH_MAX = 20;

export const MATRIX_LIST_HEIGHT_DEFAULT = 280;
export const MATRIX_LIST_HEIGHT_MIN = 140;
export const MATRIX_LIST_HEIGHT_MAX = 720;

export type StrategyMatrixTablePrefs = {
  columnLayout: StrategyMatrixColumnLayoutItem[];
  sort: StrategyMatrixSortState | null;
  favoriteColumnIds: StrategyMatrixColumnId[];
  /** Filtro Todas / Genéricas / Mis estrategias (persistente). */
  filter: StrategyMatrixFilter;
  /** Cuántas pendientes marca el check de cabecera / Marcar genéricas. */
  selectBatchSize: number;
  /** Altura del listado de estrategias (px). */
  listHeightPx: number;
};

export type BacktestZonePrefs = {
  /** Máximo de pruebas anteriores a conservar en BD (borra las más viejas). */
  historyMaxKept: number;
  strategyMatrix: StrategyMatrixTablePrefs;
};

export function clampHistoryMaxKept(value: number): number {
  if (!Number.isFinite(value)) return BACKTEST_HISTORY_MAX_DEFAULT;
  return Math.min(
    BACKTEST_HISTORY_MAX_MAX,
    Math.max(BACKTEST_HISTORY_MAX_MIN, Math.round(value)),
  );
}

export function clampSelectBatchSize(value: number): number {
  if (!Number.isFinite(value)) return MATRIX_SELECT_BATCH_DEFAULT;
  return Math.min(
    MATRIX_SELECT_BATCH_MAX,
    Math.max(MATRIX_SELECT_BATCH_MIN, Math.round(value)),
  );
}

export function clampListHeightPx(value: number): number {
  if (!Number.isFinite(value)) return MATRIX_LIST_HEIGHT_DEFAULT;
  return Math.min(
    MATRIX_LIST_HEIGHT_MAX,
    Math.max(MATRIX_LIST_HEIGHT_MIN, Math.round(value)),
  );
}

function normalizeStrategyFilter(raw: unknown): StrategyMatrixFilter {
  if (raw === 'preset' || raw === 'saved' || raw === 'all' || raw === 'finalists') return raw;
  return 'all';
}

export function defaultStrategyMatrixTablePrefs(): StrategyMatrixTablePrefs {
  return {
    columnLayout: DEFAULT_STRATEGY_MATRIX_COLUMN_LAYOUT.map((c) => ({ ...c })),
    sort: null,
    favoriteColumnIds: [...DEFAULT_STRATEGY_MATRIX_FAVORITE_COLUMN_IDS],
    filter: 'all',
    selectBatchSize: MATRIX_SELECT_BATCH_DEFAULT,
    listHeightPx: MATRIX_LIST_HEIGHT_DEFAULT,
  };
}

function normalizeStrategyMatrixPrefs(
  raw: Partial<StrategyMatrixTablePrefs> | undefined,
): StrategyMatrixTablePrefs {
  if (!raw) return defaultStrategyMatrixTablePrefs();
  return {
    columnLayout: normalizeStrategyMatrixLayout(raw.columnLayout),
    sort: normalizeStrategyMatrixSort(raw.sort ?? null),
    favoriteColumnIds: normalizeStrategyMatrixFavorites(raw.favoriteColumnIds),
    filter: normalizeStrategyFilter(raw.filter),
    selectBatchSize: clampSelectBatchSize(
      typeof raw.selectBatchSize === 'number'
        ? raw.selectBatchSize
        : MATRIX_SELECT_BATCH_DEFAULT,
    ),
    listHeightPx: clampListHeightPx(
      typeof raw.listHeightPx === 'number' ? raw.listHeightPx : MATRIX_LIST_HEIGHT_DEFAULT,
    ),
  };
}

const DEFAULTS: BacktestZonePrefs = {
  historyMaxKept: BACKTEST_HISTORY_MAX_DEFAULT,
  strategyMatrix: defaultStrategyMatrixTablePrefs(),
};

export function loadBacktestZonePrefs(): BacktestZonePrefs {
  try {
    const raw = localStorage.getItem(BACKTEST_ZONE_PREFS_KEY);
    if (!raw) return { ...DEFAULTS, strategyMatrix: defaultStrategyMatrixTablePrefs() };
    const parsed = JSON.parse(raw) as Partial<BacktestZonePrefs>;
    return {
      historyMaxKept: clampHistoryMaxKept(
        typeof parsed.historyMaxKept === 'number'
          ? parsed.historyMaxKept
          : DEFAULTS.historyMaxKept,
      ),
      strategyMatrix: normalizeStrategyMatrixPrefs(parsed.strategyMatrix),
    };
  } catch {
    return { ...DEFAULTS, strategyMatrix: defaultStrategyMatrixTablePrefs() };
  }
}

export function saveBacktestZonePrefs(prefs: BacktestZonePrefs): void {
  const strategyMatrix = normalizeStrategyMatrixPrefs(
    prefs.strategyMatrix ?? loadBacktestZonePrefs().strategyMatrix,
  );
  localStorage.setItem(
    BACKTEST_ZONE_PREFS_KEY,
    JSON.stringify({
      historyMaxKept: clampHistoryMaxKept(prefs.historyMaxKept),
      strategyMatrix: {
        columnLayout: strategyMatrix.columnLayout,
        sort: strategyMatrix.sort,
        favoriteColumnIds: strategyMatrix.favoriteColumnIds,
        filter: strategyMatrix.filter,
        selectBatchSize: strategyMatrix.selectBatchSize,
        listHeightPx: strategyMatrix.listHeightPx,
      },
    }),
  );
}

export function patchStrategyMatrixTablePrefs(
  patch: Partial<StrategyMatrixTablePrefs>,
): StrategyMatrixTablePrefs {
  const current = loadBacktestZonePrefs();
  const nextMatrix = normalizeStrategyMatrixPrefs({
    ...current.strategyMatrix,
    ...patch,
    columnLayout: patch.columnLayout ?? current.strategyMatrix.columnLayout,
    sort: patch.sort !== undefined ? patch.sort : current.strategyMatrix.sort,
    favoriteColumnIds: patch.favoriteColumnIds ?? current.strategyMatrix.favoriteColumnIds,
    filter: patch.filter ?? current.strategyMatrix.filter,
    selectBatchSize: patch.selectBatchSize ?? current.strategyMatrix.selectBatchSize,
    listHeightPx: patch.listHeightPx ?? current.strategyMatrix.listHeightPx,
  });
  saveBacktestZonePrefs({ ...current, strategyMatrix: nextMatrix });
  return nextMatrix;
}
