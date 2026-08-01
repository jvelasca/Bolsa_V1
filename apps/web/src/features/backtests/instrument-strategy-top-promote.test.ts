import { describe, expect, it } from 'vitest';
import {
  buildLabPromotionUpsert,
  buildLabPromotionUpsertMany,
  canPromoteTopFromLabEvidence,
  dedupeInstrumentTopSlots,
} from '@/features/backtests/instrument-strategy-top-promote';
import type { InstrumentStrategyTopV1 } from '@bolsa/shared';

const existing: InstrumentStrategyTopV1 = {
  id: 'ist_1',
  instrumentId: 'inst_a',
  symbol: 'SAN',
  timeframe: '1d',
  status: 'semifinal',
  version: 2,
  evidenceLevel: 'in_sample_only',
  slots: [
    {
      rank: 1,
      label: 'SMA 20/50',
      strategyType: 'sma_crossover',
      stars: 3,
      score: 62,
      source: 'coach',
      runId: 'run-sma-old',
    },
    {
      rank: 2,
      label: 'RSI 14',
      strategyType: 'rsi_mean_reversion',
      stars: 2,
      score: 55,
      source: 'coach',
      runId: 'run-rsi-old',
    },
    {
      rank: 3,
      label: 'MACD',
      strategyType: 'macd_signal_cross',
      stars: 2,
      score: 50,
      source: 'coach',
      runId: 'run-macd-old',
    },
  ],
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};

describe('buildLabPromotionUpsertMany', () => {
  it('promotes several lab winners ahead of prior coach slots', () => {
    const body = buildLabPromotionUpsertMany({
      existing,
      instrumentId: 'inst_a',
      timeframe: '1d',
      promoted: [
        {
          label: 'SMA lab',
          strategyDefinitionId: 'str_sma',
          strategyType: 'sma_crossover',
          score: 80,
          stars: 4.5,
          runId: 'run-sma',
        },
        {
          label: 'RSI lab',
          strategyDefinitionId: 'str_rsi',
          strategyType: 'rsi_mean_reversion',
          score: 70,
          stars: 3.5,
          runId: 'run-rsi',
        },
      ],
    });
    expect(body.evidenceLevel).toBe('lab_validated');
    expect(body.slots[0]).toMatchObject({
      label: 'SMA lab',
      stars: 4.5,
      source: 'optimized',
      runId: 'run-sma',
    });
    expect(body.slots[1]).toMatchObject({ label: 'RSI lab', stars: 3.5, runId: 'run-rsi' });
    expect(body.coachFacts).toMatchObject({ promotionSource: 'lab_adopt_many', promotedCount: 2 });
  });

  it('rejects lab promotion without runId', () => {
    expect(() =>
      buildLabPromotionUpsertMany({
        existing,
        instrumentId: 'inst_a',
        timeframe: '1d',
        promoted: [
          {
            label: 'SMA lab',
            strategyDefinitionId: 'str_sma',
            strategyType: 'sma_crossover',
            score: 80,
          },
        ],
      }),
    ).toThrow(/runId/i);
  });
});

describe('buildLabPromotionUpsert', () => {
  it('promotes optimized candidate to #1 and drops prior of same strategyType', () => {
    const body = buildLabPromotionUpsert({
      existing,
      instrumentId: 'inst_a',
      timeframe: '1d',
      promoted: {
        label: 'SMA 12/34 (lab)',
        strategyDefinitionId: 'str_opt',
        strategyType: 'sma_crossover',
        score: 78,
        totalReturnPct: 12,
        runId: 'run-opt',
      },
      labFacts: { kind: 'holdout', oosScore: 4.2 },
    });

    expect(body.status).toBe('active');
    expect(body.evidenceLevel).toBe('lab_validated');
    expect(body.slots).toHaveLength(3);
    expect(body.slots[0]).toMatchObject({
      rank: 1,
      strategyDefinitionId: 'str_opt',
      source: 'optimized',
      stars: 4,
      runId: 'run-opt',
    });
    // Coach SMA 20/50 (same type) is replaced, not duplicated as #2
    expect(body.slots.map((s) => s.strategyType)).toEqual([
      'sma_crossover',
      'rsi_mean_reversion',
      'macd_signal_cross',
    ]);
    expect(body.slots[1]?.label).toBe('RSI 14');
    expect(body.slots[2]?.label).toBe('MACD');
    expect(body.coachFacts).toMatchObject({ kind: 'holdout', promotionSource: 'lab_adopt' });
  });

  it('creates fresh TOP when none exists', () => {
    const body = buildLabPromotionUpsert({
      existing: null,
      instrumentId: 'inst_b',
      symbol: 'BBVA',
      timeframe: '1d',
      promoted: {
        label: 'Mejor lab',
        strategyDefinitionId: 'str_x',
        score: 40,
        runId: 'run-x',
      },
    });
    expect(body.slots).toHaveLength(1);
    expect(body.slots[0]?.rank).toBe(1);
    expect(body.slots[0]?.runId).toBe('run-x');
    expect(body.symbol).toBe('BBVA');
  });
});

describe('dedupeInstrumentTopSlots', () => {
  it('keeps first of duplicate strategyType / definitionId', () => {
    const slots = dedupeInstrumentTopSlots([
      {
        rank: 1,
        label: 'A',
        strategyType: 'sma_crossover',
        strategyDefinitionId: 's1',
        stars: 3,
        score: 60,
        source: 'coach',
      },
      {
        rank: 2,
        label: 'A clone',
        strategyType: 'sma_crossover',
        strategyDefinitionId: 's2',
        stars: 2,
        score: 50,
        source: 'coach',
      },
      {
        rank: 3,
        label: 'B',
        strategyType: 'rsi_mean_reversion',
        strategyDefinitionId: 's3',
        stars: 2,
        score: 48,
        source: 'coach',
      },
      {
        rank: 3,
        label: 'B again',
        strategyType: 'rsi_mean_reversion',
        strategyDefinitionId: 's3',
        stars: 2,
        score: 48,
        source: 'coach',
      },
    ]);
    expect(slots).toHaveLength(2);
    expect(slots.map((s) => s.label)).toEqual(['A', 'B']);
    expect(slots.map((s) => s.rank)).toEqual([1, 2]);
  });
});

describe('canPromoteTopFromLabEvidence', () => {
  it('allows holdout / wf / cpcv only', () => {
    expect(canPromoteTopFromLabEvidence('holdout')).toBe(true);
    expect(canPromoteTopFromLabEvidence('walkforward')).toBe(true);
    expect(canPromoteTopFromLabEvidence('cpcv')).toBe(true);
    expect(canPromoteTopFromLabEvidence('none')).toBe(false);
    expect(canPromoteTopFromLabEvidence(undefined)).toBe(false);
  });
});
