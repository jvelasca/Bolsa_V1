/**
 * V1.83 — LifecycleSnapshot: canonical mock projection (lineage + financials).
 * Stateful Projection E2E (stage → DTO), not event-driven engine.
 */
import {
  E2E_INSTRUMENT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  E2E_LIFECYCLE_TRADE_PLAN_ID,
  E2E_SYMBOL,
} from "./ids";
import { mercadoOpenPosition, type MercadoOpenPosition } from "./mercado";

/** V1.78–V1.79 + V1.81 T2. `clean` unchanged for GP-V178. */
export type E2eGoldenPositionStage =
  | "clean"
  | "candidate"
  | "open"
  | "t1_ready"
  | "t1_executed"
  | "t2_ready"
  | "t2_executed"
  | "trailing"
  | "exit_required"
  | "closed";

/** Trail golden (V1.79) vs T2 (V1.81). CLOSED/EXIT inherit this prefix. */
export type LifecycleLineagePath = "trail" | "t2";

export const LIFECYCLE_BIRTH_QTY = 10;
export const LIFECYCLE_AVG_COST = 100;
export const LIFECYCLE_INITIAL_STOP = 95;
export const LIFECYCLE_INITIAL_RISK =
  (LIFECYCLE_AVG_COST - LIFECYCLE_INITIAL_STOP) * LIFECYCLE_BIRTH_QTY;
export const LIFECYCLE_CASH = 100_000;
export const LIFECYCLE_REMAINING_AFTER_T1 = 5;
export const LIFECYCLE_REMAINING_AFTER_T2 = 2;

const T1_AT = "2026-09-02T11:00:00.000Z";
const TRAIL_AT = "2026-09-02T12:00:00.000Z";
const T1_EXEC_AT = "2026-09-02T11:30:00.000Z";
const T2_AT = "2026-09-02T12:15:00.000Z";
const T2_EXEC_AT = "2026-09-02T12:45:00.000Z";
const CLOSED_AT = "2026-09-02T15:00:00.000Z";
export const MOCK_T1_FILL_ID = "fill-mock-t1";
export const MOCK_T2_FILL_ID = "fill-mock-t2";

const EPS = 1e-6;

type LegPending = { status: "pending" };
type LegTriggered = { status: "triggered"; at: string };
type LegExecuted = { status: "executed"; at: string; fillId: string };
type TargetLeg = LegPending | LegTriggered | LegExecuted;
type ViewLeg = {
  status: "triggered" | "executed";
  at: string;
  fillId?: string;
};

type LifecycleEvent = {
  kind: string;
  at: string;
  fillId?: string;
};

type StopHistoryEntry = {
  label: string;
  stop: number | undefined;
  origin: string;
  delta?: number;
  at?: string;
};

type TrailRevision = {
  revisionId: string;
  at: string;
  previousStop: number | undefined;
  nextStop: number;
  previousStatus: "PROTECTED";
  nextStatus: "PROTECTED";
  origin: "trail";
  reason: "trail";
};

export type LifecycleAccountSnapshot = {
  stage: E2eGoldenPositionStage;
  lineagePath: LifecycleLineagePath;
  position: MercadoOpenPosition | null;
  cash: number;
  totalEquity: number;
  openPositions: number;
  dayPnl: number;
  dayPnlPct: number;
};

export type LifecycleFinancialPosition = {
  quantity: number;
  avgCost: number;
  lastPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  operational?: {
    remainingQuantity?: number;
    unrealizedR?: number;
    realizedPnl?: number;
    totalPnl?: number;
    operationalView?: {
      quantity?: number;
      remainingQuantity?: number;
      levels?: { unrealizedR?: number };
      t1?: { status?: string } | null;
      t2?: { status?: string } | null;
      stopHistory?: unknown[];
      events?: Array<{ kind?: string }>;
    };
  };
};

export function lifecycleOpenPosition(): MercadoOpenPosition {
  const pos = mercadoOpenPosition({
    id: E2E_LIFECYCLE_POSITION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    name: "Apple E2E",
    tradePlanId: E2E_LIFECYCLE_TRADE_PLAN_ID,
    avgCost: LIFECYCLE_AVG_COST,
    lastPrice: 102,
    currentStop: LIFECYCLE_INITIAL_STOP,
    target1: 105,
    target2: 110,
  });
  return {
    ...pos,
    operational: {
      ...pos.operational,
      operationalView: {
        ...pos.operational.operationalView,
        decisionId: E2E_LIFECYCLE_DECISION_ID,
      },
    },
  };
}

