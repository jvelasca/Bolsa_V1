import { describe, expect, it } from 'vitest';
import {
  buyHoldReturnFromSeries,
  filterBarsToBacktestWindow,
  trailingYearReturns,
  trailingYearStartIndex,
} from '@/features/backtests/backtest-buy-hold';
import type { BacktestEquityPointDto, OhlcvBarDto } from '@bolsa/shared';

function bar(day: string, close: number): OhlcvBarDto {
  return {
    timestamp: `${day}T00:00:00.000Z`,
    open: close,
    high: close,
    low: close,
    close,
    volume: 1,
  };
}

function eq(day: string, equity: number): BacktestEquityPointDto {
  return { timestamp: `${day}T00:00:00.000Z`, equity };
}

/** Daily points from startDay for `days` calendar days (UTC). */
function dailySeries(
  startDay: string,
  days: number,
  valueAt: (i: number) => number,
): { bars: OhlcvBarDto[]; equity: BacktestEquityPointDto[] } {
  const start = Date.parse(`${startDay}T00:00:00.000Z`);
  const bars: OhlcvBarDto[] = [];
  const equity: BacktestEquityPointDto[] = [];
  for (let i = 0; i < days; i += 1) {
    const day = new Date(start + i * 86_400_000).toISOString().slice(0, 10);
    const v = valueAt(i);
    bars.push(bar(day, v));
    equity.push(eq(day, v * 10));
  }
  return { bars, equity };
}

describe('buyHoldReturnFromSeries', () => {
  it('calcula % primera→última vela', () => {
    expect(buyHoldReturnFromSeries([bar('2020-01-01', 100), bar('2024-01-01', 150)])).toBe(50);
  });
});

describe('filterBarsToBacktestWindow', () => {
  const bars = [
    bar('2020-01-01', 10),
    bar('2022-06-01', 20),
    bar('2024-01-01', 30),
  ];

  it('sin fechas → serie completa', () => {
    expect(filterBarsToBacktestWindow(bars, { limit: 10_000 })).toHaveLength(3);
  });

  it('recorta por dateFrom/dateTo', () => {
    const sliced = filterBarsToBacktestWindow(bars, {
      dateFrom: '2021-01-01',
      dateTo: '2023-12-31',
      limit: 10_000,
    });
    expect(sliced).toHaveLength(1);
    expect(sliced[0]?.close).toBe(20);
  });
});

describe('trailingYearStartIndex', () => {
  it('null si la serie es más corta que ~1 año', () => {
    const ts = Array.from({ length: 100 }, (_, i) => {
      const d = new Date(Date.UTC(2024, 0, 1 + i));
      return d.toISOString();
    });
    expect(trailingYearStartIndex(ts)).toBeNull();
  });

  it('apunta cerca de hace 365 días', () => {
    const ts = Array.from({ length: 500 }, (_, i) => {
      const d = new Date(Date.UTC(2023, 0, 1 + i));
      return d.toISOString();
    });
    const start = trailingYearStartIndex(ts);
    expect(start).not.toBeNull();
    const endMs = Date.parse(ts[ts.length - 1]!);
    const startMs = Date.parse(ts[start!]!);
    expect(endMs - startMs).toBeGreaterThanOrEqual(365 * 86_400_000 * 0.85);
  });
});

describe('trailingYearReturns', () => {
  it('null sin suficiente historial', () => {
    const { bars, equity } = dailySeries('2024-01-01', 60, () => 100);
    expect(trailingYearReturns(equity, bars)).toBeNull();
  });

  it('estrategia, B&H y Δ en los últimos ~12m', () => {
    // Precio/equity planos 2 años, luego +20% en el último tramo de equity
    // y +10% en precio → Δ ≈ +10pp sobre la ventana trailing.
    const { bars, equity } = dailySeries('2023-01-01', 800, (i) => {
      if (i < 435) return 100;
      return 100 + ((i - 435) / (799 - 435)) * 10; // close → 110
    });
    for (let i = 435; i < equity.length; i += 1) {
      const t = (i - 435) / (equity.length - 1 - 435);
      equity[i] = { ...equity[i]!, equity: 1000 + t * 200 }; // → 1200 = +20%
    }
    const r = trailingYearReturns(equity, bars);
    expect(r).not.toBeNull();
    expect(r!.strategyPct).toBeCloseTo(20, 0);
    expect(r!.buyHoldPct).toBeCloseTo(10, 0);
    expect(r!.excessPct).toBeCloseTo(10, 0);
  });
});
