/**
 * PositionState — autoridad post-entrada (ADR-032 F2 + F2.1).
 * Tesis ≠ plan ≠ permiso ≠ posición. Thin 5.x/8.x siguen advisory aparte; no se promocionan.
 */

import { createRandomId } from "../create-id.js";
import type { TradePlanDirectionV1, TradePlanV1 } from "./trade-plan.js";
import {
  buildPositionRevision,
  revisionsFromUnknown,
  stopOrStatusChanged,
  type PositionRevisionOriginV1,
  type PositionRevisionV1,
} from "./position-revision.js";

export type PositionStatusV1 = "OPEN" | "PARTIAL" | "PROTECTED" | "CLOSED";

export type PositionExitStatusV1 = "none" | "hint" | "armed" | "done";

/** V1.52 — T1/T2 durable. mark >= T1 ≠ executed. */
export type TargetLegStatusV1 = "pending" | "triggered" | "executed" | "failed";

export type TargetLegV1 = {
  status: TargetLegStatusV1;
  at?: string | null;
  eventId?: string | null;
  fillId?: string | null;
};

const VALID_TARGET_LEG: ReadonlySet<TargetLegStatusV1> = new Set([
  "pending",
  "triggered",
  "executed",
  "failed",
]);

/** Slot MFE/MAE en posición; C5 honesty — al nacer siempre source none. */
export type PositionMfeMaeSlotV1 = {
  mfeR: number | null;
  maeR: number | null;
  source: "none" | "bars" | "close_proxy";
};

export type PositionStubStatusV1 = {
  status: "none";
};

export type PositionStateV1 = {
  positionId: string;
  /** V1.65 — origen DecisionPackage (≠ tradePlanId cuando ambos existen). */
  decisionId?: string | null;
  tradePlanId: string;
  instrumentId: string;
  direction: TradePlanDirectionV1;
  status: PositionStatusV1;
  plannedEntry: number | null;
  actualEntry: number | null;
  initialStop: number | null;
  currentStop: number | null;
  target1: number | null;
  target2: number | null;
  /**
   * V1.21 — T1 ya consumido (idempotencia). Si set, ExitPlan no re-emite TARGET_1.
   * Ausente en snapshots legacy = no alcanzado.
   */
  target1AchievedAt?: string | null;
  /**
   * V1.27 — T2 ya consumido (idempotencia). Ausente en snapshots legacy = no alcanzado.
   */
  target2AchievedAt?: string | null;
  /** V1.52 — estado durable T1. Legacy se hidrata desde precio / achievedAt. */
  target1Leg?: TargetLegV1 | null;
  /** V1.52 — estado durable T2. */
  target2Leg?: TargetLegV1 | null;
  quantity: number;
  remainingQuantity: number;
  initialRisk: number | null;
  realizedR: number;
  unrealizedR: number | null;
  mfeMae: PositionMfeMaeSlotV1;
  /** Stub F2 — no se rellena desde runtime.thesisHealth thin. */
  thesisHealth: PositionStubStatusV1 | null;
  /** Stub F2 — no se rellena desde protectPlan/trailPlan thin. */
  protectionState: PositionStubStatusV1 | null;
  trailing: PositionStubStatusV1 | null;
  exitStatus: PositionExitStatusV1;
  createdAt: string;
  updatedAt: string;
  /** OI-5 — historia append-only de stop/status. */
  revisions: PositionRevisionV1[];
};

export type PositionFillV1 = {
  price: number;
  quantity: number;
  filledAt?: string | null;
  positionId?: string | null;
};

/** Override auditado (H2 / ADR-033 §5). Reason no vacío. No persiste. */
export type FactoryOverrideV1 = {
  reason: string;
};

export function isAuditedOverride(
  override: FactoryOverrideV1 | null | undefined,
): boolean {
  return (
    typeof override?.reason === "string" && override.reason.trim().length > 0
  );
}

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

function nowIso(at?: string | null): string {
  if (typeof at === "string" && at.trim()) return at;
  return new Date().toISOString();
}

