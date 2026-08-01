/**
 * Coach técnico profundo (local + opcional LLM).
 *
 * Contrato (2026-07-28):
 * - **Ranking / TOP ★:** siempre local (`rankTechnicalRecommendations`). Determinista
 *   dados filas + `periodReturns` (o equity) + horizonte/riesgo de cuenta.
 * - **Sesgo a futuro:** ~42% del score = **nivel** del tercio reciente (la aceleración
 *   solo bonus si reciente ≥ 0; evita crowning de rebote tras desplome).
 * - **Dedupe** por `strategyType`; **diversidad** por familia; suelos + preferencia vs B&H.
 * - **LLM:** narrador (`mergeLlmIntoDeepCoach`); no sustituye `recommendations`.
 * - **UI:** no mostrar TOP provisional mientras `running` (batería incompleta).
 *
 * No optimiza por rentabilidad bruta total del periodo.
 *
 * @see docs/engineering/research-lifecycle.md § P2
 */

import type {
  BacktestEquityPointDto,
  BacktestRunDetailDto,
  ChartTimeframe,
  ProfileHorizon,
  RiskTolerance,
  StrategyPresetCategory,
} from '@bolsa/shared';
import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';
import type { CoachAuditResultV1 } from '@/features/backtests/coach-dual-audit';
import { preferredCategoriesForHorizon } from '@/features/backtests/coach-profile-policy';

export type DeepCoachContext = {
  symbol: string;
  timeframe: ChartTimeframe | string;
  periodLabel?: string;
  horizon?: ProfileHorizon | null;
  riskTolerance?: RiskTolerance | null;
  profileName?: string | null;
  profileId?: string | null;
  /** Techo DD blando del perfil (CORE-P); alinea riskFit con Lab. */
  maxDrawdownSoftPct?: number | null;
  /** Equity curves by runId (from seeded detail cache). */
  equityByRunId?: Record<string, BacktestEquityPointDto[] | undefined>;
  /**
   * Nivel de evidencia del lote.
   * - in_sample_only (default): techo ★ ≤ 3 (no declarar “lista para paper”)
   * - lab_validated: permite ★ 4–5 si el score lo sostiene
   */
  evidenceLevel?: 'in_sample_only' | 'lab_validated';
  /**
   * Peso del sesgo futuro / tramo reciente (default 0.42).
   * El resto de componentes se reescala para sumar 1.
   */
  futureWeight?: number;
};

export type TechnicalRecommendation = {
  rank: number;
  row: ExplorePresetRow;
  /** Idoneidad 0–100 (peso fuerte en sesgo futuro / tramo reciente). */
  score: number;
  /** Estrellas 1–5 para UI (pasos de 0.5; techo según evidencia). */
  stars: number;
  /** Techo aplicado (si stars quedó capped). */
  starsCapped?: boolean;
  /** Componente 0–1 del sesgo de tendencia reciente/futura. */
  futureBias: number;
  earlyReturnPct?: number | null;
  midReturnPct?: number | null;
  lateReturnPct?: number | null;
  /** Sin tercios de equity: score con fallback suave (menos fiable). */
  usedSoftFallback?: boolean;
  /** No pasó suelos de calidad (reciente / excess); solo entra si no hay mejores. */
  qualityFlagged?: boolean;
  reasons: string[];
};

export type RankTechnicalOptions = {
  limit?: number;
  /** Diversificar TOP por familia (estilo portfolio). Default true. */
  diversifyCategories?: boolean;
  /** Tercio reciente mínimo (pp). Por debajo → qualityFlagged. Default -20. */
  minLateReturnPct?: number;
  /** Excess vs B&H mínimo. Por debajo → qualityFlagged. Default -15. */
  minExcessReturnPct?: number;
};

/** Hechos tipados para LLM / persistencia — el narrador no inventa fuera de esto. */
export type CoachFactsV1 = {
  schemaVersion: '1.0.0';
  symbol: string;
  timeframe: string;
  periodLabel?: string;
  horizon: ProfileHorizon;
  riskTolerance?: RiskTolerance | null;
  evidenceLevel: 'in_sample_only' | 'lab_validated';
  starCeiling: 3 | 5;
  buyHoldReturnPct: number | null;
  okCount: number;
  windows: {
    earlyBestLabel?: string;
    midBestLabel?: string;
    lateBestLabel?: string;
    shifted: boolean;
    narrative: string;
  };
  recommendations: Array<{
    rank: number;
    strategyType: string;
    label: string;
    category: string;
    score: number;
    stars: number;
    starsCapped: boolean;
    totalReturnPct?: number;
    excessReturnPct?: number | null;
    maxDrawdownPct?: number;
    earlyReturnPct?: number | null;
    midReturnPct?: number | null;
    lateReturnPct?: number | null;
    usedSoftFallback?: boolean;
    qualityFlagged?: boolean;
    runId?: string;
  }>;
};

export type RegimeHalfInsight = {
  label: string;
  earlyBest?: ExplorePresetRow;
  lateBest?: ExplorePresetRow;
  shifted: boolean;
  narrative: string;
};

export type DeepTechnicalCoachNote = {
  headline: string;
  /** Peso grande: análisis TA (no solo ranking de %). */
  analysis: string[];
  recommendations: TechnicalRecommendation[];
  regime?: RegimeHalfInsight;
  outlook: string[];
  disclaimer: string;
  contextLabel: string;
  /** Doble auditoría (Motor B + gate). Ausente solo en estados vacíos / running. */
  audit?: CoachAuditResultV1;
};

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

