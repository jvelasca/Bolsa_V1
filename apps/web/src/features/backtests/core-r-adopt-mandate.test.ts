/**
 * Tests — Adoptar mandato desde cola CORE-R (SEMI).
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { STRATEGY_ADOPTION_KEY } from '@/features/platform/strategy-adoption';
import { MANDATE_TENURES_KEY } from '@/features/platform/operating-mandate';
import type { InstrumentStrategyTopV1 } from '@bolsa/shared';

vi.mock('@/features/trading/demo-book-prefs', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@/features/trading/demo-book-prefs')>();
  return {
    ...actual,
    loadDemoBookPrefs: vi.fn(() => actual.defaultDemoBookPrefs()),
  };
});

import { loadDemoBookPrefs } from '@/features/trading/demo-book-prefs';
import {
  adoptMandateFromCoreR,
  canAdoptCoreRMandate,
  coreRAdoptAllowedForMode,
  coreRAdoptSlotFromTop,
} from '@/features/backtests/core-r-adopt-mandate';

const top: InstrumentStrategyTopV1 = {
  id: 'top-1',
  instrumentId: 'inst-1',
  timeframe: '1d',
  status: 'active',
  version: 2,
  evidenceLevel: 'lab_validated',
  slots: [
    {
      rank: 1,
      label: 'SMA cross',
      strategyDefinitionId: 'strat-1',
      stars: 3,
      score: 1,
      source: 'coach',
      runId: 'run-1',
    },
  ],
  createdAt: '2026-08-01T00:00:00.000Z',
  updatedAt: '2026-08-01T00:00:00.000Z',
};

describe('core-r-adopt-mandate', () => {
  beforeEach(() => {
    localStorage.removeItem(STRATEGY_ADOPTION_KEY);
    localStorage.removeItem(MANDATE_TENURES_KEY);
    vi.mocked(loadDemoBookPrefs).mockReturnValue({
      mode: 'semi',
      maxOpenPositions: 10,
      defaultSizePctOfCash: 10,
      countryPrefer: 'home_first',
    });
  });

  it('reads slot #1 with strategyDefinitionId', () => {
    expect(coreRAdoptSlotFromTop(top)?.strategyDefinitionId).toBe('strat-1');
    expect(coreRAdoptSlotFromTop({ ...top, slots: [] })).toBeNull();
  });

  it('allows only SEMI mode', () => {
    expect(coreRAdoptAllowedForMode('semi')).toBe(true);
    expect(coreRAdoptAllowedForMode('manual')).toBe(false);
    expect(coreRAdoptAllowedForMode('auto')).toBe(false);
  });

  it('canAdopt requires SEMI + consider_replace (+ TOP usable si se pasa)', () => {
    expect(
      canAdoptCoreRMandate({
        verdict: 'consider_replace',
        mode: 'semi',
        accountId: 'acc-1',
      }),
    ).toBe(true);
    expect(
      canAdoptCoreRMandate({
        verdict: 'consider_replace',
        mode: 'semi',
        accountId: 'acc-1',
        top,
      }),
    ).toBe(true);
    expect(
      canAdoptCoreRMandate({
        verdict: 'consider_replace',
        mode: 'semi',
        accountId: 'acc-1',
        top: { ...top, slots: [] },
      }),
    ).toBe(false);
    expect(
      canAdoptCoreRMandate({
        verdict: 'review_lab',
        mode: 'semi',
        accountId: 'acc-1',
        top,
      }),
    ).toBe(false);
    expect(
      canAdoptCoreRMandate({
        verdict: 'consider_replace',
        mode: 'manual',
        accountId: 'acc-1',
        top,
      }),
    ).toBe(false);
  });

  it('adopts mandate with actor core_r · propose_accepted', () => {
    const res = adoptMandateFromCoreR({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      verdict: 'consider_replace',
      timeframe: '1d',
      top,
      mode: 'semi',
    });
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.record.state).toBe('adoptada');
    expect(res.record.strategyDefinitionId).toBe('strat-1');
    expect(res.record.mandateTenureId).toBeTruthy();
  });

  it('denies when not SEMI', () => {
    const res = adoptMandateFromCoreR({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      verdict: 'consider_replace',
      timeframe: '1d',
      top,
      mode: 'auto',
    });
    expect(res).toEqual({ ok: false, reason: 'not_semi' });
  });
});
