/**
 * V1.47/V1.48 — OperationalContext / MarketSnapshot + nextAction semantics.
 *
 * @see docs/engineering/spec-v148-paper-desk-event-continuity-2026-09-01.md
 */

import { assertNever } from "./never.js";
import type { PortfolioReconStatusV1 } from "./reconciliation-opening-veto.js";

export type MarketDataPermissionV1 = "FRESH" | "STALE" | "MISSING" | "INVALID";

export type SessionStateV1 = "PRE" | "OPEN" | "BREAK" | "CLOSED" | "POST";

export type PaperDeskNextActionV1 =
  | "MANTENER"
  | "MONITOR"
  | "SUBIR_STOP"
  | "REDUCIR"
  | "SALIR"
  | "ESPERAR_APERTURA"
  | "REVISAR_DATOS_NO_FRESCOS"
  | "BLOQUEADO";

export type PaperDeskExecutedActionV1 =
  | "NONE"
  | "APPLIED"
  | "DRY_RUN"
  | "DENIED";

export type PaperDeskDecisionActionV1 =
  | "HOLD"
  | "PROTECT"
  | "TRAIL"
  | "REDUCE"
  | "EXIT"
  | "UNKNOWN";

export type PositionOperatingStateV1 =
  | "OPEN_UNPROTECTED"
  | "PROTECTED"
  | "TRAILING"
  | "PARTIALLY_REDUCED"
  | "EXIT_PENDING"
  | "CLOSED"
  | "RECONCILIATION_ERROR"
  | "RECONCILIATION_DRIFT";

/** V1.57 — drift ≠ unavailable. null = no override (clean / ausente). */
export function resolveReconOperatingState(
  recon: PortfolioReconStatusV1 | null | undefined,
): "RECONCILIATION_ERROR" | "RECONCILIATION_DRIFT" | null {
  if (recon == null) return null;
  switch (recon) {
    case "unavailable":
      return "RECONCILIATION_ERROR";
    case "drift":
      return "RECONCILIATION_DRIFT";
    case "clean":
      return null;
    default:
      return assertNever(recon);
  }
}

export type MarketSnapshotV1 = {
  instrumentId: string;
  lastPrice: number | null;
  permission: MarketDataPermissionV1;
  timestamp?: string | null;
  source?: string;
  asOf?: string | null;
  session?: SessionStateV1;
};

export function sessionIsOpen(state: SessionStateV1): boolean {
  return state === "OPEN";
}

export function classifyMarketData(input: {
  lastPrice: number | null;
  barDate: string | null;
  expectedIsoDate: string;
}): MarketDataPermissionV1 {
  const price = input.lastPrice;
  if (price == null || price <= 0) {
    return input.barDate ? "INVALID" : "MISSING";
  }
  const raw = input.barDate?.trim().slice(0, 10) ?? "";
  if (!raw) return "MISSING";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return "INVALID";
  if (raw < input.expectedIsoDate) return "STALE";
  return "FRESH";
}

export function resolveExecutedAction(input: {
  status: string;
  reason?: string | null;
}): PaperDeskExecutedActionV1 {
  if (input.reason === "dry_run") return "DRY_RUN";
  if (input.status === "denied") return "DENIED";
  if (
    input.status === "protected" ||
    input.status === "reduced" ||
    input.status === "exited"
  ) {
    return "APPLIED";
  }
  return "NONE";
}

export function resolveDecisionAction(
  verdict?: string | null,
): PaperDeskDecisionActionV1 {
  const raw = (verdict ?? "").trim().toUpperCase();
  if (
    raw === "HOLD" ||
    raw === "PROTECT" ||
    raw === "TRAIL" ||
    raw === "REDUCE" ||
    raw === "EXIT"
  ) {
    return raw;
  }
  return "UNKNOWN";
}

export function resolvePaperDeskNextAction(input: {
  status: string;
  decisionVerdict?: string | null;
  permissionReasons?: string[];
  reason?: string | null;
  session?: SessionStateV1;
  executedAction?: PaperDeskExecutedActionV1 | null;
}): PaperDeskNextActionV1 {
  const reasons = new Set(input.permissionReasons ?? []);
  const reason = input.reason ?? null;
  if (
    reason === "data_unavailable" ||
    reason === "missing_mark_price" ||
    reasons.has("data_unavailable") ||
    reason === "data_stale" ||
    reasons.has("data_stale")
  ) {
    return "REVISAR_DATOS_NO_FRESCOS";
  }
  if (input.status === "denied") return "BLOQUEADO";
  const session = input.session ?? "OPEN";
  if (
    input.status === "held" &&
    (!sessionIsOpen(session) || reason === "queue_next_session")
  ) {
    return "ESPERAR_APERTURA";
  }
  const executed =
    input.executedAction ??
    resolveExecutedAction({ status: input.status, reason });
  if (
    executed === "APPLIED" &&
    (input.status === "protected" ||
      input.status === "reduced" ||
      input.status === "exited")
  ) {
    return "MONITOR";
  }
  if (input.status === "protected") return "SUBIR_STOP";
  if (input.status === "reduced") return "REDUCIR";
  if (input.status === "exited") return "SALIR";
  if (input.status === "held") return "MANTENER";
  if (
    input.status === "error" ||
    input.status === "no_plan" ||
    input.status === "skipped" ||
    input.status === "sell_skipped"
  ) {
    return "BLOQUEADO";
  }
  return "MANTENER";
}

function finitePositiveStop(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

export function resolvePositionOperatingState(input: {
  positionStatus?: string | null;
  remainingQuantity?: number | null;
  quantity?: number | null;
  hasTrailRevision?: boolean;
  hasProtectRevision?: boolean;
  reconStatus?: PortfolioReconStatusV1;
  hasUnresolvedExit?: boolean;
  /** V2.33 — structural stop at birth counts as protected (honesty = phase). */
  currentStop?: number | null;
  initialStop?: number | null;
}): PositionOperatingStateV1 {
  const reconOverride = resolveReconOperatingState(input.reconStatus);
  if (reconOverride) return reconOverride;
  if ((input.positionStatus ?? "").toUpperCase() === "CLOSED") return "CLOSED";
  if (input.hasUnresolvedExit) return "EXIT_PENDING";
  const qty = input.quantity ?? 0;
  const rem = input.remainingQuantity ?? qty;
  if (qty > 0 && rem + 1e-9 < qty) return "PARTIALLY_REDUCED";
  if (input.hasTrailRevision) return "TRAILING";
  if (
    input.hasProtectRevision ||
    (input.positionStatus ?? "").toUpperCase() === "PROTECTED"
  ) {
    return "PROTECTED";
  }
  // V2.33 — birth fill with signed structural stop is not OPEN_UNPROTECTED.
  if (
    finitePositiveStop(input.currentStop) ||
    finitePositiveStop(input.initialStop)
  ) {
    return "PROTECTED";
  }
  return "OPEN_UNPROTECTED";
}
