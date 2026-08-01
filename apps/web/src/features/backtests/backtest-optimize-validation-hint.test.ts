import { describe, expect, it } from 'vitest';
import {
  coachValidationNextStep,
  suggestOptimizeValidation,
} from '@/features/backtests/backtest-optimize-validation-hint';
import {
  buildOptimizeSeedFromExploreRow,
  buildOptimizeSeedFromRun,
} from '@/features/backtests/backtest-optimize-seed';
import { buildExploreCoachNote } from '@/features/backtests/backtest-explore-value';
import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';

function okRow(partial: Partial<ExplorePresetRow> = {}): ExplorePresetRow {
  return {
    strategyType: 'sma_crossover',
    label: 'Cruce SMA',
    category: 'trend',
    categoryLabel: 'Tendencia',
    status: 'ok',
    barCount: 500,
    totalReturnPct: 12,
    maxDrawdownPct: 8,
    tradeCount: 10,
    excessReturnPct: 3,
    buyHoldReturnPct: 9,
    ...partial,
  };
}

describe('suggestOptimizeValidation (P6)', () => {
  it('keeps validation off for short history', () => {
    const hint = suggestOptimizeValidation(200);
    expect(hint.mode).toBe('none');
    expect(coachValidationNextStep(hint)).toMatch(/cautela/i);
  });

  it('prefers hold-out for medium history', () => {
    const hint = suggestOptimizeValidation(500);
    expect(hint.mode).toBe('holdout');
    expect(hint.oosPct).toBe(0.2);
  });

  it('prefers walk-forward for long history', () => {
    const hint = suggestOptimizeValidation(1200);
    expect(hint.mode).toBe('walkforward');
    expect(hint.walkForwardFolds).toBe(3);
  });
});

describe('OptimizeSeed carries validationHint', () => {
  it('from explore row', () => {
    const seed = buildOptimizeSeedFromExploreRow(okRow({ barCount: 900 }), {
      instrumentId: 'i1',
      initialCash: 10_000,
      timeframe: '1d',
      source: 'explore_best',
    });
    expect(seed.validationHint?.mode).toBe('walkforward');
  });

  it('from result run', () => {
    const seed = buildOptimizeSeedFromRun({
      instrumentId: 'i1',
      strategyType: 'sma_crossover',
      initialCash: 10_000,
      timeframe: '1d',
      barCount: 400,
      totalReturnPct: 5,
      maxDrawdownPct: 4,
    });
    expect(seed.validationHint?.mode).toBe('holdout');
    expect(seed.validationHint?.oosPct).toBe(0.2);
  });
});

describe('explore coach → Optimizar hint', () => {
  it('mentions hold-out next step when medium bars beat B&H', () => {
    const note = buildExploreCoachNote(
      [okRow({ barCount: 450, excessReturnPct: 2 })],
      'ACS',
    );
    expect(note.validationHint?.mode).toBe('holdout');
    expect(note.nextSteps.some((s) => /hold-out/i.test(s))).toBe(true);
    expect(note.bullets.some((b) => /in-sample/i.test(b))).toBe(true);
  });

  it('mentions walk-forward when long bars', () => {
    const note = buildExploreCoachNote(
      [okRow({ barCount: 2000, excessReturnPct: 4 })],
      'SAN',
      { barLimit: 2000 },
    );
    expect(note.validationHint?.mode).toBe('walkforward');
    expect(note.nextSteps.some((s) => /walk-forward/i.test(s))).toBe(true);
  });
});