function nonEmptyStr(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function targetLegFromUnknown(
  raw: unknown,
  price: number | null | undefined,
  achievedAt: string | null | undefined,
): TargetLegV1 | null {
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    const status = typeof o.status === "string" ? o.status : null;
    if (status && VALID_TARGET_LEG.has(status as TargetLegStatusV1)) {
      return {
        status: status as TargetLegStatusV1,
        at: nonEmptyStr(o.at),
        eventId: nonEmptyStr(o.eventId),
        fillId: nonEmptyStr(o.fillId),
      };
    }
  }
  const achieved = nonEmptyStr(achievedAt);
  if (achieved) {
    return { status: "executed", at: achieved, eventId: null, fillId: null };
  }
  if (finite(price) && price > 0) {
    return { status: "pending", at: null, eventId: null, fillId: null };
  }
  return null;
}

export function birthTargetLeg(
  price: number | null | undefined,
): TargetLegV1 | null {
  if (!finite(price) || price <= 0) return null;
  return { status: "pending", at: null, eventId: null, fillId: null };
}

function advanceTargetLeg(
  current: TargetLegV1 | null | undefined,
  nextStatus: TargetLegStatusV1,
  at: string,
  eventId?: string | null,
  fillId?: string | null,
): TargetLegV1 | null {
  if (!current) return current ?? null;
  if (current.status === "executed") {
    return current;
  }
  if (nextStatus === "failed" && current.status === "pending") {
    return current;
  }
  return {
    status: nextStatus,
    at,
    eventId: nonEmptyStr(eventId) ?? current.eventId ?? null,
    fillId: nonEmptyStr(fillId) ?? current.fillId ?? null,
  };
}

export function applyTargetLeg(
  position: PositionStateV1,
  which: "t1" | "t2",
  status: TargetLegStatusV1,
  at?: string | null,
  eventId?: string | null,
  fillId?: string | null,
): PositionStateV1 {
  const when = nowIso(at);
  if (which === "t1") {
    return {
      ...position,
      target1Leg: advanceTargetLeg(
        position.target1Leg,
        status,
        when,
        eventId,
        fillId,
      ),
      updatedAt: when,
    };
  }
  return {
    ...position,
    target2Leg: advanceTargetLeg(
      position.target2Leg,
      status,
      when,
      eventId,
      fillId,
    ),
    updatedAt: when,
  };
}

/** R firmado vs entry/risk. Sin inputs válidos → null. */
export function signedRFromPrice(
  direction: TradePlanDirectionV1,
  entry: number | null | undefined,
  risk: number | null | undefined,
  price: number,
): number | null {
  if (direction !== "long" && direction !== "short") return null;
  if (!finite(entry) || !finite(risk) || risk <= 0) return null;
  if (!finite(price) || price <= 0) return null;
  const raw =
    direction === "long" ? (price - entry) / risk : (entry - price) / risk;
  return round4(raw);
}

type PositionStatusFields = Pick<
  PositionStateV1,
  | "status"
  | "remainingQuantity"
  | "quantity"
  | "direction"
  | "actualEntry"
  | "currentStop"
>;

function isBreakEvenStop(position: PositionStatusFields): boolean {
  const entry = position.actualEntry;
  const stop = position.currentStop;
  if (!finite(entry) || !finite(stop)) return false;
  if (position.direction === "long") return stop >= entry;
  if (position.direction === "short") return stop <= entry;
  return false;
}

/**
 * Precedencia F2.1: CLOSED > BE→PROTECTED > PARTIAL > OPEN.
 * Mark no participa.
 */
export function derivePositionStatus(
  position: PositionStatusFields,
): PositionStatusV1 {
  if (position.status === "CLOSED" || position.remainingQuantity <= 0) {
    return "CLOSED";
  }
  if (isBreakEvenStop(position)) return "PROTECTED";
  if (position.remainingQuantity < position.quantity) return "PARTIAL";
  return "OPEN";
}