/** lastPrice chosen so R = PnL / initialRisk matches HUD (lifecycle identity). */
export function lifecycleLastPriceForStage(
  stage: E2eGoldenPositionStage,
  lineagePath: LifecycleLineagePath = "trail",
): number {
  if (stage === "clean" || stage === "candidate" || stage === "open")
    return 102;
  if (stage === "t1_ready") return 103;
  if (stage === "t1_executed") return 108;
  if (stage === "t2_ready" || stage === "t2_executed") return 110;
  if (stage === "closed") return lineagePath === "t2" ? 110 : 106;
  return 106;
}

export function lifecycleRemainingForStage(
  stage: E2eGoldenPositionStage,
  isLifecycle: boolean,
): number {
  if (stage === "closed") return 0;
  if (stage === "t2_executed") return LIFECYCLE_REMAINING_AFTER_T2;
  if (
    stage === "t1_executed" ||
    stage === "t2_ready" ||
    stage === "trailing" ||
    stage === "exit_required"
  ) {
    return isLifecycle ? LIFECYCLE_REMAINING_AFTER_T1 : LIFECYCLE_BIRTH_QTY;
  }
  return LIFECYCLE_BIRTH_QTY;
}

export function derivePositionFinancials(opts: {
  avgCost: number;
  lastPrice: number;
  remaining: number;
  initialRisk: number;
}): {
  quantity: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  unrealizedR: number;
} {
  const quantity = opts.remaining;
  const marketValue = opts.lastPrice * quantity;
  const unrealizedPnl = (opts.lastPrice - opts.avgCost) * quantity;
  const cost = opts.avgCost * quantity;
  const unrealizedPnlPct = cost === 0 ? 0 : (unrealizedPnl / cost) * 100;
  const unrealizedR =
    quantity === 0 || opts.initialRisk === 0
      ? 0
      : unrealizedPnl / opts.initialRisk;
  return {
    quantity,
    marketValue,
    unrealizedPnl,
    unrealizedPnlPct,
    unrealizedR,
  };
}

export function resolveLineagePathForStage(
  stage: E2eGoldenPositionStage,
  previous: LifecycleLineagePath,
): LifecycleLineagePath {
  if (stage === "t2_ready" || stage === "t2_executed") return "t2";
  if (stage === "trailing" || stage === "exit_required") return "trail";
  if (stage === "closed") return previous;
  return previous;
}

function nearlyEqual(a: number, b: number): boolean {
  return Math.abs(a - b) <= EPS;
}

export function assertLifecycleFinancialInvariants(
  position: LifecycleFinancialPosition,
  opts?: { birthQty?: number; initialRisk?: number },
): void {
  const birthQty = opts?.birthQty ?? LIFECYCLE_BIRTH_QTY;
  const initialRisk = opts?.initialRisk ?? LIFECYCLE_INITIAL_RISK;
  const remaining =
    position.operational?.remainingQuantity ??
    position.operational?.operationalView?.remainingQuantity ??
    position.quantity;
  const viewQty = position.operational?.operationalView?.quantity ?? birthQty;
  const derived = derivePositionFinancials({
    avgCost: position.avgCost,
    lastPrice: position.lastPrice,
    remaining: position.quantity,
    initialRisk,
  });
  const errors: string[] = [];
  if (remaining < 0) errors.push(`remainingQuantity ${remaining} < 0`);
  if (remaining > viewQty) {
    errors.push(`remainingQuantity ${remaining} > birthQty ${viewQty}`);
  }
  if (!nearlyEqual(position.marketValue, derived.marketValue)) {
    errors.push(
      `marketValue ${position.marketValue} ≠ lastPrice×qty ${derived.marketValue}`,
    );
  }
  if (!nearlyEqual(position.unrealizedPnl, derived.unrealizedPnl)) {
    errors.push(
      `unrealizedPnl ${position.unrealizedPnl} ≠ (last-avg)×qty ${derived.unrealizedPnl}`,
    );
  }
  if (!nearlyEqual(position.unrealizedPnlPct, derived.unrealizedPnlPct)) {
    errors.push(
      `unrealizedPnlPct ${position.unrealizedPnlPct} ≠ ${derived.unrealizedPnlPct}`,
    );
  }
  const viewR = position.operational?.operationalView?.levels?.unrealizedR;
  const opR = position.operational?.unrealizedR;
  if (viewR != null && !nearlyEqual(viewR, derived.unrealizedR)) {
    errors.push(
      `levels.unrealizedR ${viewR} ≠ PnL/initialRisk ${derived.unrealizedR}`,
    );
  }
  if (opR != null && !nearlyEqual(opR, derived.unrealizedR)) {
    errors.push(
      `operational.unrealizedR ${opR} ≠ PnL/initialRisk ${derived.unrealizedR}`,
    );
  }
  if (errors.length > 0) {
    throw new Error(
      `lifecycle financial invariants:\n- ${errors.join("\n- ")}`,
    );
  }
}

