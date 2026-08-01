/**
 * Tests — Lista AUTO campaña (avance, pausa, stop, labels).
 */

import { describe, expect, it } from 'vitest';
import {
  LIST_AUTO_MAX_INSTRUMENTS,
  advanceListAutoAfterSettle,
  confirmListAutoOverCap,
  createListAutoCampaign,
  filterListAutoIdsWithoutFinalists,
  isListAutoComplete,
  listAutoDoneStatus,
  listAutoOverCapWarning,
  listAutoPausedStatus,
  listAutoPlayTitle,
  listAutoProgressLabel,
  listAutoUniverseHint,
  listModeWizardTitle,
  nextListAutoIndex,
  pauseListAutoCampaign,
  resumeListAutoCampaign,
  shouldStartListAuto,
  sliceListAutoInstrumentIds,
  stopListAutoCampaign,
} from '@/features/backtests/backtest-list-auto';

describe('sliceListAutoInstrumentIds', () => {
  it('caps at soft max', () => {
    const ids = Array.from({ length: 50 }, (_, i) => `id-${i}`);
    expect(sliceListAutoInstrumentIds(ids)).toHaveLength(LIST_AUTO_MAX_INSTRUMENTS);
    expect(sliceListAutoInstrumentIds(ids, 5)).toHaveLength(5);
  });
});

describe('confirmListAutoOverCap', () => {
  it('skips dialog when under cap', () => {
    let called = false;
    expect(
      confirmListAutoOverCap(10, 40, () => {
        called = true;
        return false;
      }),
    ).toBe(true);
    expect(called).toBe(false);
  });

  it('asks and respects cancel when over cap', () => {
    expect(confirmListAutoOverCap(500, 40, () => false)).toBe(false);
    expect(confirmListAutoOverCap(500, 40, () => true)).toBe(true);
  });
});

describe('listAutoOverCapWarning', () => {
  it('returns null under cap and message over cap', () => {
    expect(listAutoOverCapWarning(35)).toBeNull();
    expect(listAutoOverCapWarning(500)).toMatch(/500/);
  });
});

describe('filterListAutoIdsWithoutFinalists', () => {
  it('keeps ids without slots and drops those with TOP', async () => {
    const ids = await filterListAutoIdsWithoutFinalists(['a', 'b', 'c'], async (id) => {
      if (id === 'b') return { data: { slots: [{ rank: 1 }] } };
      return { data: { slots: [] } };
    });
    expect(ids).toEqual(['a', 'c']);
  });
});

describe('createListAutoCampaign / advance', () => {
  it('creates capped queue and advances until complete', () => {
    const c = createListAutoCampaign({
      listId: 'L1',
      instrumentIds: ['a', 'b', 'c'],
    });
    expect(c.instrumentIds).toEqual(['a', 'b', 'c']);
    expect(c.paused).toBe(false);
    expect(isListAutoComplete(c)).toBe(false);
    expect(advanceListAutoAfterSettle(c)).toBe('next');
    expect(c.index).toBe(1);
    expect(advanceListAutoAfterSettle(c)).toBe('next');
    expect(c.index).toBe(2);
    expect(advanceListAutoAfterSettle(c)).toBe('done');
    expect(isListAutoComplete(c)).toBe(true);
  });

  it('pause defers next start; resume clears flag', () => {
    const c = createListAutoCampaign({ listId: 'L1', instrumentIds: ['a', 'b', 'c'] });
    pauseListAutoCampaign(c);
    expect(advanceListAutoAfterSettle(c)).toBe('paused');
    expect(c.index).toBe(1);
    expect(c.paused).toBe(true);
    resumeListAutoCampaign(c);
    expect(c.paused).toBe(false);
    expect(advanceListAutoAfterSettle(c)).toBe('next');
    expect(c.index).toBe(2);
  });

  it('stops when aborted', () => {
    const c = createListAutoCampaign({ listId: 'L1', instrumentIds: ['a', 'b'] });
    stopListAutoCampaign(c);
    expect(advanceListAutoAfterSettle(c)).toBe('aborted');
    expect(nextListAutoIndex(c)).toBeNull();
  });
});

describe('shouldStartListAuto', () => {
  it('requires list mode + full cycle + list with instruments', () => {
    expect(
      shouldStartListAuto({
        universeMode: 'list',
        fullCycleOnPlay: true,
        listId: 'L1',
        instrumentCount: 3,
      }),
    ).toBe(true);
    expect(
      shouldStartListAuto({
        universeMode: 'single',
        fullCycleOnPlay: true,
        listId: 'L1',
        instrumentCount: 3,
      }),
    ).toBe(false);
    expect(
      shouldStartListAuto({
        universeMode: 'list',
        fullCycleOnPlay: false,
        listId: 'L1',
        instrumentCount: 3,
      }),
    ).toBe(false);
  });
});

describe('labels', () => {
  it('formats progress and play title', () => {
    expect(listAutoProgressLabel({ index: 0, total: 35, symbol: 'SAN' })).toBe(
      'Lista AUTO 1/35 · SAN',
    );
    expect(listAutoDoneStatus(2)).toMatch(/Lista AUTO ✓ 2/);
    expect(listAutoPausedStatus({ index: 2, total: 35, symbol: 'GRF' })).toMatch(/pausa/i);
    expect(listAutoPlayTitle({ fullCycleOnPlay: true, listMode: true })).toMatch(/lista AUTO/i);
    expect(listAutoPlayTitle({ fullCycleOnPlay: true, listMode: false })).toMatch(
      /ciclo completo/i,
    );
  });

  it('list auto copy does not ask to pick a strategy', () => {
    expect(listAutoUniverseHint()).toMatch(/No hace falta seleccionar/i);
    expect(listAutoUniverseHint()).toMatch(/Pausa|frescura/i);
    expect(listModeWizardTitle(true)).toMatch(/sin elegir estrategia/i);
    expect(listModeWizardTitle(false)).toMatch(/ciclo completo/i);
  });
});
