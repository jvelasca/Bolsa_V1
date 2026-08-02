import { beforeEach, describe, expect, it } from 'vitest';
import {
  MANDATE_TENURES_KEY,
  MANDATE_TRADE_LINKS_KEY,
  applyMandateChange,
  countTradeLinksForInstrument,
  getOpenMandateTenure,
  linkTradeToMandate,
  listMandateTenures,
  summarizeMandateChurn,
} from '@/features/platform/operating-mandate';
import {
  STRATEGY_ADOPTION_KEY,
  clearAdoption,
  getAdoption,
  getAdoptionState,
  setAdoption,
} from '@/features/platform/strategy-adoption';

describe('operating-mandate', () => {
  beforeEach(() => {
    localStorage.removeItem(MANDATE_TENURES_KEY);
    localStorage.removeItem(MANDATE_TRADE_LINKS_KEY);
    localStorage.removeItem(STRATEGY_ADOPTION_KEY);
  });

  it('opens a tenure and keeps a single open slot', () => {
    const { opened } = applyMandateChange({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      open: {
        strategyDefinitionId: 's1',
        strategyLabelSnapshot: 'SMA',
        actor: 'user',
        reason: 'adopt',
      },
    });
    expect(opened?.strategyDefinitionId).toBe('s1');
    expect(getOpenMandateTenure('inst-1', 'acc-1')?.id).toBe(opened?.id);

    applyMandateChange({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      open: {
        strategyDefinitionId: 's2',
        strategyLabelSnapshot: 'RSI',
        actor: 'coach',
        reason: 'switch',
      },
    });
    const rows = listMandateTenures('inst-1', 'acc-1');
    expect(rows).toHaveLength(2);
    expect(rows[0].effectiveTo).not.toBeNull();
    expect(rows[1].effectiveTo).toBeNull();
    expect(rows[1].actor).toBe('coach');
  });

  it('does not duplicate tenure for the same strategy', () => {
    applyMandateChange({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      open: { strategyDefinitionId: 's1', strategyLabelSnapshot: 'SMA' },
    });
    applyMandateChange({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      open: { strategyDefinitionId: 's1', strategyLabelSnapshot: 'SMA' },
    });
    expect(listMandateTenures('inst-1', 'acc-1')).toHaveLength(1);
  });

  it('links trades to the open mandate', () => {
    const { opened } = applyMandateChange({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      open: { strategyDefinitionId: 's1' },
    });
    const link = linkTradeToMandate({
      transactionId: 'tx-1',
      instrumentId: 'inst-1',
      accountId: 'acc-1',
    });
    expect(link?.mandateTenureId).toBe(opened?.id);
    expect(countTradeLinksForInstrument('inst-1', 'acc-1')).toBe(1);
  });

  it('summarizes churn by actor', () => {
    applyMandateChange({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      open: { strategyDefinitionId: 's1', actor: 'user' },
    });
    applyMandateChange({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      open: { strategyDefinitionId: 's2', actor: 'coach' },
    });
    const s = summarizeMandateChurn({ accountId: 'acc-1' });
    expect(s.totalChanges).toBe(2);
    expect(s.byActor.user).toBe(1);
    expect(s.byActor.coach).toBe(1);
    expect(s.openCount).toBe(1);
    expect(s.closedCount).toBe(1);
  });
});

describe('strategy-adoption ↔ mandate', () => {
  beforeEach(() => {
    localStorage.removeItem(MANDATE_TENURES_KEY);
    localStorage.removeItem(MANDATE_TRADE_LINKS_KEY);
    localStorage.removeItem(STRATEGY_ADOPTION_KEY);
  });

  it('adoptada opens mandate tenure', () => {
    const rec = setAdoption({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      state: 'adoptada',
      strategyDefinitionId: 's1',
      strategyLabel: 'SMA',
    });
    expect(getAdoptionState('inst-1', 'acc-1')).toBe('adoptada');
    expect(rec.mandateTenureId).toBeTruthy();
    expect(getOpenMandateTenure('inst-1', 'acc-1')?.strategyDefinitionId).toBe('s1');
  });

  it('candidata does not open mandate', () => {
    setAdoption({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      state: 'candidata',
      strategyDefinitionId: 's1',
    });
    expect(listMandateTenures('inst-1', 'acc-1')).toHaveLength(0);
  });

  it('obsoleta and clear close open tenure', () => {
    setAdoption({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      state: 'adoptada',
      strategyDefinitionId: 's1',
    });
    setAdoption({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      state: 'obsoleta',
      strategyDefinitionId: 's1',
    });
    expect(getOpenMandateTenure('inst-1', 'acc-1')).toBeNull();
    expect(listMandateTenures('inst-1', 'acc-1')[0]?.effectiveTo).toBeTruthy();

    setAdoption({
      instrumentId: 'inst-1',
      accountId: 'acc-1',
      state: 'adoptada',
      strategyDefinitionId: 's2',
    });
    clearAdoption('inst-1', 'acc-1');
    expect(getAdoptionState('inst-1', 'acc-1')).toBe('none');
    expect(getOpenMandateTenure('inst-1', 'acc-1')).toBeNull();
  });

  it('seeds tenure from legacy adoptada without mandateTenureId', () => {
    localStorage.setItem(
      STRATEGY_ADOPTION_KEY,
      JSON.stringify({
        'inst-1::acc-1': {
          engine: 'strategy-adoption-v1',
          instrumentId: 'inst-1',
          accountId: 'acc-1',
          state: 'adoptada',
          strategyDefinitionId: 'legacy-s',
          strategyLabel: 'Legacy',
          updatedAt: '2026-07-01T00:00:00.000Z',
        },
      }),
    );
    const rec = getAdoption('inst-1', 'acc-1');
    expect(rec?.mandateTenureId).toBeTruthy();
    expect(getOpenMandateTenure('inst-1', 'acc-1')?.strategyDefinitionId).toBe('legacy-s');
  });
});
