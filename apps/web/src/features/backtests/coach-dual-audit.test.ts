/**
 * Tests — doble auditoría Coach ★ (A/A2/B/C + gate + red-team + post-Lab).
 */

import { describe, expect, it } from 'vitest';
import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';
import {
  applyAuditGate,
  auditFindingsFromLlmPayload,
  auditHeuristicFindings,
  buildAuditedDeepTechnicalCoachNote,
  buildCoachQuorum,
  filterLlmFindingsToAllowlist,
  runCoachChallengePack,
  runCoachDualAudit,
  shadowScoreA2,
} from '@/features/backtests/coach-dual-audit';
import { rankTechnicalRecommendations } from '@/features/backtests/backtest-deep-coach';

function row(
  partial: Partial<ExplorePresetRow> & Pick<ExplorePresetRow, 'strategyType' | 'label'>,
): ExplorePresetRow {
  return {
    category: 'trend',
    categoryLabel: 'Tendencia',
    status: 'ok',
    totalReturnPct: 20,
    excessReturnPct: 5,
    maxDrawdownPct: 12,
    tradeCount: 20,
    barCount: 500,
    sharpeRatio: 0.8,
    buyHoldReturnPct: 15,
    periodReturns: { early: 5, mid: 6, late: 10 },
    ...partial,
  };
}

const ctx = {
  symbol: 'BBVA',
  timeframe: '1d' as const,
  horizon: 'swing' as const,
  riskTolerance: 'moderate' as const,
};