function horizonFromTimeframe(tf: string): ProfileHorizon {
  if (tf === '1m' || tf === '5m' || tf === '15m' || tf === '30m' || tf === '1h') {
    return 'intraday';
  }
  if (tf === '4h' || tf === '1d') return 'swing';
  if (tf === '1wk') return 'position';
  return 'swing';
}

function preferredCategories(horizon: ProfileHorizon): StrategyPresetCategory[] {
  return preferredCategoriesForHorizon(horizon);
}

function tradesPerHundredBars(row: ExplorePresetRow): number | null {
  if (row.tradeCount == null || row.barCount == null || row.barCount <= 0) return null;
  return (row.tradeCount / row.barCount) * 100;
}

function activityFit(row: ExplorePresetRow, horizon: ProfileHorizon): number {
  const tpb = tradesPerHundredBars(row);
  if (tpb == null) return 0.55;
  // Expected intensity by horizon (heuristic).
  const ideal =
    horizon === 'intraday' ? 8 : horizon === 'swing' ? 2.5 : horizon === 'position' ? 0.8 : 0.35;
  const ratio = tpb / ideal;
  if (ratio <= 0) return 0.2;
  // Peak near 1.0; too many trades = overtrading for that horizon.
  if (ratio < 1) return clamp01(0.35 + ratio * 0.55);
  return clamp01(1.1 - (ratio - 1) * 0.35);
}

function riskFit(
  row: ExplorePresetRow,
  risk: RiskTolerance | null | undefined,
  softCapOverride?: number | null,
): number {
  const dd = Math.abs(row.maxDrawdownPct ?? 25);
  const tol = risk ?? 'moderate';
  const softCap =
    softCapOverride != null && Number.isFinite(softCapOverride)
      ? softCapOverride
      : tol === 'low'
        ? 12
        : tol === 'high'
          ? 35
          : 20;
  let fit = 0.2;
  if (dd <= softCap * 0.5) fit = 1;
  else if (dd <= softCap) fit = 0.75;
  else if (dd <= softCap * 1.5) fit = 0.45;
  // DD bajo no salva una estrategia que pierde vs B&H / tramo reciente (cash o almost-flat).
  const excess = row.excessReturnPct;
  if (excess != null && excess < 0) fit = Math.min(fit, 0.55);
  if (excess != null && excess < -10) fit = Math.min(fit, 0.35);
  return fit;
}

function categoryFit(row: ExplorePresetRow, horizon: ProfileHorizon): number {
  const prefs = preferredCategories(horizon);
  const idx = prefs.indexOf(row.category);
  if (idx < 0) return 0.45;
  return clamp01(1 - idx * 0.12);
}

function edgeQuality(row: ExplorePresetRow): number {
  const excess = row.excessReturnPct ?? 0;
  const sharpe = row.sharpeRatio;
  const ret = row.totalReturnPct ?? 0;
  // Excess manda más: el usuario ve vs B&H; no coronar “tranquila pero perdedora”.
  const excessScore = clamp01(0.5 + excess / 35);
  const sharpeScore =
    sharpe == null || !Number.isFinite(sharpe) ? 0.45 : clamp01(0.5 + sharpe / 2.5);
  const retScore = clamp01(0.45 + ret / 55);
  return excessScore * 0.45 + sharpeScore * 0.3 + retScore * 0.25;
}

export function halfPeriodReturn(
  equity: BacktestEquityPointDto[],
): { early: number; late: number } | null {
  if (equity.length < 8) return null;
  const mid = Math.floor(equity.length / 2);
  const start = equity[0]!.equity;
  const midEq = equity[mid]!.equity;
  const end = equity[equity.length - 1]!.equity;
  if (!(start > 0) || !(midEq > 0)) return null;
  return {
    early: ((midEq - start) / start) * 100,
    late: ((end - midEq) / midEq) * 100,
  };
}

/** Tres ventanas temporales (temprana / media / reciente) sobre la equity. */
export function thirdPeriodReturns(
  equity: BacktestEquityPointDto[],
): { early: number; mid: number; late: number } | null {
  if (equity.length < 12) {
    const halves = halfPeriodReturn(equity);
    if (!halves) return null;
    return { early: halves.early, mid: halves.early, late: halves.late };
  }
  const a = Math.floor(equity.length / 3);
  const b = Math.floor((2 * equity.length) / 3);
  const e0 = equity[0]!.equity;
  const e1 = equity[a]!.equity;
  const e2 = equity[b]!.equity;
  const e3 = equity[equity.length - 1]!.equity;
  if (!(e0 > 0) || !(e1 > 0) || !(e2 > 0)) return null;
  return {
    early: ((e1 - e0) / e0) * 100,
    mid: ((e2 - e1) / e1) * 100,
    late: ((e3 - e2) / e2) * 100,
  };
}

/**
 * Sesgo de tendencia futura (0–1): prioriza el **nivel** del tramo reciente.
 * La aceleración solo suma si el reciente ya es ≥ 0 (evita crowning de “rebote
 * tras desplome” — caso BBVA: #1 mala con 2ª/3ª buenas).
 */
