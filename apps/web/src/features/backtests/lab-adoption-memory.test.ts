/**
 * Tests — CORE B v0–v0.1 Lab adoption memory + guided space (meseta/pico).
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  LAB_ADOPTION_MEMORY_KEY,
  buildLabAdoptionFacts,
  clearLabAdoption,
  formatLabAdoptionHint,
  guidedHalfWidthsForPlateau,
  guidedSpaceFromAdoption,
  readLabAdoption,
  rememberLabAdoption,
  shouldApplyGuidedSpace,
} from '@/features/backtests/lab-adoption-memory';
import { plateauAdoptionMetaFromTrials } from '@/features/backtests/backtest-optimize-heatmap';
import type { SmaGridTrialDto } from '@bolsa/shared';

function baseSmaRec(
  plateau?: { isPlateau: boolean; neighborCount: number; closeNeighborCount: number } | null,
) {
  return {
    engine: 'lab-adoption-v1' as const,
    instrumentId: 'i',
    timeframe: '1d',
    family: 'sma_crossover' as const,
    params: { fastPeriod: 20, slowPeriod: 60 },
    paramsLabel: 'SMA 20/60',
    adoptedAt: '2026-07-29T00:00:00.000Z',
    plateau: plateau ?? null,
  };
}

describe('lab-adoption-memory', () => {
  beforeEach(() => {
    localStorage.removeItem(LAB_ADOPTION_MEMORY_KEY);
  });

  it('roundtrips remember / read / clear (incl. plateau)', () => {
    expect(readLabAdoption('inst-1', '1d')).toBeNull();
    const saved = rememberLabAdoption({
      instrumentId: 'inst-1',
      timeframe: '1d',
      family: 'sma_crossover',
      params: { fastPeriod: 15, slowPeriod: 50 },
      paramsLabel: 'SMA 15/50',
      strategyId: 'strat-1',
      oosKind: 'holdout',
      oosScore: 4.2,
      score: 12,
      maxDrawdownPct: 14,
      profileId: 'p1',
      plateau: { isPlateau: true, neighborCount: 4, closeNeighborCount: 3 },
    });
    expect(saved.engine).toBe('lab-adoption-v1');
    const got = readLabAdoption('inst-1', '1d');
    expect(got?.paramsLabel).toBe('SMA 15/50');
    expect(got?.oosKind).toBe('holdout');
    expect(got?.strategyId).toBe('strat-1');
    expect(got?.plateau?.isPlateau).toBe(true);
    expect(formatLabAdoptionHint(got!)).toMatch(/Adopción previa/);
    expect(formatLabAdoptionHint(got!)).toMatch(/holdout/);
    expect(formatLabAdoptionHint(got!)).toMatch(/meseta/);
    expect(buildLabAdoptionFacts(got)?.labAdoption).toMatchObject({
      family: 'sma_crossover',
      paramsLabel: 'SMA 15/50',
      plateau: { isPlateau: true },
    });
    clearLabAdoption('inst-1', '1d');
    expect(readLabAdoption('inst-1', '1d')).toBeNull();
  });

  it('guides SMA / RSI space around last Mejor (v0 widths sin plateau)', () => {
    const sma = guidedSpaceFromAdoption(baseSmaRec());
    expect(sma?.family).toBe('sma_crossover');
    if (sma?.family === 'sma_crossover') {
      expect(sma.fast.min).toBe(15);
      expect(sma.fast.max).toBe(25);
      expect(sma.slow.min).toBe(45);
      expect(sma.slow.max).toBe(75);
    }

    const rsi = guidedSpaceFromAdoption({
      engine: 'lab-adoption-v1',
      instrumentId: 'i',
      timeframe: '1d',
      family: 'rsi_mean_reversion',
      params: { period: 14, oversold: 30, overbought: 70 },
      paramsLabel: 'RSI 14 · 30/70',
      adoptedAt: '2026-07-29T00:00:00.000Z',
    });
    expect(rsi?.family).toBe('rsi_mean_reversion');
    if (rsi?.family === 'rsi_mean_reversion') {
      expect(rsi.period.min).toBe(10);
      expect(rsi.period.max).toBe(18);
      expect(rsi.oversold.min).toBe(25);
      expect(rsi.oversold.max).toBe(35);
    }

    expect(shouldApplyGuidedSpace(baseSmaRec(), 'sma_crossover')).toBe(true);
    expect(shouldApplyGuidedSpace(baseSmaRec(), 'rsi_mean_reversion')).toBe(false);
  });

  it('v0.1: meseta ensancha y pico estrecha el espacio SMA', () => {
    expect(guidedHalfWidthsForPlateau(undefined)).toEqual({
      smaFast: 5,
      smaSlow: 15,
      rsiPeriod: 4,
      rsiBand: 5,
    });
    expect(
      guidedHalfWidthsForPlateau({ isPlateau: true, neighborCount: 4, closeNeighborCount: 3 }),
    ).toMatchObject({ smaFast: 10, smaSlow: 25 });
    expect(
      guidedHalfWidthsForPlateau({ isPlateau: false, neighborCount: 4, closeNeighborCount: 0 }),
    ).toMatchObject({ smaFast: 3, smaSlow: 8 });

    const wide = guidedSpaceFromAdoption(
      baseSmaRec({ isPlateau: true, neighborCount: 4, closeNeighborCount: 3 }),
    );
    const tight = guidedSpaceFromAdoption(
      baseSmaRec({ isPlateau: false, neighborCount: 4, closeNeighborCount: 0 }),
    );
    expect(wide?.family).toBe('sma_crossover');
    expect(tight?.family).toBe('sma_crossover');
    if (wide?.family === 'sma_crossover' && tight?.family === 'sma_crossover') {
      expect(wide.fast.max - wide.fast.min).toBeGreaterThan(tight.fast.max - tight.fast.min);
      expect(wide.slow.max - wide.slow.min).toBeGreaterThan(tight.slow.max - tight.slow.min);
      expect(
        formatLabAdoptionHint(
          baseSmaRec({ isPlateau: false, neighborCount: 2, closeNeighborCount: 0 }),
        ),
      ).toMatch(/pico/);
    }
  });

  it('plateauAdoptionMetaFromTrials mirrors heatmap meseta', () => {
    const trials = [
      { fastPeriod: 10, slowPeriod: 40, score: 5.0 },
      { fastPeriod: 12, slowPeriod: 40, score: 4.95 },
      { fastPeriod: 10, slowPeriod: 45, score: 4.9 },
      { fastPeriod: 20, slowPeriod: 60, score: 1.0 },
    ] as SmaGridTrialDto[];
    const meta = plateauAdoptionMetaFromTrials({
      trials,
      family: 'sma_crossover',
      scoreMode: 'is',
    });
    expect(meta?.isPlateau).toBe(true);
    expect(meta?.closeNeighborCount).toBeGreaterThanOrEqual(2);
  });
});
