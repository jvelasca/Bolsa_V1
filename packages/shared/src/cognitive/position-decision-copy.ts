/**
 * Copy humano para PositionDecision (V1.36 Daily Operating UI).
 * Proyección read-only; no es permiso ni firma.
 */

import type {
  PositionDecisionActionV1,
  PositionDecisionV1,
  PositionNextEventV1,
  PositionProtectionV1,
} from "./position-decision.js";

export type PositionExitCtaKindV1 =
  | "maintain"
  | "protect"
  | "reduce"
  | "exit"
  | "review";

export type PositionOperatingCtaV1 = {
  kind: PositionExitCtaKindV1;
  label: string;
};

/** CTA principal sugerida por PositionDecision (≠ permiso). */
export function primaryPositionExitCta(
  decision: PositionDecisionV1,
): PositionExitCtaKindV1 {
  if (decision.reconHealth === "CRITICAL") return "review";
  switch (decision.action) {
    case "HOLD":
      return "maintain";
    case "PROTECT":
      return "protect";
    case "REDUCE":
    case "TAKE_PROFIT":
      return "reduce";
    case "EXIT":
      return "exit";
    case "REVIEW":
      return "review";
    default:
      return "maintain";
  }
}

export function isPrimaryPositionExitCta(
  decision: PositionDecisionV1,
  kind: PositionExitCtaKindV1,
): boolean {
  return primaryPositionExitCta(decision) === kind;
}

export const POSITION_DECISION_ACTION_LABEL: Record<
  PositionExitCtaKindV1,
  string
> = {
  maintain: "Mantener",
  protect: "Proteger",
  reduce: "Reducir",
  exit: "Salir",
  review: "Revisar",
};

export function formatPositionDecisionActionLabel(
  decision: PositionDecisionV1,
): string {
  return positionOperatingCtaFromDecision(decision).label;
}

/** CTA canónica de posición abierta — alineada a `decision.action` (V1.39). */
export function positionOperatingCtaFromDecision(
  decision: PositionDecisionV1,
): PositionOperatingCtaV1 {
  const kind = primaryPositionExitCta(decision);
  return {
    kind,
    label: POSITION_DECISION_ACTION_LABEL[kind],
  };
}

export const NEXT_EVENT_LABEL: Record<PositionNextEventV1, string> = {
  NONE: "Ninguno pendiente",
  T1: "T1",
  T2: "T2",
  STOP: "Stop estructural",
  TRAIL: "Trailing",
  THESIS_REVIEW: "Revisar tesis",
  RECONCILIATION: "Reconciliar cartera",
};

export const PROTECTION_LABEL: Record<PositionProtectionV1, string> = {
  ACTIVE: "Stop operativo vigente",
  NONE: "Sin stop operativo registrado",
};

export function formatNextEventLabel(nextEvent: PositionNextEventV1): string {
  return NEXT_EVENT_LABEL[nextEvent] ?? nextEvent;
}

export function formatProtectionLabel(
  protection: PositionProtectionV1,
): string {
  return PROTECTION_LABEL[protection] ?? protection;
}

function actionVerb(action: PositionDecisionActionV1): string {
  switch (action) {
    case "HOLD":
      return "Mantén";
    case "PROTECT":
      return "Protege";
    case "REDUCE":
      return "Reduce";
    case "TAKE_PROFIT":
      return "Toma beneficio parcial";
    case "EXIT":
      return "Sal";
    case "REVIEW":
      return "Revisa";
    default:
      return action;
  }
}

/** Frase operativa corta para cockpit Mercado (≠ permiso). Spec §B.5 — sin enums. */
export function formatPositionDecisionPhrase(
  decision: PositionDecisionV1,
): string {
  if (decision.reconHealth === "CRITICAL") {
    return "No operes: discrepancia de cartera. Reconcilia antes de cualquier acción.";
  }

  // §B.5 — T1 alcanzado + HOLD → frase humana (nunca T1_REACHED).
  if (decision.action === "HOLD" && decision.nextEvent === "T1") {
    const bits = ["T1 alcanzado · Mantener."];
    if (decision.protection === "ACTIVE") {
      bits.push("Stop operativo registrado.");
    }
    return bits.join(" ");
  }

  if (decision.action === "HOLD" && decision.nextEvent === "T2") {
    return "T2 pendiente · Mantener.";
  }

  const verb = actionVerb(decision.action);
  const parts: string[] = [verb + "."];

  if (decision.protection === "ACTIVE") {
    parts.push("Stop operativo registrado.");
  } else if (decision.action === "PROTECT") {
    parts.push("Falta stop operativo vigente.");
  }

  if (decision.nextEvent === "T1") {
    parts.push("T1 alcanzado.");
  } else if (decision.nextEvent === "T2") {
    parts.push("T2 es el siguiente hito.");
  } else if (decision.nextEvent === "STOP") {
    parts.push("Stop estructural alcanzado o inminente.");
  } else if (decision.nextEvent === "THESIS_REVIEW") {
    parts.push("La tesis requiere revisión.");
  } else if (decision.nextEvent === "TRAIL") {
    parts.push("Trail sugerido · no aplicado · requiere Confirm.");
  } else if (decision.action === "HOLD" && decision.nextEvent === "NONE") {
    parts.push("Sin evento operativo pendiente.");
  }

  if (
    decision.action === "TAKE_PROFIT" &&
    decision.suggestedQty != null &&
    decision.suggestedQty > 0
  ) {
    parts.push(`Sugerencia: reducir ${decision.suggestedQty} u.`);
  }

  return parts.join(" ");
}

/** Labels humanos para ExitPlan en Confirm / shell (V1.42 F7 — sin enums). */
export function formatExitOperativaIntentLabel(intent: string): string {
  switch (intent) {
    case "exit_hint":
      return "Salir";
    case "reduce":
      return "Reducir";
    case "protect":
      return "Proteger";
    case "review":
      return "Revisar";
    default:
      return intent;
  }
}

export function formatExitPlanStatusLabel(status: string): string {
  switch (status) {
    case "ARMED":
      return "Armado";
    case "TRIGGERED":
      return "Disparado";
    case "WATCH":
      return "Vigilar";
    case "NONE":
      return "Sin plan";
    case "EXPIRED":
      return "Caducado";
    case "CANCELLED":
      return "Cancelado";
    case "BLOCKED":
      return "Bloqueado";
    default:
      return status;
  }
}

export function formatExitSuggestedActionLabel(action: string): string {
  switch (action) {
    case "hold":
      return "Mantener";
    case "protect":
      return "Proteger";
    case "reduce":
      return "Reducir";
    case "full_exit":
      return "Salir";
    default:
      return action;
  }
}

export function formatExitReasonLabel(
  reason: string | null | undefined,
): string {
  if (!reason) return "—";
  switch (reason) {
    case "TARGET_1":
      return "T1";
    case "TARGET_2":
      return "T2";
    case "STRUCTURAL_STOP":
      return "Stop estructural";
    case "TRAIL":
      return "Trailing";
    case "TIME_STOP":
      return "Time stop";
    case "THESIS_INVALIDATION":
      return "Tesis invalidada";
    case "PORTFOLIO_RISK":
      return "Riesgo de cartera";
    case "MANUAL":
      return "Manual";
    default:
      return reason;
  }
}