export function futureTrendBias(row: ExplorePresetRow, ctx: DeepCoachContext): {
  bias: number;
  earlyReturnPct: number | null;
  midReturnPct: number | null;
  lateReturnPct: number | null;
  usedSoftFallback: boolean;
} {
  // Prefer periodReturns fijados en el run (estable). Fallback: equity del caché.
  const thirds =
    row.periodReturns ??
    (() => {
      const eq = row.runId ? ctx.equityByRunId?.[row.runId] : undefined;
      return eq?.length ? thirdPeriodReturns(eq) : null;
    })();
  if (thirds) {
    // Nivel absoluto del tramo reciente (manda).
    const lateScore = clamp01(0.5 + thirds.late / 28);
    const accelLateVsMid = clamp01(0.5 + (thirds.late - thirds.mid) / 36);
    const accelLateVsEarly = clamp01(0.5 + (thirds.late - thirds.early) / 40);
    // Aceleración solo como bonus si el reciente no es negativo.
    const accelBonus =
      thirds.late >= 0
        ? accelLateVsMid * 0.12 + accelLateVsEarly * 0.08
        : 0;
    const latePenalty =
      thirds.late < 0 ? Math.min(0.4, Math.abs(thirds.late) / 35) : 0;
    return {
      bias: clamp01(lateScore * 0.8 + accelBonus - latePenalty),
      earlyReturnPct: thirds.early,
      midReturnPct: thirds.mid,
      lateReturnPct: thirds.late,
      usedSoftFallback: false,
    };
  }
  const soft = clamp01(0.42 + (row.excessReturnPct ?? 0) / 55);
  return {
    // Cap soft path below a solid thirds-based mid score so stamped runs win ties.
    bias: soft * 0.45 + 0.15,
    earlyReturnPct: null,
    midReturnPct: null,
    lateReturnPct: null,
    usedSoftFallback: true,
  };
}

/** Techo de estrellas según evidencia (in-sample → máx 3). */
export function starCeilingForEvidence(
  evidenceLevel: DeepCoachContext['evidenceLevel'] = 'in_sample_only',
): 3 | 5 {
  return evidenceLevel === 'lab_validated' ? 5 : 3;
}

/**
 * Estrellas 1–5 (pasos de 0.5) a partir del score 0–100, con techo de evidencia.
 * Umbrales enteros conservan el mapeo histórico; los medios afinan bandas intermedias.
 */
export function scoreToStars(
  score: number,
  opts?: { ceiling?: 3 | 5 },
): { stars: number; capped: boolean } {
  const ceiling = opts?.ceiling ?? 5;
  let raw: number;
  if (score >= 82) raw = 5;
  else if (score >= 75) raw = 4.5;
  else if (score >= 68) raw = 4;
  else if (score >= 60) raw = 3.5;
  else if (score >= 52) raw = 3;
  else if (score >= 44) raw = 2.5;
  else if (score >= 36) raw = 2;
  else if (score >= 20) raw = 1.5;
  else raw = 1;
  const stars = Math.min(raw, ceiling);
  return { stars, capped: stars < raw };
}

const DEFAULT_SCORE_WEIGHTS = {
  future: 0.42,
  risk: 0.18,
  edge: 0.18,
  category: 0.12,
  activity: 0.1,
} as const;

/** Pesos del score ★; `futureWeight` reescala el resto para sumar 1. */
export function resolveCoachScoreWeights(futureWeight?: number): {
  future: number;
  risk: number;
  edge: number;
  category: number;
  activity: number;
} {
  const future = Math.min(
    0.65,
    Math.max(0.25, Number.isFinite(futureWeight) ? Number(futureWeight) : DEFAULT_SCORE_WEIGHTS.future),
  );
  const restScale = (1 - future) / (1 - DEFAULT_SCORE_WEIGHTS.future);
  return {
    future,
    risk: DEFAULT_SCORE_WEIGHTS.risk * restScale,
    edge: DEFAULT_SCORE_WEIGHTS.edge * restScale,
    category: DEFAULT_SCORE_WEIGHTS.category * restScale,
    activity: DEFAULT_SCORE_WEIGHTS.activity * restScale,
  };
}

/**
 * Score 0–100: sesgo futuro (tramo reciente) + riesgo + edge vs B&H.
 * Prefiere `row.periodReturns` (fijado al cerrar el run) frente a recompute desde equity map.
 */
export function scoreTechnicalFit(row: ExplorePresetRow, ctx: DeepCoachContext): number {
  const horizon = ctx.horizon ?? horizonFromTimeframe(String(ctx.timeframe));
  const { bias: future } = futureTrendBias(row, ctx);
  const w = resolveCoachScoreWeights(ctx.futureWeight);
  const parts = {
    future,
    risk: riskFit(row, ctx.riskTolerance, ctx.maxDrawdownSoftPct),
    activity: activityFit(row, horizon),
    category: categoryFit(row, horizon),
    edge: edgeQuality(row),
  };
  const raw =
    parts.future * w.future +
    parts.risk * w.risk +
    parts.edge * w.edge +
    parts.category * w.category +
    parts.activity * w.activity;
  return Math.round(clamp01(raw) * 100);
}

