/**
 * Operational Priority Projection — orden provisional heurístico (no score definitivo).
 */

import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";

export { projectMesaWhatIf } from "./portfolio-scenario.js";

const STATUS_WEIGHT: Record<TradePlanStatusV1, number> = {
  TRIGGERED: 100,
  ARMED: 70,
  WATCH: 40,
  BLOCKED: 0,
  EXPIRED: -10,
};

export type OperationalPriorityProjectionV1 = {
  symbol: string;
  projectionScore: number;
  qualityScore: number;
  operable: boolean;
  blockReasons: string[];
  provisional: true;
};

export type MesaOperableScoreV1 = OperationalPriorityProjectionV1 & {
  /** @deprecated Usar projectionScore */
  operationalScore: number;
};

export type MesaWhatIfProjectionV1 = {
  symbol: string;
  currentRiskR: number | null;
  projectedRiskR: number | null;
  currentExposurePct: number | null;
  projectedExposurePct: number | null;
  riskDeltaR: number | null;
  warnings: string[];
  riskLimitR: number;
};

export function scoreOperationalPriorityProjection(
  row: MesaCandidateRowV1,
  entriesBlocked: boolean,
): OperationalPriorityProjectionV1 {
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

  const projectionScore =
    statusW +
    qualityScore * 5 +
    (hasPlan ? 10 : 0) +
    Math.min(rr * 3, 15) -
    (entriesBlocked ? 50 : 0);

  return {
    symbol: row.symbol,
    projectionScore: Math.round(projectionScore * 10) / 10,
    qualityScore,
    operable,
    blockReasons,
    provisional: true,
  };
}

/** @deprecated Usar scoreOperationalPriorityProjection */
export function scoreMesaCandidateOperable(
  row: MesaCandidateRowV1,
  entriesBlocked: boolean,
): MesaOperableScoreV1 {
  const p = scoreOperationalPriorityProjection(row, entriesBlocked);
  return { ...p, operationalScore: p.projectionScore };
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
      return b.operableScore.projectionScore - a.operableScore.projectionScore;
    });
}
