import { describe, expect, it } from 'vitest';
import {
  buildDeepTechnicalCoachNote,
  inferRegimeShift,
  rankTechnicalRecommendations,
  resolveCoachScoreWeights,
  scoreTechnicalFit,
  scoreToStars,
} from '@/features/backtests/backtest-deep-coach';
import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';
import { buildOptimizeBeforeAfter } from '@/features/backtests/backtest-optimize-delta';
import type { OptimizeSeed } from '@/features/backtests/backtest-optimize-seed';
import type { OptimizeSmaGridResultDto } from '@bolsa/shared';

function row(partial: Partial<ExplorePresetRow> & Pick<ExplorePresetRow, 'strategyType' | 'label'>): ExplorePresetRow {
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

describe('deep technical coach · future stars', () => {
  it('maps scores to 1–5 stars (half steps) with evidence ceiling', () => {
    expect(scoreToStars(90).stars).toBe(5);
    expect(scoreToStars(78).stars).toBe(4.5);
    expect(scoreToStars(70).stars).toBe(4);
    expect(scoreToStars(55).stars).toBe(3);
    expect(scoreToStars(48).stars).toBe(2.5);
    expect(scoreToStars(90, { ceiling: 3 }).stars).toBe(3);
    expect(scoreToStars(90, { ceiling: 3 }).capped).toBe(true);
    expect(scoreToStars(78, { ceiling: 3 }).stars).toBe(3);
    expect(scoreToStars(78, { ceiling: 3 }).capped).toBe(true);
  });

  it('resolveCoachScoreWeights reescala el resto al cambiar peso reciente', () => {
    const d = resolveCoachScoreWeights(0.42);
    expect(d.future).toBeCloseTo(0.42, 5);
    expect(d.future + d.risk + d.edge + d.category + d.activity).toBeCloseTo(1, 5);
    const heavy = resolveCoachScoreWeights(0.55);
    expect(heavy.future).toBe(0.55);
    expect(heavy.risk).toBeLessThan(d.risk);
    expect(heavy.future + heavy.risk + heavy.edge + heavy.category + heavy.activity).toBeCloseTo(
      1,
      5,
    );
  });

  it('higher futureWeight increases score for late-strong rows', () => {
    const lateStrong = row({
      strategyType: 'sma_crossover',
      label: 'Late',
      excessReturnPct: 5,
      periodReturns: { early: -5, mid: 0, late: 25 },
    });
    const ctxBase = {
      symbol: 'X',
      timeframe: '1d' as const,
      horizon: 'swing' as const,
      riskTolerance: 'moderate' as const,
    };
    const low = scoreTechnicalFit(lateStrong, { ...ctxBase, futureWeight: 0.3 });
    const high = scoreTechnicalFit(lateStrong, { ...ctxBase, futureWeight: 0.55 });
    expect(high).toBeGreaterThanOrEqual(low);
  });

  it('ACS-like: Golden Cross can lead on total return while coach prefers SMA 20/50 on late equity', () => {
    const golden = row({
      strategyType: 'golden_cross',
      label: 'Golden cross SMA 50/200',
      runId: 'run-gc',
      totalReturnPct: 340,
      excessReturnPct: 280,
      maxDrawdownPct: 35,
      tradeCount: 8,
      sharpeRatio: 0.9,
    });
    const sma2050 = row({
      strategyType: 'sma_crossover',
      label: 'Cruce SMA 20/50',
      runId: 'run-sma',
      totalReturnPct: 120,
      excessReturnPct: 60,
      maxDrawdownPct: 18,
      tradeCount: 40,
      sharpeRatio: 1.1,
    });
    const stack = row({
      strategyType: 'ma_stack_bullish',
      label: 'Apilamiento alcista MA',
      runId: 'run-stack',
      totalReturnPct: 90,
      excessReturnPct: 40,
      maxDrawdownPct: 22,
      tradeCount: 25,
      sharpeRatio: 0.95,
    });
    // Golden: strong early, flat/weak late. SMA 20/50: modest early, strong recent.
    const equityByRunId = {
      'run-gc': [
        { timestamp: '1', equity: 100 },
        { timestamp: '2', equity: 180 },
        { timestamp: '3', equity: 280 },
        { timestamp: '4', equity: 360 },
        { timestamp: '5', equity: 400 },
        { timestamp: '6', equity: 410 },
        { timestamp: '7', equity: 405 },
        { timestamp: '8', equity: 400 },
        { timestamp: '9', equity: 395 },
      ],
      'run-sma': [
        { timestamp: '1', equity: 100 },
        { timestamp: '2', equity: 105 },
        { timestamp: '3', equity: 108 },
        { timestamp: '4', equity: 112 },
        { timestamp: '5', equity: 130 },
        { timestamp: '6', equity: 155 },
        { timestamp: '7', equity: 185 },
        { timestamp: '8', equity: 210 },
        { timestamp: '9', equity: 240 },
      ],
      'run-stack': [
        { timestamp: '1', equity: 100 },
        { timestamp: '2', equity: 110 },
        { timestamp: '3', equity: 120 },
        { timestamp: '4', equity: 125 },
        { timestamp: '5', equity: 140 },
        { timestamp: '6', equity: 155 },
        { timestamp: '7', equity: 165 },
        { timestamp: '8', equity: 175 },
        { timestamp: '9', equity: 185 },
      ],
    };
    const ctx = {
      symbol: 'ACS',
      timeframe: '1d',
      horizon: 'swing' as const,
      riskTolerance: 'moderate' as const,
      equityByRunId,
    };

    // Matrix-style ranking by total return → Golden wins
    const byReturn = [golden, sma2050, stack].sort(
      (a, b) => (b.totalReturnPct ?? 0) - (a.totalReturnPct ?? 0),
    );
    expect(byReturn[0]?.strategyType).toBe('golden_cross');

    // Coach ranking by future-fit score → SMA 20/50 first (not Golden despite +340%)
    const coach = rankTechnicalRecommendations([golden, sma2050, stack], ctx, 3);
    expect(coach[0]?.row.strategyType).toBe('sma_crossover');
    expect(coach.map((c) => c.row.strategyType)).toContain('golden_cross');
    expect(coach[0]?.row.totalReturnPct).toBeLessThan(golden.totalReturnPct!);
  });

  it('prefers late-half winner over early historical champion', () => {
    const oldChamp = row({
      strategyType: 'sma_crossover',
      label: 'SMA old',
      runId: 'run-old',
      totalReturnPct: 80,
      excessReturnPct: 40,
      maxDrawdownPct: 20,
    });
    const recent = row({
      strategyType: 'stoch_oversold',
      label: 'Stoch recent',
      runId: 'run-new',
      totalReturnPct: 15,
      excessReturnPct: 3,
      maxDrawdownPct: 10,
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
      sharpeRatio: 1.0,
    });
    const equityByRunId = {
      'run-old': [
        { timestamp: 'a', equity: 100 },
        { timestamp: 'b', equity: 140 },
        { timestamp: 'c', equity: 160 },
        { timestamp: 'd', equity: 170 },
        { timestamp: 'e', equity: 165 },
        { timestamp: 'f', equity: 160 },
        { timestamp: 'g', equity: 155 },
        { timestamp: 'h', equity: 150 },
      ],
      'run-new': [
        { timestamp: 'a', equity: 100 },
        { timestamp: 'b', equity: 101 },
        { timestamp: 'c', equity: 100 },
        { timestamp: 'd', equity: 99 },
        { timestamp: 'e', equity: 110 },
        { timestamp: 'f', equity: 125 },
        { timestamp: 'g', equity: 140 },
        { timestamp: 'h', equity: 155 },
      ],
    };
    const ctx = {
      symbol: 'TEF',
      timeframe: '1d',
      horizon: 'swing' as const,
      riskTolerance: 'moderate' as const,
      equityByRunId,
    };
    expect(scoreTechnicalFit(recent, ctx)).toBeGreaterThan(scoreTechnicalFit(oldChamp, ctx));
    const top = rankTechnicalRecommendations([oldChamp, recent], ctx, 3);
    expect(top[0]?.row.strategyType).toBe('stoch_oversold');
    expect(top[0]?.stars).toBeGreaterThanOrEqual(3);
  });

  it('BBVA-like: dead-cat bounce (early crash + mild late) must not beat solid winners', () => {
    const bounce = row({
      strategyType: 'vwap_reclaim',
      label: 'VWAP reclaim (rebote)',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
      // Desplome temprano + rebote leve → antes la “aceleración” lo coronaba
      periodReturns: { early: -55, mid: -25, late: 8 },
      totalReturnPct: -40,
      excessReturnPct: -35,
      maxDrawdownPct: 8, // DD bajo (casi cash) inflaba riskFit
      tradeCount: 4,
      barCount: 800,
      sharpeRatio: -0.2,
    });
    const goodTrend = row({
      strategyType: 'sma_crossover',
      label: 'SMA 20/50',
      periodReturns: { early: 8, mid: 10, late: 16 },
      totalReturnPct: 45,
      excessReturnPct: 12,
      maxDrawdownPct: 18,
      tradeCount: 35,
      barCount: 800,
      sharpeRatio: 1.0,
    });
    const goodMom = row({
      strategyType: 'macd_signal_cross',
      label: 'MACD',
      category: 'momentum',
      categoryLabel: 'Momentum',
      periodReturns: { early: 5, mid: 8, late: 14 },
      totalReturnPct: 38,
      excessReturnPct: 9,
      maxDrawdownPct: 16,
      tradeCount: 40,
      barCount: 800,
      sharpeRatio: 0.95,
    });
    const top = rankTechnicalRecommendations([bounce, goodTrend, goodMom], {
      symbol: 'BBVA',
      timeframe: '1d',
      horizon: 'swing',
      riskTolerance: 'moderate',
    });
    expect(top[0]?.row.strategyType).not.toBe('vwap_reclaim');
    expect(['sma_crossover', 'macd_signal_cross']).toContain(top[0]?.row.strategyType);
    // Con solo 2 candidatas sólidas, la 3ª puede rellenar; lo crítico es que #1 no sea el rebote.
    expect(top[0]?.row.excessReturnPct).toBeGreaterThan(0);
  });

  it('detects regime shift from equity halves', () => {
    const a = row({ strategyType: 'sma_crossover', label: 'SMA', runId: 'run-a' });
    const b = row({
      strategyType: 'stoch_oversold',
      label: 'Stoch',
      runId: 'run-b',
      category: 'mean_reversion',
      categoryLabel: 'Reversión',
    });
    const equityByRunId = {
      'run-a': [
        { timestamp: '2020-01-01', equity: 100 },
        { timestamp: '2020-06-01', equity: 130 },
        { timestamp: '2021-01-01', equity: 125 },
        { timestamp: '2021-06-01', equity: 120 },
        { timestamp: '2022-01-01', equity: 118 },
        { timestamp: '2022-06-01', equity: 115 },
        { timestamp: '2023-01-01', equity: 112 },
        { timestamp: '2023-06-01', equity: 110 },
      ],
      'run-b': [
        { timestamp: '2020-01-01', equity: 100 },
        { timestamp: '2020-06-01', equity: 102 },
        { timestamp: '2021-01-01', equity: 101 },
        { timestamp: '2021-06-01', equity: 100 },
        { timestamp: '2022-01-01', equity: 110 },
        { timestamp: '2022-06-01', equity: 125 },
        { timestamp: '2023-01-01', equity: 140 },
        { timestamp: '2023-06-01', equity: 155 },
      ],
    };
    const regime = inferRegimeShift([a, b], equityByRunId);
    expect(regime?.shifted).toBe(true);
    expect(regime?.earlyBest?.strategyType).toBe('sma_crossover');
    expect(regime?.lateBest?.strategyType).toBe('stoch_oversold');
  });

  it('builds note with top-3 stars and outlook', () => {
    const rows = [
      row({ strategyType: 'sma_crossover', label: 'SMA', totalReturnPct: 30, maxDrawdownPct: 25 }),
      row({
        strategyType: 'rsi_mean_reversion',
        label: 'RSI',
        totalReturnPct: 8,
        maxDrawdownPct: 9,
        category: 'mean_reversion',
        categoryLabel: 'Reversión',
      }),
      row({
        strategyType: 'macd_signal_cross',
        label: 'MACD',
        totalReturnPct: 15,
        maxDrawdownPct: 14,
        category: 'momentum',
        categoryLabel: 'Momentum',
      }),
    ];
    const note = buildDeepTechnicalCoachNote(rows, {
      symbol: 'SAN',
      timeframe: '1d',
      horizon: 'swing',
      riskTolerance: 'moderate',
    });
    expect(note.recommendations.length).toBe(3);
    expect(note.recommendations[0]?.stars).toBeGreaterThanOrEqual(1);
    expect(note.outlook.length).toBeGreaterThan(0);
    expect(note.headline).toMatch(/SAN/);
  });
  it('uses periodReturns on the row even without equity cache', () => {
    const strongLate = row({
      strategyType: 'sma_crossover',
      label: 'SMA',
      runId: 'a',
      totalReturnPct: 50,
      periodReturns: { early: -5, mid: 2, late: 25 },
    });
    const strongEarly = row({
      strategyType: 'golden_cross',
      label: 'GC',
      runId: 'b',
      totalReturnPct: 200,
      periodReturns: { early: 80, mid: 10, late: -8 },
    });
    const ranked = rankTechnicalRecommendations([strongEarly, strongLate], {
      symbol: 'ACS',
      timeframe: '1d',
    });
    expect(ranked[0]?.row.strategyType).toBe('sma_crossover');
  });
});

describe('optimize before/after', () => {
  it('builds snapshot from seed + result', () => {
    const seed: OptimizeSeed = {
      instrumentId: 'i1',
      symbol: 'SAN',
      strategyType: 'sma_crossover',
      strategyLabel: 'Cruce SMA',
      initialCash: 10_000,
      timeframe: '1d',
      source: 'explore_best',
      anchorReturnPct: 10,
      anchorMaxDrawdownPct: 15,
      anchorTradeCount: 20,
      anchorScore: 5,
      anchorFast: 20,
      anchorSlow: 50,
    };
    const result: OptimizeSmaGridResultDto = {
      instrumentId: 'i1',
      barCount: 500,
      engine: 'h0',
      strategyFamily: 'sma_crossover',
      baseline: {
        fastPeriod: 20,
        slowPeriod: 50,
        totalReturnPct: 10,
        maxDrawdownPct: 15,
        tradeCount: 20,
        score: 5,
      },
      trials: [
        {
          fastPeriod: 15,
          slowPeriod: 40,
          totalReturnPct: 18,
          maxDrawdownPct: 12,
          tradeCount: 28,
          score: 12,
        },
      ],
    };
    const snap = buildOptimizeBeforeAfter(seed, result);
    expect(snap?.improved).toBe(true);
    expect(snap?.deltaReturnPct).toBeCloseTo(8);
    expect(snap?.after.paramsLabel).toMatch(/15/);
  });
});
