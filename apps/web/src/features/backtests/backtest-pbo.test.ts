import { describe, expect, it } from 'vitest';
import { classifyPbo, formatPbo, pboBandLabel } from '@/features/backtests/backtest-pbo';

describe('PBO helpers (P3.N)', () => {
  it('classifies bands', () => {
    expect(classifyPbo(0.2)).toBe('low');
    expect(classifyPbo(0.55)).toBe('elevated');
    expect(classifyPbo(0.75)).toBe('high');
    expect(pboBandLabel('elevated')).toMatch(/elevado/i);
  });

  it('formats values', () => {
    expect(formatPbo(0.42)).toBe('0.42');
    expect(formatPbo(null)).toBe('n/d');
  });
});
