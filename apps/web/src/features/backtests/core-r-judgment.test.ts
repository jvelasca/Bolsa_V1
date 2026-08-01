/**
 * Tests — CORE-R v0 juicio de reevaluación.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  CORE_R_REPORT_KEY,
  buildCoreRPaperPnlReviewRow,
  buildCoreRReportFromBoard,
  coreRAccountReturnPct,
  coreRNeedsAction,
  coreROosDegradation,
  coreRPaperPnlDegradation,
  judgeCoreR,
  listCoreRActionRows,
  readCoreRReport,
  readCoreRVerdictForInstrument,
  saveCoreRReport,
} from '@/features/backtests/core-r-judgment';

const base = {
  instrumentId: 'inst-1',
  timeframe: '1d',
  symbol: 'TEF',
};

describe('judgeCoreR', () => {
  it('marks omitido as fresh_ok', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'skip_fresh',
      change: 'same',
    });
    expect(j.verdict).toBe('fresh_ok');
    expect(j.reason).toMatch(/fresco/i);
  });

  it('flags high PBO OOS as consider_replace', () => {
    expect(coreROosDegradation({ kind: 'holdout', pbo: 0.62 })?.level).toBe(
      'consider_replace',
    );
    const j = judgeCoreR({
      ...base,
      settleReason: 'saved',
      change: 'same',
      evidenceLevel: 'lab_validated',
      oos: { kind: 'cpcv', pbo: 0.7 },
    });
    expect(j.verdict).toBe('consider_replace');
    expect(j.reason).toMatch(/PBO/i);
  });

  it('does not let OOS override skip_fresh', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'skip_fresh',
      change: 'same',
      oos: { kind: 'holdout', pbo: 0.9 },
    });
    expect(j.verdict).toBe('fresh_ok');
  });

  it('flags profile mismatch', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'saved',
      change: 'changed',
      evidenceLevel: 'lab_validated',
      topProfileId: 'old',
      activeProfileId: 'new',
    });
    expect(j.verdict).toBe('profile_mismatch');
  });

  it('skip_lab → skipped_weak', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'skip_lab',
      change: 'same',
    });
    expect(j.verdict).toBe('skipped_weak');
    expect(j.actions.some((a) => a.id === 'lab')).toBe(true);
  });

  it('saved without lab_validated → review_lab', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'saved',
      change: 'new',
      evidenceLevel: 'in_sample_only',
    });
    expect(j.verdict).toBe('review_lab');
  });

  it('fails B&H → consider_replace with actions', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'saved',
      change: 'changed',
      evidenceLevel: 'lab_validated',
      dualAudit: {
        confidence: 'consensus',
        challenge: {
          passed: false,
          checks: [{ code: 'top_beats_bh', passed: false }],
        },
      },
      slot1RunId: 'run-1',
    });
    expect(j.verdict).toBe('consider_replace');
    expect(j.actions.map((a) => a.id)).toEqual(
      expect.arrayContaining(['lab', 'finalists', 'checklist']),
    );
  });

  it('stable lab_validated → keep', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'saved',
      change: 'same',
      evidenceLevel: 'lab_validated',
      dualAudit: { confidence: 'consensus', softWeak: false },
      activeProfileId: 'p1',
      topProfileId: 'p1',
    });
    expect(j.verdict).toBe('keep');
  });

  it('paper PnL −5% → review_lab; −10% → consider_replace', () => {
    expect(
      coreRPaperPnlDegradation({
        accountId: 'a',
        returnPct: -5,
        totalUnrealizedPnl: -500,
        totalEquity: 9500,
        initialDeposit: 10_000,
      })?.level,
    ).toBe('review_lab');
    expect(
      coreRPaperPnlDegradation({
        accountId: 'a',
        returnPct: -10,
        totalUnrealizedPnl: -1000,
        totalEquity: 9000,
        initialDeposit: 10_000,
      })?.level,
    ).toBe('consider_replace');
    expect(
      coreRPaperPnlDegradation({
        accountId: 'a',
        returnPct: -4.9,
        totalUnrealizedPnl: -490,
        totalEquity: 9510,
        initialDeposit: 10_000,
      }),
    ).toBeNull();
  });

  it('does not let paper PnL override skip_fresh', () => {
    const j = judgeCoreR({
      ...base,
      settleReason: 'skip_fresh',
      change: 'same',
      paperPnl: {
        accountId: 'a',
        returnPct: -20,
        totalUnrealizedPnl: -2000,
        totalEquity: 8000,
        initialDeposit: 10_000,
      },
    });
    expect(j.verdict).toBe('fresh_ok');
  });

  it('buildCoreRPaperPnlReviewRow enqueues from live DEMO PnL', () => {
    const row = buildCoreRPaperPnlReviewRow({
      instrumentId: 'inst-1',
      symbol: 'TEF',
      timeframe: '1d',
      pnl: {
        accountId: 'demo-1',
        returnPct: -12,
        totalUnrealizedPnl: -1200,
        totalEquity: 8800,
        initialDeposit: 10_000,
      },
      slot1RunId: 'run-1',
    });
    expect(row?.verdict).toBe('consider_replace');
    expect(row?.reason).toMatch(/PnL/i);
  });
});

describe('coreRAccountReturnPct', () => {
  it('computes vs initial deposit', () => {
    expect(coreRAccountReturnPct(10_000, 9500)).toBeCloseTo(-5);
    expect(coreRAccountReturnPct(0, 100)).toBeNull();
  });
});

describe('core-r report store', () => {
  beforeEach(() => {
    localStorage.removeItem(CORE_R_REPORT_KEY);
  });

  it('persists and reads per list / instrument', () => {
    const judgment = judgeCoreR({
      ...base,
      settleReason: 'skip_fresh',
      change: 'same',
    });
    const report = buildCoreRReportFromBoard({
      listId: 'list-ibex',
      timeframe: '1d',
      rows: [
        {
          instrumentId: 'inst-1',
          symbol: 'TEF',
          reeval: judgment,
          settleReason: 'skip_fresh',
          change: 'same',
        },
      ],
    });
    saveCoreRReport(report);
    expect(readCoreRReport('list-ibex')?.rows).toHaveLength(1);
    expect(readCoreRVerdictForInstrument('list-ibex', 'inst-1')?.verdict).toBe(
      'fresh_ok',
    );
    expect(readCoreRVerdictForInstrument('list-ibex', 'other')).toBeNull();
  });

  it('coreRNeedsAction + listCoreRActionRows filter keep/fresh_ok', () => {
    expect(coreRNeedsAction('keep')).toBe(false);
    expect(coreRNeedsAction('fresh_ok')).toBe(false);
    expect(coreRNeedsAction('review_lab')).toBe(true);
    const report = buildCoreRReportFromBoard({
      listId: 'L',
      timeframe: '1d',
      rows: [
        {
          instrumentId: 'a',
          symbol: 'A',
          reeval: judgeCoreR({
            ...base,
            instrumentId: 'a',
            settleReason: 'skip_fresh',
            change: 'same',
          }),
        },
        {
          instrumentId: 'b',
          symbol: 'B',
          reeval: judgeCoreR({
            ...base,
            instrumentId: 'b',
            settleReason: 'skip_lab',
            change: 'same',
          }),
        },
      ],
    });
    expect(listCoreRActionRows(report)).toHaveLength(1);
    expect(listCoreRActionRows(report)[0]?.verdict).toBe('skipped_weak');
  });
});
