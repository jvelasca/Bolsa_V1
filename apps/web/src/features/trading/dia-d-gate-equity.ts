/**
 * DÍA D — aplica decisiones Semi/Manual sobre el run Auto y reconstruye equity.
 * Long-only: reject = no ejecutar; buy con posición abierta se ignora; sell en flat se ignora.
 *
 * Política:
 * - `auto`: ejecuta todos salvo `reject` explícito.
 * - `gated` (Semi/Manual): solo ejecuta `accept`; undecided y reject no rellenan.
 * - Reject de un buy anula el sell emparejado (parejas FIFO).
 *
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md §3c
 */

import type {
  BacktestEquityPointDto,
  BacktestRunDetailDto,
  BacktestTradeDto,
} from '@bolsa/shared';

export type GateDecisionLike = {
  tradeId: string;
  action: 'accept' | 'reject';
};

export type GateFillPolicy = 'auto' | 'gated';

/** Trades que realmente se ejecutan tras el gate (orden temporal del Auto). */
export function applyGateFills(
  trades: BacktestTradeDto[],
  decisions: ReadonlyArray<GateDecisionLike>,
  policy: GateFillPolicy = 'auto',
  opts?: { initialShares?: number },
): BacktestTradeDto[] {
  const decision = new Map(decisions.map((d) => [d.tradeId, d.action]));
  const applied: BacktestTradeDto[] = [];
  let shares = opts?.initialShares ?? 0;
  for (const trade of trades) {
    const action = decision.get(trade.id);
    if (policy === 'gated') {
      if (action !== 'accept') continue;
    } else if (action === 'reject') {
      continue;
    }
    if (trade.type === 'buy') {
      if (shares > 0) continue;
      shares = trade.quantity;
      applied.push(trade);
      continue;
    }
    if (trade.type === 'sell') {
      if (shares <= 0) continue;
      shares = 0;
      applied.push(trade);
    }
  }
  return applied;
}

export function rebuildEquityCurve(opts: {
  initialCash: number;
  /** Posición ya abierta al inicio de la ventana (p. ej. carry a DÍA D). */
  initialShares?: number;
  bars: ReadonlyArray<{ timestamp: string; close: number }>;
  trades: ReadonlyArray<BacktestTradeDto>;
}): BacktestEquityPointDto[] {
  let cash = opts.initialCash;
  let shares = opts.initialShares ?? 0;
  let tradeIdx = 0;
  const curve: BacktestEquityPointDto[] = [];

  for (const bar of opts.bars) {
    while (
      tradeIdx < opts.trades.length &&
      opts.trades[tradeIdx]!.timestamp <= bar.timestamp
    ) {
      const trade = opts.trades[tradeIdx]!;
      const notional = trade.price * trade.quantity;
      if (trade.type === 'buy') {
        cash -= notional;
        shares += trade.quantity;
      } else {
        cash += notional;
        shares -= trade.quantity;
        if (shares < 0) shares = 0;
      }
      tradeIdx += 1;
    }
    curve.push({
      timestamp: bar.timestamp,
      equity: cash + shares * bar.close,
    });
  }
  return curve;
}

export function maxDrawdownPct(curve: ReadonlyArray<BacktestEquityPointDto>): number {
  if (curve.length === 0) return 0;
  let peak = curve[0]!.equity;
  let maxDd = 0;
  for (const point of curve) {
    if (point.equity > peak) peak = point.equity;
    if (peak > 0) {
      const dd = ((peak - point.equity) / peak) * 100;
      if (dd > maxDd) maxDd = dd;
    }
  }
  return maxDd;
}

export type GatedSessionMetrics = {
  trades: BacktestTradeDto[];
  equityCurve: BacktestEquityPointDto[];
  finalEquity: number;
  totalReturnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
};

export function computeGatedSessionMetrics(opts: {
  initialCash: number;
  /** Carry de posición al inicio (Verify continuo desde D). */
  initialShares?: number;
  bars: ReadonlyArray<{ timestamp: string; close: number }>;
  autoTrades: ReadonlyArray<BacktestTradeDto>;
  decisions: ReadonlyArray<GateDecisionLike>;
  policy?: GateFillPolicy;
}): GatedSessionMetrics {
  const policy = opts.policy ?? 'auto';
  const initialShares = opts.initialShares ?? 0;
  const trades = applyGateFills([...opts.autoTrades], opts.decisions, policy, {
    initialShares,
  });
  const equityCurve = rebuildEquityCurve({
    initialCash: opts.initialCash,
    initialShares,
    bars: opts.bars,
    trades,
  });
  const startEquity =
    opts.bars.length > 0
      ? opts.initialCash + initialShares * opts.bars[0]!.close
      : opts.initialCash;
  const finalEquity =
    equityCurve.length > 0
      ? equityCurve[equityCurve.length - 1]!.equity
      : startEquity;
  const totalReturnPct =
    startEquity > 0 ? ((finalEquity - startEquity) / startEquity) * 100 : 0;
  return {
    trades,
    equityCurve,
    finalEquity,
    totalReturnPct,
    maxDrawdownPct: maxDrawdownPct(equityCurve),
    tradeCount: trades.length,
  };
}

/** Overlay del run Auto con fills/equity del gate (misma id para no resetear la película). */
export function detailWithGatedFills(
  detail: BacktestRunDetailDto,
  gated: GatedSessionMetrics,
): BacktestRunDetailDto {
  return {
    ...detail,
    trades: gated.trades,
    equityCurve: gated.equityCurve,
    finalEquity: gated.finalEquity,
    totalReturnPct: gated.totalReturnPct,
    maxDrawdownPct: gated.maxDrawdownPct,
    tradeCount: gated.tradeCount,
  };
}
