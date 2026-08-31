/**
 * V1.47 — OperationalContext / MarketSnapshot contracts + nextAction.
 *
 * @see docs/engineering/spec-v147-paper-desk-runtime-truth-2026-09-01.md
 */

export type MarketDataPermissionV1 = "FRESH" | "STALE" | "MISSING" | "INVALID";

export type SessionStateV1 = "PRE" | "OPEN" | "BREAK" | "CLOSED" | "POST";

export type PaperDeskNextActionV1 =
  | "MANTENER"
  | "SUBIR_STOP"
  | "REDUCIR"
  | "SALIR"
  | "ESPERAR_APERTURA"
  | "REVISAR_DATOS_NO_FRESCOS"
  | "BLOQUEADO";

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

export function resolvePaperDeskNextAction(input: {
  status: string;
  decisionVerdict?: string | null;
  permissionReasons?: string[];
  reason?: string | null;
  session?: SessionStateV1;
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
