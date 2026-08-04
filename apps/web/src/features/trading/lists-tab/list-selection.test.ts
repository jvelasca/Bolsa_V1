/**
 * list-selection — tests Ctrl/Shift.
 */

import { describe, expect, it } from 'vitest';
import { applyInstrumentSelection } from '@/features/trading/lists-tab/list-selection';

describe('applyInstrumentSelection', () => {
  const ids = ['a', 'b', 'c', 'd'];

  it('toggles one without modifiers', () => {
    const r = applyInstrumentSelection({
      prev: new Set(['a']),
      instrumentId: 'c',
      index: 2,
      orderedIds: ids,
      modifiers: {},
      anchorIndex: 0,
    });
    expect([...r.next].sort()).toEqual(['a', 'c']);
    expect(r.anchorIndex).toBe(2);
  });

  it('Ctrl toggles without clearing others', () => {
    const r = applyInstrumentSelection({
      prev: new Set(['a', 'c']),
      instrumentId: 'b',
      index: 1,
      orderedIds: ids,
      modifiers: { ctrlKey: true },
      anchorIndex: 0,
    });
    expect([...r.next].sort()).toEqual(['a', 'b', 'c']);
  });

  it('Shift selects inclusive range from anchor', () => {
    const r = applyInstrumentSelection({
      prev: new Set(['a']),
      instrumentId: 'd',
      index: 3,
      orderedIds: ids,
      modifiers: { shiftKey: true },
      anchorIndex: 1,
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
    });
    expect([...r.next].sort()).toEqual(['a', 'b', 'c']);
  });
});
