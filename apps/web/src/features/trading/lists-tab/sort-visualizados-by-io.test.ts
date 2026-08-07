import { describe, expect, it } from 'vitest';
import {
  compareIoQuality,
  orderInstrumentIdsByIo,
} from '@/features/trading/lists-tab/sort-visualizados-by-io';

describe('orderInstrumentIdsByIo', () => {
  it('puts higher IO to the left (first)', () => {
    const io = new Map<string, number | null>([
      ['a', 40],
      ['b', 82],
      ['c', 70],
    ]);
    expect(orderInstrumentIdsByIo(['a', 'b', 'c'], io, { a: 'A', b: 'B', c: 'C' })).toEqual([
      'b',
      'c',
      'a',
    ]);
  });

  it('ranks missing IO last', () => {
    const io = new Map<string, number | null>([
      ['x', null],
      ['y', 55],
    ]);
    expect(orderInstrumentIdsByIo(['x', 'y'], io, { x: 'X', y: 'Y' })).toEqual(['y', 'x']);
  });
});

describe('compareIoQuality', () => {
  it('sorts descending by io', () => {
    const rows = [
      { instrumentId: 'a', io: 10, symbol: 'A' },
      { instrumentId: 'b', io: 90, symbol: 'B' },
    ];
    expect([...rows].sort(compareIoQuality).map((r) => r.instrumentId)).toEqual(['b', 'a']);
  });
});
