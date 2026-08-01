import { describe, expect, it } from 'vitest';
import {
  buildDiaDSessionEvidence,
  type DiaDSessionEvidenceInput,
} from './dia-d-session-evidence';

const base = (): DiaDSessionEvidenceInput => ({
  mode: 'semi',
  symbol: 'ACS',
  strategyLabel: 'SMA cross',
  diaD: '2024-01-01',
  endDate: '2024-12-31',
  initialCash: 10_000,
  auto: {
    totalReturnPct: 12,
    maxDrawdownPct: 8,
    tradeCount: 6,
    finalEquity: 11_200,
  },
  gated: {
    totalReturnPct: 10,
    maxDrawdownPct: 7,
    tradeCount: 4,
    finalEquity: 11_000,
  },
  gate: { accepted: 4, rejected: 2 },
});

describe('buildDiaDSessionEvidence', () => {
  it('marks incomplete when semi has no decisions', () => {
    const ev = buildDiaDSessionEvidence({
      ...base(),
      gate: { accepted: 0, rejected: 0 },
      gated: { ...base().gated, tradeCount: 0, totalReturnPct: 0 },
    });
    expect(ev.band).toBe('incomplete');
    expect(ev.confidence).toBe('LOW');
    expect(ev.schemaVersion).toBe('dia_d_session_evidence_v1');
  });

  it('favorable when gated return solid vs auto', () => {
    const ev = buildDiaDSessionEvidence({
      ...base(),
      gated: {
        totalReturnPct: 14,
        maxDrawdownPct: 6,
        tradeCount: 4,
        finalEquity: 11_400,
      },
      gate: { accepted: 4, rejected: 2 },
    });
    expect(ev.band).toBe('favorable');
    expect(ev.metrics.returnDeltaVsAutoPct).toBeCloseTo(2, 5);
    expect(ev.paragraphs).toHaveLength(3);
  });

  it('adverse on large negative delta', () => {
    const ev = buildDiaDSessionEvidence({
      ...base(),
      gated: {
        totalReturnPct: -10,
        maxDrawdownPct: 22,
        tradeCount: 2,
        finalEquity: 9_000,
      },
    });
    expect(ev.band).toBe('adverse');
    expect(ev.warnings.some((w) => w.includes('DD'))).toBe(true);
  });

  it('auto mode uses auto path without incomplete', () => {
    const ev = buildDiaDSessionEvidence({
      ...base(),
      mode: 'auto',
      gate: { accepted: 0, rejected: 0 },
      gated: base().auto,
    });
    expect(ev.band).not.toBe('incomplete');
    expect(ev.claims.some((c) => c.includes('Auto'))).toBe(true);
  });
});