type LineageBundle = {
  remaining: number;
  operatingState: string;
  primaryAction: string;
  status: string;
  target1Leg: TargetLeg;
  target2Leg: TargetLeg;
  t1: ViewLeg | null;
  t2: ViewLeg | null;
  stopHistory: StopHistoryEntry[];
  revisions: TrailRevision[];
  events: LifecycleEvent[];
};

function trailHistory(currentStop: number | undefined): StopHistoryEntry[] {
  const trailStop = (currentStop ?? 95) + 3;
  return [
    { label: "Initial", stop: currentStop, origin: "birth" },
    {
      label: "Trail #1",
      stop: trailStop,
      delta: 3,
      at: TRAIL_AT,
      origin: "trail",
    },
  ];
}

function trailRevisions(
  positionId: string,
  currentStop: number | undefined,
): TrailRevision[] {
  const trailStop = (currentStop ?? 95) + 3;
  return [
    {
      revisionId: `rev-trail-${positionId}`,
      at: TRAIL_AT,
      previousStop: currentStop,
      nextStop: trailStop,
      previousStatus: "PROTECTED",
      nextStatus: "PROTECTED",
      origin: "trail",
      reason: "trail",
    },
  ];
}

function t1ExecutedLeg(): LegExecuted {
  return { status: "executed", at: T1_EXEC_AT, fillId: MOCK_T1_FILL_ID };
}

function t1ExecutedView(): ViewLeg {
  return { status: "executed", at: T1_EXEC_AT, fillId: MOCK_T1_FILL_ID };
}

function t2ExecutedLeg(): LegExecuted {
  return { status: "executed", at: T2_EXEC_AT, fillId: MOCK_T2_FILL_ID };
}

function t2ExecutedView(): ViewLeg {
  return { status: "executed", at: T2_EXEC_AT, fillId: MOCK_T2_FILL_ID };
}

function t1Event(): LifecycleEvent {
  return { kind: "T1_EXECUTED", at: T1_EXEC_AT, fillId: MOCK_T1_FILL_ID };
}

function t2TriggeredEvent(): LifecycleEvent {
  return { kind: "T2_TRIGGERED", at: T2_AT };
}

function t2ExecutedEvent(): LifecycleEvent {
  return { kind: "T2_EXECUTED", at: T2_EXEC_AT, fillId: MOCK_T2_FILL_ID };
}

