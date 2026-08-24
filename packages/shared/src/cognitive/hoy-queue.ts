/**
 * Proyección Decision Board → cola Hoy (ADR-031 Ciclo 3).
 * No es un motor: comprime buckets existentes a BUY / ARMED / WATCH / REVIEW / BLOCKED.
 * Prefiere un TradePlan vivo cuando el payload ya lo trae; si no, heurística de gate.
 */

import type { DecisionBoardV1, SemiF3ViewV1 } from "../decision-board.js";
import type {
  TradePlanStatusV1,
  TradePlanV1,
  TradePlanWhyNotV1,
} from "./trade-plan.js";

export type HoyActionKindV1 = "BUY" | "ARMED" | "WATCH" | "REVIEW" | "BLOCKED";

export type HoyQueueItemV1 = {
  id: string;
  symbol: string;
  kind: HoyActionKindV1;
  status: TradePlanStatusV1;
  whyNot: TradePlanWhyNotV1[];
  gate: string;
};

const PLAN_STATUSES = new Set<TradePlanStatusV1>([
  "WATCH",
  "ARMED",
  "TRIGGERED",
  "BLOCKED",
  "EXPIRED",
]);

const PLAN_WHY_NOT = new Set<TradePlanWhyNotV1>([
  "fit",
  "freshness",
  "mandate",
  "entry",
  "no_stop",
  "expired",
  "orphan",
  "rr",
  "regime",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asLiveTradePlan(value: unknown): TradePlanV1 | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  if (
    typeof status !== "string" ||
    !PLAN_STATUSES.has(status as TradePlanStatusV1)
  ) {
    return null;
  }
  const whyNotRaw = value.whyNot;
  const whyNot: TradePlanWhyNotV1[] = Array.isArray(whyNotRaw)
    ? whyNotRaw.filter(
        (code): code is TradePlanWhyNotV1 =>
          typeof code === "string" &&
          PLAN_WHY_NOT.has(code as TradePlanWhyNotV1),
      )
    : [];
  return {
    ...(value as TradePlanV1),
    status: status as TradePlanStatusV1,
    whyNot,
  };
}

function tradePlanFromPayloadish(value: unknown): TradePlanV1 | null {
  if (!isRecord(value)) return null;
  return asLiveTradePlan(value.tradePlan);
}

/** F3: extra.payload.tradePlan → extra.tradePlan → top-level payload (flatten). */
function readTradePlanFromF3Row(row: SemiF3ViewV1): TradePlanV1 | null {
  const extra = row.extra;
  if (isRecord(extra)) {
    const fromPayload = tradePlanFromPayloadish(extra.payload);
    if (fromPayload) return fromPayload;
    const fromExtra = asLiveTradePlan(extra.tradePlan);
    if (fromExtra) return fromExtra;
  }
  const flattened = row as SemiF3ViewV1 & {
    payload?: unknown;
    tradePlan?: unknown;
  };
  const fromTopPayload = tradePlanFromPayloadish(flattened.payload);
  if (fromTopPayload) return fromTopPayload;
  return asLiveTradePlan(flattened.tradePlan);
}

function kindFromGate(
  gate: string,
  bucket: "pending" | "vetoed" | "deferred" | "auto",
): HoyActionKindV1 {
  if (bucket === "vetoed" || gate.toUpperCase() === "VETO") return "BLOCKED";
  if (bucket === "deferred" || gate.toUpperCase() === "DEFERRED")
    return "WATCH";
  if (bucket === "auto") return "ARMED";
  return "BUY";
}

function kindFromPlanStatus(status: TradePlanStatusV1): HoyActionKindV1 {
  switch (status) {
    case "TRIGGERED":
      return "BUY";
    case "ARMED":
      return "ARMED";
    case "BLOCKED":
      return "BLOCKED";
    case "EXPIRED":
      return "REVIEW";
    case "WATCH":
      return "WATCH";
  }
}

function statusFromKind(kind: HoyActionKindV1): TradePlanStatusV1 {
  switch (kind) {
    case "BUY":
      return "TRIGGERED";
    case "ARMED":
      return "ARMED";
    case "BLOCKED":
      return "BLOCKED";
    default:
      return "WATCH";
  }
}

function whyNotFromKind(kind: HoyActionKindV1): TradePlanWhyNotV1[] {
  if (kind === "BLOCKED") return ["fit"];
  if (kind === "WATCH") return ["entry"];
  return [];
}

function toHoyItem(
  id: string,
  symbol: string,
  gate: string,
  live: TradePlanV1 | null,
  heuristicKind: HoyActionKindV1,
): HoyQueueItemV1 {
  if (live) {
    return {
      id,
      symbol,
      kind: kindFromPlanStatus(live.status),
      status: live.status,
      whyNot: live.whyNot,
      gate,
    };
  }
  return {
    id,
    symbol,
    kind: heuristicKind,
    status: statusFromKind(heuristicKind),
    whyNot: whyNotFromKind(heuristicKind),
    gate,
  };
}

/** Mapea el Decision Board a ítems de la tira Hoy (máx. 8). */
export function mapDecisionBoardToHoyQueue(
  board: DecisionBoardV1,
  limit = 8,
): HoyQueueItemV1[] {
  const items: HoyQueueItemV1[] = [];

  for (const row of board.semiF3Queue) {
    const kind = kindFromGate("unknown", "pending");
    items.push(
      toHoyItem(
        `f3-${row.instrumentId ?? row.symbol ?? items.length}`,
        row.symbol ?? row.instrumentId ?? "—",
        row.status,
        readTradePlanFromF3Row(row),
        kind,
      ),
    );
  }

  for (const session of board.decisionSessions) {
    const gate = session.gate || "unknown";
    let bucket: "pending" | "vetoed" | "deferred" | "auto" = "pending";
    if (gate.toUpperCase() === "VETO") bucket = "vetoed";
    else if (gate.toUpperCase() === "DEFERRED") bucket = "deferred";
    else if (session.kind.includes("paper") || session.kind.includes("auto"))
      bucket = "auto";
    const kind = kindFromGate(gate, bucket);
    items.push(
      toHoyItem(
        session.sessionId,
        session.symbol ?? session.instrumentId,
        gate,
        asLiveTradePlan(session.tradePlan),
        kind,
      ),
    );
  }

  const seen = new Set<string>();
  const deduped: HoyQueueItemV1[] = [];
  for (const item of items) {
    const key = `${item.symbol}:${item.kind}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
    if (deduped.length >= limit) break;
  }
  return deduped;
}
