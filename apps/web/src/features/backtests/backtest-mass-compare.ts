/**
 * Q3.3 — comparación masiva v1: lista × estrategias × TF (soft-cap).
 * Compone N×M llamadas a POST /backtests/run (sin batch API).
 */

import type { BacktestStrategyType } from '@bolsa/shared';
import { api } from '@/lib/api';
import type { ResolvedBacktestWindow } from '@/features/backtests/backtest-period';
import { LIST_AUTO_MAX_INSTRUMENTS } from '@/features/backtests/backtest-list-auto';

export const MASS_COMPARE_MAX_INSTRUMENTS = LIST_AUTO_MAX_INSTRUMENTS; // 40
export const MASS_COMPARE_MAX_STRATEGIES = 8;
export const MASS_COMPARE_MAX_CELLS = 120;

export type MassCompareCellStatus = 'pending' | 'running' | 'ok' | 'error' | 'skipped';

export type MassCompareCell = {
  instrumentId: string;
  symbol: string;
  strategyKey: string;
  strategyLabel: string;
  status: MassCompareCellStatus;
  error?: string;
  runId?: string;
  sharpeRatio?: number | null;
  totalReturnPct?: number;
  maxDrawdownPct?: number;
  tradeCount?: number;
};

export type MassCompareParams = {
  instrumentIds: string[];
  labels: Record<string, { symbol: string; name?: string }>;
  strategies: Array<{ key: string; label: string; strategyType?: BacktestStrategyType; strategyDefinitionId?: string }>;
  initialCash: number;
  commissionBps: number;
  slippageBps: number;
  timeframe: string;
  window: ResolvedBacktestWindow;
  maxInstruments?: number;
  maxStrategies?: number;
  concurrency?: number;
  onProgress?: (cells: MassCompareCell[], done: number, total: number) => void;
  signal?: AbortSignal;
};

function metricNum(
  metrics: Record<string, number | string | null> | undefined,
  key: string,
): number | null {
  if (!metrics) return null;
  const v = metrics[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

export function planMassCompareJobs(params: MassCompareParams): MassCompareCell[] {
  const maxI = params.maxInstruments ?? MASS_COMPARE_MAX_INSTRUMENTS;
  const maxS = params.maxStrategies ?? MASS_COMPARE_MAX_STRATEGIES;
  const ids = params.instrumentIds.slice(0, maxI);
  const strategies = params.strategies.slice(0, maxS);
  const cells: MassCompareCell[] = [];
  for (const id of ids) {
    const label = params.labels[id];
    for (const s of strategies) {
      cells.push({
        instrumentId: id,
        symbol: label?.symbol ?? id.slice(0, 8),
        strategyKey: s.key,
        strategyLabel: s.label,
        status: 'pending',
      });
    }
  }
  return cells.slice(0, MASS_COMPARE_MAX_CELLS);
}

/** Ranking: media Sharpe por instrumento (solo celdas ok). */
export function rankMassCompareByInstrument(cells: MassCompareCell[]): Array<{
  instrumentId: string;
  symbol: string;
  avgSharpe: number | null;
  okCount: number;
}> {
  const byInst = new Map<string, { symbol: string; sharpes: number[] }>();
  for (const c of cells) {
    if (c.status !== 'ok') continue;
    const cur = byInst.get(c.instrumentId) ?? { symbol: c.symbol, sharpes: [] };
    if (c.sharpeRatio != null) cur.sharpes.push(c.sharpeRatio);
    byInst.set(c.instrumentId, cur);
  }
  return [...byInst.entries()]
    .map(([instrumentId, v]) => ({
      instrumentId,
      symbol: v.symbol,
      avgSharpe:
        v.sharpes.length > 0
          ? v.sharpes.reduce((a, b) => a + b, 0) / v.sharpes.length
          : null,
      okCount: v.sharpes.length,
    }))
    .sort((a, b) => (b.avgSharpe ?? -Infinity) - (a.avgSharpe ?? -Infinity));
}

export async function runMassCompare(params: MassCompareParams): Promise<MassCompareCell[]> {
  const cells = planMassCompareJobs(params);
  const total = cells.length;
  let done = 0;
  const concurrency = Math.max(1, Math.min(params.concurrency ?? 3, 6));
  let next = 0;

  const emit = () => params.onProgress?.([...cells], done, total);
  emit();

  async function worker() {
    while (next < cells.length) {
      if (params.signal?.aborted) break;
      const i = next;
      next += 1;
      const cell = cells[i]!;
      cells[i] = { ...cell, status: 'running' };
      emit();

      const strat = params.strategies.find((s) => s.key === cell.strategyKey);
      try {
        const result = await api.runBacktest(
          {
            instrumentId: cell.instrumentId,
            ...(strat?.strategyDefinitionId
              ? { strategyDefinitionId: strat.strategyDefinitionId }
              : { strategyType: strat?.strategyType }),
            initialCash: params.initialCash,
            commissionBps: params.commissionBps,
            slippageBps: params.slippageBps,
            timeframe: params.timeframe,
            ...params.window,
          },
          { signal: params.signal },
        );
        if (params.signal?.aborted) {
          cells[i] = { ...cell, status: 'skipped', error: 'Cancelado' };
        } else {
          cells[i] = {
            ...cell,
            status: 'ok',
            runId: result.data.id,
            symbol: result.data.symbol || cell.symbol,
            totalReturnPct: result.data.totalReturnPct,
            maxDrawdownPct: result.data.maxDrawdownPct,
            tradeCount: result.data.tradeCount,
            sharpeRatio: metricNum(result.metrics, 'sharpeRatio'),
          };
        }
      } catch (error) {
        if (params.signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          cells[i] = { ...cell, status: 'skipped', error: 'Cancelado' };
        } else {
          cells[i] = {
            ...cell,
            status: 'error',
            error: error instanceof Error ? error.message : 'Error',
          };
        }
      }
      done += 1;
      emit();
    }
  }

  await Promise.all(Array.from({ length: concurrency }, () => worker()));

  if (params.signal?.aborted) {
    for (let i = 0; i < cells.length; i += 1) {
      if (cells[i]!.status === 'pending' || cells[i]!.status === 'running') {
        cells[i] = { ...cells[i]!, status: 'skipped', error: 'Cancelado' };
      }
    }
    emit();
  }

  return cells;
}

/** Heatmap norm 0..1 for Sharpe cells (null → null). */
export function massCompareHeatNorm(
  sharpe: number | null | undefined,
  min: number,
  max: number,
): number | null {
  if (sharpe == null || !Number.isFinite(sharpe)) return null;
  if (max <= min) return 0.5;
  return Math.max(0, Math.min(1, (sharpe - min) / (max - min)));
}
