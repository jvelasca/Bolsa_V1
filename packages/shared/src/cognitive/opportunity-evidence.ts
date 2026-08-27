/**
 * OpportunityEvidence — Quality pura read-only (ADR-039 / RFC-008).
 *
 * Responde: ¿hay setup interesante? ≠ permiso ≠ BUY ≠ score definitivo.
 * Distinto de Operational Priority (Quality×Suitability×Operability) y del
 * emisor Python `build_opportunity_package` (spine Runtime).
 *
 * Freeze: Ranking≠BUY · Confirm=firma · Opportunity≠Permission ·
 * PAPER_D_EXECUTE off · AUTO off · provisional.
 *
 * V1.19: Quality 0–100 = strength (máx 60) + R/R (máx 40). Sin TRIGGERED/hasPlan.
 */

import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import type { PortfolioRiskSnapshotV1 } from "./portfolio-risk-metrics.js";
import type { TradePlanV1 } from "./trade-plan.js";

/** Shape compatible con QualityScoreV1 — evita ciclo con operational-priority. */
export type OpportunityQualityScoreV1 = {
  value: number;
  label: string;
  factors: string[];
};

/** Evidencia de oportunidad — solo tesis/setup; sin action/BUY/permission. */
export type OpportunityEvidenceV1 = {
  symbol: string;
  /** Strength de estudio (0–10 típico); 0 si ausente. */
  strength: number;
  /** R/R esperado del setup; null si no hay dato. */
  expectedRR: number | null;
  /** Factores de Quality pura (strength + R/R). Sin TRIGGERED/hasPlan. */
  factors: string[];
  /** Etiqueta provisional de calidad (Excelente…No atractiva). */
  label: string;
  /** Composite 0–100 solo strength+RR; no es score definitivo. */
  qualityValue: number;
  provisional: true;
};

/**
 * Proyección informativa “best next R” entre candidatos.
 * Ordena por reward esperado en R; **no** implica operable ni permiso.
 */
export type BestNextRCandidateV1 = {
  symbol: string;
  expectedRR: number | null;
  initialRiskR: number | null;
  /** expectedRR × initialRiskR cuando ambos son finitos > 0; si no, null. */
  expectedRewardR: number | null;
  rank: number;
};

export type BestNextRProjectionV1 = {
  ordered: BestNextRCandidateV1[];
  bestSymbol: string | null;
  provisional: true;
  /** Semántica explícita: orden informativo ≠ ejecutable. */
  impliesOperable: false;
  /** Riesgo abierto de cartera (contexto); no veta ni autoriza. */
  portfolioOpenRiskR: number | null;
  portfolioRiskLimitR: number | null;
};

export type BestNextRContextV1 = {
  portfolioRisk?: PortfolioRiskSnapshotV1 | null;
  /**
   * TradePlan vivo por símbolo (opcional). Si falta, se usa study del row.
   * No sustituye Operability ni check_opening.
   */
  tradePlanBySymbol?: Record<
    string,
    Pick<TradePlanV1, "expectedRR" | "initialRiskR"> | null
  >;
};

function finiteNonNeg(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n >= 0;
}

