/**
 * V1.84–V1.86 — Lifecycle event log: validate → append → reduce → snapshot + accounting.
 * V1.86: ENTRY fill on POSITION_OPENED · strict eventId idempotency · identity envelope ·
 * payload/trail guards. Wire `events` come from the persisted log.
 */
import {
  E2E_ACCOUNT_ID,
  E2E_INSTRUMENT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  E2E_LIFECYCLE_TRADE_PLAN_ID,
  E2E_SYMBOL,
} from "./ids";
import {
  buildLifecycleSnapshot,
  derivePositionFinancials,
  LIFECYCLE_AVG_COST,
  LIFECYCLE_BIRTH_QTY,
  LIFECYCLE_CASH,
  LIFECYCLE_INITIAL_RISK,
  LIFECYCLE_INITIAL_STOP,
  LIFECYCLE_REMAINING_AFTER_T1,
  LIFECYCLE_REMAINING_AFTER_T2,
  lifecycleLastPriceForStage,
  MOCK_T1_FILL_ID,
  MOCK_T2_FILL_ID,
  type E2eGoldenPositionStage,
  type LifecycleAccountSnapshot,
  type LifecycleLineagePath,
} from "./lifecycle-snapshot";

export type LifecycleStoreEventKind =
  | "POSITION_OPENED"
  | "T1_TRIGGERED"
  | "T1_EXECUTED"
  | "T2_TRIGGERED"
  | "T2_EXECUTED"
  | "TRAIL_APPLIED"
  | "EXIT_REQUIRED"
  | "POSITION_CLOSED";

export type LifecycleAppendErrorCode =
  | "illegal_transition"
  | "time_regression"
  | "duplicate_fill_id"
  | "position_mismatch"
  | "identity_mismatch"
  | "invalid_kind"
  | "invalid_payload"
  | "event_id_conflict"
  | "trail_relaxation"
  | "invalid_timestamp";

export type LifecycleAppendError = {
  code: LifecycleAppendErrorCode;
  message: string;
};

export type LifecycleStoreEvent = {
  eventId: string;
  positionId: string;
  kind: LifecycleStoreEventKind;
  at: string;
  accountId?: string;
  fillId?: string;
  quantity?: number;
  price?: number;
  fees?: number;
  venue?: string;
  venueOrderId?: string;
  currency?: string;
  instrumentId?: string;
  decisionId?: string;
  tradePlanId?: string;
  symbol?: string;
  side?: string;
  previousStop?: number;
  newStop?: number;
  reason?: string;
  revisionId?: string;
  payloadHash?: string;
};

export type LifecycleEventInput = {
  kind: LifecycleStoreEventKind;
  at?: string;
  eventId?: string;
  positionId?: string;
  accountId?: string;
  fillId?: string;
  quantity?: number;
  price?: number;
  fees?: number;
  venue?: string;
  venueOrderId?: string;
  currency?: string;
  instrumentId?: string;
  decisionId?: string;
  tradePlanId?: string;
  symbol?: string;
  side?: string;
  previousStop?: number;
  newStop?: number;
  reason?: string;
  revisionId?: string;
};

export type LifecycleAccounting = {
  cash: number;
  remaining: number;
  realizedPnl: number;
  unrealizedPnl: number;
  totalPnl: number;
  lastPrice: number;
  marketValue: number;
  totalEquity: number;
  avgCost: number;
  initialEquity: number;
};

/** Kinds that appear on operationalView.events (V1.83/V1.84 wire contract). */
const WIRE_EVENT_KINDS = new Set<LifecycleStoreEventKind>([
  "T1_EXECUTED",
  "T2_TRIGGERED",
  "T2_EXECUTED",
  "POSITION_CLOSED",
]);

/** All cash-moving fills including ENTRY (POSITION_OPENED). */
const FILL_KINDS = new Set<LifecycleStoreEventKind>([
  "POSITION_OPENED",
  "T1_EXECUTED",
  "T2_EXECUTED",
  "POSITION_CLOSED",
]);

const EXIT_FILL_KINDS = new Set<LifecycleStoreEventKind>([
  "T1_EXECUTED",
  "T2_EXECUTED",
  "POSITION_CLOSED",
]);

