import {
  BACKTEST_STRATEGIES,
  STRATEGY_PRESET_CATEGORY_LABELS,
  STRATEGY_PRESET_KEYS,
  type BacktestStrategyType,
  type StrategyDefinitionSummaryDto,
} from '@bolsa/shared';
import { api } from '@/lib/api';
import type { ResolvedBacktestWindow } from '@/features/backtests/backtest-period';
import { periodReturnsFromEquity } from '@/features/backtests/backtest-period-returns';

export const STRATEGY_MATRIX_MAX_SELECTED = 40;

export type StrategyMatrixFilter = 'all' | 'preset' | 'saved' | 'finalists';

export type StrategyMatrixRowStatus = 'idle' | 'pending' | 'running' | 'ok' | 'error' | 'skipped';

export type StrategyMatrixRow = {
  rowId: string;
  kind: 'preset' | 'saved';
  label: string;
  subtitle: string;
  presetKey?: BacktestStrategyType;
  strategyDefinitionId?: string;
  /** Rank 1–3 si forma parte del InstrumentStrategyTop del valor. */
  topRank?: 1 | 2 | 3;
  status: StrategyMatrixRowStatus;
  error?: string;
  runId?: string;
  totalReturnPct?: number;
  buyHoldReturnPct?: number | null;
  excessReturnPct?: number | null;
  tradeCount?: number;
  maxDrawdownPct?: number;
  barCount?: number;
  sharpeRatio?: number | null;
  /**
   * Tercios de equity al cerrar el run (misma fuente que el coach ★).
   * Evita depender del caché RQ / prune de historial.
   */
  periodReturns?: {
    early: number;
    mid: number;
    late: number;
  } | null;
};

