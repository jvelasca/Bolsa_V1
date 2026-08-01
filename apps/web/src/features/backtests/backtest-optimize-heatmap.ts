/**
 * Heatmap + top-5 + plateau detection over optimize trials (Lab P1).
 */

import type { OptimizeStrategyFamily, SmaGridTrialDto } from '@bolsa/shared';
import { formatTrialParams } from '@/features/backtests/backtest-optimize-space';

export type OptimizeHeatmapScoreMode = 'is' | 'oos';

export type OptimizeHeatmapCell = {
  x: number;
  y: number;
  score: number | null;
  trial: SmaGridTrialDto | null;
  isBest: boolean;
};

export type OptimizePlateauInfo = {
  isPlateau: boolean;
  neighborCount: number;
  closeNeighborCount: number;
  detail: string;
};

export type OptimizeTopTrial = {
  rank: number;
  score: number;
  paramsLabel: string;
  trial: SmaGridTrialDto;
};

export type OptimizeHeatmapModel = {
  family: OptimizeStrategyFamily | string;
  xLabel: string;
  yLabel: string;
  xTicks: number[];
  yTicks: number[];
  cells: OptimizeHeatmapCell[];
  top5: OptimizeTopTrial[];
  plateau: OptimizePlateauInfo;
  scoreMin: number;
  scoreMax: number;
  scoreMode: OptimizeHeatmapScoreMode;
  best: { x: number; y: number; score: number } | null;
};

function trialScore(trial: SmaGridTrialDto, mode: OptimizeHeatmapScoreMode): number | null {
  if (mode === 'oos') {
    const s = trial.oosMetrics?.score;
    return typeof s === 'number' && Number.isFinite(s) ? s : null;
  }
  return Number.isFinite(trial.score) ? trial.score : null;
}

function axesForFamily(family: string): { xLabel: string; yLabel: string } {
  if (family === 'rsi_mean_reversion') {
    return { xLabel: 'Periodo', yLabel: 'Oversold' };
  }
  if (family === 'macd_signal_cross') {
    return { xLabel: 'Fast', yLabel: 'Slow' };
  }
  return { xLabel: 'Fast', yLabel: 'Slow' };
}

function xyOf(trial: SmaGridTrialDto, family: string): { x: number; y: number } | null {
  if (family === 'rsi_mean_reversion') {
    if (trial.period == null || trial.oversold == null) return null;
    return { x: trial.period, y: trial.oversold };
  }
  if (trial.fastPeriod == null || trial.slowPeriod == null) return null;
  return { x: trial.fastPeriod, y: trial.slowPeriod };
}

function uniqSorted(values: number[]): number[] {
  return [...new Set(values.filter((n) => Number.isFinite(n)))].sort((a, b) => a - b);
}

/**
 * Build 2D score grid + top-5 + plateau around Mejor.
 * For duplicate (x,y) keeps the better score (e.g. MACD signal variants).
 */
