/**
 * Batería de coherencia del coach ★ — pilar del embudo.
 *
 * Simula lotes multi-instrumento (sin API) y verifica:
 * - periodReturns fijados → ranking estable (no soft fallback)
 * - TOP diverso por familia
 * - suelos de calidad (no crowning de “muy mala”)
 * - dedupe por strategyType
 * - Guardar TOP-3 produce 3 slots únicos
 * - Distintos valores → TOP distinto cuando el tramo reciente difiere
 */

import { describe, expect, it } from 'vitest';
import {
  dedupeExploreRowsByStrategyType,
  pickDiversifiedTop,
  rankTechnicalRecommendations,
  type DeepCoachContext,
} from '@/features/backtests/backtest-deep-coach';
import {
  matrixRowsToExploreRows,
  type ExplorePresetRow,
} from '@/features/backtests/backtest-explore-value';
import { periodReturnsFromEquity } from '@/features/backtests/backtest-period-returns';
import { buildCoachTopSlots } from '@/features/backtests/coach-top-save';
import type { StrategyMatrixRow } from '@/features/backtests/backtest-strategy-matrix';
import type { StrategyDefinitionSummaryDto } from '@bolsa/shared';

function row(
  partial: Partial<ExplorePresetRow> & Pick<ExplorePresetRow, 'strategyType' | 'label'>,
): ExplorePresetRow {
  return {
    category: 'trend',
    categoryLabel: 'Tendencia',
    status: 'ok',
    totalReturnPct: 10,
    excessReturnPct: 2,
    maxDrawdownPct: 12,
    tradeCount: 20,
    barCount: 500,
    sharpeRatio: 0.8,
    buyHoldReturnPct: 8,
    ...partial,
  };
}

function equityRamp(points: number[]): Array<{ equity: number }> {
  return points.map((equity) => ({ equity }));
}

/** 12 puntos: early / mid / late shaped by multipliers on thirds. */
function thirdsEquity(earlyMul: number, midMul: number, lateMul: number) {
  const pts: number[] = [];
  let eq = 100;
  for (let i = 0; i < 4; i += 1) {
    eq *= 1 + earlyMul / 4 / 100;
    pts.push(eq);
  }
  for (let i = 0; i < 4; i += 1) {
    eq *= 1 + midMul / 4 / 100;
    pts.push(eq);
  }
  for (let i = 0; i < 4; i += 1) {
    eq *= 1 + lateMul / 4 / 100;
    pts.push(eq);
  }
  return periodReturnsFromEquity(equityRamp(pts))!;
}

const baseCtx = (symbol: string): DeepCoachContext => ({
  symbol,
  timeframe: '1d',
  horizon: 'swing',
  riskTolerance: 'moderate',
});

/** Catálogo sintético tipado como lote de genéricas. */
function catalogForInstrument(symbol: string, lateByType: Record<string, number>): ExplorePresetRow[] {
  const defs: Array<{
    strategyType: ExplorePresetRow['strategyType'];
    label: string;
    category: ExplorePresetRow['category'];
    categoryLabel: string;
  }> = [
    { strategyType: 'sma_crossover', label: 'SMA 20/50', category: 'trend', categoryLabel: 'Tendencia' },
    { strategyType: 'golden_cross', label: 'Golden', category: 'trend', categoryLabel: 'Tendencia' },
    { strategyType: 'ma_stack_bullish', label: 'MA stack', category: 'trend', categoryLabel: 'Tendencia' },
    {
      strategyType: 'rsi_mean_reversion',
      label: 'RSI',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
    },
    {
      strategyType: 'stoch_oversold',
      label: 'Stoch',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
    },
    {
      strategyType: 'macd_signal_cross',
      label: 'MACD',
      category: 'momentum',
      categoryLabel: 'Momentum',
    },
    {
      strategyType: 'donchian_breakout',
      label: 'Donchian',
      category: 'trend',
      categoryLabel: 'Tendencia',
    },
  ];
  return defs.map((d) => {
    const late = lateByType[d.strategyType] ?? 0;
    const early = late > 0 ? late * 0.2 : 15;
    const mid = late > 0 ? late * 0.4 : 5;
    const pr = thirdsEquity(early, mid, late);
    const excess = late - 2;
    return row({
      ...d,
      runId: `${symbol}-${d.strategyType}`,
      periodReturns: pr,
      totalReturnPct: early + mid + late,
      excessReturnPct: excess,
      maxDrawdownPct: Math.max(8, 25 - late / 2),
      sharpeRatio: 0.5 + late / 40,
    });
  });
}

