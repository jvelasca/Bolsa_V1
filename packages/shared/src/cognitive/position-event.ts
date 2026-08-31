/**
 * PositionEvent — vista canónica de ExitReason (V1.44).
 * No sustituye ExitPlan. No es autoridad. No persiste.
 */

import type { ExitReasonV1 } from "./exit-plan.js";

export type PositionEventKindV1 =
  | "STOP"
  | "T1"
  | "T2"
  | "TRAIL"
  | "INVALIDATION"
  | "TIME"
  | "PORTFOLIO_RISK"
  | "MANUAL";

export type PositionEventV1 = {
  kind: PositionEventKindV1;
  reasonCode: ExitReasonV1;
  at: string;
};

const KIND_BY_REASON: Record<ExitReasonV1, PositionEventKindV1> = {
  STRUCTURAL_STOP: "STOP",
  TARGET_1: "T1",
  TARGET_2: "T2",
  TRAIL: "TRAIL",
  THESIS_INVALIDATION: "INVALIDATION",
  TIME_STOP: "TIME",
  PORTFOLIO_RISK: "PORTFOLIO_RISK",
  MANUAL: "MANUAL",
};

export function positionEventKindFromReason(
  reason: ExitReasonV1 | null | undefined,
): PositionEventKindV1 | null {
  if (!reason) return null;
  return KIND_BY_REASON[reason] ?? null;
}

export function buildPositionEvent(
  reason: ExitReasonV1 | null | undefined,
  at: string,
): PositionEventV1 | null {
  const kind = positionEventKindFromReason(reason);
  if (!kind || !reason) return null;
  const stamp = typeof at === "string" && at.trim() ? at : "";
  if (!stamp) return null;
  return { kind, reasonCode: reason, at: stamp };
}

export function isTargetEventKind(kind: PositionEventKindV1 | null): boolean {
  return kind === "T1" || kind === "T2" || kind === "TIME";
}

export function isImmediateRiskReason(
  reason: ExitReasonV1 | null | undefined,
): boolean {
  return (
    reason === "STRUCTURAL_STOP" ||
    reason === "THESIS_INVALIDATION" ||
    reason === "PORTFOLIO_RISK"
  );
}
