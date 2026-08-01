/**
 * Tests — resumen estado backtesting por miembro de lista.
 */

import { describe, expect, it } from 'vitest';
import type { InstrumentStrategyTopV1 } from '@bolsa/shared';
import { summarizeListMemberBacktest } from '@/features/backtests/backtest-list-member-status';

function makeTop(
  partial: Partial<InstrumentStrategyTopV1> &
    Pick<InstrumentStrategyTopV1, 'status' | 'evidenceLevel' | 'slots'>,
): InstrumentStrategyTopV1 {
  return {
    id: 't1',
    instrumentId: 'i1',
    timeframe: '1d',
    version: 1,
    createdAt: '2026-07-30T10:00:00.000Z',
    updatedAt: '2026-07-30T12:00:00.000Z',
    ...partial,
  };
}

describe('summarizeListMemberBacktest', () => {
  it('marks empty as pendiente', () => {
    const s = summarizeListMemberBacktest({ top: null });
    expect(s.primary).toMatch(/Sin Finalistas/i);
    expect(s.rankScore).toBe(0);
  });

  it('summarizes active lab top with stars', () => {
    const s = summarizeListMemberBacktest({
      top: makeTop({
        status: 'active',
        evidenceLevel: 'lab_validated',
        slots: [
          {
            rank: 1,
            label: 'SMA',
            stars: 4,
            score: 80,
            source: 'optimized',
            excessReturnPct: 12.3,
          },
        ],
      }),
    });
    expect(s.primary).toMatch(/4★/);
    expect(s.primary).toMatch(/Activo/);
    expect(s.primary).toMatch(/Lab/);
    expect(s.secondary).toMatch(/12\.3%/);
    expect(s.tone).toBe('emerald');
  });

  it('prefers AUTO running over TOP line', () => {
    const s = summarizeListMemberBacktest({
      autoPhase: 'running',
      top: makeTop({
        status: 'semifinal',
        evidenceLevel: 'in_sample_only',
        slots: [{ rank: 1, label: 'RSI', stars: 3, score: 50, source: 'coach' }],
      }),
    });
    expect(s.primary).toMatch(/en curso/i);
    expect(s.secondary).toMatch(/3★/);
  });
});
