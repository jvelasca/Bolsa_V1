/**
 * V2.0.2 / V2.0.4 — PositionJourneyReadout: derived HUD for MERCADO DECISIÓN.
 * Composes lifecycle snapshot + POV + PositionState. Not a cockpit phase.
 * event log = truth · stage/lineagePath = derived · no second FSM.
 */

import type { PaperAutoPostureV1 } from "./paper-auto-posture.js";
import type { PaperDeskNextActionV1 } from "./operational-context.js";
import type {
  PositionOperationalViewV1,
  StopHistoryEntryV1,
} from "./position-operational-view.js";
import type { TargetLegStatusV1, TargetLegV1 } from "./position-state.js";
import { resolveExitPolicy, type ExitPolicyV1 } from "./exit-policy.js";
import { lifecycleStageLabel } from "./lifecycle-stage-label.js";

export type LifecycleSnapshotLiteV1 = {
  positionId?: string | null;
  stage?: string | null;
  /** last-wins classification — NOT history */
  lineagePath?: string | null;
  events?: ReadonlyArray<{ kind?: string | null } | Record<string, unknown>>;
};

export type JourneyLegReadoutV1 = {
  trigger: number | null;
  status: TargetLegStatusV1 | "absent";
  qtyFractionPct: number | null;
  executed: boolean;
};

export type JourneyRiskReadoutV1 = {
  /** Birth risk — immutable after trail/reduce (V1.99). */
  initialRisk: number | null;
  initialStop: number | null;
  /** Loss-at-current-stop in money units when geometry known; else null. */
  currentProtected: number | null;
  realizedR: number | null;
  unrealizedR: number | null;
  remainingQuantity: number;
};

export type JourneyTrailReadoutV1 = {
  active: boolean;
  /** Post-T1 activation (FSM rule). */
  activationEligible: boolean;
  currentStop: number | null;
  lastRatchet: StopHistoryEntryV1 | null;
  trailWidth: ExitPolicyV1["trailWidth"] | null;
};

