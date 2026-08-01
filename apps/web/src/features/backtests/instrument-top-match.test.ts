import { describe, expect, it } from 'vitest';
import {
  finalistHudBadgeFromTop,
  matchInstrumentTopSlot,
} from '@/features/backtests/instrument-top-match';
import type { InstrumentStrategyTopV1 } from '@bolsa/shared';

const top: InstrumentStrategyTopV1 = {
  id: 'top1',
  instrumentId: 'inst-bbva',
  timeframe: '1d',
  status: 'semifinal',
  version: 1,
  evidenceLevel: 'in_sample_only',
  createdAt: 't',
  updatedAt: 't',
  slots: [
    {
      rank: 1,
      label: 'SMA 20/50',
      strategyType: 'sma_crossover',
      strategyDefinitionId: 'def-sma',
      stars: 3,
      score: 72,
      starsCapped: true,
      runId: 'run-sma',
      source: 'coach',
    },
    {
      rank: 2,
      label: 'RSI',
      strategyType: 'rsi_mean_reversion',
      stars: 2,
      score: 55,
      runId: 'run-rsi',
      source: 'coach',
    },
  ],
};

describe('instrument-top-match', () => {
  it('matches by runId first', () => {
    const slot = matchInstrumentTopSlot(
      { id: 'run-rsi', strategyType: 'sma_crossover', strategyDefinitionId: 'def-sma' },
      top,
    );
    expect(slot?.rank).toBe(2);
  });

  it('matches by strategyDefinitionId', () => {
    const slot = matchInstrumentTopSlot(
      { id: 'other-run', strategyType: 'x', strategyDefinitionId: 'def-sma' },
      top,
    );
    expect(slot?.rank).toBe(1);
  });

  it('matches by strategyType', () => {
    const slot = matchInstrumentTopSlot(
      { id: 'x', strategyType: 'rsi_mean_reversion' },
      top,
    );
    expect(slot?.rank).toBe(2);
  });

  it('builds HUD badge with stars', () => {
    const badge = finalistHudBadgeFromTop(
      { id: 'run-sma', strategyType: 'sma_crossover', strategyDefinitionId: 'def-sma' },
      top,
    );
    expect(badge).toMatchObject({ rank: 1, stars: 3, starsCapped: true });
  });
});