/** H2 — long: new stop lower than current; short: new stop higher. */
export function doesStopWorsen(
  direction: TradePlanDirectionV1 | string,
  current: number | null | undefined,
  next: number,
): boolean {
  if (!finite(current) || current <= 0) return false;
  if (direction === "long") return next < current - 1e-9;
  if (direction === "short") return next > current + 1e-9;
  return false;
}

/**
 * V1.29 — trail/protect advisory: nunca proponer un stop que empeore el vigente.
 * Si empeoraría, devuelve el stop actual (hold de riesgo).
 */
export function clampStopNotWorsen(
  direction: TradePlanDirectionV1 | string,
  current: number | null | undefined,
  next: number,
): number {
  if (!finite(next) || next <= 0) return next;
  if (
    doesStopWorsen(direction, current, next) &&
    finite(current) &&
    current > 0
  ) {
    return round4(current);
  }
  return round4(next);
}

function stopWorsens(
  direction: TradePlanDirectionV1,
  current: number | null | undefined,
  next: number,
): boolean {
  return doesStopWorsen(direction, current, next);
}

/**
 * Factory F2: TradePlan + fill → PositionState OPEN.
 * H2: exige status TRIGGERED, o override auditado. WATCH/ARMED no nacen.
 * Sin plan / sin fill válido → null (no inventa posición).
 */
export function buildPositionStateFromFill(
  tradePlan: TradePlanV1 | null | undefined,
  fill: PositionFillV1 | null | undefined,
  override?: FactoryOverrideV1 | null,
): PositionStateV1 | null {
  if (!tradePlan) return null;
  if (tradePlan.direction !== "long" && tradePlan.direction !== "short") {
    return null;
  }
  if (tradePlan.status !== "TRIGGERED" && !isAuditedOverride(override)) {
    return null;
  }
  if (!fill || !finite(fill.price) || fill.price <= 0) return null;
  if (!finite(fill.quantity) || fill.quantity <= 0) return null;

  const now = fill.filledAt ?? new Date().toISOString();
  const plannedEntry = finite(tradePlan.entry) ? tradePlan.entry : null;
  const plannedStop = finite(tradePlan.structuralStop)
    ? tradePlan.structuralStop
    : null;
  const actualEntry = round4(fill.price);
  const initialStop = plannedStop;
  const riskAnchor = actualEntry;
  const initialRisk =
    initialStop != null && riskAnchor > 0
      ? round4(Math.abs(riskAnchor - initialStop))
      : plannedEntry != null && plannedStop != null
        ? round4(Math.abs(plannedEntry - plannedStop))
        : null;

  const qty = round4(fill.quantity);
  const planDecisionId = tradePlan.decisionId;
  const planTradePlanId = tradePlan.tradePlanId?.trim() || planDecisionId;
  return {
    positionId: fill.positionId?.trim() || createRandomId(),
    decisionId: planDecisionId,
    tradePlanId: planTradePlanId,
    instrumentId: tradePlan.instrumentId,
    direction: tradePlan.direction,
    status: "OPEN",
    plannedEntry,
    actualEntry,
    initialStop,
    currentStop: initialStop,
    target1: finite(tradePlan.target1) ? tradePlan.target1 : null,
    target2: finite(tradePlan.target2) ? tradePlan.target2 : null,
    target1AchievedAt: null,
    target2AchievedAt: null,
    target1Leg: birthTargetLeg(
      finite(tradePlan.target1) ? tradePlan.target1 : null,
    ),
    target2Leg: birthTargetLeg(
      finite(tradePlan.target2) ? tradePlan.target2 : null,
    ),
    quantity: qty,
    remainingQuantity: qty,
    initialRisk: initialRisk != null && initialRisk > 0 ? initialRisk : null,
    realizedR: 0,
    unrealizedR: null,
    mfeMae: { mfeR: null, maeR: null, source: "none" },
    thesisHealth: { status: "none" },
    protectionState: { status: "none" },
    trailing: { status: "none" },
    exitStatus: "none",
    createdAt: now,
    updatedAt: now,
    revisions: [],
  };
}

