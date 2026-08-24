/**
 * Proyección Decision Board → cola Hoy (ADR-031 Ciclo 3).
 * No es un motor: comprime buckets existentes a BUY / ARMED / WATCH / REVIEW / BLOCKED.
 */

import type { DecisionBoardV1 } from "../decision-board.js";
import type { TradePlanStatusV1, TradePlanWhyNotV1 } from "./trade-plan.js";

export type HoyActionKindV1 = "BUY" | "ARMED" | "WATCH" | "REVIEW" | "BLOCKED";

export type HoyQueueItemV1 = {
  id: string;
  symbol: string;
  kind: HoyActionKindV1;
  status: TradePlanStatusV1;
  whyNot: TradePlanWhyNotV1[];
  gate: string;
};

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

/** Mapea el Decision Board a ítems de la tira Hoy (máx. 8). */
export function mapDecisionBoardToHoyQueue(
  board: DecisionBoardV1,
  limit = 8,
): HoyQueueItemV1[] {
  const items: HoyQueueItemV1[] = [];

  for (const row of board.semiF3Queue) {
    const kind = kindFromGate("unknown", "pending");
    items.push({
      id: `f3-${row.instrumentId ?? row.symbol ?? items.length}`,
      symbol: row.symbol ?? row.instrumentId ?? "—",
      kind,
      status: statusFromKind(kind),
      whyNot: whyNotFromKind(kind),
      gate: row.status,
    });
  }

  for (const session of board.decisionSessions) {
    const gate = session.gate || "unknown";
    let bucket: "pending" | "vetoed" | "deferred" | "auto" = "pending";
    if (gate.toUpperCase() === "VETO") bucket = "vetoed";
    else if (gate.toUpperCase() === "DEFERRED") bucket = "deferred";
    else if (session.kind.includes("paper") || session.kind.includes("auto"))
      bucket = "auto";
    const kind = kindFromGate(gate, bucket);
    items.push({
      id: session.sessionId,
      symbol: session.symbol ?? session.instrumentId,
      kind,
      status: statusFromKind(kind),
      whyNot: whyNotFromKind(kind),
      gate,
    });
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
