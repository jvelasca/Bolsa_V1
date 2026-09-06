/**
 * Escalera de estados LIVE VIRTUAL (simulado) — Confirm híbrido.
 * proposed → signed → submitted → filled*|rejected|not_wired (+ unknown).
 * @see docs/engineering/design-live-virtual-order-gateway-ui-2026-09-07.md
 */

export type LiveVirtualLadderStep =
  | "proposed"
  | "signed"
  | "submitted"
  | "filled"
  | "rejected"
  | "not_wired"
  | "unknown";

export const LIVE_VIRTUAL_LADDER_ORDER: LiveVirtualLadderStep[] = [
  "proposed",
  "signed",
  "submitted",
  "filled",
  "rejected",
  "not_wired",
  "unknown",
];

/** Copy obligatorio por peldaño (honestidad VIRTUAL). */
export const LIVE_VIRTUAL_LADDER_COPY: Record<LiveVirtualLadderStep, string> = {
  proposed: "Propuesta · sin firma",
  signed: "Firmado · envío VIRTUAL",
  submitted: "Enviada (simulado) · no fill",
  filled: "Fill SIMULADO · ≠ settlement real",
  rejected: "Rechazada (simulado o policy)",
  not_wired: "Broker no cableado",
  unknown: "Estado desconocido · no asumir fill",
};

const FILL_STATUS_TO_STEP: Record<string, LiveVirtualLadderStep> = {
  submitted: "submitted",
  rejected: "rejected",
  not_wired: "not_wired",
  unknown: "unknown",
  /** Adapter «executed» en LIVE de estudio = fill mock, no capital. */
  executed: "filled",
  filled: "filled",
};

/**
 * Mapea fillStatus del BrokerAdapterReceipt (o trade.status) al peldaño UI.
 * Sin status → null (el caller decide proposed/signed).
 */
export function liveVirtualStepFromFillStatus(
  fillStatus: string | null | undefined,
): LiveVirtualLadderStep | null {
  if (fillStatus == null || !String(fillStatus).trim()) return null;
  const key = String(fillStatus).trim().toLowerCase();
  return FILL_STATUS_TO_STEP[key] ?? "unknown";
}

/**
 * Tras Confirmar Intent / Ejecutar: avanza escalera con honestidad.
 * `executedIntent` sin fill → signed (firma humana, aún sin envío mock).
 */
export function resolveLiveVirtualLadderStep(input: {
  hasPending: boolean;
  intentStatus?: string | null;
  execute?: boolean;
  fillStatus?: string | null;
  previous?: LiveVirtualLadderStep | null;
}): LiveVirtualLadderStep {
  const fromFill = liveVirtualStepFromFillStatus(input.fillStatus);
  if (fromFill) return fromFill;

  if (input.execute) {
    // Execute sin fillStatus legible → no asumir fill.
    return "unknown";
  }

  const intent = String(input.intentStatus ?? "")
    .trim()
    .toLowerCase();
  if (
    intent === "authorized" ||
    intent === "approved" ||
    intent === "confirmed"
  ) {
    return "signed";
  }

  if (input.hasPending) {
    return input.previous === "signed" ? "signed" : "proposed";
  }

  return input.previous ?? "proposed";
}