function resolveRevisionDecisionId(
  position: PositionStateV1,
  lineage?: { decisionId?: string | null; policyId?: string | null } | null,
): string | null {
  return (
    nonEmptyStr(lineage?.decisionId) ?? nonEmptyStr(position.decisionId) ?? null
  );
}

function withRevisionIfChanged(
  previous: PositionStateV1,
  next: PositionStateV1,
  origin: PositionRevisionOriginV1,
  reason: string | null | undefined,
  at: string,
  lineage?: { decisionId?: string | null; policyId?: string | null } | null,
): PositionStateV1 {
  if (
    !stopOrStatusChanged({
      previousStop: previous.currentStop,
      nextStop: next.currentStop,
      previousStatus: previous.status,
      nextStatus: next.status,
    })
  ) {
    return next;
  }
  const revision = buildPositionRevision({
    at,
    previousStop: previous.currentStop,
    nextStop: next.currentStop,
    previousStatus: previous.status,
    nextStatus: next.status,
    origin,
    reason: reason ?? null,
    decisionId: resolveRevisionDecisionId(previous, lineage),
    policyId: lineage?.policyId ?? null,
  });
  return {
    ...next,
    revisions: [...(previous.revisions ?? []), revision],
  };
}

/**
 * F2.1 mark → unrealizedR + picos MFE/MAE (source close_proxy si era none).
 * No cambia status. CLOSED / inputs inválidos → null.
 */
export function applyPositionMark(
  position: PositionStateV1 | null | undefined,
  markPrice: number,
  at?: string | null,
): PositionStateV1 | null {
  if (!position || position.status === "CLOSED") return null;
  if (!finite(markPrice) || markPrice <= 0) return null;

  const unrealizedR = signedRFromPrice(
    position.direction,
    position.actualEntry,
    position.initialRisk,
    markPrice,
  );

  let mfeMae = position.mfeMae;
  if (unrealizedR != null) {
    const prevMfe = finite(mfeMae.mfeR) ? mfeMae.mfeR : unrealizedR;
    const prevMae = finite(mfeMae.maeR) ? mfeMae.maeR : unrealizedR;
    const source = mfeMae.source === "none" ? "close_proxy" : mfeMae.source;
    mfeMae = {
      mfeR: round4(Math.max(prevMfe, unrealizedR)),
      maeR: round4(Math.min(prevMae, unrealizedR)),
      source,
    };
  }

  return {
    ...position,
    unrealizedR,
    mfeMae,
    updatedAt: nowIso(at),
  };
}

/**
 * F2.1 reduce → remaining / realizedR / PARTIAL|CLOSED.
 * CLOSED terminal; qty inválida → null.
 * OI-5: append revisión si status cambia.
 * V1.21: `markTarget1Achieved` fija target1AchievedAt (idempotencia T1).
 * V1.27: `markTarget2Achieved` fija target2AchievedAt (idempotencia T2).
 */
