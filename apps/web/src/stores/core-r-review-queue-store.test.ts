/**
 * Tests — cola CORE-R Monitor (v1).
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  CORE_R_ENGINE,
  CORE_R_REPORT_KEY,
  type CoreRReport,
  saveCoreRReport,
} from '@/features/backtests/core-r-judgment';
import {
  CORE_R_REVIEW_QUEUE_KEY,
  primaryCoreRAction,
  useCoreRReviewQueueStore,
} from '@/stores/core-r-review-queue-store';

function sampleReport(overrides?: Partial<CoreRReport>): CoreRReport {
  return {
    engine: CORE_R_ENGINE,
    listId: 'list-ibex',
    timeframe: '1d',
    at: '2026-07-30T10:00:00.000Z',
    rows: [
      {
        instrumentId: 'inst-keep',
        symbol: 'AAA',
        verdict: 'keep',
        reason: 'ok',
        actions: [{ id: 'finalists', label: 'Finalistas', href: '/a' }],
      },
      {
        instrumentId: 'inst-lab',
        symbol: 'TEF',
        verdict: 'review_lab',
        reason: 'sin lab_validated',
        actions: [
          { id: 'lab', label: 'Lab', href: '/backtests?tab=jobs' },
          { id: 'finalists', label: 'Finalistas', href: '/f' },
        ],
      },
      {
        instrumentId: 'inst-replace',
        symbol: 'SAN',
        verdict: 'consider_replace',
        reason: 'no bate B&H',
        actions: [{ id: 'lab', label: 'Lab', href: '/lab' }],
      },
    ],
    ...overrides,
  };
}

describe('core-r-review-queue-store', () => {
  beforeEach(() => {
    localStorage.removeItem(CORE_R_REPORT_KEY);
    localStorage.removeItem(CORE_R_REVIEW_QUEUE_KEY);
    useCoreRReviewQueueStore.setState({ items: [] });
  });

  it('primaryCoreRAction picks first with href', () => {
    expect(
      primaryCoreRAction([
        { id: 'none', label: '—' },
        { id: 'lab', label: 'Lab', href: '/x' },
      ])?.id,
    ).toBe('lab');
  });

  it('syncFromReport enqueues only action rows and dedupes', () => {
    const report = sampleReport();
    saveCoreRReport(report);
    const store = useCoreRReviewQueueStore.getState();
    expect(store.syncFromReport('list-ibex')).toBe(2);
    expect(store.openCount('list-ibex')).toBe(2);
    expect(store.syncFromReport('list-ibex')).toBe(0);
    expect(store.openForList('list-ibex').map((i) => i.symbol).sort()).toEqual([
      'SAN',
      'TEF',
    ]);
  });

  it('syncFromReport merges extraRows (PnL) and dedupes by instrument', () => {
    saveCoreRReport(sampleReport());
    const store = useCoreRReviewQueueStore.getState();
    const n = store.syncFromReport('list-ibex', undefined, [
      {
        instrumentId: 'inst-pnl',
        symbol: 'BBVA',
        verdict: 'review_lab',
        reason: 'Demo/paper PnL -6.0%',
        actions: [{ id: 'lab', label: 'Lab', href: '/lab' }],
      },
      {
        // already in report → dedupe
        instrumentId: 'inst-lab',
        symbol: 'TEF',
        verdict: 'review_lab',
        reason: 'duplicate',
        actions: [{ id: 'lab', label: 'Lab', href: '/lab' }],
      },
    ]);
    expect(n).toBe(3); // TEF + SAN from report + BBVA from PnL
    expect(store.openCount('list-ibex')).toBe(3);
    expect(store.openForList('list-ibex').map((i) => i.symbol).sort()).toEqual([
      'BBVA',
      'SAN',
      'TEF',
    ]);
  });

  it('syncFromReport works with only extraRows (no report)', () => {
    const store = useCoreRReviewQueueStore.getState();
    const n = store.syncFromReport('list-empty', null, [
      {
        instrumentId: 'inst-x',
        symbol: 'ACS',
        verdict: 'consider_replace',
        reason: 'PnL -12%',
        actions: [{ id: 'finalists', label: 'Finalistas', href: '/f' }],
      },
    ]);
    expect(n).toBe(1);
    expect(store.openForList('list-empty')[0]?.symbol).toBe('ACS');
  });

  it('dismiss marks done; clearDone removes them', () => {
    saveCoreRReport(sampleReport());
    const store = useCoreRReviewQueueStore.getState();
    store.syncFromReport('list-ibex');
    const id = store.openForList('list-ibex')[0]!.id;
    store.dismiss(id);
    expect(store.openCount('list-ibex')).toBe(1);
    store.clearDone();
    expect(useCoreRReviewQueueStore.getState().items).toHaveLength(1);
  });

  it('dismissOpen closes all open for a list', () => {
    saveCoreRReport(sampleReport());
    const store = useCoreRReviewQueueStore.getState();
    store.syncFromReport('list-ibex');
    expect(store.openCount('list-ibex')).toBe(2);
    const n = store.dismissOpen('list-ibex');
    expect(n).toBe(2);
    expect(useCoreRReviewQueueStore.getState().openCount('list-ibex')).toBe(0);
  });
});
