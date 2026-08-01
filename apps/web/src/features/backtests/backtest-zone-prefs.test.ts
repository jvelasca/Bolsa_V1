import { describe, expect, it } from 'vitest';

import {
  BACKTEST_HISTORY_MAX_DEFAULT,
  MATRIX_LIST_HEIGHT_DEFAULT,
  MATRIX_SELECT_BATCH_DEFAULT,
  clampHistoryMaxKept,
  clampListHeightPx,
  clampSelectBatchSize,
} from '@/features/backtests/backtest-zone-prefs';

describe('clampHistoryMaxKept', () => {
  it('defaults invalid values to 20', () => {
    expect(clampHistoryMaxKept(Number.NaN)).toBe(BACKTEST_HISTORY_MAX_DEFAULT);
  });

  it('clamps to [5, 100]', () => {
    expect(clampHistoryMaxKept(1)).toBe(5);
    expect(clampHistoryMaxKept(20)).toBe(20);
    expect(clampHistoryMaxKept(999)).toBe(100);
  });
});

describe('clampSelectBatchSize', () => {
  it('defaults and clamps to [1, 20]', () => {
    expect(clampSelectBatchSize(Number.NaN)).toBe(MATRIX_SELECT_BATCH_DEFAULT);
    expect(clampSelectBatchSize(0)).toBe(1);
    expect(clampSelectBatchSize(8)).toBe(8);
    expect(clampSelectBatchSize(99)).toBe(20);
  });
});

describe('clampListHeightPx', () => {
  it('defaults and clamps to [160, 560]', () => {
    expect(clampListHeightPx(Number.NaN)).toBe(MATRIX_LIST_HEIGHT_DEFAULT);
    expect(clampListHeightPx(50)).toBe(160);
    expect(clampListHeightPx(280)).toBe(280);
    expect(clampListHeightPx(900)).toBe(560);
  });
});
