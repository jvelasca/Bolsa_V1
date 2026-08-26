/**
 * Mesa · Hoy — honestidad PLAN / PROPUESTA / EJECUTADO (V1.16).
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { ProtectPlanV1 } from "./protect-plan.js";

export type MesaProtectionLayerV1 = "plan" | "proposal" | "executed";

export type MesaProtectionLineV1 = {
  layer: MesaProtectionLayerV1;
  label: string;
  value: number | null;
  formatted: string;
};

export type MesaProtectionStateV1 = {
  plan: MesaProtectionLineV1;
  proposal: MesaProtectionLineV1;
  executed: MesaProtectionLineV1;
  /** true cuando hay plan/propuesta pero no stop ejecutado confirmado. */
  discrepancy: boolean;
  summaryLabel: string;
};

function line(
  layer: MesaProtectionLayerV1,
  label: string,
  value: number | null,
): MesaProtectionLineV1 {
  return {
    layer,
    label,
    value,
    formatted: value != null && Number.isFinite(value) ? String(value) : "—",
  };
}

export type BuildMesaProtectionStateInput = {
  study?: Pick<
    DecisionJournalStudyViewV1,
    "hasOperationalPlan" | "stop"
  > | null;
  exitSuggestedStop?: number | null;
  currentStop?: number | null;
  protectPlan?: Pick<ProtectPlanV1, "status" | "suggestedProtectStop"> | null;
  /** PH-1 — último persist de protección en Confirm. */
  persistSkipped?: boolean;
};

export function buildMesaProtectionState(
  input: BuildMesaProtectionStateInput,
): MesaProtectionStateV1 {
  const planStop =
    input.study?.hasOperationalPlan && input.study.stop != null
      ? input.study.stop
      : (input.exitSuggestedStop ?? null);

  const proposalStop =
    input.protectPlan?.status === "protect_hint"
      ? (input.protectPlan.suggestedProtectStop ?? null)
      : null;

  const executedStop = input.currentStop ?? null;

  const hasPlan = planStop != null;
  const hasProposal = proposalStop != null;
  const hasExecuted = executedStop != null;

  let discrepancy = false;
  if (input.persistSkipped) {
    discrepancy = true;
  } else if (hasProposal && !hasExecuted) {
    discrepancy = true;
  } else if (
    hasPlan &&
    hasExecuted &&
    planStop != null &&
    executedStop != null &&
    Math.abs(planStop - executedStop) > 0.0001
  ) {
    discrepancy = false;
  }

  let summaryLabel = "Sin protección";
  if (discrepancy) {
    summaryLabel = "Discrepancia";
  } else if (hasExecuted) {
    summaryLabel = "Confirmada";
  } else if (hasProposal) {
    summaryLabel = "Planificada";
  } else if (hasPlan) {
    summaryLabel = "Plan";
  }

  return {
    plan: line("plan", "Plan", planStop),
    proposal: line("proposal", "Propuesta", proposalStop),
    executed: line("executed", "Ejecutado", executedStop),
    discrepancy,
    summaryLabel,
  };
}

/** Distancia % al stop (planificado o ejecutado), etiquetada. */
export function stopDistancePct(
  lastPrice: number | null | undefined,
  stop: number | null | undefined,
): number | null {
  if (
    lastPrice == null ||
    stop == null ||
    !Number.isFinite(lastPrice) ||
    !Number.isFinite(stop) ||
    lastPrice <= 0
  ) {
    return null;
  }
  return Math.round(((lastPrice - stop) / lastPrice) * 1000) / 10;
}
