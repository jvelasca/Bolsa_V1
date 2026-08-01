import { describe, expect, it } from 'vitest';
import type { OhlcvBarDto } from '@bolsa/shared';
import {
  barsToKagiSeries,
  barsToLineBreakSeries,
  barsToPointAndFigureSeries,
  barsToRenkoSeries,
  defaultPriceBoxSize,
  resolveRenkoBrickSize,
} from './chart-advanced-series';
import sampleBars from '@fixtures/ohlcv-ibe-sample.json';

const UP = '#22c55e';
const DOWN = '#ef4444';

function bar(timestamp: string, close: number, open = close): OhlcvBarDto {
  return {
    timestamp,
    open,
    high: Math.max(open, close) + 0.1,
    low: Math.min(open, close) - 0.1,
    close,
    volume: 1000,
    adjClose: null,
    source: 'yahoo',
  };
}

describe('chart-advanced-series', () => {
  it('calcula tamaño de ladrillo automático a partir del precio medio', () => {
    const bars = [bar('2024-01-02', 100), bar('2024-01-03', 102)];
    expect(defaultPriceBoxSize(bars)).toBeCloseTo(0.505, 2);
    expect(resolveRenkoBrickSize(bars, {})).toBeCloseTo(0.505, 2);
    expect(resolveRenkoBrickSize(bars, { renkoBrickSize: 2 })).toBe(2);
  });

  it('genera ladrillos Renko cuando el precio supera el tamaño configurado', () => {
    const bars = [
      bar('2024-01-02', 100),
      bar('2024-01-03', 102),
      bar('2024-01-04', 104),
      bar('2024-01-05', 106),
    ];
    const series = barsToRenkoSeries(bars, 2, UP, DOWN);
    expect(series.length).toBeGreaterThanOrEqual(2);
    expect(series[0]!.close).toBeGreaterThan(series[0]!.open);
  });

  it('genera bloques de ruptura de línea al romper mínimos y máximos recientes', () => {
    const bars = [
      bar('2024-01-02', 100, 99),
      bar('2024-01-03', 98, 100),
      bar('2024-01-04', 96, 98),
      bar('2024-01-05', 103, 96),
    ];
    const series = barsToLineBreakSeries(bars, 2, UP, DOWN);
    expect(series.length).toBeGreaterThanOrEqual(2);
  });

  it('genera tramos Kagi tras una reversión suficiente', () => {
    const bars = [
      bar('2024-01-02', 100),
      bar('2024-01-03', 105),
      bar('2024-01-04', 99),
      bar('2024-01-05', 94),
    ];
    const series = barsToKagiSeries(bars, 4, UP, DOWN);
    expect(series.length).toBeGreaterThanOrEqual(1);
  });

  it('asigna tiempos estrictamente ascendentes (velas diarias)', () => {
    const daily = sampleBars as OhlcvBarDto[];
    const assertAscending = (times: number[]) => {
      for (let i = 1; i < times.length; i++) {
        expect(times[i]).toBeGreaterThan(times[i - 1]!);
      }
    };

    const kagiTimes = barsToKagiSeries(daily, 4, UP, DOWN).map((c) => c.time as number);
    assertAscending(kagiTimes);
    if (kagiTimes.length >= 2) {
      expect(kagiTimes[kagiTimes.length - 1]!).toBeGreaterThan(kagiTimes[0]!);
    }

    assertAscending(
      barsToRenkoSeries(daily, resolveRenkoBrickSize(daily), UP, DOWN).map((c) => c.time as number),
    );
    assertAscending(
      barsToLineBreakSeries(daily, 3, UP, DOWN).map((c) => c.time as number),
    );
    assertAscending(
      barsToPointAndFigureSeries(daily, defaultPriceBoxSize(daily), 3, UP, DOWN).map(
        (c) => c.time as number,
      ),
    );
  });
});
