/**
 * Fase de producto Mercado 2.0 (cockpit) — lenguaje UI, no Decision Spine.
 * Ranking ≠ BUY. Confirm = firma.
 * V1.23 — InstrumentOperationalContext: un resolver, panel contextual.
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
  "confirmada",
  "posicion",
] as const;

export type MercadoCockpitPhase = (typeof MERCADO_COCKPIT_PHASES)[number];

export const MERCADO_COCKPIT_PHASE_LABEL: Record<MercadoCockpitPhase, string> =
  {
    sin_contexto: "Sin valor",
    descubierto: "Descubierto",
    vigilar: "En estudio",
    preparada: "Preparada",
    disparada: "Disparada",
    propuesta: "Propuesta",
    confirmada: "Confirmada",
    posicion: "Posición",
  };

export type MercadoCockpitPhaseInput = {
  instrumentId: string | null | undefined;
  inEstudio: boolean;
  hasOpenPosition: boolean;
  inConfirmQueue: boolean;
  /** Firma hecha, fill pendiente (orden en vuelo). Alias: orderPendingFill. */
  hasSignedPendingOrder?: boolean;
  orderPendingFill?: boolean;
  tradePlanStatus?: string | null;
  hasOperationalPlan?: boolean;
};

/**
 * Prioridad: posición → confirmada → cola Confirm → TRIGGERED → plan → Estudio → descubierto.
 */
export function resolveMercadoCockpitPhase(
  input: MercadoCockpitPhaseInput,
): MercadoCockpitPhase {
  if (!input.instrumentId) return "sin_contexto";
  if (input.hasOpenPosition) return "posicion";
  if (input.hasSignedPendingOrder || input.orderPendingFill)
    return "confirmada";
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

/** Anti-ruido: no mostrar Entrada/Stop/T1/T2 en estudio puro. */
export function mercadoCockpitShowsPlanLevels(
  phase: MercadoCockpitPhase,
): boolean {
  switch (phase) {
    case "preparada":
    case "disparada":
    case "propuesta":
    case "confirmada":
    case "posicion":
      return true;
    default:
      return false;
  }
}

export function mercadoCockpitPrimaryCta(
  phase: MercadoCockpitPhase,
): string | null {
  switch (phase) {
    case "descubierto":
      return "Añadir a Estudio";
    case "vigilar":
      return "Ver análisis";
    case "preparada":
      return "Revisar operación";
    case "disparada":
      return "Confirmar";
    case "propuesta":
      return "Revisar y confirmar";
    case "confirmada":
      return "Ver operaciones";
    case "posicion":
      return "Mantener";
    default:
      return null;
  }
}

/** Copy corto de por qué no hay niveles (VIGILAR / DESCUBIERTO / sin valor). */
export function mercadoCockpitNoLevelsCopy(
  phase: MercadoCockpitPhase,
): string | null {
  switch (phase) {
    case "vigilar":
      return "En supervisión. Sin disparador de entrada todavía — Ranking ≠ BUY.";
    case "descubierto":
      return "Fuera de Estudio. Sin plan diario — añádelo a Estudio para supervisarlo.";
    case "sin_contexto":
      return "Selecciona un valor en listas o gráfico.";
    default:
      return null;
  }
}

/** Copy trailing: stop vigente (autoridad) vs stop sugerido · No aplicado / Revisar. */
export type MercadoTrailingStatusLabel = "No aplicado" | "Revisar";

export type MercadoTrailingCopyV1 = {
  show: boolean;
  stopVigente: number | null;
  stopSugerido: number | null;
  /** true = el stop vigente ya recoge la sugerencia: nada que firmar. */
  applied: boolean;
  label: "↗ Trailing sugerido";
  stopVigenteLabel: "Stop vigente";
  stopSugeridoLabel: "Stop sugerido";
  /** null cuando la sugerencia ya está recogida en el stop vigente. */
  statusLabel: MercadoTrailingStatusLabel | null;
};

function finite(n: number | null | undefined): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/**
 * El trail nunca se promueve a `currentStop`: si el stop vigente no lo recoge
 * es «No aplicado»; si el trail está activo sin precio resoluble, «Revisar».
 */
export function resolveMercadoTrailingCopy(input: {
  phase: MercadoCockpitPhase;
  entry: number | null;
  stopVigente: number | null;
  trailingActive: boolean;
  trailingStopHint: number | null;
  /** Direccion del plan; por defecto long. */
  direction?: "long" | "short" | null;
}): MercadoTrailingCopyV1 {
  const base = {
    show: false,
    stopVigente: input.stopVigente,
    stopSugerido: null,
    applied: false,
    label: "↗ Trailing sugerido" as const,
    stopVigenteLabel: "Stop vigente" as const,
    stopSugeridoLabel: "Stop sugerido" as const,
    statusLabel: null as MercadoTrailingStatusLabel | null,
  };

  if (input.phase !== "posicion" || !input.trailingActive) return { ...base };
  if (!finite(input.trailingStopHint)) {
    return { ...base, show: true, statusLabel: "Revisar" };
  }
  const hint = input.trailingStopHint;
  const current = input.stopVigente;
  const isShort = input.direction === "short";
  const applied = finite(current)
    ? isShort
      ? current <= hint
      : current >= hint
    : false;
  return {
    ...base,
    show: true,
    stopSugerido: hint,
    applied,
    statusLabel: applied ? null : "No aplicado",
  };
}
