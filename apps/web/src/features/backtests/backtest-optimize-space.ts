/** Search-space helpers for SMA / RSI / MACD optimization (min / max / step). */

import type { OptimizeStrategyFamily } from '@bolsa/shared';

export type OptimizeVarRange = {
  min: number;
  max: number;
  step: number;
};

export type SmaSearchSpace = {
  family: 'sma_crossover';
  fast: OptimizeVarRange;
  slow: OptimizeVarRange;
};

export type RsiSearchSpace = {
  family: 'rsi_mean_reversion';
  period: OptimizeVarRange;
  oversold: OptimizeVarRange;
  overbought: OptimizeVarRange;
};

export type MacdSearchSpace = {
  family: 'macd_signal_cross';
  /** Compact neighbourhood around classic 12/26/9 — not a full cube. */
  useDefaultTriples: boolean;
};

export type OptimizeSearchSpace = SmaSearchSpace | RsiSearchSpace | MacdSearchSpace;

export const OPTIMIZE_CRITERION_LABEL =
  'Búsqueda IS: score = retorno % − 0.25 × drawdown máximo %. Con hold-out/WF, el «Mejor» se elige por score OOS (más fiable).';

export const OPTIMIZE_OOS_HELP =
  'Hold-out: optimiza en las primeras barras (IS) y valida el candidato en el tramo final (OOS). Un solo corte.';

export const OPTIMIZE_WF_HELP =
  'Walk-forward expandido: varios pliegues; en cada uno se re-optimiza en train y se valida en el tramo siguiente. Más lento; solo grid H0.';

export const OPTIMIZE_CPCV_HELP =
  'CPCV ligero: combina grupos de test con purge/embargo en barras. Al terminar calcula PBO CSCV lab (S par). Solo grid H0; más lento que WF.';

/** C(n,2) path counts for CPCV groups 4–6. */
export function cpcvPathCount(nGroups: number): number {
  const n = Math.max(4, Math.min(6, Math.round(nGroups) || 5));
  return (n * (n - 1)) / 2;
}

export function clampRange(range: OptimizeVarRange, minFloor = 2): OptimizeVarRange {
  const step = Math.max(1, Math.round(range.step) || 1);
  let min = Math.max(minFloor, Math.round(range.min) || minFloor);
  let max = Math.max(min, Math.round(range.max) || min);
  return { min, max, step };
}

/**
 * Ensancha/estrecha un rango alrededor de su centro (CORE-P soft-bias riesgo).
 * factor &lt; 1 → más estrecho · &gt; 1 → más ancho. Step intacto.
 */
export function scaleVarRange(
  range: OptimizeVarRange,
  factor: number,
  minFloor = 2,
): OptimizeVarRange {
  if (!Number.isFinite(factor) || factor <= 0 || Math.abs(factor - 1) < 1e-9) {
    return clampRange(range, minFloor);
  }
  const mid = (range.min + range.max) / 2;
  const half = Math.max(range.step, ((range.max - range.min) / 2) * factor);
  return clampRange(
    {
      min: mid - half,
      max: mid + half,
      step: range.step,
    },
    minFloor,
  );
}

/** Soft-bias del espacio Lab por factor de riesgo (no cambia familia). */
export function scaleSearchSpace(
  space: OptimizeSearchSpace,
  factor: number,
): OptimizeSearchSpace {
  if (!Number.isFinite(factor) || Math.abs(factor - 1) < 1e-9) return space;
  if (space.family === 'sma_crossover') {
    return {
      family: 'sma_crossover',
      fast: scaleVarRange(space.fast, factor),
      slow: scaleVarRange(space.slow, factor),
    };
  }
  if (space.family === 'rsi_mean_reversion') {
    return {
      family: 'rsi_mean_reversion',
      period: scaleVarRange(space.period, factor),
      oversold: scaleVarRange(space.oversold, factor, 5),
      overbought: scaleVarRange(space.overbought, factor, 50),
    };
  }
  return space;
}

/** Expand min/max/step into a discrete period list. */
export function expandRange(range: OptimizeVarRange, minFloor = 2): number[] {
  const { min, max, step } = clampRange(range, minFloor);
  const values: number[] = [];
  for (let value = min; value <= max; value += step) {
    values.push(value);
  }
  if (values[values.length - 1] !== max) values.push(max);
  return [...new Set(values)].sort((a, b) => a - b);
}

