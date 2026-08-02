import { describe, expect, it } from 'vitest';
import type { InstrumentStrategyTopSlotV1 } from '@bolsa/shared';
import {
  resolveExecutableStrategyType,
  sanitizeTopSlotStrategyType,
  sanitizeTopSlotsStrategyTypes,
} from '@/features/backtests/instrument-top-strategy-type';

describe('instrument-top-strategy-type', () => {
  it('prefers definition preset over proxy seed type', () => {
    expect(
      resolveExecutableStrategyType({
        slotStrategyType: 'supertrend_follow',
        definitionPresetKey: 'sma_crossover',
      }),
    ).toBe('sma_crossover');
  });

  it('keeps valid slot type when no definition', () => {
    expect(
      resolveExecutableStrategyType({
        slotStrategyType: 'rsi_mean_reversion',
      }),
    ).toBe('rsi_mean_reversion');
  });

  it('sanitizes TOP slots by definition map', () => {
    const slot = {
      rank: 1,
      label: 'SMA 20/45',
      strategyType: 'supertrend_follow',
      strategyDefinitionId: 'def-1',
      stars: 5,
      score: 1,
      source: 'optimized',
    } as InstrumentStrategyTopSlotV1;
    const out = sanitizeTopSlotsStrategyTypes(
      [slot],
      new Map([['def-1', 'sma_crossover']]),
    );
    expect(out[0]?.strategyType).toBe('sma_crossover');
    expect(sanitizeTopSlotStrategyType(slot, 'sma_crossover').strategyType).toBe(
      'sma_crossover',
    );
  });
});
