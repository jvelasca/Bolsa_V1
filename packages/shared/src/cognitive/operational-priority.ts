/**
 * Operational Priority 2.0 — Quality × Suitability × Operability.
 * La heurística legacy queda como projection fallback.
 */

import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";
import {
  scoreOperationalPriorityProjection,
  type OperationalPriorityProjectionV1,
} from "./mesa-operable-ranking.js";
import type { PortfolioRiskSnapshotV1 } from "./portfolio-risk-metrics.js";

export type QualityScoreV1 = {
  value: number;
  label: string;
  factors: string[];
};

export type SuitabilityScoreV1 = {
  value: number;
  label: string;
  factors: string[];
};

export type OperabilityScoreV1 = {
  value: number;
  label: string;
  operable: boolean;
  blockReasons: string[];
};

export type OperationalPriorityV1 = {
  symbol: string;
  quality: QualityScoreV1;
  suitability: SuitabilityScoreV1;
  operability: OperabilityScoreV1;
  priorityScore: number;
  verdict: "OPERABLE" | "NO_OPERAR" | "WATCH";
  projection: OperationalPriorityProjectionV1;
};

export type PortfolioContextForPriorityV1 = {
  entriesBlocked?: boolean;
  portfolioRisk?: PortfolioRiskSnapshotV1 | null;
  sectorExposurePct?: Record<string, number>;
  maxSectorExposurePct?: number;
  candidateSector?: string | null;
  /** Sector por instrumentId — usado en sort de lista. */
  sectorByInstrumentId?: Record<string, string | null | undefined>;
};

const STATUS_OPERABILITY: Record<TradePlanStatusV1, number> = {
  TRIGGERED: 90,
  ARMED: 60,
  WATCH: 30,
  BLOCKED: 0,
  EXPIRED: 0,
};

function scoreQuality(row: MesaCandidateRowV1): QualityScoreV1 {
  const study = row.study;
  const factors: string[] = [];
  let value = 0;

  const strength = study?.strength ?? 0;
  value += Math.min(strength * 10, 50);
  if (strength > 0) factors.push(`Strength ${strength.toFixed(1)}`);

  const rr = study?.expectedRR ?? 0;
  value += Math.min(rr * 8, 24);
  if (rr > 0) factors.push(`R/R 1:${rr.toFixed(1)}`);

  if (study?.hasOperationalPlan) {
    value += 15;
    factors.push("Plan operativo");
  }

  if (row.status === "TRIGGERED") {
    value += 10;
    factors.push("Trigger alcanzado");
  }

  value = Math.min(100, Math.round(value));

  let label = "Media";
  if (value >= 75) label = "Alta";
  else if (value < 45) label = "Baja";

  return { value, label, factors };
}

function scoreSuitability(
  row: MesaCandidateRowV1,
  ctx: PortfolioContextForPriorityV1,
): SuitabilityScoreV1 {
  const factors: string[] = [];
  let value = 70;

  const sector = ctx.candidateSector?.trim();
  if (!sector) {
    value -= 15;
    factors.push("Sector desconocido");
    const unknownPct = ctx.sectorExposurePct?.Unknown ?? 0;
    if (unknownPct > 0) {
      value -= 10;
      factors.push(`Cartera con Unknown ${unknownPct}%`);
    }
  } else if (ctx.sectorExposurePct) {
    const current = ctx.sectorExposurePct[sector] ?? 0;
    const max = ctx.maxSectorExposurePct ?? 40;
    if (current >= max) {
      value -= 40;
      factors.push(`Sector ${sector} saturado (${current}%)`);
    } else if (current >= max * 0.75) {
      value -= 20;
      factors.push(`Sector ${sector} elevado (${current}%)`);
    } else {
      factors.push(`Sector ${sector} OK`);
    }
  }

  const openRisk = ctx.portfolioRisk?.portfolioOpenRiskR;
  const limit = ctx.portfolioRisk?.portfolioRiskLimitR ?? 5;
  if (openRisk != null && openRisk >= limit * 0.8) {
    value -= 25;
    factors.push(`Riesgo cartera ${openRisk}R / ${limit}R`);
  }

  if (row.gate === "VETO") {
    value -= 30;
    factors.push("Veto portfolio fit");
  }

  value = Math.max(0, Math.min(100, Math.round(value)));

  let label = "Encaja";
  if (value < 50) label = "No encaja";
  else if (value < 65) label = "Parcial";

  return { value, label, factors };
}

function scoreOperability(
  row: MesaCandidateRowV1,
  entriesBlocked: boolean,
): OperabilityScoreV1 {
  const projection = scoreOperationalPriorityProjection(row, entriesBlocked);
  const statusW = STATUS_OPERABILITY[row.status] ?? 0;
  let value = statusW;
  if (projection.operable) value = Math.max(value, 85);
  if (entriesBlocked) value = Math.min(value, 20);

  return {
    value,
    label: projection.operable ? "Ejecutable" : "No ejecutable",
    operable: projection.operable,
    blockReasons: projection.blockReasons,
  };
}

export function computeOperationalPriority(
  row: MesaCandidateRowV1,
  ctx: PortfolioContextForPriorityV1 = {},
): OperationalPriorityV1 {
  const entriesBlocked = ctx.entriesBlocked ?? false;
  const candidateSector =
    ctx.candidateSector ??
    (row.instrumentId ? ctx.sectorByInstrumentId?.[row.instrumentId] : null) ??
    null;
  const ctxWithSector: PortfolioContextForPriorityV1 = {
    ...ctx,
    candidateSector,
  };
  const quality = scoreQuality(row);
  const suitability = scoreSuitability(row, ctxWithSector);
  const operability = scoreOperability(row, entriesBlocked);
  const projection = scoreOperationalPriorityProjection(row, entriesBlocked);

  const priorityScore = Math.round(
    quality.value * 0.35 + suitability.value * 0.35 + operability.value * 0.3,
  );

  let verdict: OperationalPriorityV1["verdict"] = "WATCH";
  if (operability.operable && suitability.value >= 50 && quality.value >= 45) {
    verdict = "OPERABLE";
  } else if (quality.value >= 70 && suitability.value < 50) {
    verdict = "NO_OPERAR";
  } else if (!operability.operable) {
    verdict = "NO_OPERAR";
  }

  return {
    symbol: row.symbol,
    quality,
    suitability,
    operability,
    priorityScore,
    verdict,
    projection,
  };
}

export function sortByOperationalPriority(
  rows: MesaCandidateRowV1[],
  ctx: PortfolioContextForPriorityV1 = {},
): Array<MesaCandidateRowV1 & { operationalPriority: OperationalPriorityV1 }> {
  return rows
    .map((row) => ({
      ...row,
      operationalPriority: computeOperationalPriority(row, ctx),
    }))
    .sort((a, b) => {
      const va = a.operationalPriority;
      const vb = b.operationalPriority;
      if (va.verdict !== vb.verdict) {
        const order = { OPERABLE: 0, WATCH: 1, NO_OPERAR: 2 };
        return order[va.verdict] - order[vb.verdict];
      }
      return vb.priorityScore - va.priorityScore;
    });
}