export function countValidCombinations(space: OptimizeSearchSpace, maxTrials = 200): number {
  if (space.family === 'sma_crossover') {
    const fast = expandRange(space.fast);
    const slow = expandRange(space.slow);
    let count = 0;
    for (const f of fast) {
      for (const s of slow) {
        if (f >= s) continue;
        count += 1;
        if (count >= maxTrials) return maxTrials;
      }
    }
    return Math.max(1, count);
  }
  if (space.family === 'rsi_mean_reversion') {
    const periods = expandRange(space.period);
    const os = expandRange(space.oversold, 5);
    const ob = expandRange(space.overbought, 50);
    let count = 0;
    for (const _p of periods) {
      for (const o of os) {
        for (const b of ob) {
          if (o >= b) continue;
          count += 1;
          if (count >= maxTrials) return maxTrials;
        }
      }
    }
    return Math.max(1, count);
  }
  // MACD default neighbourhood ≈ 25
  return Math.min(25, maxTrials);
}

export function spaceFromPeriodLists(fastCsv: string, slowCsv: string): SmaSearchSpace {
  const parse = (raw: string) =>
    raw
      .split(/[,;\s]+/)
      .map((part) => Number.parseInt(part.trim(), 10))
      .filter((value) => Number.isFinite(value) && value >= 2);
  const fast = parse(fastCsv);
  const slow = parse(slowCsv);
  const fastMin = fast.length ? Math.min(...fast) : 10;
  const fastMax = fast.length ? Math.max(...fast) : 30;
  const slowMin = slow.length ? Math.min(...slow) : 40;
  const slowMax = slow.length ? Math.max(...slow) : 100;
  const fastStep =
    fast.length >= 2
      ? Math.max(1, Math.round((fastMax - fastMin) / Math.max(1, fast.length - 1)))
      : 5;
  const slowStep =
    slow.length >= 2
      ? Math.max(1, Math.round((slowMax - slowMin) / Math.max(1, slow.length - 1)))
      : 10;
  return {
    family: 'sma_crossover',
    fast: { min: fastMin, max: fastMax, step: fastStep },
    slow: { min: slowMin, max: slowMax, step: slowStep },
  };
}

export function spaceFromAnchor(anchorFast: number, anchorSlow: number): SmaSearchSpace {
  return {
    family: 'sma_crossover',
    fast: {
      min: Math.max(2, anchorFast - 10),
      max: anchorFast + 10,
      step: 5,
    },
    slow: {
      min: Math.max(anchorFast + 5, anchorSlow - 20),
      max: anchorSlow + 30,
      step: 10,
    },
  };
}

export function defaultRsiSpace(): RsiSearchSpace {
  return {
    family: 'rsi_mean_reversion',
    period: { min: 10, max: 20, step: 2 },
    oversold: { min: 20, max: 35, step: 5 },
    overbought: { min: 65, max: 80, step: 5 },
  };
}

export function defaultMacdSpace(): MacdSearchSpace {
  return { family: 'macd_signal_cross', useDefaultTriples: true };
}

export function defaultSpaceForFamily(family: OptimizeStrategyFamily): OptimizeSearchSpace {
  if (family === 'rsi_mean_reversion') return defaultRsiSpace();
  if (family === 'macd_signal_cross') return defaultMacdSpace();
  return spaceFromPeriodLists('10,15,20,25,30', '40,50,60,80,100');
}

export function formatDelta(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}`;
}

export function formatTrialParams(trial: {
  fastPeriod?: number | null;
  slowPeriod?: number | null;
  signalPeriod?: number | null;
  period?: number | null;
  oversold?: number | null;
  overbought?: number | null;
}, family: OptimizeStrategyFamily | string = 'sma_crossover'): string {
  if (family === 'rsi_mean_reversion' || (trial.period != null && trial.oversold != null)) {
    return `RSI ${trial.period} · ${trial.oversold}/${trial.overbought}`;
  }
  if (family === 'macd_signal_cross' || trial.signalPeriod != null) {
    return `MACD ${trial.fastPeriod}/${trial.slowPeriod}/${trial.signalPeriod}`;
  }
  return `SMA ${trial.fastPeriod ?? '—'}/${trial.slowPeriod ?? '—'}`;
}
