import { describe, expect, it } from 'vitest';
import {
  clampRange,
  countValidCombinations,
  cpcvPathCount,
  expandRange,
  scaleSearchSpace,
  spaceFromAnchor,
  spaceFromPeriodLists,
} from '@/features/backtests/backtest-optimize-space';

describe('optimize search space', () => {
  it('expands min/max/step into discrete periods', () => {
    expect(expandRange({ min: 10, max: 20, step: 5 })).toEqual([10, 15, 20]);
  });

  it('clamps invalid ranges', () => {
    const range = clampRange({ min: 0, max: 3, step: 0 });
    expect(range.min).toBeGreaterThanOrEqual(2);
    expect(range.step).toBeGreaterThanOrEqual(1);
    expect(range.max).toBeGreaterThanOrEqual(range.min);
  });

  it('counts only valid SMA pairs (fast < slow)', () => {
    const space = spaceFromPeriodLists('10,20,30', '20,40');
    // pairs: 10/20, 10/40, 20/40 (30/20 invalid, 30/40 ok) → 10/20,10/40,20/40,30/40 = 4
    expect(countValidCombinations(space, 200)).toBe(4);
  });

  it('builds neighbourhood space around anchor', () => {
    const space = spaceFromAnchor(20, 50);
    expect(space.family).toBe('sma_crossover');
    expect(space.fast.min).toBeLessThanOrEqual(20);
    expect(space.slow.max).toBeGreaterThanOrEqual(50);
  });

  it('counts CPCV combinatorial paths C(n,2)', () => {
    expect(cpcvPathCount(5)).toBe(10);
    expect(cpcvPathCount(4)).toBe(6);
    expect(cpcvPathCount(6)).toBe(15);
  });

  it('soft-bias scales SMA search space around midpoints', () => {
    const base: ReturnType<typeof spaceFromAnchor> = {
      family: 'sma_crossover',
      fast: { min: 10, max: 50, step: 5 },
      slow: { min: 40, max: 120, step: 10 },
    };
    const narrow = scaleSearchSpace(base, 0.75);
    const wide = scaleSearchSpace(base, 1.35);
    if (narrow.family !== 'sma_crossover' || wide.family !== 'sma_crossover') {
      throw new Error('expected sma_crossover');
    }
    expect(narrow.fast.max - narrow.fast.min).toBeLessThan(
      base.fast.max - base.fast.min,
    );
    expect(wide.fast.max - wide.fast.min).toBeGreaterThan(
      base.fast.max - base.fast.min,
    );
    expect(scaleSearchSpace(base, 1)).toBe(base);
  });
});
