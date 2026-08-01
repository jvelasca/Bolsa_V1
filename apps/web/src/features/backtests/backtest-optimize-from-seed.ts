/**
 * Build default optimize job request(s) from an OptimizeSeed (Coach → Lab).
 */

import type { OptimizeSmaGridRequestDto, OptimizeStrategyFamily } from '@bolsa/shared';
import {
  optimizeFamilyForStrategy,
  type OptimizeSeed,
} from '@/features/backtests/backtest-optimize-seed';
import {
  defaultMacdSpace,
  defaultRsiSpace,
  expandRange,
  spaceFromAnchor,
  type OptimizeSearchSpace,
} from '@/features/backtests/backtest-optimize-space';

function spaceForSeed(seed: OptimizeSeed, family: OptimizeStrategyFamily): OptimizeSearchSpace {
  if (family === 'sma_crossover') {
    if (seed.anchorFast != null && seed.anchorSlow != null) {
      return spaceFromAnchor(seed.anchorFast, seed.anchorSlow);
    }
    return spaceFromAnchor(20, 50);
  }
  if (family === 'rsi_mean_reversion') {
    const base = defaultRsiSpace();
    if (seed.anchorPeriod != null) {
      return {
        ...base,
        period: {
          min: Math.max(2, seed.anchorPeriod - 4),
          max: seed.anchorPeriod + 6,
          step: 2,
        },
      };
    }
    return base;
  }
  return defaultMacdSpace();
}

function attachSpace(
  base: OptimizeSmaGridRequestDto,
  space: OptimizeSearchSpace,
): OptimizeSmaGridRequestDto {
  if (space.family === 'sma_crossover') {
    return {
      ...base,
      fastPeriods: expandRange(space.fast),
      slowPeriods: expandRange(space.slow),
    };
  }
  if (space.family === 'rsi_mean_reversion') {
    return {
      ...base,
      periods: expandRange(space.period),
      oversoldLevels: expandRange(space.oversold, 5),
      overboughtLevels: expandRange(space.overbought, 50),
    };
  }
  // MACD: API defaults triples when omitted.
  return base;
}

/**
 * Jobs a encolar al «Pasar al Lab».
 * SMA/proxies: **H0 + Optuna** (mismo criterio que Play por defecto) → el panel une candidatos.
 * RSI/MACD: solo grid H0.
 */
export function buildOptimizeRequestsFromSeed(
  seed: OptimizeSeed,
): OptimizeSmaGridRequestDto[] {
  const family = optimizeFamilyForStrategy(seed.strategyType);
  if (!family) return [];

  const space = spaceForSeed(seed, family);
  const hint = seed.validationHint;
  const shared: OptimizeSmaGridRequestDto = {
    instrumentId: seed.instrumentId,
    strategyFamily: family,
    initialCash: seed.initialCash,
    timeframe: seed.timeframe,
    ...(seed.barLimit != null && seed.barLimit > 0 ? { barLimit: seed.barLimit } : {}),
  };

  if (hint?.mode === 'walkforward' && hint.walkForwardFolds) {
    shared.walkForwardFolds = hint.walkForwardFolds;
  } else if (hint?.mode === 'holdout' && hint.oosPct) {
    shared.oosPct = hint.oosPct;
  } else if (hint?.mode !== 'none') {
    if ((seed.barLimit ?? 0) >= 250) shared.oosPct = 0.2;
  }

  // WF/CPCV en seed → solo H0 (motores avanzados no aplican en WF v1).
  if (shared.walkForwardFolds != null || shared.cpcvGroups != null) {
    return [attachSpace({ ...shared, engine: 'h0', maxTrials: 80 }, space)];
  }

  if (family === 'sma_crossover') {
    return [
      attachSpace({ ...shared, engine: 'h0', maxTrials: 200 }, space),
      attachSpace({ ...shared, engine: 'optuna', maxTrials: 100 }, space),
    ];
  }

  return [attachSpace({ ...shared, engine: 'h0', maxTrials: 80 }, space)];
}

/** Primer job (compat). Preferir `buildOptimizeRequestsFromSeed` en Coach→Lab. */
export function buildOptimizeRequestFromSeed(
  seed: OptimizeSeed,
): OptimizeSmaGridRequestDto | null {
  return buildOptimizeRequestsFromSeed(seed)[0] ?? null;
}

/** True if Mejor is ≥ ancla under the ranking in use (OOS preferred). */
export function isLabCandidateAtLeastAnchor(opts: {
  improved: boolean;
  /** Explicit equal-or-better when delta is available. */
  deltaScore?: number | null;
  deltaOosScore?: number | null;
  rankedByOos?: boolean;
}): boolean {
  if (opts.rankedByOos && opts.deltaOosScore != null) {
    return opts.deltaOosScore >= 0;
  }
  if (opts.deltaScore != null) return opts.deltaScore >= 0;
  return opts.improved;
}