describe('coach coherence · periodReturns path', () => {
  it('matrix → explore preserves stamped periodReturns', () => {
    const pr = { early: 1, mid: 2, late: 12 };
    const matrix: StrategyMatrixRow[] = [
      {
        rowId: 'preset:sma_crossover',
        kind: 'preset',
        label: 'SMA',
        subtitle: 'Tendencia',
        presetKey: 'sma_crossover',
        status: 'ok',
        runId: 'r1',
        totalReturnPct: 20,
        excessReturnPct: 5,
        periodReturns: pr,
      },
    ];
    const explore = matrixRowsToExploreRows(matrix);
    expect(explore[0]?.periodReturns).toEqual(pr);
    const top = rankTechnicalRecommendations(explore, baseCtx('IBE'));
    expect(top[0]?.usedSoftFallback).toBe(false);
    expect(top[0]?.lateReturnPct).toBeCloseTo(12, 0);
  });

  it('soft fallback loses to stamped thirds when comparable', () => {
    const stamped = row({
      strategyType: 'rsi_mean_reversion',
      label: 'RSI stamped',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
      periodReturns: { early: 2, mid: 3, late: 18 },
      excessReturnPct: 4,
      totalReturnPct: 25,
    });
    const soft = row({
      strategyType: 'sma_crossover',
      label: 'SMA soft',
      excessReturnPct: 8,
      totalReturnPct: 40,
      // no periodReturns, no equity
    });
    const top = rankTechnicalRecommendations([soft, stamped], baseCtx('SAN'));
    expect(top[0]?.row.strategyType).toBe('rsi_mean_reversion');
    expect(top[0]?.usedSoftFallback).toBe(false);
    expect(top.find((t) => t.row.strategyType === 'sma_crossover')?.usedSoftFallback).toBe(true);
  });
});

describe('coach coherence · diversify + quality', () => {
  it('dedupes duplicate strategyType before ranking', () => {
    const a = row({
      strategyType: 'sma_crossover',
      label: 'SMA genérica',
      periodReturns: { early: 1, mid: 1, late: 5 },
      excessReturnPct: 1,
    });
    const b = row({
      strategyType: 'sma_crossover',
      label: 'SAN · SMA guardada',
      periodReturns: { early: 1, mid: 2, late: 20 },
      excessReturnPct: 10,
    });
    const deduped = dedupeExploreRowsByStrategyType([a, b]);
    expect(deduped).toHaveLength(1);
    expect(deduped[0]?.label).toContain('guardada');
  });

  it('TOP-3 diversifies categories when possible', () => {
    const rows = catalogForInstrument('ACS', {
      sma_crossover: 22,
      golden_cross: 20,
      ma_stack_bullish: 19,
      rsi_mean_reversion: 8,
      stoch_oversold: 6,
      macd_signal_cross: 10,
      donchian_breakout: 18,
    });
    const top = rankTechnicalRecommendations(rows, baseCtx('ACS'), {
      limit: 3,
      diversifyCategories: true,
    });
    expect(top).toHaveLength(3);
    const cats = new Set(top.map((t) => t.row.category));
    expect(cats.size).toBeGreaterThanOrEqual(2);
    // Should not be 3 trend clones when mean_reversion/momentum exist
    expect(top.filter((t) => t.row.category === 'trend').length).toBeLessThanOrEqual(2);
  });

  it('does not crown severely bad late+excess when better options exist', () => {
    const bad = row({
      strategyType: 'golden_cross',
      label: 'Bad late',
      periodReturns: { early: 80, mid: 10, late: -35 },
      excessReturnPct: -30,
      totalReturnPct: 55,
      maxDrawdownPct: 40,
    });
    const good = row({
      strategyType: 'rsi_mean_reversion',
      label: 'Good recent',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
      periodReturns: { early: 2, mid: 4, late: 14 },
      excessReturnPct: 5,
      totalReturnPct: 18,
      maxDrawdownPct: 10,
    });
    const mid = row({
      strategyType: 'macd_signal_cross',
      label: 'Mid',
      category: 'momentum',
      categoryLabel: 'Momentum',
      periodReturns: { early: 3, mid: 3, late: 9 },
      excessReturnPct: 2,
      totalReturnPct: 14,
    });
    const top = rankTechnicalRecommendations([bad, good, mid], baseCtx('TEF'));
    expect(top[0]?.row.strategyType).not.toBe('golden_cross');
    expect(top.find((t) => t.row.strategyType === 'golden_cross')?.qualityFlagged).toBe(true);
  });

  it('pickDiversifiedTop fills after category pass', () => {
    const ranked = [
      { row: row({ strategyType: 'sma_crossover', label: 'A', category: 'trend', categoryLabel: 'T' }) },
      { row: row({ strategyType: 'golden_cross', label: 'B', category: 'trend', categoryLabel: 'T' }) },
      {
        row: row({
          strategyType: 'rsi_mean_reversion',
          label: 'C',
          category: 'mean_reversion',
          categoryLabel: 'R',
        }),
      },
    ];
    const picked = pickDiversifiedTop(ranked, 3);
    expect(picked.map((p) => p.row.strategyType)).toEqual([
      'sma_crossover',
      'rsi_mean_reversion',
      'golden_cross',
    ]);
  });
});