function lineageBundle(
  position: MercadoOpenPosition,
  stage: E2eGoldenPositionStage,
  lineagePath: LifecycleLineagePath,
  isLifecycle: boolean,
): LineageBundle {
  const levels = position.operational.operationalView.levels;
  const remaining = lifecycleRemainingForStage(stage, isLifecycle);
  const t1LifecycleLeg = isLifecycle
    ? t1ExecutedLeg()
    : ({ status: "pending" } as LegPending);
  const t1LifecycleView = isLifecycle ? t1ExecutedView() : null;
  const t1Events: LifecycleEvent[] = isLifecycle ? [t1Event()] : [];
  const trailStopHistory = trailHistory(levels.currentStop);
  const trailRevs = trailRevisions(position.id, levels.currentStop);

  const openBits = (): LineageBundle => ({
    remaining,
    operatingState: "PROTECTED",
    primaryAction: "MANTENER",
    status: "PROTECTED",
    target1Leg: { status: "pending" },
    target2Leg: { status: "pending" },
    t1: null,
    t2: null,
    stopHistory: [],
    revisions: [],
    events: [],
  });

  const t1ReadyBits = (): LineageBundle => ({
    remaining,
    operatingState: "T1_READY",
    primaryAction: "REDUCIR",
    status: "PROTECTED",
    target1Leg: { status: "triggered", at: T1_AT },
    target2Leg: { status: "pending" },
    t1: { status: "triggered", at: T1_AT },
    t2: null,
    stopHistory: [],
    revisions: [],
    events: [],
  });

  const t1ExecutedBits = (): LineageBundle => ({
    remaining,
    operatingState: "T1_EXECUTED",
    primaryAction: "MANTENER",
    status: "PARTIAL",
    target1Leg: t1ExecutedLeg(),
    target2Leg: { status: "pending" },
    t1: t1ExecutedView(),
    t2: null,
    stopHistory: [],
    revisions: [],
    events: [t1Event()],
  });

  const t2ReadyBits = (): LineageBundle => ({
    remaining,
    operatingState: "T2_READY",
    primaryAction: "MONITOR",
    status: "PARTIAL",
    target1Leg: t1ExecutedLeg(),
    target2Leg: { status: "triggered", at: T2_AT },
    t1: t1ExecutedView(),
    t2: { status: "triggered", at: T2_AT },
    stopHistory: [],
    revisions: [],
    events: [t1Event(), t2TriggeredEvent()],
  });

  const t2ExecutedBits = (): LineageBundle => ({
    remaining,
    operatingState: "T2_EXECUTED",
    primaryAction: "MONITOR",
    status: "PARTIAL",
    target1Leg: t1ExecutedLeg(),
    target2Leg: t2ExecutedLeg(),
    t1: t1ExecutedView(),
    t2: t2ExecutedView(),
    stopHistory: [],
    revisions: [],
    events: [t1Event(), t2TriggeredEvent(), t2ExecutedEvent()],
  });

  const trailingBits = (): LineageBundle => ({
    remaining,
    operatingState: "TRAILING",
    primaryAction: "SUBIR_STOP",
    status: "TRAILING",
    target1Leg: t1LifecycleLeg,
    target2Leg: { status: "pending" },
    t1: t1LifecycleView,
    t2: null,
    stopHistory: trailStopHistory,
    revisions: trailRevs,
    events: t1Events,
  });

  const t2Prefix = t2ExecutedBits();
  const trailPrefix = trailingBits();

  if (stage === "open") return openBits();
  if (stage === "t1_ready") return t1ReadyBits();
  if (stage === "t1_executed") return t1ExecutedBits();
  if (stage === "t2_ready") return t2ReadyBits();
  if (stage === "t2_executed") return t2ExecutedBits();
  if (stage === "trailing") return trailPrefix;

  if (stage === "exit_required") {
    const prefix = lineagePath === "t2" ? t2Prefix : trailPrefix;
    return {
      ...prefix,
      remaining,
      operatingState: "EXIT_REQUIRED",
      primaryAction: "SALIR",
    };
  }

  const prefix = lineagePath === "t2" ? t2Prefix : trailPrefix;
  return {
    ...prefix,
    remaining: 0,
    operatingState: "CLOSED",
    primaryAction: "MANTENER",
    status: "CLOSED",
    events: [...prefix.events, { kind: "POSITION_CLOSED", at: CLOSED_AT }],
  };
}

export function applyGoldenPositionStage(
  position: MercadoOpenPosition,
  stage: E2eGoldenPositionStage,
  lineagePath: LifecycleLineagePath = "trail",
): MercadoOpenPosition {
  if (stage === "clean" || stage === "candidate") return position;

  const levels = position.operational.operationalView.levels;
  const decisionId =
    position.operational.operationalView.decisionId ?? `dec-${position.id}`;
  const isLifecycle = position.id === E2E_LIFECYCLE_POSITION_ID;
  const lastPrice = isLifecycle
    ? lifecycleLastPriceForStage(stage, lineagePath)
    : position.lastPrice;
  const initialStop =
    position.operational.initialStop ??
    levels.currentStop ??
    LIFECYCLE_INITIAL_STOP;
  const initialRisk = (position.avgCost - initialStop) * LIFECYCLE_BIRTH_QTY;
  const bits = lineageBundle(position, stage, lineagePath, isLifecycle);
  const fin = derivePositionFinancials({
    avgCost: position.avgCost,
    lastPrice,
    remaining: bits.remaining,
    initialRisk,
  });

  return {
    ...position,
    quantity: fin.quantity,
    lastPrice,
    marketValue: fin.marketValue,
    unrealizedPnl: fin.unrealizedPnl,
    unrealizedPnlPct: fin.unrealizedPnlPct,
    operational: {
      ...position.operational,
      status: bits.status,
      remainingQuantity: bits.remaining,
      unrealizedR: fin.unrealizedR,
      target1Leg: bits.target1Leg,
      target2Leg: bits.target2Leg,
      revisions: bits.revisions,
      operationalView: {
        positionId: position.operational.operationalView.positionId,
        instrumentId: position.instrumentId,
        tradePlanId: position.operational.tradePlanId,
        decisionId,
        lineageCollapsed: false,
        operatingState: bits.operatingState,
        primaryAction: bits.primaryAction,
        levels: {
          ...levels,
          unrealizedR: fin.unrealizedR,
        },
        t1: bits.t1,
        t2: bits.t2,
        stopHistory: bits.stopHistory,
        events: bits.events,
        quantity: LIFECYCLE_BIRTH_QTY,
        remainingQuantity: bits.remaining,
      },
    },
  };
}