export function applyPositionReduce(
  position: PositionStateV1 | null | undefined,
  qty: number,
  exitPrice?: number | null,
  at?: string | null,
  origin: PositionRevisionOriginV1 = "reduce",
  reason?: string | null,
  options?: {
    markTarget1Achieved?: boolean;
    markTarget2Achieved?: boolean;
    fillId?: string | null;
    eventId?: string | null;
    decisionId?: string | null;
    policyId?: string | null;
  } | null,
): PositionStateV1 | null {
  if (!position || position.status === "CLOSED") return null;
  if (!finite(qty) || qty <= 0) return null;
  if (qty > position.remainingQuantity + 1e-12) return null;

  const cut = round4(Math.min(qty, position.remainingQuantity));
  const remaining = round4(position.remainingQuantity - cut);
  let realizedR = position.realizedR;
  if (finite(exitPrice) && exitPrice > 0 && position.quantity > 0) {
    const sliceR = signedRFromPrice(
      position.direction,
      position.actualEntry,
      position.initialRisk,
      exitPrice,
    );
    if (sliceR != null) {
      realizedR = round4(realizedR + sliceR * (cut / position.quantity));
    }
  }

  const updatedAt = nowIso(at);
  const target1AchievedAt =
    options?.markTarget1Achieved === true
      ? (position.target1AchievedAt ?? updatedAt)
      : (position.target1AchievedAt ?? null);
  const target2AchievedAt =
    options?.markTarget2Achieved === true
      ? (position.target2AchievedAt ?? updatedAt)
      : (position.target2AchievedAt ?? null);
  const target1Leg =
    options?.markTarget1Achieved === true
      ? advanceTargetLeg(
          position.target1Leg,
          "executed",
          updatedAt,
          options.eventId,
          options.fillId,
        )
      : (position.target1Leg ?? null);
  const target2Leg =
    options?.markTarget2Achieved === true
      ? advanceTargetLeg(
          position.target2Leg,
          "executed",
          updatedAt,
          options.eventId,
          options.fillId,
        )
      : (position.target2Leg ?? null);
  const lineage = {
    decisionId: options?.decisionId ?? position.decisionId ?? null,
    policyId: options?.policyId ?? null,
  };

  if (remaining <= 0) {
    const next: PositionStateV1 = {
      ...position,
      remainingQuantity: 0,
      realizedR,
      status: "CLOSED",
      exitStatus: "done",
      target1AchievedAt,
      target2AchievedAt,
      target1Leg,
      target2Leg,
      updatedAt,
    };
    return withRevisionIfChanged(
      position,
      next,
      origin,
      reason,
      updatedAt,
      lineage,
    );
  }

  const mid: PositionStateV1 = {
    ...position,
    remainingQuantity: remaining,
    realizedR,
    target1AchievedAt,
    target2AchievedAt,
    target1Leg,
    target2Leg,
    updatedAt,
  };
  const next: PositionStateV1 = {
    ...mid,
    status: derivePositionStatus(mid),
  };
  return withRevisionIfChanged(
    position,
    next,
    origin,
    reason,
    updatedAt,
    lineage,
  );
}

/**
 * F2.1 currentStop geométrico → posible PROTECTED (BE).
 * H2: no empeora el stop sin override auditado.
 * OI-5: append revisión si stop o status cambian de verdad.
 * No lee thin. CLOSED / stop inválido / empeora → null.
 */
export function applyPositionCurrentStop(
  position: PositionStateV1 | null | undefined,
  stop: number,
  at?: string | null,
  override?: FactoryOverrideV1 | null,
  origin?: PositionRevisionOriginV1 | null,
  reason?: string | null,
  lineage?: { decisionId?: string | null; policyId?: string | null } | null,
): PositionStateV1 | null {
  if (!position || position.status === "CLOSED") return null;
  if (!finite(stop) || stop <= 0) return null;
  const worsens = stopWorsens(position.direction, position.currentStop, stop);
  if (worsens && !isAuditedOverride(override)) {
    return null;
  }

  const updatedAt = nowIso(at);
  const mid: PositionStateV1 = {
    ...position,
    currentStop: round4(stop),
    updatedAt,
  };
  const next: PositionStateV1 = {
    ...mid,
    status: derivePositionStatus(mid),
  };

  const resolvedOrigin: PositionRevisionOriginV1 =
    origin ?? (worsens ? "override" : "stop");
  const resolvedReason =
    reason ??
    (typeof override?.reason === "string" && override.reason.trim()
      ? override.reason.trim()
      : null);

  return withRevisionIfChanged(
    position,
    next,
    resolvedOrigin,
    resolvedReason,
    updatedAt,
    {
      decisionId: lineage?.decisionId ?? position.decisionId ?? null,
      policyId: lineage?.policyId ?? null,
    },
  );
}

/** Rehidrata revisions desde snapshot JSON (OI-5). */
export function positionStateRevisionsFromUnknown(
  raw: unknown,
): PositionRevisionV1[] {
  return revisionsFromUnknown(raw);
}
