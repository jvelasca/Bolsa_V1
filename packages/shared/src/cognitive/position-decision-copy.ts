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

/** Frase operativa corta para cockpit Mercado (≠ permiso). */
export function formatPositionDecisionPhrase(
  decision: PositionDecisionV1,
): string {
  if (decision.reconHealth === "CRITICAL") {
    return "No operes: discrepancia de cartera. Reconcilia antes de cualquier acción.";
  }

  const verb = actionVerb(decision.action);
  const parts: string[] = [verb + "."];

  if (decision.protection === "ACTIVE") {
    parts.push("Stop operativo registrado.");
  } else if (decision.action === "PROTECT") {
    parts.push("Falta stop operativo vigente.");
  }

  if (decision.nextEvent === "T1") {
    parts.push("T1 aún no gestionado.");
  } else if (decision.nextEvent === "T2") {
    parts.push("T2 es el siguiente hito.");
  } else if (decision.nextEvent === "STOP") {
    parts.push("Stop estructural alcanzado o inminente.");
  } else if (decision.nextEvent === "THESIS_REVIEW") {
    parts.push("La tesis requiere revisión.");
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