export function buildLifecycleSnapshot(opts: {
  stage: E2eGoldenPositionStage;
  lineagePath?: LifecycleLineagePath;
}): LifecycleAccountSnapshot {
  const stage = opts.stage;
  const lineagePath = opts.lineagePath ?? "trail";
  const hasPosition = stage !== "candidate";
  const projectedStage: E2eGoldenPositionStage =
    stage === "clean" ? "open" : stage;
  const position = hasPosition
    ? applyGoldenPositionStage(
        lifecycleOpenPosition(),
        projectedStage,
        lineagePath,
      )
    : null;
  const marketValue =
    position && position.quantity > 0 ? position.marketValue : 0;
  const dayPnl = position && position.quantity > 0 ? position.unrealizedPnl : 0;
  const openPositions =
    position != null && position.quantity > 0 && stage !== "candidate" ? 1 : 0;
  return {
    stage,
    lineagePath,
    position,
    cash: LIFECYCLE_CASH,
    totalEquity: LIFECYCLE_CASH + marketValue,
    openPositions,
    dayPnl,
    dayPnlPct: (dayPnl / LIFECYCLE_CASH) * 100,
  };
}

export function assertMonotonicClosedLineage(
  view: {
    t1?: { status?: string } | null;
    t2?: { status?: string } | null;
    stopHistory?: unknown[];
    events?: Array<{ kind?: string }>;
    remainingQuantity?: number;
  },
  path: LifecycleLineagePath,
): void {
  const events = view.events ?? [];
  const kinds = events.map((row) => row.kind);
  if (view.t1?.status !== "executed") {
    throw new Error(
      `CLOSED/EXIT lineage: expected t1 executed, got ${view.t1?.status}`,
    );
  }
  if (kinds.includes("T1_EXECUTED") !== true) {
    throw new Error("CLOSED/EXIT lineage: missing T1_EXECUTED event");
  }
  if (path === "t2") {
    if (view.t2?.status !== "executed") {
      throw new Error(`T2 path: expected t2 executed, got ${view.t2?.status}`);
    }
    if (!kinds.includes("T2_EXECUTED")) {
      throw new Error("T2 path: missing T2_EXECUTED event");
    }
  } else {
    if ((view.stopHistory?.length ?? 0) < 1) {
      throw new Error("trail path: expected stopHistory");
    }
  }
}

export function assertClosedLineage(
  view: {
    t1?: { status?: string } | null;
    t2?: { status?: string } | null;
    stopHistory?: unknown[];
    events?: Array<{ kind?: string }>;
    remainingQuantity?: number;
    operatingState?: string;
  },
  path: LifecycleLineagePath,
): void {
  assertMonotonicClosedLineage(view, path);
  if (view.operatingState !== "CLOSED") {
    throw new Error(`expected CLOSED, got ${view.operatingState}`);
  }
  if (view.remainingQuantity !== 0) {
    throw new Error(`CLOSED remainingQuantity ${view.remainingQuantity} ≠ 0`);
  }
  const last = view.events?.[view.events.length - 1];
  if (last?.kind !== "POSITION_CLOSED") {
    throw new Error(
      `CLOSED last event ${last?.kind ?? "none"} ≠ POSITION_CLOSED`,
    );
  }
}