export type PositionJourneyReadoutV1 = {
  entry: number | null;
  risk: JourneyRiskReadoutV1;
  t1: JourneyLegReadoutV1;
  t2: JourneyLegReadoutV1;
  trail: JourneyTrailReadoutV1;
  remainingQuantity: number;
  primaryAction: PaperDeskNextActionV1;
  /** Derived FSM stage label (not the log). */
  stageLabel: string | null;
  stageMachine: string | null;
  /** last-wins tag — never shown as history. */
  lineagePathLabel: string | null;
  /** True when log still contains T2_EXECUTED after later TRAIL. */
  logHasT2Executed: boolean;
  logHasTrailApplied: boolean;
  eventKinds: string[];
  autoPosture: PaperAutoPostureV1 | null;
  killOn: boolean | null;
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function legStatus(
  leg: TargetLegV1 | null | undefined,
): TargetLegStatusV1 | "absent" {
  if (!leg) return "absent";
  return leg.status;
}

function buildLeg(
  trigger: number | null | undefined,
  leg: TargetLegV1 | null | undefined,
  qtyFraction: number | null,
): JourneyLegReadoutV1 {
  const status = legStatus(leg);
  return {
    trigger: finite(trigger) ? trigger : null,
    status,
    qtyFractionPct:
      qtyFraction != null && Number.isFinite(qtyFraction)
        ? Math.round(qtyFraction * 100)
        : null,
    executed: status === "executed",
  };
}

/** Protected money at current stop vs entry (not R); null if geometry missing. */
export function deriveCurrentProtectedMoney(input: {
  entry: number | null | undefined;
  currentStop: number | null | undefined;
  remainingQuantity: number;
  direction?: "long" | "short" | null;
}): number | null {
  const entry = input.entry;
  const stop = input.currentStop;
  const qty = input.remainingQuantity;
  if (!finite(entry) || !finite(stop) || !finite(qty) || qty <= 0) return null;
  const isShort = input.direction === "short";
  const perUnit = isShort ? stop - entry : entry - stop;
  if (perUnit < 0) return 0;
  return Math.round(perUnit * qty * 100) / 100;
}

function lastTrailRatchet(
  history: ReadonlyArray<StopHistoryEntryV1>,
): StopHistoryEntryV1 | null {
  for (let i = history.length - 1; i >= 0; i--) {
    const e = history[i]!;
    if (e.origin === "trail" || e.label.startsWith("Trail")) return e;
  }
  return null;
}

function eventKindsFromSnapshot(
  snap: LifecycleSnapshotLiteV1 | null | undefined,
): string[] {
  const events = snap?.events ?? [];
  const kinds: string[] = [];
  for (const ev of events) {
    const kind =
      ev && typeof ev === "object" && "kind" in ev
        ? (ev as { kind?: unknown }).kind
        : undefined;
    if (typeof kind === "string" && kind) kinds.push(kind);
  }
  return kinds;
}

export function buildPositionJourneyReadout(input: {
  view: PositionOperationalViewV1;
  /** Optional PositionState-ish fields not on POV levels. */
  initialRisk?: number | null;
  initialStop?: number | null;
  realizedR?: number | null;
  direction?: "long" | "short" | null;
  templateId?: string | null;
  lifecycle?: LifecycleSnapshotLiteV1 | null;
  autoPosture?: PaperAutoPostureV1 | null;
  killOn?: boolean | null;
}): PositionJourneyReadoutV1 {
  const { view } = input;
  const policy = resolveExitPolicy(input.templateId ?? view.templateId);
  const kinds = eventKindsFromSnapshot(input.lifecycle);
  const stageMachine = input.lifecycle?.stage?.trim() || null;
  const lineageRaw = input.lifecycle?.lineagePath?.trim() || null;
  const t1Executed =
    view.t1?.status === "executed" || kinds.includes("T1_EXECUTED");
  const trailActive =
    view.operatingState === "TRAILING" ||
    kinds.includes("TRAIL_APPLIED") ||
    Boolean(lastTrailRatchet(view.stopHistory));

  const entry = view.levels.entry;
  const initialStop = finite(input.initialStop)
    ? input.initialStop
    : (view.stopHistory.find((h) => h.origin === "birth")?.stop ?? null);
  const initialRisk = finite(input.initialRisk) ? input.initialRisk : null;
  const currentStop = view.levels.currentStop;
  const currentProtected = deriveCurrentProtectedMoney({
    entry,
    currentStop,
    remainingQuantity: view.remainingQuantity,
    direction: input.direction,
  });

  return {
    entry,
    risk: {
      initialRisk,
      initialStop: finite(initialStop) ? initialStop : null,
      currentProtected,
      realizedR: finite(input.realizedR) ? input.realizedR : null,
      unrealizedR: finite(view.levels.unrealizedR)
        ? view.levels.unrealizedR
        : null,
      remainingQuantity: view.remainingQuantity,
    },
    t1: buildLeg(view.levels.target1, view.t1, policy.t1ReduceFraction),
    t2: buildLeg(view.levels.target2, view.t2, policy.t2ReduceFraction),
    trail: {
      active: trailActive,
      activationEligible: t1Executed,
      currentStop: finite(currentStop) ? currentStop : null,
      lastRatchet: lastTrailRatchet(view.stopHistory),
      trailWidth: policy.trailWidth,
    },
    remainingQuantity: view.remainingQuantity,
    primaryAction: view.primaryAction,
    stageLabel: lifecycleStageLabel(stageMachine),
    stageMachine,
    lineagePathLabel: lineageRaw,
    logHasT2Executed: kinds.includes("T2_EXECUTED"),
    logHasTrailApplied: kinds.includes("TRAIL_APPLIED"),
    eventKinds: kinds,
    autoPosture: input.autoPosture ?? null,
    killOn: input.killOn ?? null,
  };
}
