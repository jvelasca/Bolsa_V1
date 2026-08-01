import { describe, expect, it } from 'vitest';
import {
  formatCoreREnqueueToast,
  formatCoreROpenSymbolsKey,
  formatCoreRStatusChip,
  formatCoreRStatusTitle,
} from '@/features/backtests/core-r-status';

describe('core-r-status chip', () => {
  it('hides when empty', () => {
    expect(formatCoreRStatusChip(0)).toBeNull();
    expect(formatCoreRStatusChip(-1)).toBeNull();
  });

  it('formats singular and plural', () => {
    expect(formatCoreRStatusChip(1)).toBe('CORE-R 1');
    expect(formatCoreRStatusChip(3)).toBe('CORE-R 3');
  });

  it('title lists symbols and points to Monitor', () => {
    const t = formatCoreRStatusTitle(3, ['ACS', 'ITX', 'SAN', 'BBVA', 'REP']);
    expect(t).toMatch(/CORE-R 3/);
    expect(t).toMatch(/ACS/);
    expect(t).toMatch(/\+1/);
    expect(t).toMatch(/Monitor/i);
  });
});

describe('core-r open symbols key (zustand-safe)', () => {
  it('is stable for same open set (no new array identity needed)', () => {
    const items = [
      { status: 'open', symbol: 'ACS' },
      { status: 'done', symbol: 'ITX' },
      { status: 'open', symbol: 'SAN' },
    ];
    expect(formatCoreROpenSymbolsKey(items)).toBe(
      formatCoreROpenSymbolsKey([...items]),
    );
    expect(formatCoreROpenSymbolsKey(items)).toBe('ACS\u0001SAN');
  });

  it('empty when no open rows', () => {
    expect(formatCoreROpenSymbolsKey([{ status: 'done', symbol: 'ACS' }])).toBe(
      '',
    );
  });
});

describe('core-r enqueue toast', () => {
  it('silent when nothing added', () => {
    expect(formatCoreREnqueueToast(0)).toBeNull();
  });

  it('mentions Monitor / chip for new rows', () => {
    expect(formatCoreREnqueueToast(1)).toMatch(/1 valor encolado/);
    expect(formatCoreREnqueueToast(4)).toMatch(/4 valores encolados/);
    expect(formatCoreREnqueueToast(2)).toMatch(/Monitor|chip/i);
  });
});
