import { describe, expect, it } from 'vitest';
import type { SmaGridTrialDto } from '@bolsa/shared';
import {
  buildCompareRows,
  oosRankScore,
  rankTrialsForCompare,
} from '@/features/backtests/backtest-optimize-compare';

function trial(
  fast: number,
  slow: number,
  score: number,
  oosScore?: number,
  oosTrades = 4,
): SmaGridTrialDto {
  return {
    fastPeriod: fast,
    slowPeriod: slow,
    totalReturnPct: score + 5,
    maxDrawdownPct: 20,
    tradeCount: 10,
    score,
    oosMetrics:
      oosScore == null
        ? null
        : {
            totalReturnPct: oosScore,
            maxDrawdownPct: 15,
            tradeCount: oosTrades,
            score: oosScore,
          },
  };
}

describe('rankTrialsForCompare', () => {
  it('ranks by IS when requested', () => {
    const ranked = rankTrialsForCompare(
      [trial(10, 50, 5, 1), trial(20, 50, 8, 9)],
      'is',
    );
    expect(ranked[0]?.fastPeriod).toBe(20);
  });

  it('ranks by OOS when all trials have oosMetrics', () => {
    const ranked = rankTrialsForCompare(
      [trial(10, 50, 12, 2), trial(15, 40, 7, 11)],
      'oos',
    );
    expect(ranked[0]?.fastPeriod).toBe(15);
    expect(ranked[0]?.oosMetrics?.score).toBe(11);
  });

  it('penalizes sparse OOS trade counts when ranking', () => {
    const dense = trial(15, 40, 5, 6, 5);
    const sparse = trial(10, 50, 5, 9, 1);
    expect(oosRankScore(dense)).toBeGreaterThan(oosRankScore(sparse));
    const ranked = rankTrialsForCompare([sparse, dense], 'oos');
    expect(ranked[0]?.fastPeriod).toBe(15);
  });
});

describe('buildCompareRows rankBy oos', () => {
  it('marks OOS champion as Mejor and flags IS-only champ', () => {
    const rows = buildCompareRows({
      family: 'sma_crossover',
      rankBy: 'oos',
      anchor: {
        fastPeriod: 20,
        slowPeriod: 50,
        totalReturnPct: 1,
        maxDrawdownPct: 10,
        tradeCount: 5,
        score: 0,
        label: 'Ancla',
        oosMetrics: {
          totalReturnPct: 0,
          maxDrawdownPct: 10,
          tradeCount: 2,
          score: 0,
        },
      },
      trials: [trial(10, 40, 20, 1), trial(12, 45, 6, 8)],
      topN: 5,
    });
    const best = rows.find((row) => row.status === 'best');
    const isOnly = rows.find((row) => row.label === 'Mejor IS (no OOS)');
    expect(best?.label).toBe('Mejor OOS');
    expect(best?.fastPeriod).toBe(12);
    expect(isOnly?.fastPeriod).toBe(10);
  });
});