function scoreReasons(
  row: ExplorePresetRow,
  ctx: DeepCoachContext,
  score: number,
  future: ReturnType<typeof futureTrendBias>,
  starsInfo: { stars: number; capped: boolean },
): string[] {
  const horizon = ctx.horizon ?? horizonFromTimeframe(String(ctx.timeframe));
  const ceiling = starCeilingForEvidence(ctx.evidenceLevel);
  const reasons: string[] = [];
  reasons.push(
    `Estrellas ${starsInfo.stars}/5 · idoneidad futura ${score}/100 (TF ${ctx.timeframe}, horizonte «${horizon}»).`,
  );
  if (starsInfo.capped) {
    reasons.push(
      `Techo ★${ceiling}: lote solo in-sample — ★4–5 requieren validación lab (OOS/WF/CPCV).`,
    );
  }
  if (
    future.lateReturnPct != null &&
    future.earlyReturnPct != null &&
    future.midReturnPct != null
  ) {
    reasons.push(
      `Ventanas equity: temprana ${future.earlyReturnPct.toFixed(1)}% · media ${future.midReturnPct.toFixed(1)}% · reciente ${future.lateReturnPct.toFixed(1)}% (manda la reciente).`,
    );
    if (future.lateReturnPct + 2 < future.earlyReturnPct) {
      reasons.push(
        'Cuidado: el tramo reciente empeora vs el histórico temprano — no anclarse al resultado total del periodo.',
      );
    } else if (future.lateReturnPct > future.midReturnPct + 2) {
      reasons.push(
        'El tramo reciente acelera vs la ventana media: mejor señal operativa hacia delante que el total del backtest.',
      );
    }
  } else {
    reasons.push(
      'Sin curva de equity en 3 ventanas: estrellas más cautas (fallback suave) hasta abrir el detalle.',
    );
  }
  if (future.usedSoftFallback) {
    reasons.push(
      'Aviso: ranking sin tercios fijados — menos fiable; re-ejecuta Probar + coach si persiste.',
    );
  }
  const dd = row.maxDrawdownPct;
  if (dd != null) {
    reasons.push(`Drawdown ${(dd).toFixed(1)}% vs perfil de riesgo (${ctx.riskTolerance ?? 'moderate'}).`);
  }
  if ((row.totalReturnPct ?? 0) > 15 && (future.lateReturnPct ?? 0) < 0) {
    reasons.push(
      'Rentabilidad total alta pero tramo reciente negativo: el pasado lejano no justifica priorizarla a futuro.',
    );
  }
  return reasons;
}

/**
 * Una fila por strategyType: prioriza periodReturns fijados, luego excess, luego label.
 * Evita TOP con genérica + guardada del mismo preset.
 */
/**
 * Dedup del lote coach: por strategyDefinitionId si existe (Mejores Lab),
 * si no por strategyType (genéricas).
 */
export function dedupeExploreRowsByStrategyType(rows: ExplorePresetRow[]): ExplorePresetRow[] {
  const byKey = new Map<string, ExplorePresetRow>();
  for (const row of rows) {
    const key = row.strategyDefinitionId
      ? `id:${row.strategyDefinitionId}`
      : `type:${row.strategyType}`;
    const prev = byKey.get(key);
    if (!prev) {
      byKey.set(key, row);
      continue;
    }
    const prevHas = Boolean(prev.periodReturns);
    const nextHas = Boolean(row.periodReturns);
    if (nextHas && !prevHas) {
      byKey.set(key, row);
      continue;
    }
    if (prevHas === nextHas) {
      const pe = prev.excessReturnPct ?? -Infinity;
      const ne = row.excessReturnPct ?? -Infinity;
      if (ne > pe) byKey.set(key, row);
    }
  }
  return [...byKey.values()];
}

function isQualityFlagged(
  item: {
    lateReturnPct?: number | null;
    row: ExplorePresetRow;
    usedSoftFallback?: boolean;
  },
  minLate: number,
  minExcess: number,
): boolean {
  const late = item.lateReturnPct;
  const excess = item.row.excessReturnPct;
  if (late != null && late < minLate) return true;
  if (excess != null && excess < minExcess) return true;
  // Reciente negativo + no bate B&H → no merece TOP alto
  if (late != null && late < 0 && (excess == null || excess < 0)) return true;
  // Soft fallback + negative excess: treat as flagged
  if (item.usedSoftFallback && (excess == null || excess < 0)) return true;
  return false;
}

/** B domina a A en late + excess + total (al menos una mejora estricta). */
export function isStrictlyDominatedBy(
  a: {
    lateReturnPct?: number | null;
    row: ExplorePresetRow;
  },
  b: {
    lateReturnPct?: number | null;
    row: ExplorePresetRow;
  },
): boolean {
  const lateA = a.lateReturnPct ?? -999;
  const lateB = b.lateReturnPct ?? -999;
  const exA = a.row.excessReturnPct ?? -999;
  const exB = b.row.excessReturnPct ?? -999;
  const totA = a.row.totalReturnPct ?? -999;
  const totB = b.row.totalReturnPct ?? -999;
  const allGe = lateB >= lateA && exB >= exA && totB >= totA;
  const anyGt = lateB > lateA || exB > exA || totB > totA;
  return allGe && anyGt;
}

function beatsBuyHold(row: ExplorePresetRow, late: number | null | undefined): boolean {
  return (row.excessReturnPct ?? -1) >= 0 && (late == null || late >= 0);
}

