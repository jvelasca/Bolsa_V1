/**
 * Proyección Decision Board → cola Hoy (ADR-031 Ciclo 3).
 * No es un motor: comprime buckets existentes a BUY / ARMED / WATCH / REVIEW / BLOCKED.
 * Prefiere un TradePlan vivo cuando el payload ya lo trae; si no, heurística de gate.
 * Ciclo 4.8: Setup thin (entrySetup + phase/effort del anchor) — no whyNot nuevos.
 * Ciclo 4.9: sesiones Board echo tradePlan + anchor → Hoy deja heurística cuando hay plan.
 */

import type {
  DecisionBoardV1,
  DecisionSessionViewV1,
  SemiF3ViewV1,
} from "../decision-board.js";
import type {
  EntrySetupV1,
  TradePlanStatusV1,
  TradePlanV1,
  TradePlanWhyNotV1,
} from "./trade-plan.js";

export type HoyActionKindV1 = "BUY" | "ARMED" | "WATCH" | "REVIEW" | "BLOCKED";

/** Evidencia SETUP en superficie Hoy (runtime echo; no contrato TradePlan). */
export type HoySetupEvidenceV1 = {
  entrySetup?: EntrySetupV1 | null;
  phase?: string | null;
  effort?: string | null;
};

export type HoyQueueItemV1 = {
  id: string;
  symbol: string;
  kind: HoyActionKindV1;
  status: TradePlanStatusV1;
  whyNot: TradePlanWhyNotV1[];
  gate: string;
  /** Ciclo 4.8 — bloque Setup en el dialog Hoy. */
  setup?: HoySetupEvidenceV1 | null;
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

const ENTRY_SETUPS = new Set<EntrySetupV1>([
  "breakout",
  "pullback",
  "wyckoff",
  "none",
]);

const SETUP_PHASES = new Set(["none", "spring", "reclaim", "sos", "lps"]);

const SETUP_EFFORTS = new Set([
  "none",
  "spring_low_effort",
  "spring_high_effort",
  "result_ok",
  "result_weak",
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

function asEntrySetup(value: unknown): EntrySetupV1 | null {
  return typeof value === "string" && ENTRY_SETUPS.has(value as EntrySetupV1)
    ? (value as EntrySetupV1)
    : null;
}

function readAnchor(raw: unknown): { phase?: string; effort?: string } | null {
  if (!isRecord(raw)) return null;
  const out: { phase?: string; effort?: string } = {};
  if (typeof raw.phase === "string" && SETUP_PHASES.has(raw.phase)) {
    out.phase = raw.phase;
  }
  if (typeof raw.effort === "string" && SETUP_EFFORTS.has(raw.effort)) {
    out.effort = raw.effort;
  }
  return out.phase !== undefined || out.effort !== undefined ? out : null;
}

/** Anchor: payload.wyckoffSpringAnchor → decisionSession.runtime → runtime. */
function readAnchorFromPayloadish(value: unknown): {
  phase?: string;
  effort?: string;
} | null {
  if (!isRecord(value)) return null;
  const top = readAnchor(value.wyckoffSpringAnchor);
  if (top) return top;
  if (isRecord(value.decisionSession)) {
    const runtime = value.decisionSession.runtime;
    if (isRecord(runtime)) {
      const fromSession = readAnchor(runtime.wyckoffSpringAnchor);
      if (fromSession) return fromSession;
    }
  }
  if (isRecord(value.runtime)) {
    return readAnchor(value.runtime.wyckoffSpringAnchor);
  }
  return null;
}

function readSetupFromF3Row(row: SemiF3ViewV1): HoySetupEvidenceV1 | null {
  const live = readTradePlanFromF3Row(row);
  const entrySetup = asEntrySetup(live?.entrySetup);
  const extra = row.extra;
  let anchor: { phase?: string; effort?: string } | null = null;
  if (isRecord(extra)) {
    anchor =
      readAnchorFromPayloadish(extra.payload) ??
      readAnchor(extra.wyckoffSpringAnchor) ??
      readAnchorFromPayloadish(extra);
  }
  const flattened = row as SemiF3ViewV1 & { payload?: unknown };
  if (!anchor) {
    anchor = readAnchorFromPayloadish(flattened.payload);
  }
  if (!entrySetup && !anchor) return null;
  return {
    entrySetup: entrySetup ?? null,
    phase: anchor?.phase ?? null,
    effort: anchor?.effort ?? null,
  };
}

function readSetupFromSession(
  session: DecisionSessionViewV1,
  tradePlan: TradePlanV1 | null,
): HoySetupEvidenceV1 | null {
  const entrySetup = asEntrySetup(tradePlan?.entrySetup);
  const anchor = readAnchor(session.wyckoffSpringAnchor);
  if (!entrySetup && !anchor) return null;
  return {
    entrySetup: entrySetup ?? null,
    phase: anchor?.phase ?? null,
    effort: anchor?.effort ?? null,
  };
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
  setup: HoySetupEvidenceV1 | null,
): HoyQueueItemV1 {
  if (live) {
    return {
      id,
      symbol,
      kind: kindFromPlanStatus(live.status),
      status: live.status,
      whyNot: live.whyNot,
      gate,
      setup,
    };
  }
  return {
    id,
    symbol,
    kind: heuristicKind,
    status: statusFromKind(heuristicKind),
    whyNot: whyNotFromKind(heuristicKind),
    gate,
    setup,
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
        readSetupFromF3Row(row),
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
    const live = asLiveTradePlan(session.tradePlan);
    items.push(
      toHoyItem(
        session.sessionId,
        session.symbol ?? session.instrumentId,
        gate,
        live,
        kind,
        readSetupFromSession(session, live),
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