const DEFAULT_AT: Record<LifecycleStoreEventKind, string> = {
  POSITION_OPENED: "2026-09-02T10:00:00.000Z",
  T1_TRIGGERED: "2026-09-02T11:00:00.000Z",
  T1_EXECUTED: "2026-09-02T11:30:00.000Z",
  TRAIL_APPLIED: "2026-09-02T12:00:00.000Z",
  T2_TRIGGERED: "2026-09-02T12:15:00.000Z",
  T2_EXECUTED: "2026-09-02T12:45:00.000Z",
  EXIT_REQUIRED: "2026-09-02T14:00:00.000Z",
  POSITION_CLOSED: "2026-09-02T15:00:00.000Z",
};

const MOCK_OPEN_FILL_ID = "fill-mock-entry";
const MOCK_CLOSE_FILL_ID = "fill-mock-exit";

const HASH_KEYS = [
  "kind",
  "at",
  "positionId",
  "accountId",
  "instrumentId",
  "decisionId",
  "tradePlanId",
  "symbol",
  "side",
  "currency",
  "fillId",
  "quantity",
  "price",
  "fees",
  "venue",
  "venueOrderId",
  "previousStop",
  "newStop",
  "reason",
  "revisionId",
] as const;

/** Legal FSM edges (preserve GP-V184 goldens: optional T1_TRIGGERED; T2 closes without EXIT). */
const TRANSITIONS: Record<
  E2eGoldenPositionStage,
  Partial<Record<LifecycleStoreEventKind, E2eGoldenPositionStage>>
> = {
  clean: {},
  candidate: { POSITION_OPENED: "open" },
  open: { T1_TRIGGERED: "t1_ready", T1_EXECUTED: "t1_executed" },
  t1_ready: { T1_EXECUTED: "t1_executed" },
  t1_executed: { TRAIL_APPLIED: "trailing", T2_TRIGGERED: "t2_ready" },
  trailing: { EXIT_REQUIRED: "exit_required" },
  exit_required: { POSITION_CLOSED: "closed" },
  t2_ready: { T2_EXECUTED: "t2_executed" },
  t2_executed: { POSITION_CLOSED: "closed" },
  closed: {},
};

function ms(iso: string): number | LifecycleAppendError {
  const value = Date.parse(iso);
  if (Number.isNaN(value)) {
    return {
      code: "invalid_timestamp",
      message: `invalid ISO timestamp: ${iso}`,
    };
  }
  return value;
}