function compareRanked(
  a: {
    score: number;
    futureBias: number;
    qualityFlagged?: boolean;
    usedSoftFallback?: boolean;
    lateReturnPct?: number | null;
    row: ExplorePresetRow;
  },
  b: typeof a,
): number {
  // Prefer non-flagged, then solid thirds over soft fallback
  if (Boolean(a.qualityFlagged) !== Boolean(b.qualityFlagged)) {
    return a.qualityFlagged ? 1 : -1;
  }
  if (Boolean(a.usedSoftFallback) !== Boolean(b.usedSoftFallback)) {
    return a.usedSoftFallback ? 1 : -1;
  }
  // Prefer bate B&H con reciente ≥ 0 (evita #1 “mala” con 2ª/3ª buenas).
  const aBeat = beatsBuyHold(a.row, a.lateReturnPct);
  const bBeat = beatsBuyHold(b.row, b.lateReturnPct);
  if (aBeat !== bBeat) return aBeat ? -1 : 1;
  return (
    b.score - a.score ||
    b.futureBias - a.futureBias ||
    (b.lateReturnPct ?? -999) - (a.lateReturnPct ?? -999) ||
    (b.row.excessReturnPct ?? -999) - (a.row.excessReturnPct ?? -999) ||
    (b.row.sharpeRatio ?? -99) - (a.row.sharpeRatio ?? -99) ||
    a.row.strategyType.localeCompare(b.row.strategyType)
  );
}

/**
 * Greedy TOP con diversidad por familia (máx. 1 de la misma category mientras queden
 * alternativas). No mete candidatas `qualityFlagged` si hay no-flagged disponibles.
 */
export function pickDiversifiedTop<
  T extends { row: ExplorePresetRow; qualityFlagged?: boolean },
>(ranked: T[], limit: number): T[] {
  if (limit <= 0 || ranked.length === 0) return [];
  const picked: T[] = [];
  const usedCategories = new Set<string>();
  const used = new Set<T>();

  const take = (predicate: (item: T) => boolean) => {
    while (picked.length < limit) {
      const next = ranked.find((item) => !used.has(item) && predicate(item));
      if (!next) break;
      picked.push(next);
      used.add(next);
      usedCategories.add(next.row.category);
    }
  };

  // Pass 1: best unused category, non-flagged
  take((item) => !item.qualityFlagged && !usedCategories.has(item.row.category));
  // Pass 2: fill with non-flagged by score order
  take((item) => !item.qualityFlagged);
  // Pass 3: only if still short — flagged last resort
  take(() => true);

  return picked;
}

export function rankTechnicalRecommendations(
  rows: ExplorePresetRow[],
  ctx: DeepCoachContext,
  limitOrOpts: number | RankTechnicalOptions = 3,
): TechnicalRecommendation[] {
  const opts: RankTechnicalOptions =
    typeof limitOrOpts === 'number' ? { limit: limitOrOpts } : limitOrOpts;
  const limit = opts.limit ?? 3;
  const diversify = opts.diversifyCategories !== false;
  const minLate = opts.minLateReturnPct ?? -12;
  const minExcess = opts.minExcessReturnPct ?? -8;

  const ceiling = starCeilingForEvidence(ctx.evidenceLevel);
  const ok = dedupeExploreRowsByStrategyType(
    rows.filter((r) => r.status === 'ok' && r.labPass !== 'lab_carry'),
  );
  const ranked = ok
    .map((row) => {
      const future = futureTrendBias(row, ctx);
      let score = scoreTechnicalFit(row, ctx);
      // Soft fallback: mild penalty so stamped thirds dominate when comparable
      if (future.usedSoftFallback) score = Math.max(0, score - 8);
      let qualityFlagged = isQualityFlagged(
        {
          lateReturnPct: future.lateReturnPct,
          row,
          usedSoftFallback: future.usedSoftFallback,
        },
        minLate,
        minExcess,
      );
      if (qualityFlagged) score = Math.max(0, score - 18);
      const starsInfo = scoreToStars(score, { ceiling });
      const reasons = scoreReasons(row, ctx, score, future, starsInfo);
      if (qualityFlagged) {
        reasons.push(
          `Suelo de calidad: tramo reciente o vs B&H flojos (umbrales ${minLate}% / ${minExcess}%).`,
        );
      }
      return {
        rank: 0,
        row,
        score,
        stars: starsInfo.stars,
        starsCapped: starsInfo.capped,
        futureBias: future.bias,
        earlyReturnPct: future.earlyReturnPct,
        midReturnPct: future.midReturnPct,
        lateReturnPct: future.lateReturnPct,
        usedSoftFallback: future.usedSoftFallback,
        qualityFlagged,
        reasons,
      };
    });

  // Dominancia solo para trampas (excess/total negativos): p. ej. rebote tras desplome.
  for (const item of ranked) {
    const looksTrap =
      (item.row.excessReturnPct ?? 0) < 0 || (item.row.totalReturnPct ?? 0) < 0;
    if (!looksTrap) continue;
    const dominated = ranked.some(
      (other) =>
        other !== item &&
        beatsBuyHold(other.row, other.lateReturnPct) &&
        isStrictlyDominatedBy(item, other),
    );
    if (dominated) {
      item.score = Math.max(0, item.score - 22);
      item.qualityFlagged = true;
      item.reasons.push(
        'Dominada por otra candidata (mejor en reciente, vs B&H y total).',
      );
    }
  }

  ranked.sort(compareRanked);

  const selected = diversify
    ? pickDiversifiedTop(ranked, limit)
    : ranked.slice(0, limit);

  return selected.map((item, i) => ({ ...item, rank: i + 1 }));
}

