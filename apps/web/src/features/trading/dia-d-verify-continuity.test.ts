import { describe, expect, it } from 'vitest';
import type { BacktestRunDetailDto, BacktestTradeDto } from '@bolsa/shared';
import {
  portfolioJustBeforeDiaD,
  sliceDetailFromDiaD,
  tradesOnOrAfterDiaD,
  verifyApiDateFrom,
} from '@/features/trading/dia-d-verify-continuity';

function trade(
  partial: Partial<BacktestTradeDto> & Pick<BacktestTradeDto, 'id' | 'type' | 'timestamp'>,
): BacktestTradeDto {
  return {
    price: 100,
    quantity: 10,
    equityAfter: 10_000,
    ...partial,
  };
}

describe('dia-d-verify-continuity', () => {
  it('verifyApiDateFrom resta años de lookback', () => {
    expect(verifyApiDateFrom('2025-08-01', 3)).toBe('2022-08-01');
  });

  it('portfolioJustBeforeDiaD detecta posición abierta a D', () => {
    const port = portfolioJustBeforeDiaD(
      10_000,
      [
        trade({ id: 'b1', type: 'buy', timestamp: '2025-01-10T00:00:00Z', price: 50, quantity: 100 }),
        trade({ id: 's1', type: 'sell', timestamp: '2025-06-01T00:00:00Z', price: 60, quantity: 100 }),
        trade({ id: 'b2', type: 'buy', timestamp: '2025-07-01T00:00:00Z', price: 55, quantity: 80 }),
        trade({ id: 's2', type: 'sell', timestamp: '2025-09-01T00:00:00Z', price: 70, quantity: 80 }),
      ],
      '2025-08-01',
      55,
    );
    expect(port.shares).toBe(80);
    expect(port.cash).toBe(10_000 - 50 * 100 + 60 * 100 - 55 * 80);
    expect(port.equity).toBe(port.cash + 80 * 55);
  });

  it('sliceDetailFromDiaD cuenta sells OOS de posición pre-D (no 0 ops en frío)', () => {
    const bars = [
      { timestamp: '2025-07-31T00:00:00Z', close: 54 },
      { timestamp: '2025-08-01T00:00:00Z', close: 55 },
      { timestamp: '2025-09-01T00:00:00Z', close: 70 },
      { timestamp: '2025-10-01T00:00:00Z', close: 72 },
    ];
    const detail = {
      id: 'run-1',
      instrumentId: 'acs',
      symbol: 'ACS',
      strategyType: 'sma_crossover',
      timeframe: '1d',
      initialCash: 10_000,
      finalEquity: 12_000,
      totalReturnPct: 20,
      maxDrawdownPct: 5,
      tradeCount: 2,
      barCount: 4,
      firstDate: '2025-07-31T00:00:00Z',
      lastDate: '2025-10-01T00:00:00Z',
      createdAt: '2026-01-01T00:00:00Z',
      trades: [
        trade({ id: 'b1', type: 'buy', timestamp: '2025-07-01T00:00:00Z', price: 50, quantity: 100 }),
        trade({ id: 's1', type: 'sell', timestamp: '2025-09-01T00:00:00Z', price: 70, quantity: 100 }),
      ],
      equityCurve: [],
    } as BacktestRunDetailDto;

    const sliced = sliceDetailFromDiaD(detail, '2025-08-01', bars);
    expect(tradesOnOrAfterDiaD(detail.trades, '2025-08-01')).toHaveLength(1);
    expect(sliced.tradeCount).toBe(1);
    expect(sliced.trades[0]?.type).toBe('sell');
    expect(sliced.tradeCount).toBeGreaterThan(0);
  });
});
