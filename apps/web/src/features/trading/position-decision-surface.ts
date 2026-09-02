/**
 * V1.61 — Position Decision Surface helpers (tono, headline, ejecución, CTA).
 * V1.71 — REVISAR en recon/BLOQUEADO · headlines sin colapsar T2/DRIFT · assertNever.
 * Display-only — no firma · no BUY.
 */

import type {
  MesaNextActionKindV1,
  PaperDeskNextActionV1,
  PositionExitCtaKindV1,
  PositionOperationalStateV1,
} from "@bolsa/shared";
import { assertNever } from "@bolsa/shared";

export type PovVisualToneV1 = "emerald" | "amber" | "rose" | "muted";

export function povOperatingStateTone(
  state: PositionOperationalStateV1,
): PovVisualToneV1 {
  switch (state) {
    case "PROTECTED":
    case "TRAILING":
    case "T1_EXECUTED":
    case "T2_EXECUTED":
    case "PARTIALLY_REDUCED":
      return "emerald";
    case "T1_READY":
    case "T2_READY":
    case "PROTECT_REQUIRED":
    case "OPEN_UNPROTECTED":
    case "RECONCILIATION_ERROR":
      return "amber";
    case "EXIT_REQUIRED":
    case "EXIT_PENDING":
    case "RECONCILIATION_DRIFT":
      return "rose";
    case "CLOSED":
      return "muted";
    default:
      return assertNever(state);
  }
}

export function povOperatingStateToneClasses(tone: PovVisualToneV1): string {
  switch (tone) {
    case "emerald":
      return "border-emerald-700/25 bg-emerald-500/5";
    case "amber":
      return "border-amber-700/30 bg-amber-500/5";
    case "rose":
      return "border-rose-700/30 bg-rose-500/5";
    case "muted":
      return "border-border/60 bg-muted/15";
  }
}

export function povOperatingStateHeadline(
  state: PositionOperationalStateV1,
): string {
  switch (state) {
    case "PROTECTED":
    case "TRAILING":
      return "Protegida";
    case "T1_EXECUTED":
      return "T1 ejecutado";
    case "T2_EXECUTED":
      return "T2 ejecutado";
    case "PARTIALLY_REDUCED":
      return "Parcial";
    case "EXIT_REQUIRED":
    case "EXIT_PENDING":
      return "Salida necesaria";
    case "RECONCILIATION_DRIFT":
      return "Recon drift";
    case "RECONCILIATION_ERROR":
      return "Recon no disponible";
    case "T1_READY":
    case "T2_READY":
    case "PROTECT_REQUIRED":
    case "OPEN_UNPROTECTED":
      return "Requiere atención";
    case "CLOSED":
      return "Cerrada";
    default:
      return assertNever(state);
  }
}

export type PovExecutionCopyV1 =
  | "NO REQUERIDA"
  | "PENDIENTE"
  | "EJECUTADA"
  | "REVISAR";

export function povExecutionStateLabel(
  state: PositionOperationalStateV1,
  primaryAction: PaperDeskNextActionV1,
): PovExecutionCopyV1 {
  if (state === "RECONCILIATION_DRIFT" || state === "RECONCILIATION_ERROR") {
    return "REVISAR";
  }
  if (
    primaryAction === "BLOQUEADO" ||
    primaryAction === "REVISAR_DATOS_NO_FRESCOS"
  ) {
    return "REVISAR";
  }
  if (
    state === "T1_EXECUTED" ||
    state === "T2_EXECUTED" ||
    state === "PARTIALLY_REDUCED"
  ) {
    return "EJECUTADA";
  }
  if (
    state === "T1_READY" ||
    state === "T2_READY" ||
    state === "PROTECT_REQUIRED" ||
    state === "EXIT_REQUIRED" ||
    state === "EXIT_PENDING" ||
    primaryAction === "SUBIR_STOP" ||
    primaryAction === "REDUCIR" ||
    primaryAction === "SALIR"
  ) {
    return "PENDIENTE";
  }
  return "NO REQUERIDA";
}

export function mapPovPrimaryActionToCtaKind(
  action: PaperDeskNextActionV1,
): MesaNextActionKindV1 {
  switch (action) {
    case "SUBIR_STOP":
      return "protect";
    case "REDUCIR":
      return "reduce";
    case "SALIR":
      return "exit";
    case "REVISAR_DATOS_NO_FRESCOS":
    case "BLOQUEADO":
      return "review";
    case "ESPERAR_APERTURA":
      return "watch";
    case "MONITOR":
    case "MANTENER":
      return "maintain";
    default:
      return assertNever(action);
  }
}

export function mapPovPrimaryActionToExitCtaKind(
  action: PaperDeskNextActionV1,
): PositionExitCtaKindV1 | undefined {
  const kind = mapPovPrimaryActionToCtaKind(action);
  if (
    kind === "maintain" ||
    kind === "protect" ||
    kind === "reduce" ||
    kind === "exit" ||
    kind === "review"
  ) {
    return kind;
  }
  return undefined;
}

export function formatLevel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(2);
}

export function formatPctSigned(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function formatRSigned(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}R`;
}