export function inferRegimeShift(
  rows: ExplorePresetRow[],
  equityByRunId?: Record<string, BacktestEquityPointDto[] | undefined>,
): RegimeHalfInsight | undefined {
  const ok = rows.filter((r) => r.status === 'ok' && r.runId);
  const scored: {
    row: ExplorePresetRow;
    early: number;
    mid: number;
    late: number;
  }[] = [];
  for (const row of ok) {
    const thirds =
      row.periodReturns ??
      (() => {
        const eq = equityByRunId?.[row.runId!];
        return eq?.length ? thirdPeriodReturns(eq) : null;
      })();
    if (!thirds) continue;
    scored.push({ row, early: thirds.early, mid: thirds.mid, late: thirds.late });
  }
  if (scored.length < 2) return undefined;

  const earlyBest = [...scored].sort((a, b) => b.early - a.early)[0]!;
  const midBest = [...scored].sort((a, b) => b.mid - a.mid)[0]!;
  const lateBest = [...scored].sort((a, b) => b.late - a.late)[0]!;
  const shifted =
    earlyBest.row.strategyType !== lateBest.row.strategyType ||
    midBest.row.strategyType !== lateBest.row.strategyType;
  const narrative = shifted
    ? `Ventanas: temprana «${earlyBest.row.label}» (${earlyBest.early.toFixed(1)}%) · media «${midBest.row.label}» (${midBest.mid.toFixed(1)}%) · reciente «${lateBest.row.label}» (${lateBest.late.toFixed(1)}%). El régimen parece haber rotado: lo que funcionó al inicio no es necesariamente lo coherente ahora.`
    : `«${lateBest.row.label}» lidera de forma estable en las ventanas — régimen relativo coherente para esa familia AT.`;

  return {
    label: shifted ? 'Cambio de régimen detectado' : 'Régimen relativamente estable',
    earlyBest: earlyBest.row,
    lateBest: lateBest.row,
    shifted,
    narrative,
  };
}

function buildOutlook(
  recs: TechnicalRecommendation[],
  regime: RegimeHalfInsight | undefined,
  ctx: DeepCoachContext,
): string[] {
  const lines: string[] = [];
  const top = recs[0];
  if (top) {
    lines.push(
      `Mirada hacia delante (AT, no predicción de precio): priorizar «${top.row.label}» mientras el valor se comporte acorde a la familia «${top.row.categoryLabel}» en TF ${ctx.timeframe}.`,
    );
  }
  if (regime?.shifted && regime.lateBest) {
    lines.push(
      `Si el tramo reciente manda, el sesgo operativo inclina a «${regime.lateBest.label}» frente a la estrategia “ganadora histórica” del tramo inicial.`,
    );
  } else if (regime && !regime.shifted && regime.lateBest) {
    lines.push(
      `La continuidad 1ª→2ª mitad refuerza vigilar la misma familia; invalidación si el drawdown rompe el perfil (${ctx.riskTolerance ?? 'moderate'}).`,
    );
  } else {
    lines.push(
      'Sin curvas de equity en caché no se parte el periodo: conviene abrir el detalle de las 3 recomendadas y comparar operaciones recientes vs tempranas.',
    );
  }
  lines.push(
    'Falsador: si el precio deja el contexto (tendencia↔rango) que justifica la familia elegida, dejar de insistir en la misma regla aunque el backtest total siga en verde.',
  );
  return lines;
}