function finitePositive(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

/** Bandas honestas 0–100 (solo strength + R/R). */
export function opportunityQualityLabel(qualityValue: number): string {
  if (qualityValue >= 90) return "Excelente";
  if (qualityValue >= 80) return "Alta";
  if (qualityValue >= 70) return "Buena";
  if (qualityValue >= 60) return "Débil";
  return "No atractiva";
}

/**
 * Quality pura: strength (máx 60) + expectedRR (máx 40).
 * NO usa TRIGGERED / hasOperationalPlan (eso es Operability).
 * Escala 0–100 para que las bandas Excelente/Alta sean alcanzables.
 */
export function projectOpportunityEvidence(
  row: MesaCandidateRowV1,
): OpportunityEvidenceV1 {
  const study = row.study;
  const strength = finiteNonNeg(study?.strength) ? study.strength : 0;
  const expectedRR = finitePositive(study?.expectedRR)
    ? study.expectedRR
    : null;

  const factors: string[] = [];
  let qualityValue = 0;

  // strength 0–10 → hasta 60
  qualityValue += Math.min(strength * 6, 60);
  if (strength > 0) factors.push(`Strength ${strength.toFixed(1)}`);

  // R/R → hasta 40 (R/R 4.0 = techo)
  if (expectedRR != null) {
    qualityValue += Math.min(expectedRR * 10, 40);
    factors.push(`R/R 1:${expectedRR.toFixed(1)}`);
  }

  qualityValue = Math.min(100, Math.round(qualityValue));
  const label = opportunityQualityLabel(qualityValue);

  return {
    symbol: row.symbol,
    strength,
    expectedRR,
    factors,
    label,
    qualityValue,
    provisional: true,
  };
}

/**
 * Thin adapter: QualityScoreV1 lee OpportunityEvidence.
 * Pesos Priority 35/35/30 intactos; Operability sigue aparte.
 */
export function qualityScoreFromOpportunityEvidence(
  evidence: OpportunityEvidenceV1,
): OpportunityQualityScoreV1 {
  return {
    value: evidence.qualityValue,
    label: evidence.label,
    factors: [...evidence.factors],
  };
}

function planOrStudyMetrics(
  row: MesaCandidateRowV1,
  ctx: BestNextRContextV1,
): { expectedRR: number | null; initialRiskR: number | null } {
  const fromPlan = ctx.tradePlanBySymbol?.[row.symbol];
  const expectedRR = finitePositive(fromPlan?.expectedRR)
    ? fromPlan.expectedRR
    : finitePositive(row.study?.expectedRR)
      ? row.study!.expectedRR
      : null;
  const initialRiskR = finitePositive(fromPlan?.initialRiskR)
    ? fromPlan.initialRiskR
    : finitePositive(row.study?.initialRiskR)
      ? row.study!.initialRiskR
      : null;
  return { expectedRR, initialRiskR };
}

/**
 * Orden informativo por R esperado (reward en R).
 * No implica operable / permiso / BUY.
 */
export function projectBestNextR(
  rows: ReadonlyArray<MesaCandidateRowV1>,
  ctx: BestNextRContextV1 = {},
): BestNextRProjectionV1 {
  const scored = rows.map((row) => {
    const { expectedRR, initialRiskR } = planOrStudyMetrics(row, ctx);
    const expectedRewardR =
      expectedRR != null && initialRiskR != null
        ? Math.round(expectedRR * initialRiskR * 100) / 100
        : null;
    return {
      symbol: row.symbol,
      expectedRR,
      initialRiskR,
      expectedRewardR,
      strength: finiteNonNeg(row.study?.strength) ? row.study!.strength : 0,
    };
  });

  scored.sort((a, b) => {
    const ra = a.expectedRewardR;
    const rb = b.expectedRewardR;
    if (ra != null && rb != null && ra !== rb) return rb - ra;
    if (ra != null && rb == null) return -1;
    if (ra == null && rb != null) return 1;
    const rra = a.expectedRR ?? -1;
    const rrb = b.expectedRR ?? -1;
    if (rra !== rrb) return rrb - rra;
    return b.strength - a.strength;
  });

  const ordered: BestNextRCandidateV1[] = scored.map((s, i) => ({
    symbol: s.symbol,
    expectedRR: s.expectedRR,
    initialRiskR: s.initialRiskR,
    expectedRewardR: s.expectedRewardR,
    rank: i + 1,
  }));

  const best =
    ordered.find((c) => c.expectedRewardR != null || c.expectedRR != null) ??
    null;

  return {
    ordered,
    bestSymbol: best?.symbol ?? null,
    provisional: true,
    impliesOperable: false,
    portfolioOpenRiskR: ctx.portfolioRisk?.portfolioOpenRiskR ?? null,
    portfolioRiskLimitR: ctx.portfolioRisk?.portfolioRiskLimitR ?? null,
  };
}
