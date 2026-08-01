import type { BacktestTradeDto } from '@bolsa/shared';

export type ClosedRoundTrip = {
  entry: BacktestTradeDto;
  exit: BacktestTradeDto;
  /** Approximate PnL in currency (price delta × qty; costs not fully modeled). */
  pnl: number;
};

export type MovieTradeStats = {
  opsCount: number;
  buyCount: number;
  sellCount: number;
  closedCount: number;
  winners: number;
  losers: number;
  breakeven: number;
  moneyWon: number;
  moneyLost: number;
  /** Net of closed round trips. */
  closedNet: number;
  lastClosedPnl: number | null;
  lastTrade: BacktestTradeDto | null;
  openEntry: BacktestTradeDto | null;
  roundTrips: ClosedRoundTrip[];
};

function pairRoundTrips(trades: BacktestTradeDto[]): ClosedRoundTrip[] {
  const trips: ClosedRoundTrip[] = [];
  let open: BacktestTradeDto | null = null;
  for (const trade of trades) {
    if (trade.type === 'buy') {
      open = trade;
      continue;
    }
    if (trade.type === 'sell' && open) {
      const qty = Math.min(open.quantity, trade.quantity);
      const pnl = (trade.price - open.price) * qty;
      trips.push({ entry: open, exit: trade, pnl });
      open = null;
    }
  }
  return trips;
}

/** Open long entry at/before timestamp, if still held. */
export function openPositionAt(
  trades: BacktestTradeDto[],
  untilTimestamp: string | null | undefined,
): BacktestTradeDto | null {
  const visible =
    untilTimestamp == null
      ? trades
      : trades.filter((trade) => trade.timestamp <= untilTimestamp);
  let open: BacktestTradeDto | null = null;
  for (const trade of visible) {
    if (trade.type === 'buy') open = trade;
    if (trade.type === 'sell') open = null;
  }
  return open;
}

export function unrealizedFromEntry(
  entry: BacktestTradeDto,
  markPrice: number,
): { pnl: number; pct: number } {
  const qty = entry.quantity;
  const pnl = (markPrice - entry.price) * qty;
  const pct = entry.price > 0 ? ((markPrice - entry.price) / entry.price) * 100 : 0;
  return { pnl, pct };
}

/** Stats for the movie HUD — filter by replay cursor when provided. */
export function computeMovieTradeStats(
  trades: BacktestTradeDto[],
  untilTimestamp?: string | null,
): MovieTradeStats {
  const visible =
    untilTimestamp == null
      ? trades
      : trades.filter((trade) => trade.timestamp <= untilTimestamp);
  const roundTrips = pairRoundTrips(visible);
  let winners = 0;
  let losers = 0;
  let breakeven = 0;
  let moneyWon = 0;
  let moneyLost = 0;
  for (const trip of roundTrips) {
    if (trip.pnl > 0) {
      winners += 1;
      moneyWon += trip.pnl;
    } else if (trip.pnl < 0) {
      losers += 1;
      moneyLost += Math.abs(trip.pnl);
    } else {
      breakeven += 1;
    }
  }

  const openEntry = openPositionAt(trades, untilTimestamp);
  const lastClosed = roundTrips[roundTrips.length - 1] ?? null;

  return {
    opsCount: visible.length,
    buyCount: visible.filter((t) => t.type === 'buy').length,
    sellCount: visible.filter((t) => t.type === 'sell').length,
    closedCount: roundTrips.length,
    winners,
    losers,
    breakeven,
    moneyWon,
    moneyLost,
    closedNet: moneyWon - moneyLost,
    lastClosedPnl: lastClosed?.pnl ?? null,
    lastTrade: visible[visible.length - 1] ?? null,
    openEntry,
    roundTrips,
  };
}