describe('coach coherence · multi-instrument battery', () => {
  const INSTRUMENTS = [
    {
      symbol: 'ACS',
      late: {
        sma_crossover: 25,
        golden_cross: 5,
        ma_stack_bullish: 4,
        rsi_mean_reversion: 3,
        stoch_oversold: 2,
        macd_signal_cross: 12,
        donchian_breakout: 6,
      },
    },
    {
      symbol: 'TEF',
      late: {
        sma_crossover: 2,
        golden_cross: 3,
        ma_stack_bullish: 1,
        rsi_mean_reversion: 22,
        stoch_oversold: 18,
        macd_signal_cross: 4,
        donchian_breakout: 5,
      },
    },
    {
      symbol: 'IBE',
      late: {
        sma_crossover: 6,
        golden_cross: 7,
        ma_stack_bullish: 5,
        rsi_mean_reversion: 4,
        stoch_oversold: 3,
        macd_signal_cross: 24,
        donchian_breakout: 8,
      },
    },
    {
      symbol: 'SAN',
      late: {
        sma_crossover: 8,
        golden_cross: 20,
        ma_stack_bullish: 15,
        rsi_mean_reversion: -5,
        stoch_oversold: -8,
        macd_signal_cross: 6,
        donchian_breakout: 18,
      },
    },
    {
      symbol: 'ITX',
      late: {
        sma_crossover: 10,
        golden_cross: 11,
        ma_stack_bullish: 9,
        rsi_mean_reversion: 12,
        stoch_oversold: 8,
        macd_signal_cross: 11,
        donchian_breakout: 13,
      },
    },
  ] as const;

  it('TOP #1 changes with instrument late-window profile (not sticky alphabetical)', () => {
    const tops = INSTRUMENTS.map((inst) => {
      const rows = catalogForInstrument(inst.symbol, inst.late);
      const top = rankTechnicalRecommendations(rows, baseCtx(inst.symbol), 3);
      return { symbol: inst.symbol, types: top.map((t) => t.row.strategyType) };
    });

    // Sanity: all have 3
    for (const t of tops) expect(t.types).toHaveLength(3);

    const firsts = new Set(tops.map((t) => t.types[0]));
    expect(firsts.size).toBeGreaterThanOrEqual(3);

    // ACS should prefer trend/momentum with strong late SMA
    expect(tops.find((t) => t.symbol === 'ACS')?.types[0]).toBe('sma_crossover');
    // TEF mean-reversion regime
    expect(['rsi_mean_reversion', 'stoch_oversold']).toContain(
      tops.find((t) => t.symbol === 'TEF')?.types[0],
    );
    // IBE momentum
    expect(tops.find((t) => t.symbol === 'IBE')?.types[0]).toBe('macd_signal_cross');
  });

  it('never recommends soft-fallback-only TOP when all rows have periodReturns', () => {
    for (const inst of INSTRUMENTS) {
      const rows = catalogForInstrument(inst.symbol, inst.late);
      const top = rankTechnicalRecommendations(rows, baseCtx(inst.symbol), 3);
      for (const rec of top) {
        expect(rec.usedSoftFallback).toBe(false);
        expect(rec.lateReturnPct).not.toBeNull();
      }
    }
  });

  it('Guardar TOP-3 yields 3 unique strategyTypes (no collapse to 1)', async () => {
    const rows = catalogForInstrument('ACS', INSTRUMENTS[0]!.late);
    const recs = rankTechnicalRecommendations(rows, baseCtx('ACS'), 3);
    expect(recs).toHaveLength(3);

    let created = 0;
    const slots = await buildCoachTopSlots({
      recommendations: recs,
      symbol: 'ACS',
      timeframe: '1d',
      lookup: {
        existing: [] as StrategyDefinitionSummaryDto[],
        createFromPreset: async (input) => {
          created += 1;
          return {
            id: `def-${input.presetKey}`,
            name: input.name,
            presetKey: input.presetKey as StrategyDefinitionSummaryDto['presetKey'],
            origin: 'preset',
            timeframe: '1d',
            kind: 'rules',
            updatedAt: new Date().toISOString(),
            createdAt: new Date().toISOString(),
          };
        },
      },
    });

    expect(slots).toHaveLength(3);
    expect(created).toBe(3);
    expect(new Set(slots.map((s) => s.strategyType)).size).toBe(3);
    expect(new Set(slots.map((s) => s.strategyDefinitionId)).size).toBe(3);
  });
});