/** Coach local profundo — siempre disponible (fallback si no hay LLM). */
export function buildDeepTechnicalCoachNote(
  rows: ExplorePresetRow[],
  ctx: DeepCoachContext,
): DeepTechnicalCoachNote {
  const horizon = ctx.horizon ?? horizonFromTimeframe(String(ctx.timeframe));
  const contextLabel = [
    ctx.symbol,
    `TF ${ctx.timeframe}`,
    ctx.periodLabel,
    ctx.profileName ? `perfil ${ctx.profileName}` : null,
    `horizonte ${horizon}`,
    ctx.riskTolerance ? `riesgo ${ctx.riskTolerance}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const ok = rows.filter((r) => r.status === 'ok');
  if (ok.length === 0) {
    return {
      headline: `${ctx.symbol}: sin resultados útiles para análisis técnico del lote.`,
      analysis: ['Revisa sync OHLCV y vuelve a lanzar la batería.'],
      recommendations: [],
      outlook: ['Sincronizar el valor y repetir genéricas.'],
      disclaimer:
        'Análisis local heurístico. No es consejo de inversión ni predicción de precios.',
      contextLabel,
    };
  }

  const recommendations = rankTechnicalRecommendations(rows, ctx, 3);
  const regime = inferRegimeShift(rows, ctx.equityByRunId);
  const byReturn = [...ok].sort(
    (a, b) => (b.totalReturnPct ?? -Infinity) - (a.totalReturnPct ?? -Infinity),
  )[0];
  const top = recommendations[0];

  const ceiling = starCeilingForEvidence(ctx.evidenceLevel);
  const analysis: string[] = [
    `Criterio principal: sesgo de tendencia futura (nivel del tercio reciente), no el máximo beneficio histórico.`,
    `Evidencia del lote: ${ctx.evidenceLevel === 'lab_validated' ? 'lab validada' : 'solo in-sample'} · techo ★${ceiling}.`,
    top
      ? `Top futuro: «${top.row.label}» · ${top.stars}/5 estrellas (${top.score}/100)${
          top.starsCapped ? ' (tope por evidencia)' : ''
        }${
          byReturn && byReturn.strategyType !== top.row.strategyType
            ? ` — «${byReturn.label}» ganó más en total (${(byReturn.totalReturnPct ?? 0).toFixed(1)}%) pero no manda a futuro.`
            : '.'
        }`
      : 'Sin recomendación.',
    `Escala ${ctx.timeframe} → horizonte «${horizon}»; familias preferidas: ${preferredCategories(horizon).join(', ')}.`,
  ];
  if (regime) {
    analysis.push(regime.narrative);
  }

  const familyCounts = new Map<string, number>();
  for (const r of recommendations) {
    familyCounts.set(r.row.categoryLabel, (familyCounts.get(r.row.categoryLabel) ?? 0) + 1);
  }
  if (familyCounts.size > 0) {
    analysis.push(
      `Top-3 por familias: ${[...familyCounts.entries()]
        .map(([k, v]) => `${k}×${v}`)
        .join(', ')}.`,
    );
  }

  return {
    headline: top
      ? `${ctx.symbol}: a futuro prioriza «${top.row.label}» (${top.stars}★) — no el ranking de rentabilidad total.`
      : `${ctx.symbol}: lote evaluado sin candidato claro.`,
    analysis,
    recommendations,
    regime,
    outlook: buildOutlook(recommendations, regime, ctx),
    disclaimer:
      ceiling <= 3
        ? 'Motor AT local (hechos + techo ★3 in-sample). La lectura IA es narrador, no oráculo. No es consejo de inversión.'
        : 'Motor AT local + evidencia lab. La lectura IA narra hechos; no declara edge futuro. No es consejo de inversión.',
    contextLabel,
  };
}

/** Exportado para el pipeline de doble auditoría (misma narrativa base). */
export function composeDeepTechnicalCoachNote(opts: {
  rows: ExplorePresetRow[];
  ctx: DeepCoachContext;
  recommendations: TechnicalRecommendation[];
  audit?: CoachAuditResultV1;
}): DeepTechnicalCoachNote {
  const { rows, ctx, recommendations, audit } = opts;
  const horizon = ctx.horizon ?? horizonFromTimeframe(String(ctx.timeframe));
  const contextLabel = [
    ctx.symbol,
    `TF ${ctx.timeframe}`,
    ctx.periodLabel,
    ctx.profileName ? `perfil ${ctx.profileName}` : null,
    `horizonte ${horizon}`,
    ctx.riskTolerance ? `riesgo ${ctx.riskTolerance}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const ok = rows.filter((r) => r.status === 'ok');
  if (ok.length === 0) {
    return {
      headline: `${ctx.symbol}: sin resultados útiles para análisis técnico del lote.`,
      analysis: ['Revisa sync OHLCV y vuelve a lanzar la batería.'],
      recommendations: [],
      outlook: ['Sincronizar el valor y repetir genéricas.'],
      disclaimer:
        'Análisis local heurístico. No es consejo de inversión ni predicción de precios.',
      contextLabel,
      audit,
    };
  }

  const regime = inferRegimeShift(rows, ctx.equityByRunId);
  const byReturn = [...ok].sort(
    (a, b) => (b.totalReturnPct ?? -Infinity) - (a.totalReturnPct ?? -Infinity),
  )[0];
  const top = recommendations[0];
  const ceiling = starCeilingForEvidence(ctx.evidenceLevel);

  const analysis: string[] = [
    `Criterio: ranking local (A) + auditor heurístico (B) + gate. Sesgo a futuro = nivel del tramo reciente.`,
    `Evidencia: ${ctx.evidenceLevel === 'lab_validated' ? 'lab validada' : 'solo in-sample'} · techo ★${ceiling}${
      audit ? ` · confianza «${audit.confidence}»` : ''
    }.`,
    top
      ? `Top futuro: «${top.row.label}» · ${top.stars}/5 (${top.score}/100)${
          top.starsCapped ? ' (tope evidencia)' : ''
        }${
          byReturn && byReturn.strategyType !== top.row.strategyType
            ? ` — «${byReturn.label}» ganó más en total pero no manda a futuro.`
            : '.'
        }`
      : 'Sin recomendación tras auditoría (vetos / challenge).',
    `Escala ${ctx.timeframe} → horizonte «${horizon}»; familias: ${preferredCategories(horizon).join(', ')}.`,
  ];
  if (audit?.shadowDisagreement && audit.shadowTopType) {
    analysis.push(
      `Discrepancia shadow A2: preferiría «${audit.shadowTopType}» — el gate no corona a ciegas.`,
    );
  }
  const vetos = audit?.findings.filter((f) => f.action === 'veto') ?? [];
  if (vetos.length > 0) {
    analysis.push(`Auditor B vetó: ${vetos.map((v) => `${v.strategyType} (${v.code})`).join(', ')}.`);
  }
  if (regime) analysis.push(regime.narrative);

  const familyCounts = new Map<string, number>();
  for (const r of recommendations) {
    familyCounts.set(r.row.categoryLabel, (familyCounts.get(r.row.categoryLabel) ?? 0) + 1);
  }
  if (familyCounts.size > 0) {
    analysis.push(
      `Top-3 por familias: ${[...familyCounts.entries()]
        .map(([k, v]) => `${k}×${v}`)
        .join(', ')}.`,
    );
  }

  return {
    headline: top
      ? `${ctx.symbol}: a futuro prioriza «${top.row.label}» (${top.stars}★) — auditado.`
      : `${ctx.symbol}: lote evaluado sin candidato claro tras auditoría.`,
    analysis,
    recommendations,
    regime,
    outlook: buildOutlook(recommendations, regime, ctx),
    disclaimer:
      ceiling <= 3
        ? 'Motor AT local + auditor B (techo ★3 in-sample). La IA puede vetar tipado; no es oráculo. No es consejo de inversión.'
        : 'Motor AT local + evidencia lab + auditor B. No declara edge futuro. No es consejo de inversión.',
    contextLabel,
    audit,
  };
}

export function buildCoachFacts(
  rows: ExplorePresetRow[],
  ctx: DeepCoachContext,
  note?: DeepTechnicalCoachNote,
): CoachFactsV1 {
  const built = note ?? buildDeepTechnicalCoachNote(rows, ctx);
  const horizon = ctx.horizon ?? horizonFromTimeframe(String(ctx.timeframe));
  const evidenceLevel = ctx.evidenceLevel ?? 'in_sample_only';
  const ok = rows.filter((r) => r.status === 'ok');
  const buyHold =
    ok.map((r) => r.buyHoldReturnPct).find((v) => v != null && Number.isFinite(v)) ?? null;
  return {
    schemaVersion: '1.0.0',
    symbol: ctx.symbol,
    timeframe: String(ctx.timeframe),
    periodLabel: ctx.periodLabel,
    horizon,
    riskTolerance: ctx.riskTolerance ?? null,
    evidenceLevel,
    starCeiling: starCeilingForEvidence(evidenceLevel),
    buyHoldReturnPct: buyHold,
    okCount: ok.length,
    windows: {
      earlyBestLabel: built.regime?.earlyBest?.label,
      lateBestLabel: built.regime?.lateBest?.label,
      shifted: built.regime?.shifted ?? false,
      narrative: built.regime?.narrative ?? 'Sin ventanas de equity suficientes.',
    },
    recommendations: built.recommendations.map((r) => ({
      rank: r.rank,
      strategyType: r.row.strategyType,
      label: r.row.label,
      category: r.row.category,
      score: r.score,
      stars: r.stars,
      starsCapped: Boolean(r.starsCapped),
      totalReturnPct: r.row.totalReturnPct,
      excessReturnPct: r.row.excessReturnPct ?? null,
      maxDrawdownPct: r.row.maxDrawdownPct,
      earlyReturnPct: r.earlyReturnPct ?? null,
      midReturnPct: r.midReturnPct ?? null,
      lateReturnPct: r.lateReturnPct ?? null,
      usedSoftFallback: Boolean(r.usedSoftFallback),
      qualityFlagged: Boolean(r.qualityFlagged),
      runId: r.row.runId,
    })),
  };
}

export type LlmDeepCoachPayload = {
  headline?: string;
  analysis?: string[];
  recommendations?: Array<{
    label?: string;
    strategyType?: string;
    score?: number;
    reasons?: string[];
  }>;
  regimeNarrative?: string;
  outlook?: string[];
  disclaimer?: string;
  /** Veto/downgrade tipado (Fase 1 — no reordena). */
  audit?: {
    findings?: Array<{
      strategyType?: string;
      action?: string;
      code?: string;
      reason?: string;
    }>;
  };
};

/**
 * Fusiona narrativa LLM. Si hay `llmFindings` / audit en payload, el caller debe
 * reconstruir el TOP con `buildAuditedDeepTechnicalCoachNote(..., llmFindings)`.
 * Aquí solo se mezcla prosa (headline/analysis/outlook).
 */
export function mergeLlmIntoDeepCoach(
  local: DeepTechnicalCoachNote,
  llm: LlmDeepCoachPayload | null | undefined,
): DeepTechnicalCoachNote {
  if (!llm) return local;
  const analysis =
    Array.isArray(llm.analysis) && llm.analysis.length > 0
      ? [...llm.analysis, ...local.analysis.slice(0, 2)]
      : local.analysis;
  const outlook =
    Array.isArray(llm.outlook) && llm.outlook.length > 0 ? llm.outlook : local.outlook;
  const regime = local.regime
    ? {
        ...local.regime,
        narrative: llm.regimeNarrative?.trim() || local.regime.narrative,
      }
    : llm.regimeNarrative
      ? {
          label: 'Lectura de régimen (IA)',
          shifted: true,
          narrative: llm.regimeNarrative,
        }
      : undefined;

  return {
    ...local,
    headline: llm.headline?.trim() || local.headline,
    analysis,
    outlook,
    regime,
    disclaimer: llm.disclaimer?.trim() || local.disclaimer,
  };
}

export function equityMapFromDetails(
  details: Array<BacktestRunDetailDto | undefined | null>,
): Record<string, BacktestEquityPointDto[] | undefined> {
  const map: Record<string, BacktestEquityPointDto[] | undefined> = {};
  for (const d of details) {
    if (!d?.id) continue;
    map[d.id] = d.equityCurve;
  }
  return map;
}
