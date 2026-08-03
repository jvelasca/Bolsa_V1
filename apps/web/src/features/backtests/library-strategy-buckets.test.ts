import { describe, expect, it } from 'vitest';
import {
  countLibraryBuckets,
  filterStrategiesByLibraryBucket,
  librarySavedBucket,
  normalizeStrategiesListFilter,
} from '@/features/backtests/library-strategy-buckets';

describe('library-strategy-buckets', () => {
  const rows = [
    { origin: 'preset', presetKey: 'sma_crossover' },
    { origin: 'manual', presetKey: null },
    { origin: 'ai_generated', presetKey: 'rsi_mean_reversion' },
    { origin: 'assisted', presetKey: null },
    { origin: 'imported', presetKey: 'macd_signal_cross' },
  ];

  it('maps preset → optimized; legacy Lab manual+presetKey → optimized', () => {
    expect(librarySavedBucket(rows[0]!)).toBe('optimized');
    expect(librarySavedBucket({ origin: 'manual', presetKey: 'sma_crossover' })).toBe(
      'optimized',
    );
    expect(librarySavedBucket(rows[1]!)).toBe('mine');
    expect(librarySavedBucket(rows[2]!)).toBe('mine');
    expect(librarySavedBucket(rows[3]!)).toBe('mine');
    expect(librarySavedBucket(rows[4]!)).toBe('mine');
  });

  it('filters and counts', () => {
    const withLegacy = [
      ...rows,
      { origin: 'manual', presetKey: 'ema_crossover' },
    ];
    expect(filterStrategiesByLibraryBucket(withLegacy, 'optimized')).toHaveLength(2);
    expect(filterStrategiesByLibraryBucket(rows, 'mine')).toHaveLength(4);
    expect(filterStrategiesByLibraryBucket(rows, 'all')).toHaveLength(5);
    expect(countLibraryBuckets(withLegacy)).toEqual({ optimized: 2, mine: 4 });
  });

  it('normalizes unknown filter', () => {
    expect(normalizeStrategiesListFilter('optimized')).toBe('optimized');
    expect(normalizeStrategiesListFilter('nope')).toBe('all');
  });
});