describe('coach dual audit', () => {
  it('vetoes dead-cat bounce and keeps solid #1', () => {
    const bounce = row({
      strategyType: 'vwap_reclaim',
      label: 'VWAP',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
      periodReturns: { early: -55, mid: -25, late: 8 },
      totalReturnPct: -40,
      excessReturnPct: -35,
      maxDrawdownPct: 8,
      tradeCount: 4,
      sharpeRatio: -0.2,
    });
    const good = row({
      strategyType: 'sma_crossover',
      label: 'SMA',
      periodReturns: { early: 8, mid: 10, late: 16 },
      totalReturnPct: 45,
      excessReturnPct: 12,
      tradeCount: 30,
    });
    const good2 = row({
      strategyType: 'macd_signal_cross',
      label: 'MACD',
      category: 'momentum',
      categoryLabel: 'Momentum',
      periodReturns: { early: 5, mid: 8, late: 14 },
      totalReturnPct: 38,
      excessReturnPct: 9,
      tradeCount: 28,
    });

    const bundle = runCoachDualAudit({ rows: [bounce, good, good2], ctx });
    expect(bundle.audit.vetoedTypes).toContain('vwap_reclaim');
    expect(bundle.recommendations).toHaveLength(3);
    expect(bundle.recommendations[0]?.row.strategyType).not.toBe('vwap_reclaim');
    expect(bundle.recommendations[0]?.row.excessReturnPct).toBeGreaterThan(0);
    expect(['consensus', 'discrepancy', 'weak']).toContain(bundle.audit.confidence);
    expect(bundle.audit.quorum.chips.map((c) => c.id)).toEqual(['A', 'A2', 'B', 'C']);
    expect(bundle.audit.whyTop1.length).toBeGreaterThan(5);
  });

  it('LLM veto demotes type (may remain as last-resort #3 with ★≤2)', () => {
    const a = row({ strategyType: 'sma_crossover', label: 'SMA' });
    const b = row({
      strategyType: 'rsi_mean_reversion',
      label: 'RSI',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
      excessReturnPct: 4,
      periodReturns: { early: 3, mid: 4, late: 9 },
    });
    const c = row({
      strategyType: 'macd_signal_cross',
      label: 'MACD',
      category: 'momentum',
      categoryLabel: 'Momentum',
      excessReturnPct: 3,
      periodReturns: { early: 2, mid: 3, late: 8 },
    });
    const llm = auditFindingsFromLlmPayload({
      audit: {
        findings: [
          {
            strategyType: 'sma_crossover',
            action: 'veto',
            code: 'llm_regime',
            reason: 'Régimen no favorece trend ahora',
          },
        ],
      },
    });
    const bundle = runCoachDualAudit({ rows: [a, b, c], ctx, llmFindings: llm });
    expect(bundle.audit.vetoedTypes).toContain('sma_crossover');
    expect(bundle.recommendations).toHaveLength(3);
    expect(bundle.recommendations[0]?.row.strategyType).not.toBe('sma_crossover');
    const smaSlot = bundle.recommendations.find((r) => r.row.strategyType === 'sma_crossover');
    if (smaSlot) expect(smaSlot.stars).toBeLessThanOrEqual(2);
  });

  it('filters hallucinated LLM strategyType outside allowlist', () => {
    const raw = auditFindingsFromLlmPayload({
      audit: {
        findings: [
          { strategyType: 'invented_alpha', action: 'veto', code: 'halluc', reason: 'x' },
          { strategyType: 'sma_crossover', action: 'veto', code: 'ok', reason: 'y' },
        ],
      },
    });
    const filtered = filterLlmFindingsToAllowlist(raw, ['sma_crossover']);
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.strategyType).toBe('sma_crossover');
  });

  it('adversary C veto on A#1 marks auditorCDisagreement', () => {
    const a = row({
      strategyType: 'sma_crossover',
      label: 'SMA',
      excessReturnPct: 12,
      periodReturns: { early: 8, mid: 10, late: 16 },
    });
    const b = row({
      strategyType: 'rsi_mean_reversion',
      label: 'RSI',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
      excessReturnPct: 4,
      periodReturns: { early: 3, mid: 4, late: 9 },
    });
    const c = row({
      strategyType: 'macd_signal_cross',
      label: 'MACD',
      category: 'momentum',
      categoryLabel: 'Momentum',
      excessReturnPct: 3,
      periodReturns: { early: 2, mid: 3, late: 8 },
    });
    const adv = auditFindingsFromLlmPayload(
      {
        audit: {
          findings: [
            {
              strategyType: 'sma_crossover',
              action: 'veto',
              code: 'c_attack',
              reason: 'Adversario duda del crowning',
            },
          ],
        },
      },
      'llm_c',
    );
    const bundle = runCoachDualAudit({
      rows: [a, b, c],
      ctx,
      adversaryFindings: adv,
    });
    expect(bundle.audit.auditorCDisagreement).toBe(true);
    expect(bundle.audit.auditorCActive).toBe(true);
    expect(bundle.recommendations[0]?.row.strategyType).not.toBe('sma_crossover');
  });

  it('always returns up to 3 candidates even if all are vetoed (weak TOP)', () => {
    const rows = [
      row({
        strategyType: 'sma_crossover',
        label: 'SMA',
        excessReturnPct: -40,
        totalReturnPct: -20,
        periodReturns: { early: -30, mid: -20, late: -5 },
      }),
      row({
        strategyType: 'rsi_mean_reversion',
        label: 'RSI',
        category: 'mean_reversion',
        categoryLabel: 'Reversión',
        excessReturnPct: -30,
        totalReturnPct: -15,
        periodReturns: { early: -25, mid: -10, late: -8 },
      }),
      row({
        strategyType: 'macd_signal_cross',
        label: 'MACD',
        category: 'momentum',
        categoryLabel: 'Momentum',
        excessReturnPct: -25,
        totalReturnPct: -10,
        periodReturns: { early: -20, mid: -12, late: -4 },
      }),
    ];
    const bundle = runCoachDualAudit({ rows, ctx });
    expect(bundle.recommendations).toHaveLength(3);
    expect(bundle.audit.confidence).toBe('weak');
    expect(bundle.recommendations.every((r) => r.stars <= 2)).toBe(true);
  });

  it('challenge fails when #1 loses buy & hold', () => {
    const weak = row({
      strategyType: 'sma_crossover',
      label: 'SMA',
      excessReturnPct: -2,
      periodReturns: { early: 1, mid: 1, late: 1 },
      totalReturnPct: 2,
    });
    const shortlist = rankTechnicalRecommendations([weak], ctx, 3);
    const findings = auditHeuristicFindings(shortlist);
    const gated = applyAuditGate(shortlist, findings, 3);
    expect(gated.length).toBeGreaterThan(0);
    const challenge = runCoachChallengePack(gated);
    expect(challenge.passed).toBe(false);
    expect(challenge.checks.some((c) => c.code === 'top_beats_bh' && !c.passed)).toBe(true);
  });

  it('red-team flags clone family as soft fail', () => {
    const clones = [
      row({
        strategyType: 'sma_crossover',
        label: 'SMA',
        strategyDefinitionId: 'a',
        category: 'trend',
        categoryLabel: 'Tendencia',
      }),
      row({
        strategyType: 'golden_cross',
        label: 'Golden',
        strategyDefinitionId: 'b',
        category: 'trend',
        categoryLabel: 'Tendencia',
        excessReturnPct: 4,
        periodReturns: { early: 4, mid: 5, late: 9 },
      }),
      row({
        strategyType: 'donchian_breakout',
        label: 'Donchian',
        strategyDefinitionId: 'c',
        category: 'trend',
        categoryLabel: 'Tendencia',
        excessReturnPct: 3,
        periodReturns: { early: 3, mid: 4, late: 8 },
      }),
    ];
    const shortlist = rankTechnicalRecommendations(clones, ctx, {
      limit: 5,
      diversifyCategories: false,
    });
    const gated = applyAuditGate(shortlist, [], 3);
    const challenge = runCoachChallengePack(gated);
    expect(challenge.passed).toBe(true);
    expect(challenge.softPassed).toBe(false);
    expect(challenge.checks.some((c) => c.code === 'family_diversity' && !c.passed)).toBe(true);
  });

  it('post_lab soft-fail does not force weak if #1 is clean', () => {
    const clones = [
      row({
        strategyType: 'sma_crossover',
        label: 'SMA',
        strategyDefinitionId: 'a',
        category: 'trend',
        categoryLabel: 'Tendencia',
        periodReturns: { early: 8, mid: 10, late: 16 },
        excessReturnPct: 12,
        tradeCount: 30,
      }),
      row({
        strategyType: 'golden_cross',
        label: 'Golden',
        strategyDefinitionId: 'b',
        category: 'trend',
        categoryLabel: 'Tendencia',
        excessReturnPct: 4,
        periodReturns: { early: 4, mid: 5, late: 9 },
        tradeCount: 22,
      }),
      row({
        strategyType: 'donchian_breakout',
        label: 'Donchian',
        strategyDefinitionId: 'c',
        category: 'trend',
        categoryLabel: 'Tendencia',
        excessReturnPct: 3,
        periodReturns: { early: 3, mid: 4, late: 8 },
        tradeCount: 18,
      }),
    ];
    const labCtx = { ...ctx, evidenceLevel: 'lab_validated' as const };
    const post = runCoachDualAudit({
      rows: clones,
      ctx: labCtx,
      coachPass: 'post_lab',
    });
    expect(post.audit.softWeak).toBe(true);
    expect(post.audit.confidence).not.toBe('weak');
    expect(['consensus', 'discrepancy']).toContain(post.audit.confidence);

    const initial = runCoachDualAudit({
      rows: clones,
      ctx,
      coachPass: 'initial',
    });
    expect(initial.audit.confidence).toBe('weak');
  });

  it('gate keeps Lab Mejores with same family type but distinct definitionId', () => {
    const a = rankTechnicalRecommendations(
      [
        row({
          strategyType: 'sma_crossover',
          label: 'SMA opt A',
          strategyDefinitionId: 'def_a',
          periodReturns: { early: 2, mid: 5, late: 12 },
          excessReturnPct: 8,
        }),
        row({
          strategyType: 'sma_crossover',
          label: 'Donchian→SMA opt B',
          strategyDefinitionId: 'def_b',
          periodReturns: { early: 1, mid: 4, late: 10 },
          excessReturnPct: 6,
        }),
        row({
          strategyType: 'rsi_mean_reversion',
          label: 'RSI opt',
          strategyDefinitionId: 'def_c',
          category: 'mean_reversion',
          categoryLabel: 'Reversión',
          periodReturns: { early: 0, mid: 3, late: 9 },
          excessReturnPct: 5,
        }),
      ],
      { ...ctx, evidenceLevel: 'lab_validated' },
      5,
    );
    const gated = applyAuditGate(a, [], 3);
    expect(gated).toHaveLength(3);
    expect(new Set(gated.map((g) => g.row.strategyDefinitionId)).size).toBe(3);
  });

  it('buildAuditedDeepTechnicalCoachNote attaches audit 1.1', () => {
    const note = buildAuditedDeepTechnicalCoachNote(
      [
        row({ strategyType: 'sma_crossover', label: 'SMA' }),
        row({
          strategyType: 'rsi_mean_reversion',
          label: 'RSI',
          category: 'mean_reversion',
          categoryLabel: 'Reversión',
        }),
      ],
      ctx,
    );
    expect(note.audit?.schemaVersion).toBe('1.1.0');
    expect(note.recommendations.length).toBeGreaterThan(0);
    expect(note.headline).toMatch(/BBVA/);
    expect(note.audit?.quorum.whyTop1).toBeTruthy();
  });

  it('quorum builder surfaces chips', () => {
    const q = buildCoachQuorum({
      primaryTopType: 'sma_crossover',
      shadowTopType: 'rsi_mean_reversion',
      shadowDisagreement: true,
      findings: [],
      challenge: { passed: true, softPassed: true, checks: [] },
      auditorCActive: false,
      auditorCDisagreement: false,
      whyTop1: 'SMA · reciente 10%',
      recommendations: [],
    });
    expect(q.agree).toBe(false);
    expect(q.chips.find((c) => c.id === 'A2')?.tone).toBe('warn');
  });

  it('shadow score prefers high excess+late', () => {
    const low = row({
      strategyType: 'sma_crossover',
      label: 'A',
      excessReturnPct: 1,
      sharpeRatio: 0.5,
      periodReturns: { early: 1, mid: 1, late: 2 },
    });
    const high = row({
      strategyType: 'golden_cross',
      label: 'B',
      excessReturnPct: 20,
      sharpeRatio: 1.2,
      periodReturns: { early: 5, mid: 8, late: 22 },
    });
    expect(shadowScoreA2(high, 22)).toBeGreaterThan(shadowScoreA2(low, 2));
  });
});
