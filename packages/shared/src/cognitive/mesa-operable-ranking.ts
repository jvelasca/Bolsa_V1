/**
 * V1.19 — ranking operable de presentación (no nuevo motor cognitivo).
 */

import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";

const STATUS_WEIGHT: Record<TradePlanStatusV1, number> = {
  TRIGGERED: 100,
  ARMED: 70,
  WATCH: 40,
  BLOCKED: 0,
  EXPIRED: -10,
};

export type MesaOperableScoreV1 = {
  symbol: string;
  operationalScore: number;
  qualityScore: number;
  operable: boolean;
  blockReasons: string[];
};

export function scoreMesaCandidateOperable(
  row: MesaCandidateRowV1,
  entriesBlocked: boolean,
): MesaOperableScoreV1 {
  const study = row.study;
  const qualityScore = study?.strength ?? 0;
  const statusW = STATUS_WEIGHT[row.status] ?? 0;
  const hasPlan = study?.hasOperationalPlan === true;
  const rr = study?.expectedRR ?? 0;

  const blockReasons: string[] = [];
  if (entriesBlocked) blockReasons.push("Entradas bloqueadas");
  if (row.status === "BLOCKED") blockReasons.push("Gate bloqueado");
  if (row.status === "EXPIRED") blockReasons.push("Plan caducado");
  if (!hasPlan) blockReasons.push("Sin plan operativo");
  if (row.gate === "VETO") blockReasons.push("Veto de apertura");

  const operable =
    blockReasons.length === 0 && row.status === "TRIGGERED" && hasPlan;

  const operationalScore =
    statusW +
    qualityScore * 5 +
    (hasPlan ? 10 : 0) +
    Math.min(rr * 3, 15) -
    (entriesBlocked ? 50 : 0);

  return {
    symbol: row.symbol,
    operationalScore: Math.round(operationalScore * 10) / 10,
    qualityScore,
    operable,
    blockReasons,
  };
}

export function sortMesaCandidatesOperable(
  rows: MesaCandidateRowV1[],
  entriesBlocked: boolean,
): Array<MesaCandidateRowV1 & { operableScore: MesaOperableScoreV1 }> {
  return rows
    .map((row) => ({
      ...row,
      operableScore: scoreMesaCandidateOperable(row, entriesBlocked),
    }))
    .sort((a, b) => {
      if (a.operableScore.operable !== b.operableScore.operable) {
        return a.operableScore.operable ? -1 : 1;
      }
      return (
        b.operableScore.operationalScore - a.operableScore.operationalScore
      );
    });
}

export type MesaWhatIfProjectionV1 = {
  symbol: string;
  currentRiskR: number | null;
  projectedRiskR: number | null;
  currentExposurePct: number | null;
  projectedExposurePct: number | null;
  riskDeltaR: number | null;
  warnings: string[];
};

export function projectMesaWhatIf(input: {
  symbol: string;
  candidateRiskAmount?: number | null;
  candidateRiskR?: number | null;
  portfolioRiskR?: number | null;
  equity?: number | null;
  cash?: number | null;
  candidateNotional?: number | null;
}): MesaWhatIfProjectionV1 {
  const warnings: string[] = [];
  const currentRiskR = input.portfolioRiskR ?? null;
  const addR = input.candidateRiskR ?? null;
  let projectedRiskR: number | null = null;
  if (currentRiskR != null && addR != null) {
    projectedRiskR = Math.round((currentRiskR + addR) * 100) / 100;
  } else if (addR != null) {
    projectedRiskR = addR;
  }

  let currentExposurePct: number | null = null;
  let projectedExposurePct: number | null = null;
  const equity = input.equity;
  const cash = input.cash;
  const notional = input.candidateNotional;
  if (equity != null && equity > 0 && cash != null) {
    currentExposurePct = Math.round(((equity - cash) / equity) * 1000) / 10;
    if (notional != null) {
      projectedExposurePct =
        Math.round(((equity - cash + notional) / equity) * 1000) / 10;
      if (projectedExposurePct > 100) {
        warnings.push("Exposición proyectada > 100%");
      }
    }
  }

  if (projectedRiskR != null && projectedRiskR > 5) {
    warnings.push("Riesgo agregado elevado (>5R)");
  }

  return {
    symbol: input.symbol,
    currentRiskR,
    projectedRiskR,
    currentExposurePct,
    projectedExposurePct,
    riskDeltaR:
      currentRiskR != null && projectedRiskR != null
        ? Math.round((projectedRiskR - currentRiskR) * 100) / 100
        : addR,
    warnings,
  };
}
