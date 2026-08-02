/**
 * Verificar D→hoy — continuidad de estrategia.
 *
 * El run API debe incluir lookback **antes** de D (indicadores + posición).
 * La película / métricas de sesión empiezan en D; un sell tras D de un buy ≤D
 * cuenta como operación (no arrancar flat el día D).
 *
 * @see docs/adr/021-dia-d-reconciliation.md
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md §1 fase C
 */

import type {
  BacktestEquityPointDto,
  BacktestRunDetailDto,
  BacktestTradeDto,
} from '@bolsa/shared';
import { isoDateUTC } from '@/features/backtests/backtest-period';
import { equityCurveFromDetail } from '@/features/backtests/backtest-export';
import {
  maxDrawdownPct,
  rebuildEquityCurve,
} from '@/features/trading/dia-d-gate-equity';

/** Años de historial previo a D para warmup (cubre SMA 200 / SuperTrend). */
export const VERIFY_LOOKBACK_YEARS = 3;

export function dayKey(timestamp: string): string {
  return timestamp.slice(0, 10);
}

/** dateFrom del POST Verify: D − N años (nunca posterior a D). */
export function verifyApiDateFrom(diaD: string, years = VERIFY_LOOKBACK_YEARS): string {
  const raw = diaD.trim().slice(0, 10);
  const d = new Date(`${raw}T12:00:00.000Z`);
  if (Number.isNaN(d.getTime())) return raw;
  d.setUTCFullYear(d.getUTCFullYear() - years);
  return isoDateUTC(d);
}

export type PortfolioAt = {
  cash: number;
  shares: number;
  /** Mark-to-market si hay precio; si no, cash + 0. */
  equity: number;
};

/** Estado de cartera justo antes del primer fill con día ≥ D. */
export function portfolioJustBeforeDiaD(
  initialCash: number,
  trades: ReadonlyArray<BacktestTradeDto>,
  diaD: string,
  markPrice?: number | null,
): PortfolioAt {
  let cash = initialCash;
  let shares = 0;
  const d = dayKey(diaD);
  for (const trade of trades) {
    if (dayKey(trade.timestamp) >= d) break;
    const notional = trade.price * trade.quantity;
    if (trade.type === 'buy') {
      cash -= notional;
      shares += trade.quantity;
    } else {
      cash += notional;
      shares -= trade.quantity;
      if (shares < 0) shares = 0;
    }
  }
  const px = markPrice != null && Number.isFinite(markPrice) ? markPrice : 0;
  return {
    cash,
    shares,
    equity: cash + shares * px,
  };
}

export function tradesOnOrAfterDiaD(
  trades: ReadonlyArray<BacktestTradeDto>,
  diaD: string,
): BacktestTradeDto[] {
  const d = dayKey(diaD);
  return trades.filter((t) => dayKey(t.timestamp) >= d);
}

export function equityFromDiaD(
  curve: ReadonlyArray<BacktestEquityPointDto>,
  diaD: string,
): BacktestEquityPointDto[] {
  const d = dayKey(diaD);
  return curve.filter((p) => dayKey(p.timestamp) >= d);
}

/**
 * Recorta un run lookback→hoy a la ventana de sesión D→hoy,
 * conservando posición abierta a D (retorno desde equity@D).
 */
export function sliceDetailFromDiaD(
  detail: BacktestRunDetailDto,
  diaD: string,
  bars?: ReadonlyArray<{ timestamp: string; close: number }>,
): BacktestRunDetailDto {
  const d = dayKey(diaD);
  const fullCurve =
    detail.equityCurve && detail.equityCurve.length > 0
      ? detail.equityCurve
      : equityCurveFromDetail(detail);

  const markBar =
    bars?.find((b) => dayKey(b.timestamp) >= d) ??
    bars?.find((b) => dayKey(b.timestamp) <= d);
  const port = portfolioJustBeforeDiaD(
    detail.initialCash,
    detail.trades,
    d,
    markBar?.close ?? null,
  );

  const oosTrades = tradesOnOrAfterDiaD(detail.trades, d);
  const fromDBars = (bars ?? []).filter((b) => dayKey(b.timestamp) >= d);

  let equityCurve: BacktestEquityPointDto[];
  if (fromDBars.length > 0) {
    equityCurve = rebuildEquityCurve({
      initialCash: port.cash,
      initialShares: port.shares,
      bars: fromDBars,
      trades: oosTrades,
    });
  } else {
    equityCurve = equityFromDiaD(fullCurve, d);
  }

  const equityAtStart = equityCurve[0]?.equity ?? (port.equity > 0 ? port.equity : detail.initialCash);
  const finalEquity =
    equityCurve.length > 0
      ? equityCurve[equityCurve.length - 1]!.equity
      : equityAtStart;
  const totalReturnPct =
    equityAtStart > 0 ? ((finalEquity - equityAtStart) / equityAtStart) * 100 : 0;

  const firstOos = fromDBars[0]?.timestamp ?? oosTrades[0]?.timestamp ?? detail.firstDate;
  const lastOos =
    fromDBars[fromDBars.length - 1]?.timestamp ??
    oosTrades[oosTrades.length - 1]?.timestamp ??
    detail.lastDate;

  return {
    ...detail,
    trades: oosTrades,
    tradeCount: oosTrades.length,
    equityCurve,
    initialCash: equityAtStart,
    finalEquity,
    totalReturnPct,
    maxDrawdownPct: maxDrawdownPct(equityCurve),
    firstDate: firstOos,
    lastDate: lastOos,
    barCount: fromDBars.length > 0 ? fromDBars.length : detail.barCount,
  };
}