export function buildOptimizeHeatmap(opts: {
  trials: SmaGridTrialDto[];
  family?: OptimizeStrategyFamily | string;
  scoreMode?: OptimizeHeatmapScoreMode;
  topN?: number;
  /** Relative tolerance vs score span (default 8%). */
  plateauRelTol?: number;
  /** Absolute floor on tolerance. */
  plateauAbsTol?: number;
  /** Min close neighbors to flag plateau. */
  plateauMinClose?: number;
}): OptimizeHeatmapModel | null {
  const family = opts.family ?? 'sma_crossover';
  const scoreMode = opts.scoreMode ?? 'is';
  const topN = opts.topN ?? 5;
  const plateauRelTol = opts.plateauRelTol ?? 0.08;
  const plateauAbsTol = opts.plateauAbsTol ?? 0.35;
  const plateauMinClose = opts.plateauMinClose ?? 2;

  const scored: Array<{ trial: SmaGridTrialDto; x: number; y: number; score: number }> = [];
  for (const trial of opts.trials) {
    const xy = xyOf(trial, family);
    const score = trialScore(trial, scoreMode);
    if (!xy || score == null) continue;
    scored.push({ trial, x: xy.x, y: xy.y, score });
  }
  if (scored.length === 0) return null;

  const byCell = new Map<string, (typeof scored)[number]>();
  for (const item of scored) {
    const key = `${item.x}|${item.y}`;
    const prev = byCell.get(key);
    if (!prev || item.score > prev.score) byCell.set(key, item);
  }
  const unique = [...byCell.values()];

  const xTicks = uniqSorted(unique.map((u) => u.x));
  const yTicks = uniqSorted(unique.map((u) => u.y));
  const scores = unique.map((u) => u.score);
  const scoreMin = Math.min(...scores);
  const scoreMax = Math.max(...scores);

  let best = unique[0]!;
  for (const u of unique) {
    if (u.score > best.score) best = u;
  }

  const cells: OptimizeHeatmapCell[] = [];
  for (const y of yTicks) {
    for (const x of xTicks) {
      const hit = byCell.get(`${x}|${y}`);
      cells.push({
        x,
        y,
        score: hit?.score ?? null,
        trial: hit?.trial ?? null,
        isBest: Boolean(hit && hit.x === best.x && hit.y === best.y),
      });
    }
  }

  const ranked = [...unique].sort((a, b) => b.score - a.score);
  const top5: OptimizeTopTrial[] = ranked.slice(0, topN).map((item, i) => ({
    rank: i + 1,
    score: item.score,
    paramsLabel: formatTrialParams(item.trial, family),
    trial: item.trial,
  }));

  const xIndex = new Map(xTicks.map((v, i) => [v, i]));
  const yIndex = new Map(yTicks.map((v, i) => [v, i]));
  const bestXi = xIndex.get(best.x);
  const bestYi = yIndex.get(best.y);
  let neighborCount = 0;
  let closeNeighborCount = 0;
  const span = Math.max(1e-6, scoreMax - scoreMin);
  const tol = Math.max(plateauAbsTol, span * plateauRelTol);

  if (bestXi != null && bestYi != null) {
    for (const u of unique) {
      if (u.x === best.x && u.y === best.y) continue;
      const xi = xIndex.get(u.x);
      const yi = yIndex.get(u.y);
      if (xi == null || yi == null) continue;
      const manhattan = Math.abs(xi - bestXi) + Math.abs(yi - bestYi);
      if (manhattan !== 1) continue;
      neighborCount += 1;
      if (Math.abs(u.score - best.score) <= tol) closeNeighborCount += 1;
    }
  }

  const isPlateau = neighborCount > 0 && closeNeighborCount >= plateauMinClose;
  const plateau: OptimizePlateauInfo = {
    isPlateau,
    neighborCount,
    closeNeighborCount,
    detail: isPlateau
      ? `Meseta: ${closeNeighborCount}/${neighborCount} vecinos ±${tol.toFixed(2)} del Mejor — params poco sensibles.`
      : neighborCount === 0
        ? 'Sin vecinos en la malla (espacio disperso).'
        : `Mejor localizado: solo ${closeNeighborCount}/${neighborCount} vecinos cercanos en score.`,
  };

  const { xLabel, yLabel } = axesForFamily(family);
  return {
    family,
    xLabel,
    yLabel,
    xTicks,
    yTicks,
    cells,
    top5,
    plateau,
    scoreMin,
    scoreMax,
    scoreMode,
    best: { x: best.x, y: best.y, score: best.score },
  };
}

/**
 * Snapshot de meseta para memoria Lab (CORE-B v0.1).
 * Null si no hay malla usable (sin trials / sin Mejor).
 */
export function plateauAdoptionMetaFromTrials(opts: {
  trials: SmaGridTrialDto[];
  family?: OptimizeStrategyFamily | string;
  scoreMode?: OptimizeHeatmapScoreMode;
}): { isPlateau: boolean; neighborCount: number; closeNeighborCount: number } | null {
  const model = buildOptimizeHeatmap(opts);
  if (!model?.best) return null;
  return {
    isPlateau: model.plateau.isPlateau,
    neighborCount: model.plateau.neighborCount,
    closeNeighborCount: model.plateau.closeNeighborCount,
  };
}

/** 0–1 for color; null → muted. */
export function heatmapNorm(score: number | null, min: number, max: number): number | null {
  if (score == null || !Number.isFinite(score)) return null;
  const span = Math.max(1e-6, max - min);
  return Math.min(1, Math.max(0, (score - min) / span));
}

export function heatmapCellStyle(norm: number | null): { backgroundColor: string } {
  if (norm == null) {
    return { backgroundColor: 'transparent' };
  }
  // sky (low) → emerald (high)
  const r = Math.round(56 + (16 - 56) * norm);
  const g = Math.round(189 + (185 - 189) * norm);
  const b = Math.round(248 + (129 - 248) * norm);
  const a = 0.18 + norm * 0.55;
  return { backgroundColor: `rgba(${r},${g},${b},${a.toFixed(3)})` };
}
