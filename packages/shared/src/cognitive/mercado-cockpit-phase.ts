/**
 * Fase de producto Mercado 2.0 (cockpit) — lenguaje UI, no Decision Spine.
 * Ranking ≠ BUY. Confirm = firma.
 * V1.24 — allowlist: BLOCKED / EXPIRED / CANCELLED nunca «Preparada».
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md
 */

import { entryOperatingPrimaryLabel } from "./entry-operating-copy.js";

export const MERCADO_COCKPIT_PHASES = [
  "sin_contexto",
  "descubierto",
  "vigilar",
  "preparada",
  "bloqueada",
  "caducada",
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
    bloqueada: "Bloqueada",
    caducada: "Caducada",
    disparada: "Disparada",
    propuesta: "Propuesta",
    confirmada: "Confirmada",
    posicion: "Posición",
  };

/** Statuses that may show as Preparada when hasOperationalPlan (allowlist). */
const PREPARADA_PLAN_STATUSES = new Set(["ARMED", "WATCH", ""]);

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
 * Prioridad: posición → confirmada → cola Confirm → TRIGGERED →
 * BLOCKED/EXPIRED → plan allowlist → Estudio → descubierto.
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
  if (status === "BLOCKED") return "bloqueada";
  if (status === "EXPIRED" || status === "CANCELLED") return "caducada";
  if (
    status === "ARMED" ||
    (input.hasOperationalPlan === true && PREPARADA_PLAN_STATUSES.has(status))
  ) {
    return "preparada";
  }
  if (input.inEstudio) return "vigilar";
  return "descubierto";
}

/** Anti-ruido: no mostrar Entrada/Stop/T1/T2 en estudio puro ni planes muertos. */
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
      // bloqueada / caducada: fail-closed — no niveles ni CTA de «Revisar operación».
      return false;
  }
}

export function mercadoCockpitPrimaryCta(
  phase: MercadoCockpitPhase,
): string | null {
  const entryLabel = entryOperatingPrimaryLabel(phase);
  if (entryLabel) return entryLabel;

  switch (phase) {
    case "descubierto":
      return "Añadir a Estudio";
    case "vigilar":
      return "Ver análisis";
    case "bloqueada":
      return "Ver motivo del bloqueo";
    case "caducada":
      return "Ver análisis";
    case "posicion":
      return "Mantener";
    default:
      return null;
  }
}

/** Copy corto de por qué no hay niveles / plan no operable. */
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
    case "bloqueada":
      return "Plan bloqueado por gate de riesgo o mandato — no es Preparada. Ranking ≠ BUY.";
    case "caducada":
      return "Plan caducado o cancelado — niveles residuales no autorizan entrada.";
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
  stopVigenteLabel: "Stop operativo";
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
    stopVigenteLabel: "Stop operativo" as const,
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
