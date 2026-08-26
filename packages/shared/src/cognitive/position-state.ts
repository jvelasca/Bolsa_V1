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
  return {
    positionId: fill.positionId?.trim() || createRandomId(),
    tradePlanId: tradePlan.decisionId,
    instrumentId: tradePlan.instrumentId,
    direction: tradePlan.direction,
    status: "OPEN",
    plannedEntry,
    actualEntry,
    initialStop,
    currentStop: initialStop,
    target1: finite(tradePlan.target1) ? tradePlan.target1 : null,
    target2: finite(tradePlan.target2) ? tradePlan.target2 : null,
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

function withRevisionIfChanged(
  previous: PositionStateV1,
  next: PositionStateV1,
  origin: PositionRevisionOriginV1,
  reason: string | null | undefined,
  at: string,
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
 */
export function applyPositionReduce(
  position: PositionStateV1 | null | undefined,
  qty: number,
  exitPrice?: number | null,
  at?: string | null,
  origin: PositionRevisionOriginV1 = "reduce",
  reason?: string | null,
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
  if (remaining <= 0) {
    const next: PositionStateV1 = {
      ...position,
      remainingQuantity: 0,
      realizedR,
      status: "CLOSED",
      exitStatus: "done",
      updatedAt,
    };
    return withRevisionIfChanged(position, next, origin, reason, updatedAt);
  }

  const mid: PositionStateV1 = {
    ...position,
    remainingQuantity: remaining,
    realizedR,
    updatedAt,
  };
  const next: PositionStateV1 = {
    ...mid,
    status: derivePositionStatus(mid),
  };
  return withRevisionIfChanged(position, next, origin, reason, updatedAt);
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
  );
}

/** Rehidrata revisions desde snapshot JSON (OI-5). */
export function positionStateRevisionsFromUnknown(
  raw: unknown,
): PositionRevisionV1[] {
  return revisionsFromUnknown(raw);
}
