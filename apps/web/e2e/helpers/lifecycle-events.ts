/**
 * V1.84/V1.85 — Lifecycle event log: validate → append → reduce → snapshot + accounting.
 * Wire `events` come from the persisted log, not a regenerated stage template.
 */
import {
  E2E_INSTRUMENT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  E2E_LIFECYCLE_TRADE_PLAN_ID,
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
  | "invalid_kind";

export type LifecycleAppendError = {
  code: LifecycleAppendErrorCode;
  message: string;
};

export type LifecycleStoreEvent = {
  eventId: string;
  positionId: string;
  kind: LifecycleStoreEventKind;
  at: string;
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
  previousStop?: number;
  newStop?: number;
  reason?: string;
  revisionId?: string;
};

export type LifecycleEventInput = {
  kind: LifecycleStoreEventKind;
  at?: string;
  eventId?: string;
  positionId?: string;
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
};

/** Kinds that appear on operationalView.events (V1.83/V1.84 wire contract). */
const WIRE_EVENT_KINDS = new Set<LifecycleStoreEventKind>([
  "T1_EXECUTED",
  "T2_TRIGGERED",
  "T2_EXECUTED",
  "POSITION_CLOSED",
]);

const FILL_KINDS = new Set<LifecycleStoreEventKind>([
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

const MOCK_CLOSE_FILL_ID = "fill-mock-exit";

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

function ms(iso: string): number {
  const value = Date.parse(iso);
  if (Number.isNaN(value)) {
    throw new Error(`invalid ISO timestamp: ${iso}`);
  }
  return value;
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
): LifecycleStoreEvent {
  const at = input.at ?? DEFAULT_AT[input.kind];
  const positionId = input.positionId ?? E2E_LIFECYCLE_POSITION_ID;
  const eventId = input.eventId ?? `evt-${input.kind}-${at}`;
  const remainingBefore = opts?.remainingBefore ?? LIFECYCLE_BIRTH_QTY;
  const lineagePath = opts?.lineagePath ?? "trail";

  const base: LifecycleStoreEvent = {
    eventId,
    positionId,
    kind: input.kind,
    at,
    instrumentId: input.instrumentId ?? E2E_INSTRUMENT_ID,
    decisionId: input.decisionId ?? E2E_LIFECYCLE_DECISION_ID,
    tradePlanId: input.tradePlanId ?? E2E_LIFECYCLE_TRADE_PLAN_ID,
  };

  if (input.kind === "TRAIL_APPLIED") {
    const previousStop = input.previousStop ?? LIFECYCLE_INITIAL_STOP;
    const newStop = input.newStop ?? previousStop + 3;
    return {
      ...base,
      previousStop,
      newStop,
      reason: input.reason ?? "trail",
      revisionId: input.revisionId ?? `rev-trail-${positionId}`,
      fillId: input.fillId,
    };
  }

  if (FILL_KINDS.has(input.kind)) {
    const defaults = defaultFillPayload(
      input.kind,
      remainingBefore,
      lineagePath,
    );
    return {
      ...base,
      fillId: input.fillId ?? defaults?.fillId,
      quantity: input.quantity ?? defaults?.quantity,
      price: input.price ?? defaults?.price,
      fees: input.fees ?? 0,
      venue: input.venue ?? "MOCK",
      venueOrderId: input.venueOrderId ?? `ord-${input.kind.toLowerCase()}`,
      currency: input.currency ?? "USD",
    };
  }

  return { ...base, fillId: input.fillId };
}

function remainingAfterLog(events: LifecycleStoreEvent[]): number {
  let remaining = LIFECYCLE_BIRTH_QTY;
  for (const ev of events) {
    if (!FILL_KINDS.has(ev.kind)) continue;
    remaining -= ev.quantity ?? 0;
  }
  return remaining;
}

function validateTimeConstraints(
  log: LifecycleStoreEvent[],
  event: LifecycleStoreEvent,
): LifecycleAppendError | null {
  const previous = log[log.length - 1];
  if (previous) {
    const prevMs = ms(previous.at);
    const nextMs = ms(event.at);
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
  if (event.kind === "T1_EXECUTED" && t1Trig && ms(event.at) <= ms(t1Trig.at)) {
    return {
      code: "time_regression",
      message: "T1_EXECUTED must be after T1_TRIGGERED",
    };
  }
  const t1Exec = [...log, event].find((e) => e.kind === "T1_EXECUTED");
  if (
    event.kind === "TRAIL_APPLIED" &&
    t1Exec &&
    ms(event.at) < ms(t1Exec.at)
  ) {
    return {
      code: "time_regression",
      message: "TRAIL_APPLIED must be >= T1_EXECUTED",
    };
  }
  const t2Trig = log.find((e) => e.kind === "T2_TRIGGERED");
  if (event.kind === "T2_EXECUTED" && t2Trig && ms(event.at) <= ms(t2Trig.at)) {
    return {
      code: "time_regression",
      message: "T2_EXECUTED must be after T2_TRIGGERED",
    };
  }
  return null;
}

/**
 * Pure append with FSM + time + identity validation.
 * Same eventId → idempotent ok (no second append).
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
  const event = normalizeLifecycleStoreEvent(input, {
    remainingBefore,
    lineagePath: reduced.lineagePath,
  });

  const existing = log.find((row) => row.eventId === event.eventId);
  if (existing) {
    return {
      ok: true,
      log,
      event: existing,
      idempotent: true,
      stage: reduced.stage,
      lineagePath: reduced.lineagePath,
    };
  }

  const anchorPositionId = log[0]?.positionId ?? E2E_LIFECYCLE_POSITION_ID;
  if (event.positionId !== anchorPositionId) {
    return {
      ok: false,
      error: {
        code: "position_mismatch",
        message: `positionId ${event.positionId} ≠ log ${anchorPositionId}`,
      },
    };
  }

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
  let remaining = LIFECYCLE_BIRTH_QTY;
  let realizedPnl = 0;

  for (const ev of events) {
    if (!FILL_KINDS.has(ev.kind)) continue;
    const qty = ev.quantity ?? 0;
    const price = ev.price ?? 0;
    const fees = ev.fees ?? 0;
    cash += qty * price - fees;
    remaining -= qty;
    realizedPnl += (price - LIFECYCLE_AVG_COST) * qty - fees;
  }

  if (remaining < 0) {
    throw new Error(`accountLifecycleFills: remaining ${remaining} < 0`);
  }

  const lastPrice = lifecycleLastPriceForStage(stage, lineagePath);
  const fin = derivePositionFinancials({
    avgCost: LIFECYCLE_AVG_COST,
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
 * V1.85 — financial overlay from fill accounting (cash / realized / unrealized).
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
  const cost = LIFECYCLE_AVG_COST * acct.remaining;
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
