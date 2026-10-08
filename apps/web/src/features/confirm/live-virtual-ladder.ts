/**
 * Escalera de estados LIVE VIRTUAL (simulado) — Confirm híbrido.
 * preparada → firmada → enviada → completada*|rechazada|no_cableado (+ desconocida).
 * @see docs/engineering/design-live-virtual-order-gateway-ui-2026-09-07.md
 */

export type LiveVirtualLadderStep =
  | "preparada"
  | "firmada"
  | "enviada"
  | "completada"
  | "rechazada"
  | "no_cableado"
  | "desconocida";

export const LIVE_VIRTUAL_LADDER_ORDER: LiveVirtualLadderStep[] = [
  "preparada",
  "firmada",
  "enviada",
  "completada",
  "rechazada",
  "no_cableado",
  "desconocida",
];

/** Copy obligatorio por peldaño (honestidad VIRTUAL, sin tokens ingleses). */
export const LIVE_VIRTUAL_LADDER_COPY: Record<LiveVirtualLadderStep, string> = {
  preparada: "Propuesta · sin firma",
  firmada: "Firmada · envío simulado",
  enviada: "Enviada (simulado) · sin ejecución real",
  completada: "Completada (simulado) · sin liquidación real",
  rechazada: "Rechazada (simulado o por política)",
  no_cableado: "Bróker no conectado",
  desconocida: "Estado desconocido · no asumir completada",
};

/** Mapea el estado devuelto por el bróker (en su idioma) al peldaño de UI. */
const FILL_STATUS_TO_STEP: Record<string, LiveVirtualLadderStep> = {
  submitted: "enviada",
  rejected: "rechazada",
  not_wired: "no_cableado",
  unknown: "desconocida",
  /** Adapter «executed» en LIVE de estudio = completado mock, no capital. */
  executed: "completada",
  filled: "completada",
};

/**
 * Mapea fillStatus del BrokerAdapterReceipt (o trade.status) al peldaño UI.
 * Sin status → null (el caller decide preparada/firmada).
 */
export function liveVirtualStepFromFillStatus(
  fillStatus: string | null | undefined,
): LiveVirtualLadderStep | null {
  if (fillStatus == null || !String(fillStatus).trim()) return null;
  const key = String(fillStatus).trim().toLowerCase();
  return FILL_STATUS_TO_STEP[key] ?? "desconocida";
}

/**
 * Tras Confirmar Intent / Ejecutar: avanza escalera con honestidad.
 * `executedIntent` sin ejecución → firmada (firma humana, aún sin envío simulado).
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
    // Execute sin estado legible → no asumir una ejecución real.
    return "desconocida";
  }

  const intent = String(input.intentStatus ?? "")
    .trim()
    .toLowerCase();
  if (
    intent === "authorized" ||
    intent === "approved" ||
    intent === "confirmed"
  ) {
    return "firmada";
  }

  if (input.hasPending) {
    return input.previous === "firmada" ? "firmada" : "preparada";
  }

  return input.previous ?? "preparada";
}
