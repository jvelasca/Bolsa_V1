import type { BacktestEquityPointDto, OhlcvBarDto } from '@bolsa/shared';
import type { ResolvedBacktestWindow } from '@/features/backtests/backtest-period';

/** Day key for comparing run window vs OHLCV timestamps. */
function dayKey(timestamp: string): string {
  return timestamp.slice(0, 10);
}

/**
 * Naive buy & hold % over [firstDate, lastDate] using closes (no costs).
 * Used as fallback when metrics.buyHoldReturnPct is missing (runs antiguos).
 */
export function buyHoldReturnFromBars(
  bars: OhlcvBarDto[] | undefined,
  firstDate: string,
  lastDate: string,
): number | null {
  if (!bars?.length) return null;
  const from = dayKey(firstDate);
  const to = dayKey(lastDate);
  const window = bars.filter((bar) => {
    const day = dayKey(bar.timestamp);
    return day >= from && day <= to;
  });
  const series = window.length >= 2 ? window : bars;
  return buyHoldReturnFromSeries(series);
}

/** Buy & hold % first→last close of a bar series (no costs). */
export function buyHoldReturnFromSeries(bars: OhlcvBarDto[] | undefined): number | null {
  if (!bars || bars.length < 2) return null;
  const first = bars[0]!.close;
  const last = bars[bars.length - 1]!.close;
  if (!(first > 0) || !Number.isFinite(first) || !Number.isFinite(last)) return null;
  return ((last - first) / first) * 100;
}

/** ~365 calendar days — trailing year for daily (and denser) series. */
export const TRAILING_YEAR_MS = 365 * 24 * 60 * 60 * 1000;

/**
 * Index of the first timestamp still inside the trailing window ending at `endIndex`.
 * Returns null if the series does not reach back ~1 year from the end (~85% of 365d).
 */
export function trailingYearStartIndex(
  timestamps: readonly string[] | undefined,
  endIndex = (timestamps?.length ?? 1) - 1,
): number | null {
  if (!timestamps?.length || endIndex < 1 || endIndex >= timestamps.length) return null;
  const endMs = Date.parse(timestamps[endIndex]!);
  if (!Number.isFinite(endMs)) return null;
  const cutoff = endMs - TRAILING_YEAR_MS;
  let start = endIndex;
  while (start > 0 && Date.parse(timestamps[start - 1]!) >= cutoff) {
    start -= 1;
  }
  const startMs = Date.parse(timestamps[start]!);
  if (!Number.isFinite(startMs) || endMs - startMs < TRAILING_YEAR_MS * 0.85) {
    return null;
  }
  return start;
}

export type TrailingYearReturns = {
  strategyPct: number;
  buyHoldPct: number;
  excessPct: number;
  from: string;
  to: string;
};

/**
 * Strategy + buy&hold + Δ over the trailing ~12 months ending at the last equity point.
 * Needs ≥ ~1 year of equity history; B&H from closes in the same calendar window.
 */
export function trailingYearReturns(
  equity: BacktestEquityPointDto[] | undefined,
  bars: OhlcvBarDto[] | undefined,
): TrailingYearReturns | null {
  if (!equity || equity.length < 2) return null;
  const end = equity.length - 1;
  const start = trailingYearStartIndex(
    equity.map((p) => p.timestamp),
    end,
  );
  if (start == null) return null;
  const fromEq = equity[start]!.equity;
  const toEq = equity[end]!.equity;
  if (!(fromEq > 0) || !Number.isFinite(fromEq) || !Number.isFinite(toEq)) return null;
  const strategyPct = ((toEq - fromEq) / fromEq) * 100;
  const from = equity[start]!.timestamp;
  const to = equity[end]!.timestamp;
  const buyHoldPct = buyHoldReturnFromBars(bars, from, to);
  if (buyHoldPct == null) return null;
  return {
    strategyPct,
    buyHoldPct,
    excessPct: strategyPct - buyHoldPct,
    from,
    to,
  };
}

/**
 * Recorta barras al periodo del wizard (API OHLCV solo trae `limit` + TF).
 * Sin dateFrom/dateTo → serie completa (p. ej. «Todo el historial»).
 */
export function filterBarsToBacktestWindow(
  bars: OhlcvBarDto[] | undefined,
  window: ResolvedBacktestWindow,
): OhlcvBarDto[] {
  if (!bars?.length) return [];
  const from = window.dateFrom ? dayKey(window.dateFrom) : null;
  const to = window.dateTo ? dayKey(window.dateTo) : null;
  if (!from && !to) return bars;
  return bars.filter((bar) => {
    const day = dayKey(bar.timestamp);
    if (from && day < from) return false;
    if (to && day > to) return false;
    return true;
  });
}

export function excessReturnPct(
  strategyReturnPct: number,
  buyHoldReturnPct: number | null | undefined,
): number | null {
  if (buyHoldReturnPct == null || !Number.isFinite(buyHoldReturnPct)) return null;
  return strategyReturnPct - buyHoldReturnPct;
}