function metricNum(
  metrics: Record<string, number | string | null> | undefined,
  key: string,
): number | null {
  if (!metrics) return null;
  const v = metrics[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

export function buildStrategyMatrixRows(
  saved: StrategyDefinitionSummaryDto[],
): StrategyMatrixRow[] {
  const presets: StrategyMatrixRow[] = STRATEGY_PRESET_KEYS.map((presetKey) => {
    const meta = BACKTEST_STRATEGIES[presetKey];
    const category = meta?.category ?? 'trend';
    return {
      rowId: `preset:${presetKey}`,
      kind: 'preset',
      label: meta?.label ?? presetKey,
      subtitle: STRATEGY_PRESET_CATEGORY_LABELS[category] ?? category,
      presetKey,
      status: 'idle',
    };
  });

  const savedRows: StrategyMatrixRow[] = saved.map((s) => {
    const presetLabel = s.presetKey
      ? (BACKTEST_STRATEGIES[s.presetKey]?.label ?? s.presetKey)
      : null;
    return {
      rowId: `saved:${s.id}`,
      kind: 'saved',
      label: s.name,
      subtitle: presetLabel ? `Mía · ${presetLabel}` : 'Mis estrategias',
      presetKey: s.presetKey ?? undefined,
      strategyDefinitionId: s.id,
      status: 'idle',
    };
  });

  return [...presets, ...savedRows];
}

/** Marca filas del TOP del valor (definitionId preferente; si no, preset por tipo). */
export function annotateStrategyMatrixRowsWithTop(
  rows: StrategyMatrixRow[],
  top: {
    slots?: Array<{
      rank: 1 | 2 | 3;
      strategyDefinitionId?: string | null;
      strategyType?: string | null;
    }>;
  } | null,
): StrategyMatrixRow[] {
  if (!top?.slots?.length) {
    return rows.map((r) => (r.topRank != null ? { ...r, topRank: undefined } : r));
  }
  const byDef = new Map<string, 1 | 2 | 3>();
  const typeByDef = new Map<string, string>();
  const byTypeOnly = new Map<string, 1 | 2 | 3>();
  for (const slot of top.slots) {
    if (slot.strategyDefinitionId) {
      byDef.set(slot.strategyDefinitionId, slot.rank);
      // Solo para rellenar presetKey en la fila saved — no marca también la genérica
      // (evita 3 finalistas → 6 filas: saved + preset).
      if (slot.strategyType) typeByDef.set(slot.strategyDefinitionId, slot.strategyType);
    } else if (slot.strategyType) {
      byTypeOnly.set(slot.strategyType, slot.rank);
    }
  }
  return rows.map((row) => {
    let topRank: 1 | 2 | 3 | undefined;
    let presetKey = row.presetKey;
    if (row.strategyDefinitionId && byDef.has(row.strategyDefinitionId)) {
      topRank = byDef.get(row.strategyDefinitionId);
      const fromSlot = typeByDef.get(row.strategyDefinitionId);
      if (!presetKey && fromSlot && fromSlot in BACKTEST_STRATEGIES) {
        presetKey = fromSlot as BacktestStrategyType;
      }
    } else if (row.kind === 'preset' && row.presetKey && byTypeOnly.has(row.presetKey)) {
      topRank = byTypeOnly.get(row.presetKey);
    }
    if (row.topRank === topRank && row.presetKey === presetKey) return row;
    return { ...row, topRank, presetKey };
  });
}

export function filterStrategyMatrixRows(
  rows: StrategyMatrixRow[],
  filter: StrategyMatrixFilter,
): StrategyMatrixRow[] {
  if (filter === 'preset') return rows.filter((r) => r.kind === 'preset');
  if (filter === 'saved') return rows.filter((r) => r.kind === 'saved');
  if (filter === 'finalists') return rows.filter((r) => r.topRank != null);
  return rows;
}

export function exploreBatteryRowIds(): string[] {
  return STRATEGY_PRESET_KEYS.map((key) => `preset:${key}`);
}

export type StrategyMatrixRunProgress = {
  done: number;
  total: number;
  ok: number;
  error: number;
  skipped: number;
  pending: number;
  runningLabels: string[];
  /** Telemetría ligera (Auditoría 2) — ms desde el arranque de la batería. */
  elapsedMs?: number;
};

export type StrategyMatrixRunParams = {
  instrumentId: string;
  selectedRowIds: string[];
  rows: StrategyMatrixRow[];
  initialCash: number;
  commissionBps: number;
  slippageBps: number;
  timeframe: string;
  window: ResolvedBacktestWindow;
  /** Concurrent backtests (capped). Default 4. */
  concurrency?: number;
  onProgress?: (
    rows: StrategyMatrixRow[],
    progress: StrategyMatrixRunProgress,
  ) => void;
  /** Called for each successful run so the UI can cache detail (avoid prune race). */
  onRunComplete?: (detail: import('@bolsa/shared').BacktestRunDetailDto) => void;
  signal?: AbortSignal;
};

function buildProgress(
  selectedIds: string[],
  byId: Map<string, StrategyMatrixRow>,
  done: number,
  total: number,
  elapsedMs?: number,
): StrategyMatrixRunProgress {
  let ok = 0;
  let error = 0;
  let skipped = 0;
  let pending = 0;
  const runningLabels: string[] = [];
  for (const id of selectedIds) {
    const row = byId.get(id);
    if (!row) continue;
    if (row.status === 'ok') ok += 1;
    else if (row.status === 'error') error += 1;
    else if (row.status === 'skipped') skipped += 1;
    else if (row.status === 'pending') pending += 1;
    else if (row.status === 'running') runningLabels.push(row.label);
  }
  return { done, total, ok, error, skipped, pending, runningLabels, elapsedMs };
}

/**
 * Run checked strategies on one instrument.
 * Results merge into the full row list (non-selected rows stay as-is).
 * Abort: pending/running → skipped; a response that arrives after abort is discarded (not shown as OK).
 */
export async function runStrategyMatrixBattery(
  params: StrategyMatrixRunParams,
): Promise<StrategyMatrixRow[]> {
  const byId = new Map(params.rows.map((r) => [r.rowId, { ...r }]));
  const selected = params.selectedRowIds
    .map((id) => byId.get(id))
    .filter((r): r is StrategyMatrixRow => Boolean(r));
  const selectedIds = selected.map((r) => r.rowId);

  for (const row of selected) {
    byId.set(row.rowId, {
      ...row,
      status: 'pending',
      error: undefined,
      runId: undefined,
      totalReturnPct: undefined,
      buyHoldReturnPct: undefined,
      excessReturnPct: undefined,
      tradeCount: undefined,
      maxDrawdownPct: undefined,
      barCount: undefined,
      sharpeRatio: undefined,
      periodReturns: undefined,
    });
  }

  const total = selected.length;
  let done = 0;
  const startedAt = performance.now();
  const emit = () => {
    params.onProgress?.(
      params.rows.map((r) => byId.get(r.rowId) ?? r),
      buildProgress(selectedIds, byId, done, total, Math.round(performance.now() - startedAt)),
    );
  };
  emit();

  const concurrency = Math.max(1, Math.min(params.concurrency ?? 4, STRATEGY_MATRIX_MAX_SELECTED));
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < selected.length) {
      if (params.signal?.aborted) break;
      const i = nextIndex;
      nextIndex += 1;
      const base = selected[i]!;
      const current = byId.get(base.rowId)!;
      byId.set(base.rowId, { ...current, status: 'running', error: undefined });
      emit();

      try {
        const result = await api.runBacktest(
          {
            instrumentId: params.instrumentId,
            ...(base.kind === 'saved' && base.strategyDefinitionId
              ? {
                  strategyDefinitionId: base.strategyDefinitionId,
                  // Fallback if the API still strips preset on old builds: also send type when known.
                  ...(base.presetKey ? { strategyType: base.presetKey } : {}),
                }
              : { strategyType: base.presetKey! }),
            initialCash: params.initialCash,
            commissionBps: params.commissionBps,
            slippageBps: params.slippageBps,
            timeframe: params.timeframe,
            ...params.window,
          },
          { signal: params.signal },
        );

        // Cancelled while in flight (or right after): do not keep the result in the UI.
        if (params.signal?.aborted) {
          byId.set(base.rowId, {
            ...current,
            status: 'skipped',
            error: 'Cancelado — no finalizada',
            runId: undefined,
          });
        } else {
          const equity =
            result.data.equityCurve ??
            (result.data.manifest?.outputs?.equityCurve as
              | Array<{ equity: number }>
              | undefined);
          byId.set(base.rowId, {
            ...current,
            status: 'ok',
            runId: result.data.id,
            totalReturnPct: result.data.totalReturnPct,
            maxDrawdownPct: result.data.maxDrawdownPct,
            tradeCount: result.data.tradeCount,
            barCount: result.data.barCount,
            buyHoldReturnPct: metricNum(result.metrics, 'buyHoldReturnPct'),
            excessReturnPct: metricNum(result.metrics, 'excessReturnPct'),
            sharpeRatio: metricNum(result.metrics, 'sharpeRatio'),
            periodReturns: periodReturnsFromEquity(equity),
          });
          params.onRunComplete?.(result.data);
        }
      } catch (error) {
        if (params.signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          byId.set(base.rowId, {
            ...current,
            status: 'skipped',
            error: 'Cancelado — no finalizada',
          });
        } else {
          const message = error instanceof Error ? error.message : 'Error al ejecutar';
          byId.set(base.rowId, { ...current, status: 'error', error: message });
        }
      }

      done += 1;
      emit();
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, total) }, () => worker()));

  if (params.signal?.aborted) {
    for (const row of selected) {
      const cur = byId.get(row.rowId)!;
      if (cur.status === 'pending' || cur.status === 'running') {
        byId.set(row.rowId, {
          ...cur,
          status: 'skipped',
          error: 'Cancelado — no finalizada',
          runId: undefined,
        });
      }
    }
    emit();
  }

  return params.rows.map((r) => byId.get(r.rowId) ?? r);
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}
