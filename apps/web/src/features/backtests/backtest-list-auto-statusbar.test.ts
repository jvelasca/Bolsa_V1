import { describe, expect, it } from 'vitest';
import {
  formatListAutoStatusBarSummary,
  shortenListAutoPhase,
} from '@/features/backtests/backtest-list-auto';

describe('formatListAutoStatusBarSummary', () => {
  it('builds compact progress with phase', () => {
    expect(
      formatListAutoStatusBarSummary({
        index: 2,
        total: 19,
        symbol: 'SAN',
        detail: 'Lista AUTO 3/19 · SAN: Lab en curso…',
      }),
    ).toMatch(/^Lista AUTO 3\/19 · SAN · Lab/);
  });

  it('marks pause', () => {
    expect(
      formatListAutoStatusBarSummary({
        index: 0,
        total: 19,
        symbol: 'BKT',
        paused: true,
      }),
    ).toBe('Lista AUTO 1/19 · BKT · pausa');
  });
});

describe('shortenListAutoPhase', () => {
  it('strips Lista AUTO prefix', () => {
    expect(shortenListAutoPhase('Lista AUTO: comprobando frescura…')).toMatch(/frescura/i);
  });
});
