/**
 * Fase de producto Mercado 2.0 (cockpit) — lenguaje UI, no Decision Spine.
 * Ranking ≠ BUY. Confirm = firma.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md
 */

export const MERCADO_COCKPIT_PHASES = [
  "sin_contexto",
  "descubierto",
  "vigilar",
  "preparada",
  "disparada",
  "propuesta",
  "posicion",
] as const;

export type MercadoCockpitPhase = (typeof MERCADO_COCKPIT_PHASES)[number];

export const MERCADO_COCKPIT_PHASE_LABEL: Record<MercadoCockpitPhase, string> =
  {
    sin_contexto: "Sin valor",
    descubierto: "Descubierto",
    vigilar: "Vigilar",
    preparada: "Preparada",
    disparada: "Disparada",
    propuesta: "Propuesta",
    posicion: "Posición",
  };

export type MercadoCockpitPhaseInput = {
  instrumentId: string | null | undefined;
  inEstudio: boolean;
  hasOpenPosition: boolean;
  inConfirmQueue: boolean;
  tradePlanStatus?: string | null;
  hasOperationalPlan?: boolean;
};

/**
 * Prioridad: posición → cola Confirm → TRIGGERED → plan ARMED/WATCH → Estudio → descubierto.
 */
export function resolveMercadoCockpitPhase(
  input: MercadoCockpitPhaseInput,
): MercadoCockpitPhase {
  if (!input.instrumentId) return "sin_contexto";
  if (input.hasOpenPosition) return "posicion";
  if (input.inConfirmQueue) return "propuesta";
  const status = (input.tradePlanStatus ?? "").toUpperCase();
  if (status === "TRIGGERED") return "disparada";
  if (
    status === "ARMED" ||
    (input.hasOperationalPlan === true &&
      (status === "WATCH" || status === "" || status === "ARMED"))
  ) {
    return "preparada";
  }
  if (input.hasOperationalPlan === true && status !== "TRIGGERED") {
    return "preparada";
  }
  if (input.inEstudio) return "vigilar";
  return "descubierto";
}

export function mercadoCockpitPrimaryCta(
  phase: MercadoCockpitPhase,
): string | null {
  switch (phase) {
    case "descubierto":
      return "Añadir a Estudio";
    case "vigilar":
      return "Seguir";
    case "preparada":
      return "Preparar operación";
    case "disparada":
    case "propuesta":
      return "Revisar y confirmar";
    case "posicion":
      return "Mantener";
    default:
      return null;
  }
}
