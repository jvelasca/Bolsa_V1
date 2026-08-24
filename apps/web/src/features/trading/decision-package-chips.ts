/**
 * U4 — mappers puros: acción DecisionPackage + Fit PASS/VETO para chips de mesa.
 *
 * No inventa Fit: sin dato explícito → null (UI neutra).
 * Fuentes: package blob · policyGate · gate del dictamen (opening/gateStatus).
 */

import type { DecisionAction } from "@bolsa/shared";

const DECISION_ACTIONS = new Set<DecisionAction>([
  "recommend_long",
  "recommend_short",
  "wait",
  "reduce",
  "exit_hint",
]);

/** Etiquetas compactas (vocabulario package; visibles en chart/Operativa). */
export const DECISION_ACTION_CHIP_LABEL: Record<DecisionAction, string> = {
  recommend_long: "LONG",
  recommend_short: "SHORT",
  wait: "WAIT",
  reduce: "REDUCE",
  exit_hint: "EXIT",
};

export const DECISION_ACTION_CHIP_TITLE: Record<DecisionAction, string> = {
  recommend_long: "Package · recommend_long (apertura larga)",
  recommend_short: "Package · recommend_short (apertura corta)",
  wait: "Package · wait (esperar)",
  reduce: "Package · reduce (reducir)",
  exit_hint: "Package · exit_hint (salida)",
};

export type FitChipStatus = "PASS" | "VETO" | "WARNING";

export type DecisionActionChipView = {
  action: DecisionAction;
  label: string;
  title: string;
};

export type FitChipView = {
  status: FitChipStatus;
  label: string;
  title: string;
};

export function parseDecisionAction(raw: unknown): DecisionAction | null {
  if (typeof raw !== "string") return null;
  return DECISION_ACTIONS.has(raw as DecisionAction)
    ? (raw as DecisionAction)
    : null;
}

/** Acción del package (preferida) o de la Recommendation en cola. */
export function resolveDecisionActionChip(input: {
  packageAction?: unknown;
  recommendationAction?: unknown;
}): DecisionActionChipView | null {
  const action =
    parseDecisionAction(input.packageAction) ??
    parseDecisionAction(input.recommendationAction);
  if (!action) return null;
  return {
    action,
    label: DECISION_ACTION_CHIP_LABEL[action],
    title: DECISION_ACTION_CHIP_TITLE[action],
  };
}

function normalizeGateToken(raw: unknown): FitChipStatus | null {
  if (typeof raw !== "string" || !raw.trim()) return null;
  const u = raw.trim().toUpperCase();
  if (u === "PASS" || u === "PASSED" || u === "ALLOW" || u === "ALLOWED") {
    return "PASS";
  }
  if (u === "VETO" || u === "FAILED" || u === "DENY" || u === "DENIED") {
    return "VETO";
  }
  if (u === "WARNING") return "WARNING";
  // SKIPPED / DEFERRED / unknown → no inventar PASS
  return null;
}

function fitView(status: FitChipStatus): FitChipView {
  if (status === "PASS") {
    return {
      status,
      label: "Fit · PASS",
      title: "Encaje / gate: PASS (permiso de apertura según datos conocidos)",
    };
  }
  if (status === "VETO") {
    return {
      status,
      label: "Fit · VETO",
      title: "Encaje / gate: VETO (apertura bloqueada según datos conocidos)",
    };
  }
  return {
    status,
    label: "Fit · AVISO",
    title: "Encaje / gate: WARNING (revisar antes de firmar)",
  };
}

/**
 * Resuelve Fit sin inventar PASS.
 * Prioridad: complianceCheck.passed → executionAllowed (solo si hay compliance) →
 * policyGate.status → opinionGateStatus.
 */
export function resolveFitChip(input: {
  compliancePassed?: boolean | null;
  executionAllowed?: boolean | null;
  hasComplianceCheck?: boolean;
  policyGateStatus?: unknown;
  opinionGateStatus?: unknown;
}): FitChipView | null {
  if (input.compliancePassed === true) return fitView("PASS");
  if (input.compliancePassed === false) return fitView("VETO");

  if (input.hasComplianceCheck) {
    if (input.executionAllowed === true) return fitView("PASS");
    if (input.executionAllowed === false) return fitView("VETO");
  }

  const fromPolicy = normalizeGateToken(input.policyGateStatus);
  if (fromPolicy) return fitView(fromPolicy);

  const fromOpinion = normalizeGateToken(input.opinionGateStatus);
  if (fromOpinion) return fitView(fromOpinion);

  return null;
}

/** Lee campos tipados desde blob `decisionPackage` + payload F3. */
export function extractPackageChipFields(payload: {
  action?: unknown;
  decisionPackage?: Record<string, unknown> | null;
  policyGate?: { status?: string | null } | null;
}): {
  packageAction: unknown;
  recommendationAction: unknown;
  compliancePassed: boolean | null;
  executionAllowed: boolean | null;
  hasComplianceCheck: boolean;
  policyGateStatus: unknown;
} {
  const pkg = payload.decisionPackage ?? null;
  const compliance = pkg?.complianceCheck;
  const hasComplianceCheck =
    compliance != null && typeof compliance === "object";
  let compliancePassed: boolean | null = null;
  if (
    hasComplianceCheck &&
    typeof (compliance as { passed?: unknown }).passed === "boolean"
  ) {
    compliancePassed = (compliance as { passed: boolean }).passed;
  }
  const executionAllowed =
    typeof pkg?.executionAllowed === "boolean" ? pkg.executionAllowed : null;

  return {
    packageAction: pkg?.action,
    recommendationAction: payload.action,
    compliancePassed,
    executionAllowed,
    hasComplianceCheck,
    policyGateStatus: payload.policyGate?.status ?? null,
  };
}

export function pickQueueItemForInstrument<
  T extends {
    id: string;
    payload: { instrumentId?: string };
  },
>(
  items: T[],
  instrumentId: string | null | undefined,
  activeId?: string | null,
): T | null {
  if (!instrumentId || items.length === 0) return null;
  const forInstrument = items.filter(
    (it) => it.payload.instrumentId === instrumentId,
  );
  if (forInstrument.length === 0) return null;
  if (activeId) {
    const active = forInstrument.find((it) => it.id === activeId);
    if (active) return active;
  }
  return forInstrument[0] ?? null;
}
