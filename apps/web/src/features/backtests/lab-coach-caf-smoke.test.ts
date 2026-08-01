/**
 * Smoke CAF / Lab→Coach²: mismos presetKey + definitionIds distintos,
 * post_lab soft ACK, heatmap plateau, handoff gate.
 *
 * Reproduce el caso IBEX (p. ej. CAF): 3 Mejores Lab familia SMA que no
 * deben colapsar a 2 en el gate, y soft-fail post-Lab no fuerza weak.
 */

import { describe, expect, it } from 'vitest';
import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';
import {
  applyAuditGate,
  runCoachDualAudit,
} from '@/features/backtests/coach-dual-audit';
import { rankTechnicalRecommendations } from '@/features/backtests/backtest-deep-coach';
import { buildOptimizeHeatmap } from '@/features/backtests/backtest-optimize-heatmap';
import { resolveLabReanalyzeGate } from '@/features/backtests/lab-coach-handoff';
import type { SmaGridTrialDto } from '@bolsa/shared';

function exploreRow(
  partial: Partial<ExplorePresetRow> &
    Pick<ExplorePresetRow, 'strategyType' | 'label' | 'strategyDefinitionId'>,
): ExplorePresetRow {
  return {
    category: 'trend',
    categoryLabel: 'Tendencia',
    status: 'ok',
    totalReturnPct: 28,
    excessReturnPct: 8,
    maxDrawdownPct: 14,
    tradeCount: 24,
    barCount: 500,
    sharpeRatio: 0.9,
    buyHoldReturnPct: 20,
    periodReturns: { early: 4, mid: 8, late: 14 },
    ...partial,
  };
}

const cafCtx = {
  symbol: 'CAF',
  timeframe: '1d' as const,
  horizon: 'swing' as const,
  riskTolerance: 'moderate' as const,
  evidenceLevel: 'lab_validated' as const,
};

describe('CAF Lab→Coach² smoke', () => {
  it('keeps 3 Lab Mejores with same presetKey via distinct definitionId', () => {
    const rows = [
      exploreRow({
        strategyType: 'sma_crossover',
        label: 'CAF · SMA opt #1',
        strategyDefinitionId: 'def_caf_1',
        periodReturns: { early: 5, mid: 9, late: 18 },
        excessReturnPct: 12,
      }),
      exploreRow({
        strategyType: 'sma_crossover',
        label: 'CAF · Donchian→SMA #2',
        strategyDefinitionId: 'def_caf_2',
        periodReturns: { early: 3, mid: 7, late: 15 },
        excessReturnPct: 9,
      }),
      exploreRow({
        strategyType: 'sma_crossover',
        label: 'CAF · Supertrend→SMA #3',
        strategyDefinitionId: 'def_caf_3',
        periodReturns: { early: 2, mid: 6, late: 12 },
        excessReturnPct: 6,
      }),
    ];

    const shortlist = rankTechnicalRecommendations(rows, cafCtx, {
      limit: 7,
      diversifyCategories: true,
    });
    const gated = applyAuditGate(shortlist, [], 3);
    expect(gated).toHaveLength(3);
    expect(new Set(gated.map((g) => g.row.strategyDefinitionId)).size).toBe(3);

    const bundle = runCoachDualAudit({
      rows,
      ctx: cafCtx,
      coachPass: 'post_lab',
    });
    expect(bundle.recommendations).toHaveLength(3);
    expect(bundle.audit.coachPass).toBe('post_lab');
    expect(bundle.audit.schemaVersion).toBe('1.1.0');
    expect(bundle.audit.quorum.chips).toHaveLength(4);
  });

  it('post_lab soft family-clone does not force weak when #1 is clean', () => {
    const clones = [
      exploreRow({
        strategyType: 'sma_crossover',
        label: 'A',
        strategyDefinitionId: 'a',
        periodReturns: { early: 8, mid: 10, late: 16 },
        excessReturnPct: 12,
        tradeCount: 30,
      }),
      exploreRow({
        strategyType: 'golden_cross',
        label: 'B',
        strategyDefinitionId: 'b',
        periodReturns: { early: 4, mid: 5, late: 9 },
        excessReturnPct: 4,
        tradeCount: 22,
      }),
      exploreRow({
        strategyType: 'donchian_breakout',
        label: 'C',
        strategyDefinitionId: 'c',
        periodReturns: { early: 3, mid: 4, late: 8 },
        excessReturnPct: 3,
        tradeCount: 18,
      }),
    ];
    // Force same category to trigger soft family_diversity
    const sameFamily = clones.map((r) => ({
      ...r,
      category: 'trend' as const,
      categoryLabel: 'Tendencia',
    }));

    const post = runCoachDualAudit({
      rows: sameFamily,
      ctx: cafCtx,
      coachPass: 'post_lab',
    });
    expect(post.audit.softWeak).toBe(true);
    expect(post.audit.confidence).not.toBe('weak');
    expect(post.recommendations[0]?.row.strategyDefinitionId).toBe('a');
  });

  it('Lab P1 heatmap + plateau + handoff block compose', () => {
    const trials: SmaGridTrialDto[] = [
      {
        fastPeriod: 10,
        slowPeriod: 50,
        totalReturnPct: 10,
        maxDrawdownPct: 12,
        tradeCount: 15,
        score: 4.8,
      },
      {
        fastPeriod: 20,
        slowPeriod: 40,
        totalReturnPct: 11,
        maxDrawdownPct: 12,
        tradeCount: 16,
        score: 4.85,
      },
      {
        fastPeriod: 20,
        slowPeriod: 50,
        totalReturnPct: 14,
        maxDrawdownPct: 11,
        tradeCount: 18,
        score: 5,
      },
      {
        fastPeriod: 20,
        slowPeriod: 60,
        totalReturnPct: 10,
        maxDrawdownPct: 12,
        tradeCount: 14,
        score: 4.7,
      },
      {
        fastPeriod: 30,
        slowPeriod: 50,
        totalReturnPct: 12,
        maxDrawdownPct: 12,
        tradeCount: 17,
        score: 4.9,
      },
    ];
    const heat = buildOptimizeHeatmap({
      trials,
      family: 'sma_crossover',
      plateauAbsTol: 0.35,
      plateauMinClose: 2,
    });
    expect(heat?.plateau.isPlateau).toBe(true);
    expect(heat?.top5[0]?.score).toBe(5);

    const blocked = resolveLabReanalyzeGate({
      improvedSaved: 1,
      saveFailures: [{ rank: 1, error: 'network' }],
      carriedCount: 0,
    });
    expect(blocked.allow).toBe(false);

    const ok = resolveLabReanalyzeGate({
      improvedSaved: 3,
      saveFailures: [],
      carriedCount: 0,
    });
    expect(ok.allow).toBe(true);
  });
});
