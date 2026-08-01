/**
 * Tests — heatmap / top-5 / plateau (Lab P1).
 */

import { describe, expect, it } from 'vitest';
import type { SmaGridTrialDto } from '@bolsa/shared';
import {
  buildOptimizeHeatmap,
  heatmapNorm,
} from '@/features/backtests/backtest-optimize-heatmap';

function sma(fast: number, slow: number, score: number, oos?: number): SmaGridTrialDto {
  return {
    fastPeriod: fast,
    slowPeriod: slow,
    totalReturnPct: score + 5,
    maxDrawdownPct: 12,
    tradeCount: 20,
    score,
    oosMetrics:
      oos == null
        ? null
        : {
            totalReturnPct: oos,
            maxDrawdownPct: 10,
            tradeCount: 6,
            score: oos,
          },
  };
}

describe('buildOptimizeHeatmap', () => {
  it('builds grid, top-5 and marks best', () => {
    const trials = [
      sma(10, 40, 1),
      sma(10, 50, 3),
      sma(20, 40, 2),
      sma(20, 50, 8),
      sma(30, 50, 4),
      sma(30, 60, 5),
    ];
    const model = buildOptimizeHeatmap({ trials, family: 'sma_crossover' });
    expect(model).not.toBeNull();
    expect(model!.best).toEqual({ x: 20, y: 50, score: 8 });
    expect(model!.top5[0]?.score).toBe(8);
    expect(model!.top5).toHaveLength(5);
    expect(model!.cells.some((c) => c.isBest && c.score === 8)).toBe(true);
    expect(model!.xTicks).toEqual([10, 20, 30]);
    expect(model!.yTicks).toEqual([40, 50, 60]);
  });

  it('detects plateau when neighbors are close in score', () => {
    // Best 20/50=5; neighbors 10/50 and 20/40 and 30/50 within tol
    const trials = [
      sma(10, 50, 4.9),
      sma(20, 40, 4.85),
      sma(20, 50, 5),
      sma(20, 60, 4.8),
      sma(30, 50, 4.9),
    ];
    const model = buildOptimizeHeatmap({
      trials,
      family: 'sma_crossover',
      plateauAbsTol: 0.3,
      plateauMinClose: 2,
    });
    expect(model!.plateau.isPlateau).toBe(true);
    expect(model!.plateau.closeNeighborCount).toBeGreaterThanOrEqual(2);
  });

  it('does not flag plateau when Mejor is isolated', () => {
    const trials = [
      sma(10, 40, 1),
      sma(10, 50, 1.2),
      sma(20, 40, 1.1),
      sma(20, 50, 9),
      sma(20, 60, 1.3),
      sma(30, 50, 1.4),
    ];
    const model = buildOptimizeHeatmap({ trials, family: 'sma_crossover' });
    expect(model!.plateau.isPlateau).toBe(false);
  });

  it('uses OOS scores when requested', () => {
    const trials = [sma(10, 50, 9, 2), sma(20, 50, 3, 7)];
    const model = buildOptimizeHeatmap({
      trials,
      family: 'sma_crossover',
      scoreMode: 'oos',
    });
    expect(model!.best?.score).toBe(7);
    expect(model!.best?.x).toBe(20);
  });

  it('keeps best of duplicate (x,y) cells', () => {
    const trials = [
      { ...sma(12, 26, 3), signalPeriod: 9 },
      { ...sma(12, 26, 6), signalPeriod: 12 },
    ];
    const model = buildOptimizeHeatmap({ trials, family: 'macd_signal_cross' });
    expect(model!.best?.score).toBe(6);
    expect(model!.cells.filter((c) => c.score != null)).toHaveLength(1);
  });
});

describe('heatmapNorm', () => {
  it('normalizes to 0–1', () => {
    expect(heatmapNorm(null, 0, 10)).toBeNull();
    expect(heatmapNorm(0, 0, 10)).toBe(0);
    expect(heatmapNorm(10, 0, 10)).toBe(1);
    expect(heatmapNorm(5, 0, 10)).toBe(0.5);
  });
});
