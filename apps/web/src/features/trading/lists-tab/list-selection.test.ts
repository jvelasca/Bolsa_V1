/**
 * list-selection — tests marca / despulsa / rango.
 */

import { describe, expect, it } from 'vitest';
import { applyInstrumentSelection } from '@/features/trading/lists-tab/list-selection';

describe('applyInstrumentSelection', () => {
  const ids = ['a', 'b', 'c', 'd'];

  it('checks one without clearing others', () => {
    const r = applyInstrumentSelection({
      prev: new Set(['a']),
      instrumentId: 'c',
      index: 2,
      orderedIds: ids,
      modifiers: {},
      anchorIndex: 0,
      checked: true,
    });
    expect([...r.next].sort()).toEqual(['a', 'c']);
    expect(r.anchorIndex).toBe(2);
  });

  it('unchecks one clearly (despulsar)', () => {
    const r = applyInstrumentSelection({
      prev: new Set(['a', 'c']),
      instrumentId: 'c',
      index: 2,
      orderedIds: ids,
      modifiers: {},
      anchorIndex: 2,
      checked: false,
    });
    expect([...r.next].sort()).toEqual(['a']);
  });

  it('Ctrl+check adds another (superior then inferior)', () => {
    const first = applyInstrumentSelection({
      prev: new Set(),
      instrumentId: 'a',
      index: 0,
      orderedIds: ids,
      modifiers: { ctrlKey: true },
      anchorIndex: null,
      checked: true,
    });
    const second = applyInstrumentSelection({
      prev: first.next,
      instrumentId: 'd',
      index: 3,
      orderedIds: ids,
      modifiers: { ctrlKey: true },
      anchorIndex: first.anchorIndex,
      checked: true,
    });
    expect([...second.next].sort()).toEqual(['a', 'd']);
  });

  it('Shift selects inclusive visual range from anchor', () => {
    const r = applyInstrumentSelection({
      prev: new Set(['a']),
      instrumentId: 'd',
      index: 3,
      orderedIds: ids,
      modifiers: { shiftKey: true },
      anchorIndex: 1,
      checked: true,
    });
    expect([...r.next].sort()).toEqual(['b', 'c', 'd']);
    expect(r.anchorIndex).toBe(1);
  });

  it('Ctrl+Shift adds range to existing selection', () => {
    const r = applyInstrumentSelection({
      prev: new Set(['a']),
      instrumentId: 'c',
      index: 2,
      orderedIds: ids,
      modifiers: { ctrlKey: true, shiftKey: true },
      anchorIndex: 1,
      checked: true,
    });
    expect([...r.next].sort()).toEqual(['a', 'b', 'c']);
  });
});
