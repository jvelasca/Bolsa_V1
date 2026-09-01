/**
 * V1.55 — PositionOperationalView: canonical projection for "what to do now".
 * V1.57 — T2_EXECUTED · stopHistory 5 orígenes · RECONCILIATION_DRIFT.
 * Does not replace PositionState; derived from durable state + ExitPlan + recon.
 *
 * @see docs/engineering/spec-v157-operational-truth-2026-09-01.md
 */

import type { PositionRevisionOriginV1 } from "./position-revision.js";
import type { PositionStateV1, TargetLegV1 } from "./position-state.js";
import { assertNever } from "./never.js";
import {
  resolvePaperDeskNextAction,
  resolvePositionOperatingState,
  type PaperDeskNextActionV1,
  type PositionOperatingStateV1,
} from "./operational-context.js";
import { revisionsFromUnknown } from "./position-revision.js";

/** Extended operating state for UI (projection only). */
export type PositionOperationalStateV1 =
  | PositionOperatingStateV1
  | "PROTECT_REQUIRED"
  | "T1_READY"
  | "T1_EXECUTED"
  | "T2_READY"
  | "T2_EXECUTED"
  | "EXIT_REQUIRED";

export type PositionOperationalEventKindV1 =
  | "STOP_LEVEL_REACHED"
  | "STOP_ORDER_TRIGGERED"
  | "STOP_FILL"
  | "POSITION_CLOSED"
  | "T1_TRIGGERED"
  | "T1_FILL"
  | "T1_EXECUTED"
  | "T2_TRIGGERED"
  | "T2_FILL"
  | "T2_EXECUTED";

export type PositionOperationalEventV1 = {
  kind: PositionOperationalEventKindV1;
  at?: string | null;
  fillId?: string | null;
};

export type StopHistoryEntryV1 = {
  label: string;
  stop: number;
  delta?: number | null;
  at?: string | null;
  origin?: string | null;
};

export type PositionOperationalLevelsV1 = {
  entry: number | null;
  currentStop: number | null;
  target1: number | null;
  target2: number | null;
  unrealizedR: number | null;
};

export type PositionOperationalViewV1 = {
  positionId: string;
  instrumentId: string;
  tradePlanId: string;
  decisionId: string;
  operatingState: PositionOperationalStateV1;
  primaryAction: PaperDeskNextActionV1;
  levels: PositionOperationalLevelsV1;
  t1: TargetLegV1 | null;
  t2: TargetLegV1 | null;
  stopHistory: StopHistoryEntryV1[];
  events: PositionOperationalEventV1[];
  quantity: number;
  remainingQuantity: number;
  templateId?: string | null;
  analysisAsOf?: string | null;
};

export type BuildPositionOperationalViewInputV1 = {
  position: PositionStateV1;
  mark?: number | null;
  reconStatus?: "clean" | "drift" | "unavailable" | null;
  stopTouched?: boolean;
  exitPending?: boolean;
  templateId?: string | null;
  analysisAsOf?: string | null;
  /** Paper desk cycle status for nextAction mapping. */
  deskStatus?: string | null;
  decisionVerdict?: string | null;
};

function resolveExtendedOperatingState(input: {
  position: PositionStateV1;
  reconStatus?: string | null;
  stopTouched?: boolean;
  exitPending?: boolean;
}): PositionOperationalStateV1 {
  const base = resolvePositionOperatingState({
    positionStatus: input.position.status,
    remainingQuantity: input.position.remainingQuantity,
    quantity: input.position.quantity,
    hasTrailRevision: input.position.revisions.some(
      (r) => r.origin === "trail",
    ),
    hasProtectRevision: input.position.revisions.some(
      (r) => r.origin === "protect",
    ),
    reconStatus:
      input.reconStatus === "drift" || input.reconStatus === "unavailable"
        ? input.reconStatus
        : "clean",
    hasUnresolvedExit: input.exitPending ?? false,
  });
  if (base === "RECONCILIATION_ERROR" || base === "RECONCILIATION_DRIFT") {
    return base;
  }
  if (base === "CLOSED") return "CLOSED";
  if (input.stopTouched && input.position.status !== "CLOSED") {
    return "EXIT_REQUIRED";
  }
  const t2 = input.position.target2Leg;
  if (t2?.status === "executed") return "T2_EXECUTED";
  if (t2?.status === "triggered") return "T2_READY";
  const t1 = input.position.target1Leg;
  if (t1?.status === "executed") return "T1_EXECUTED";
  if (t1?.status === "triggered") return "T1_READY";
  if (
    base === "OPEN_UNPROTECTED" &&
    input.position.currentStop != null &&
    input.position.revisions.length === 0
  ) {
    return "PROTECT_REQUIRED";
  }
  return base;
}

function stopHistoryLabel(
  origin: PositionRevisionOriginV1,
  trailIdx: { n: number },
): string {
  switch (origin) {
    case "protect":
      return "Protect";
    case "trail":
      return `Trail #${++trailIdx.n}`;
    case "reduce":
      return "Reduce";
    case "override":
      return "Ajuste manual";
    case "stop":
      return "Stop";
    default:
      return assertNever(origin);
  }
}