function newEventId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `evt-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Stable FNV-1a 32-bit hex (deterministic across Node/browser for tests). */
function hashCanonical(payload: Record<string, unknown>): string {
  const encoded = JSON.stringify(payload, Object.keys(payload).sort());
  let h = 0x811c9dc5;
  for (let i = 0; i < encoded.length; i += 1) {
    h ^= encoded.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}

export function computePayloadHash(event: LifecycleStoreEvent): string {
  const payload: Record<string, unknown> = {};
  for (const key of HASH_KEYS) {
    const value = event[key as keyof LifecycleStoreEvent];
    if (value !== undefined) payload[key] = value;
  }
  return hashCanonical(payload);
}

export function validateTransition(
  currentState: E2eGoldenPositionStage,
  kind: LifecycleStoreEventKind,
):
  | { ok: true; nextState: E2eGoldenPositionStage }
  | { ok: false; error: LifecycleAppendError } {
  const next = TRANSITIONS[currentState]?.[kind];
  if (!next) {
    return {
      ok: false,
      error: {
        code: "illegal_transition",
        message: `illegal transition ${currentState} + ${kind}`,
      },
    };
  }
  return { ok: true, nextState: next };
}

function defaultFillPayload(
  kind: LifecycleStoreEventKind,
  remainingBefore: number,
  lineagePath: LifecycleLineagePath,
): { quantity: number; price: number; fillId: string } | null {
  if (kind === "POSITION_OPENED") {
    return {
      quantity: LIFECYCLE_BIRTH_QTY,
      price: LIFECYCLE_AVG_COST,
      fillId: MOCK_OPEN_FILL_ID,
    };
  }
  if (kind === "T1_EXECUTED") {
    return {
      quantity: LIFECYCLE_BIRTH_QTY - LIFECYCLE_REMAINING_AFTER_T1,
      price: 105,
      fillId: MOCK_T1_FILL_ID,
    };
  }
  if (kind === "T2_EXECUTED") {
    return {
      quantity: LIFECYCLE_REMAINING_AFTER_T1 - LIFECYCLE_REMAINING_AFTER_T2,
      price: 110,
      fillId: MOCK_T2_FILL_ID,
    };
  }
  if (kind === "POSITION_CLOSED") {
    const lastPrice = lifecycleLastPriceForStage("closed", lineagePath);
    return {
      quantity: remainingBefore,
      price: lastPrice,
      fillId: MOCK_CLOSE_FILL_ID,
    };
  }
  return null;
}

export function normalizeLifecycleStoreEvent(
  input: LifecycleEventInput,
  opts?: { remainingBefore?: number; lineagePath?: LifecycleLineagePath },
): LifecycleStoreEvent | { error: LifecycleAppendError } {
  const at = input.at ?? DEFAULT_AT[input.kind];
  const atMs = ms(at);
  if (typeof atMs !== "number") {
    return { error: atMs };
  }
  const positionId = input.positionId ?? E2E_LIFECYCLE_POSITION_ID;
  const eventId = input.eventId ?? newEventId();
  const remainingBefore = opts?.remainingBefore ?? 0;
  const lineagePath = opts?.lineagePath ?? "trail";

  const base: LifecycleStoreEvent = {
    eventId,
    positionId,
    kind: input.kind,
    at,
    accountId: input.accountId ?? E2E_ACCOUNT_ID,
    instrumentId: input.instrumentId ?? E2E_INSTRUMENT_ID,
    decisionId: input.decisionId ?? E2E_LIFECYCLE_DECISION_ID,
    tradePlanId: input.tradePlanId ?? E2E_LIFECYCLE_TRADE_PLAN_ID,
    symbol: input.symbol ?? E2E_SYMBOL,
    side: input.side ?? "LONG",
    currency: input.currency ?? "USD",
  };

  let event: LifecycleStoreEvent;
  if (input.kind === "TRAIL_APPLIED") {
    const previousStop = input.previousStop ?? LIFECYCLE_INITIAL_STOP;
    const newStop = input.newStop ?? previousStop + 3;
    event = {
      ...base,
      previousStop,
      newStop,
      reason: input.reason ?? "trail",
      revisionId: input.revisionId ?? `rev-trail-${positionId}`,
      fillId: input.fillId,
    };
  } else if (FILL_KINDS.has(input.kind)) {
    const defaults = defaultFillPayload(
      input.kind,
      remainingBefore,
      lineagePath,
    );
    event = {
      ...base,
      fillId: input.fillId ?? defaults?.fillId,
      quantity: input.quantity ?? defaults?.quantity,
      price: input.price ?? defaults?.price,
      fees: input.fees ?? 0,
      venue: input.venue ?? "MOCK",
      // V1.86: never invent venueOrderId
      venueOrderId: input.venueOrderId,
      currency: input.currency ?? "USD",
    };
  } else {
    event = { ...base, fillId: input.fillId };
  }

  return { ...event, payloadHash: computePayloadHash(event) };
}

function remainingAfterLog(events: LifecycleStoreEvent[]): number {
  let remaining = 0;
  for (const ev of events) {
    if (ev.kind === "POSITION_OPENED") {
      remaining += ev.quantity ?? 0;
    } else if (EXIT_FILL_KINDS.has(ev.kind)) {
      remaining -= ev.quantity ?? 0;
    }
  }
  return remaining;
}

function validateTimeConstraints(
  log: LifecycleStoreEvent[],
  event: LifecycleStoreEvent,
): LifecycleAppendError | null {
  const previous = log[log.length - 1];
  const nextMs = ms(event.at);
  if (typeof nextMs !== "number") return nextMs;

  if (previous) {
    const prevMs = ms(previous.at);
    if (typeof prevMs !== "number") return prevMs;
    if (event.kind === "POSITION_CLOSED") {
      if (nextMs <= prevMs) {
        return {
          code: "time_regression",
          message: `POSITION_CLOSED at ${event.at} must be > previous ${previous.at}`,
        };
      }
    } else if (nextMs < prevMs) {
      return {
        code: "time_regression",
        message: `at ${event.at} < previous ${previous.at}`,
      };
    }
  }

  const t1Trig = log.find((e) => e.kind === "T1_TRIGGERED");
  if (event.kind === "T1_EXECUTED" && t1Trig) {
    const t1Ms = ms(t1Trig.at);
    if (typeof t1Ms !== "number") return t1Ms;
    if (nextMs <= t1Ms) {
      return {
        code: "time_regression",
        message: "T1_EXECUTED must be after T1_TRIGGERED",
      };
    }
  }
  const t1Exec = [...log, event].find((e) => e.kind === "T1_EXECUTED");
  if (event.kind === "TRAIL_APPLIED" && t1Exec) {
    const t1e = ms(t1Exec.at);
    if (typeof t1e !== "number") return t1e;
    if (nextMs < t1e) {
      return {
        code: "time_regression",
        message: "TRAIL_APPLIED must be >= T1_EXECUTED",
      };
    }
  }
  const t2Trig = log.find((e) => e.kind === "T2_TRIGGERED");
  if (event.kind === "T2_EXECUTED" && t2Trig) {
    const t2Ms = ms(t2Trig.at);
    if (typeof t2Ms !== "number") return t2Ms;
    if (nextMs <= t2Ms) {
      return {
        code: "time_regression",
        message: "T2_EXECUTED must be after T2_TRIGGERED",
      };
    }
  }
  return null;
}

function validateIdentity(
  log: LifecycleStoreEvent[],
  event: LifecycleStoreEvent,
): LifecycleAppendError | null {
  if (log.length === 0) return null;
  const anchor = log[0]!;
  if (event.positionId !== anchor.positionId) {
    return {
      code: "position_mismatch",
      message: `positionId ${event.positionId} ≠ log ${anchor.positionId}`,
    };
  }
  const checks: Array<[string, string | undefined, string | undefined]> = [
    ["instrumentId", event.instrumentId, anchor.instrumentId],
    ["decisionId", event.decisionId, anchor.decisionId],
    ["tradePlanId", event.tradePlanId, anchor.tradePlanId],
    ["accountId", event.accountId, anchor.accountId],
    ["symbol", event.symbol, anchor.symbol],
    ["side", event.side, anchor.side],
    ["currency", event.currency, anchor.currency],
  ];
  for (const [label, got, expected] of checks) {
    if (got !== undefined && expected !== undefined && got !== expected) {
      return {
        code: "identity_mismatch",
        message: `${label} ${got} ≠ envelope ${expected}`,
      };
    }
  }
  return null;
}

function validatePayload(
  event: LifecycleStoreEvent,
  remainingBefore: number,
  stage: E2eGoldenPositionStage,
  lineagePath: LifecycleLineagePath,
): LifecycleAppendError | null {
  if (FILL_KINDS.has(event.kind)) {
    const qty = event.quantity;
    const price = event.price;
    const fees = event.fees ?? 0;
    if (qty === undefined || !Number.isFinite(qty) || qty <= 0) {
      return {
        code: "invalid_payload",
        message: `quantity must be > 0, got ${qty}`,
      };
    }
    if (price === undefined || !Number.isFinite(price) || price <= 0) {
      return {
        code: "invalid_payload",
        message: `price must be > 0, got ${price}`,
      };
    }
    if (!Number.isFinite(fees) || fees < 0) {
      return {
        code: "invalid_payload",
        message: `fees must be >= 0 finite, got ${fees}`,
      };
    }
    if (event.kind === "POSITION_CLOSED") {
      if (Math.abs(qty - remainingBefore) > 1e-9) {
        return {
          code: "invalid_payload",
          message: `POSITION_CLOSED.quantity ${qty} != remaining ${remainingBefore}`,
        };
      }
    } else if (
      event.kind !== "POSITION_OPENED" &&
      qty > remainingBefore + 1e-9
    ) {
      return {
        code: "invalid_payload",
        message: `quantity ${qty} > remaining ${remainingBefore}`,
      };
    }
  }

  if (event.kind === "TRAIL_APPLIED") {
    const prev = event.previousStop;
    const next = event.newStop;
    if (prev === undefined || next === undefined) {
      return {
        code: "invalid_payload",
        message: "TRAIL_APPLIED requires previousStop and newStop",
      };
    }
    if (!Number.isFinite(prev) || !Number.isFinite(next)) {
      return { code: "invalid_payload", message: "trail stops must be finite" };
    }
    const side = (event.side ?? "LONG").toUpperCase();
    if (side === "LONG" && next < prev) {
      return {
        code: "trail_relaxation",
        message: `LONG trail newStop ${next} < previousStop ${prev}`,
      };
    }
    const lastPrice = lifecycleLastPriceForStage(stage, lineagePath);
    if (side === "LONG" && next >= lastPrice) {
      return {
        code: "invalid_payload",
        message: `LONG trail newStop ${next} must be < lastPrice ${lastPrice}`,
      };
    }
  }
  return null;
}

/**
 * Pure append with FSM + time + identity + payload validation.
 * Same eventId + same payloadHash → idempotent; different payload → event_id_conflict.
 */
export function appendValidatedLifecycleEvent(
  log: LifecycleStoreEvent[],
  input: LifecycleEventInput,
):
  | {
      ok: true;
      log: LifecycleStoreEvent[];
      event: LifecycleStoreEvent;
      idempotent: boolean;
      stage: E2eGoldenPositionStage;
      lineagePath: LifecycleLineagePath;
    }
  | { ok: false; error: LifecycleAppendError } {
  const reduced = reduceLifecycleEvents(log);
  const remainingBefore = remainingAfterLog(log);
  const normalized = normalizeLifecycleStoreEvent(input, {
    remainingBefore,
    lineagePath: reduced.lineagePath,
  });
  if ("error" in normalized) {
    return { ok: false, error: normalized.error };
  }
  const event = normalized;

  const existing = log.find((row) => row.eventId === event.eventId);
  if (existing) {
    const existingHash = existing.payloadHash ?? computePayloadHash(existing);
    const newHash = event.payloadHash ?? computePayloadHash(event);
    if (existingHash === newHash) {
      return {
        ok: true,
        log,
        event: existing,
        idempotent: true,
        stage: reduced.stage,
        lineagePath: reduced.lineagePath,
      };
    }
    return {
      ok: false,
      error: {
        code: "event_id_conflict",
        message: `eventId ${event.eventId} already exists with different payload`,
      },
    };
  }

  const identityError = validateIdentity(log, event);
  if (identityError) return { ok: false, error: identityError };

  if (event.fillId) {
    const dup = log.find(
      (row) => row.fillId === event.fillId && row.eventId !== event.eventId,
    );
    if (dup) {
      return {
        ok: false,
        error: {
          code: "duplicate_fill_id",
          message: `fillId ${event.fillId} already on ${dup.eventId}`,
        },
      };
    }
  }

  const timeError = validateTimeConstraints(log, event);
  if (timeError) return { ok: false, error: timeError };

  const transition = validateTransition(reduced.stage, event.kind);
  if (!transition.ok) return { ok: false, error: transition.error };

  const payloadError = validatePayload(
    event,
    remainingBefore,
    reduced.stage,
    reduced.lineagePath,
  );
  if (payloadError) return { ok: false, error: payloadError };

  const nextLog = [...log, event];
  const nextReduced = reduceLifecycleEvents(nextLog);
  return {
    ok: true,
    log: nextLog,
    event,
    idempotent: false,
    stage: nextReduced.stage,
    lineagePath: nextReduced.lineagePath,
  };
}

/**
 * Reduce a validated log. Illegal sequences fail-closed (throw).
 */
export function reduceLifecycleEvents(events: LifecycleStoreEvent[]): {
  stage: E2eGoldenPositionStage;
  lineagePath: LifecycleLineagePath;
} {
  let stage: E2eGoldenPositionStage = "candidate";
  let lineagePath: LifecycleLineagePath = "trail";
  for (const ev of events) {
    const transition = validateTransition(stage, ev.kind);
    if (!transition.ok) {
      throw new Error(
        `reduceLifecycleEvents: ${transition.error.message} at ${ev.eventId ?? ev.kind}`,
      );
    }
    stage = transition.nextState;
    if (ev.kind === "T2_TRIGGERED" || ev.kind === "T2_EXECUTED") {
      lineagePath = "t2";
    } else if (ev.kind === "TRAIL_APPLIED" || ev.kind === "EXIT_REQUIRED") {
      lineagePath = "trail";
    }
  }
  return { stage, lineagePath };
}

export function accountLifecycleFills(
  events: LifecycleStoreEvent[],
): LifecycleAccounting {
  const { stage, lineagePath } = reduceLifecycleEvents(events);
  let cash = LIFECYCLE_CASH;
  let remaining = 0;
  let realizedPnl = 0;
  let avgCost = LIFECYCLE_AVG_COST;

  for (const ev of events) {
    if (!FILL_KINDS.has(ev.kind)) continue;
    const qty = ev.quantity ?? 0;
    const price = ev.price ?? 0;
    const fees = ev.fees ?? 0;
    if (ev.kind === "POSITION_OPENED") {
      cash -= qty * price + fees;
      remaining += qty;
      avgCost = price;
    } else {
      cash += qty * price - fees;
      remaining -= qty;
      realizedPnl += (price - avgCost) * qty - fees;
    }
  }

  if (remaining < 0) {
    throw new Error(`accountLifecycleFills: remaining ${remaining} < 0`);
  }

  const lastPrice = lifecycleLastPriceForStage(stage, lineagePath);
  const fin = derivePositionFinancials({
    avgCost,
    lastPrice,
    remaining,
    initialRisk: LIFECYCLE_INITIAL_RISK,
  });
  const unrealizedPnl = fin.unrealizedPnl;
  const totalPnl = realizedPnl + unrealizedPnl;
  return {
    cash,
    remaining,
    realizedPnl,
    unrealizedPnl,
    totalPnl,
    lastPrice,
    marketValue: fin.marketValue,
    totalEquity: cash + fin.marketValue,
    avgCost,
    initialEquity: LIFECYCLE_CASH,
  };
}

export function wireEventsFromLog(
  events: LifecycleStoreEvent[],
): Array<{ kind: string; at: string; fillId?: string }> {
  return events
    .filter((ev) => WIRE_EVENT_KINDS.has(ev.kind))
    .map((ev) => ({
      kind: ev.kind,
      at: ev.at,
      ...(ev.fillId ? { fillId: ev.fillId } : {}),
    }));
}

/**
 * Snapshot whose operationalView.events are the persisted log (filtered to wire kinds).
 * V1.86 — ENTRY accounting (cash debit on OPEN) + realized/unrealized overlay.
 */
export function buildLifecycleSnapshotFromEvents(
  events: LifecycleStoreEvent[],
): LifecycleAccountSnapshot {
  const { stage, lineagePath } = reduceLifecycleEvents(events);
  const snap = buildLifecycleSnapshot({ stage, lineagePath });
  const acct = accountLifecycleFills(events);
  if (!snap.position) {
    return {
      ...snap,
      cash: acct.cash,
      totalEquity: acct.totalEquity,
      dayPnl: acct.totalPnl,
      dayPnlPct: (acct.totalPnl / LIFECYCLE_CASH) * 100,
    };
  }

  const wireEvents = wireEventsFromLog(events);
  const cost = acct.avgCost * acct.remaining;
  const unrealizedPnlPct = cost === 0 ? 0 : (acct.unrealizedPnl / cost) * 100;
  const unrealizedR =
    acct.remaining === 0 || LIFECYCLE_INITIAL_RISK === 0
      ? 0
      : acct.unrealizedPnl / LIFECYCLE_INITIAL_RISK;

  return {
    ...snap,
    cash: acct.cash,
    totalEquity: acct.totalEquity,
    dayPnl: acct.totalPnl,
    dayPnlPct: (acct.totalPnl / LIFECYCLE_CASH) * 100,
    openPositions: acct.remaining > 0 ? 1 : 0,
    position: {
      ...snap.position,
      quantity: acct.remaining,
      lastPrice: acct.lastPrice,
      marketValue: acct.marketValue,
      unrealizedPnl: acct.unrealizedPnl,
      unrealizedPnlPct,
      operational: {
        ...snap.position.operational,
        remainingQuantity: acct.remaining,
        unrealizedR,
        realizedPnl: acct.realizedPnl,
        totalPnl: acct.totalPnl,
        operationalView: {
          ...snap.position.operational.operationalView,
          remainingQuantity: acct.remaining,
          events: wireEvents,
          levels: {
            ...snap.position.operational.operationalView.levels,
            unrealizedR,
          },
        },
      },
    },
  };
}

export function assertWireEventsMatchLog(
  viewEvents: Array<{ kind?: string }> | undefined,
  log: LifecycleStoreEvent[],
): void {
  const expected = wireEventsFromLog(log).map((ev) => ev.kind);
  const actual = (viewEvents ?? []).map((ev) => ev.kind ?? "");
  if (expected.length !== actual.length) {
    throw new Error(
      `wire events length ${actual.length} ≠ log wire ${expected.length}: [${actual.join(",")}] vs [${expected.join(",")}]`,
    );
  }
  for (let i = 0; i < expected.length; i += 1) {
    if (actual[i] !== expected[i]) {
      throw new Error(`wire events[${i}] ${actual[i]} ≠ log ${expected[i]}`);
    }
  }
}
