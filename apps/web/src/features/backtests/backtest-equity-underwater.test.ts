import { describe, expect, it } from 'vitest';
import { toUnderwaterDrawdownData } from '@/features/backtests/backtest-equity-chart';

describe('toUnderwaterDrawdownData', () => {
  it('tracks drawdown from peak as non-positive pct', () => {
    const data = toUnderwaterDrawdownData(
      [
        { time: 1 as never, value: 100 },
        { time: 2 as never, value: 110 },
        { time: 3 as never, value: 99 },
      ],
      100,
    );
    expect(data[0]!.value).toBe(0);
    expect(data[1]!.value).toBe(0);
    expect(data[2]!.value).toBeCloseTo(((99 - 110) / 110) * 100, 5);
  });
});