export function buildStopHistory(
  position: PositionStateV1,
): StopHistoryEntryV1[] {
  const entries: StopHistoryEntryV1[] = [];
  const initial = position.initialStop;
  if (initial != null) {
    entries.push({ label: "Initial", stop: initial, origin: "birth" });
  }
  const trailIdx = { n: 0 };
  let prev = initial;
  for (const rev of position.revisions) {
    const stop = rev.nextStop;
    if (stop == null) continue;
    const label = stopHistoryLabel(rev.origin, trailIdx);
    const delta = prev != null ? stop - prev : null;
    entries.push({
      label,
      stop,
      delta,
      at: rev.at ?? null,
      origin: rev.origin,
    });
    prev = stop;
  }
  if (
    position.currentStop != null &&
    (entries.length === 0 ||
      entries[entries.length - 1]?.stop !== position.currentStop)
  ) {
    const last = entries[entries.length - 1]?.stop;
    entries.push({
      label: "Current",
      stop: position.currentStop,
      delta: last != null ? position.currentStop - last : null,
      origin: "current",
    });
  }
  return entries;
}

export function buildPositionOperationalEvents(input: {
  position: PositionStateV1;
  stopTouched?: boolean;
  stopFillId?: string | null;
}): PositionOperationalEventV1[] {
  const events: PositionOperationalEventV1[] = [];
  const { position } = input;
  if (input.stopTouched) {
    events.push({ kind: "STOP_LEVEL_REACHED" });
  }
  if (position.status === "CLOSED") {
    events.push({ kind: "POSITION_CLOSED" });
    if (input.stopFillId) {
      events.push({ kind: "STOP_FILL", fillId: input.stopFillId });
    }
  }
  const t1 = position.target1Leg;
  if (t1?.status === "triggered") {
    events.push({ kind: "T1_TRIGGERED", at: t1.at ?? null });
  }
  if (t1?.status === "executed") {
    events.push({
      kind: "T1_EXECUTED",
      at: t1.at ?? null,
      fillId: t1.fillId ?? null,
    });
    if (t1.fillId) {
      events.push({ kind: "T1_FILL", fillId: t1.fillId });
    }
  }
  const t2 = position.target2Leg;
  if (t2?.status === "triggered") {
    events.push({ kind: "T2_TRIGGERED", at: t2.at ?? null });
  }
  if (t2?.status === "executed") {
    events.push({
      kind: "T2_EXECUTED",
      at: t2.at ?? null,
      fillId: t2.fillId ?? null,
    });
    if (t2.fillId) {
      events.push({ kind: "T2_FILL", fillId: t2.fillId });
    }
  }
  return events;
}

export function buildPositionOperationalView(
  input: BuildPositionOperationalViewInputV1,
): PositionOperationalViewV1 {
  const { position } = input;
  const operatingState = resolveExtendedOperatingState({
    position,
    reconStatus: input.reconStatus,
    stopTouched: input.stopTouched,
    exitPending: input.exitPending,
  });
  const primaryAction = resolvePaperDeskNextAction({
    status: input.deskStatus ?? mapOperatingStateToDeskStatus(operatingState),
    decisionVerdict: input.decisionVerdict ?? null,
  });
  return {
    positionId: position.positionId,
    instrumentId: position.instrumentId,
    tradePlanId: position.tradePlanId,
    decisionId: position.tradePlanId,
    operatingState,
    primaryAction,
    levels: {
      entry: position.actualEntry ?? position.plannedEntry,
      currentStop: position.currentStop,
      target1: position.target1,
      target2: position.target2,
      unrealizedR: position.unrealizedR,
    },
    t1: position.target1Leg ?? null,
    t2: position.target2Leg ?? null,
    stopHistory: buildStopHistory(position),
    events: buildPositionOperationalEvents({
      position,
      stopTouched: input.stopTouched,
    }),
    quantity: position.quantity,
    remainingQuantity: position.remainingQuantity,
    templateId: input.templateId ?? null,
    analysisAsOf: input.analysisAsOf ?? null,
  };
}

export function mapOperatingStateToDeskStatus(
  state: PositionOperationalStateV1,
): string {
  switch (state) {
    case "PROTECT_REQUIRED":
    case "OPEN_UNPROTECTED":
      return "held";
    case "T1_READY":
    case "T1_EXECUTED":
    case "T2_READY":
    case "T2_EXECUTED":
    case "PARTIALLY_REDUCED":
      return "reduced";
    case "EXIT_REQUIRED":
    case "EXIT_PENDING":
    case "CLOSED":
      return "exited";
    case "TRAILING":
    case "PROTECTED":
      return "protected";
    case "RECONCILIATION_ERROR":
    case "RECONCILIATION_DRIFT":
      return "denied";
    default:
      return assertNever(state);
  }
}

/** Rehydrate revisions if position came from DTO blob. */
export function positionOperationalViewFromBlob(
  raw: Record<string, unknown>,
  input?: Omit<BuildPositionOperationalViewInputV1, "position">,
): PositionOperationalViewV1 | null {
  const positionId = raw.positionId;
  if (typeof positionId !== "string") return null;
  const revisions = revisionsFromUnknown(raw.revisions);
  const position = raw as unknown as PositionStateV1;
  return buildPositionOperationalView({
    position: { ...position, revisions },
    ...input,
  });
}
