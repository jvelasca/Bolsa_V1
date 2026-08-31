/**
 * PositionDecision — proyección operativa de posición (V1.27).
 * No es entidad durable ni segundo motor de salida.
 * Consume ExitPlan (evento) + ExitPolicy + recon + tesis → qué hacer ahora.
 */

import {
  buildExitPlanFromPosition,
  type ExitPlanSignalsV1,
  type ExitPlanStatusV1,
  type ExitPlanV1,
} from "./exit-plan.js";
import { resolveExitPolicy, type ExitPolicyV1 } from "./exit-policy.js";
import type { PositionStateV1 } from "./position-state.js";

export type PositionDecisionActionV1 =
  | "HOLD"
  | "PROTECT"
  | "REDUCE"
  | "TAKE_PROFIT"
  | "EXIT"
  | "REVIEW";

export type PositionAttentionV1 = "NORMAL" | "ATTENTION" | "URGENT" | "BLOCKED";

export type PositionNextEventV1 =
  | "NONE"
  | "T1"
  | "T2"
  | "STOP"
  | "TRAIL"
  | "THESIS_REVIEW"
  | "RECONCILIATION";

export type PositionReconHealthV1 = "CLEAN" | "ATTENTION" | "CRITICAL";

export type PositionProtectionV1 = "ACTIVE" | "NONE";

export type PositionUrgencyV1 = "LOW" | "MEDIUM" | "HIGH";

export const RECON_HEALTH_COPY: Record<PositionReconHealthV1, string> = {
  CLEAN: "Operativa normal",
  ATTENTION: "Operativa: atención",
  CRITICAL: "Operativa bloqueada",
};

export type PositionDecisionV1 = {
  positionId: string;
  tradePlanId: string;
  action: PositionDecisionActionV1;
  reason: string;
  confidence: number;
  urgency: PositionUrgencyV1;
  evidenceStrength: number;
  attention: PositionAttentionV1;
  nextEvent: PositionNextEventV1;
  protection: PositionProtectionV1;
  reconHealth: PositionReconHealthV1;
  suggestedQty: number | null;
  suggestedStop: number | null;
  primaryReason: string | null;
  marketAsOf: string | null;
  expiresAt: string | null;
};

const STATUS_CONFIDENCE: Record<ExitPlanStatusV1, number> = {
  TRIGGERED: 0.9,
  ARMED: 0.75,
  HINT: 0.65,
  IDLE: 0.55,
  DONE: 0.5,
};

const RECON_CONFIDENCE: Record<PositionReconHealthV1, number> = {
  CLEAN: 1,
  ATTENTION: 0.85,
  CRITICAL: 0.5,
};

export function mapReconStatusToHealth(
  status: string | null | undefined,
): PositionReconHealthV1 {
  const s = String(status ?? "")
    .trim()
    .toLowerCase();
  if (s === "drift") return "CRITICAL";
  if (s === "clean" || s === "ok") return "CLEAN";
  return "ATTENTION";
}

export function reconHealthToAttention(
  health: PositionReconHealthV1,
): PositionAttentionV1 {
  if (health === "CRITICAL") return "BLOCKED";
  if (health === "ATTENTION") return "ATTENTION";
  return "NORMAL";
}

export function attentionToUrgency(
  attention: PositionAttentionV1,
): PositionUrgencyV1 {
  if (attention === "URGENT" || attention === "BLOCKED") return "HIGH";
  if (attention === "ATTENTION") return "MEDIUM";
  return "LOW";
}

function maxAttention(
  a: PositionAttentionV1,
  b: PositionAttentionV1,
): PositionAttentionV1 {
  const rank: Record<PositionAttentionV1, number> = {
    NORMAL: 0,
    ATTENTION: 1,
    URGENT: 2,
    BLOCKED: 3,
  };
  return rank[a] >= rank[b] ? a : b;
}

function protectionState(position: PositionStateV1): PositionProtectionV1 {
  return position.currentStop != null ? "ACTIVE" : "NONE";
}

function nextEventFromPosition(
  position: PositionStateV1,
  exitPlan: ExitPlanV1,
): PositionNextEventV1 {
  const primary = exitPlan.primaryReason;
  if (primary === "STRUCTURAL_STOP") return "STOP";
  if (primary === "THESIS_INVALIDATION") return "THESIS_REVIEW";
  if (primary === "TARGET_1") return "T1";
  if (primary === "TARGET_2") return "T2";
  if (primary === "TRAIL") return "TRAIL";
  if (!position.target1AchievedAt && position.target1 != null) return "T1";
  if (!position.target2AchievedAt && position.target2 != null) return "T2";
  return "NONE";
}

function markProximityFactor(
  position: PositionStateV1,
  markPrice: number | null | undefined,
  nextEvent: PositionNextEventV1,
): number {
  if (typeof markPrice !== "number" || !Number.isFinite(markPrice)) return 0.85;
  let target: number | null = null;
  if (nextEvent === "T1" && position.target1 != null) target = position.target1;
  else if (nextEvent === "T2" && position.target2 != null) {
    target = position.target2;
  }
  if (target == null || target <= 0) return 0.9;
  const entry = position.actualEntry ?? position.plannedEntry;
  if (entry == null || entry <= 0) return 0.9;
  const span = Math.abs(target - entry);
  if (span <= 1e-9) return 0.9;
  const progress = Math.abs(markPrice - entry) / span;
  return Math.min(1, Math.max(0.75, 0.75 + progress * 0.25));
}

function evidenceStrengthFromSignals(
  exitPlan: ExitPlanV1,
  reconHealth: PositionReconHealthV1,
  markPrice: number | null | undefined,
): number {
  let score = 0.2;
  if (exitPlan.primaryReason) score += 0.25;
  if (typeof markPrice === "number" && Number.isFinite(markPrice)) score += 0.2;
  if (reconHealth === "CLEAN") score += 0.2;
  else if (reconHealth === "ATTENTION") score += 0.1;
  if (exitPlan.status === "TRIGGERED" || exitPlan.status === "ARMED") {
    score += 0.15;
  }
  return Math.round(Math.min(1, Math.max(0, score)) * 10000) / 10000;
}

function decisionConfidence(
  exitPlan: ExitPlanV1,
  reconHealth: PositionReconHealthV1,
  position: PositionStateV1,
  markPrice: number | null | undefined,
  nextEvent: PositionNextEventV1,
): number {
  const base = STATUS_CONFIDENCE[exitPlan.status] ?? 0.55;
  const recon = RECON_CONFIDENCE[reconHealth];
  const proximity = markProximityFactor(position, markPrice, nextEvent);
  const value = base * recon * proximity;
  return Math.round(Math.min(1, Math.max(0, value)) * 10000) / 10000;
}

function actionFromPlan(
  exitPlan: ExitPlanV1,
  reconHealth: PositionReconHealthV1,
  thesisInvalid: boolean,
): PositionDecisionActionV1 {
  if (reconHealth === "CRITICAL") return "REVIEW";
  if (thesisInvalid || exitPlan.primaryReason === "THESIS_INVALIDATION") {
    return "REVIEW";
  }
  const primary = exitPlan.primaryReason;
  const sug = exitPlan.suggestedAction;
  if (sug === "protect") return "PROTECT";
  if (sug === "full_exit") return "EXIT";
  if (sug === "reduce") {
    if (primary === "TARGET_1" || primary === "TARGET_2") return "TAKE_PROFIT";
    return "REDUCE";
  }
  return "HOLD";
}

export type BuildPositionDecisionInputV1 = {
  position: PositionStateV1 | null | undefined;
  signals?: ExitPlanSignalsV1 | null;
  exitPolicy?: ExitPolicyV1 | null;
  templateId?: string | null;
  portfolioReconStatus?: string | null;
  thesisInvalid?: boolean | null;
  at?: string | null;
};

export function buildPositionDecision(
  input: BuildPositionDecisionInputV1,
): PositionDecisionV1 | null {
  const position = input.position;
  if (!position) return null;
  if (position.direction !== "long" && position.direction !== "short") {
    return null;
  }

  const policy =
    input.exitPolicy ??
    (input.templateId ? resolveExitPolicy(input.templateId) : undefined);
  const thesisInvalid = input.thesisInvalid === true;
  const signals: ExitPlanSignalsV1 = {
    ...(input.signals ?? {}),
    thesisInvalid: thesisInvalid || input.signals?.thesisInvalid === true,
    exitPolicy: policy ?? input.signals?.exitPolicy,
    at: input.at ?? input.signals?.at,
  };
  const exitPlan = buildExitPlanFromPosition(position, signals);
  if (!exitPlan) return null;

  const reconHealth = mapReconStatusToHealth(input.portfolioReconStatus);
  let attention = reconHealthToAttention(reconHealth);
  if (reconHealth === "CRITICAL") {
    attention = "BLOCKED";
  }

  const action = actionFromPlan(exitPlan, reconHealth, thesisInvalid);
  const primary = exitPlan.primaryReason;
  const protection = protectionState(position);

  if (primary === "STRUCTURAL_STOP") {
    attention = maxAttention(attention, "URGENT");
  } else if (thesisInvalid || primary === "THESIS_INVALIDATION") {
    attention = maxAttention(attention, "URGENT");
  } else if (
    action === "REDUCE" ||
    action === "TAKE_PROFIT" ||
    action === "EXIT" ||
    action === "PROTECT"
  ) {
    attention = maxAttention(attention, "ATTENTION");
  }

  let reason = "hold";
  if (reconHealth === "CRITICAL") reason = "reconciliation:portfolio_drift";
  else if (primary) reason = primary.toLowerCase();
  else if (action === "HOLD") reason = "hold";

  const nextEvent =
    reconHealth === "CRITICAL"
      ? "RECONCILIATION"
      : nextEventFromPosition(position, exitPlan);
  const markPrice = signals.markPrice;
  const urgency = attentionToUrgency(attention);
  const evidenceStrength = evidenceStrengthFromSignals(
    exitPlan,
    reconHealth,
    markPrice,
  );
  const confidence = decisionConfidence(
    exitPlan,
    reconHealth,
    position,
    markPrice,
    nextEvent,
  );

  const stamp =
    typeof input.at === "string" && input.at.trim()
      ? input.at
      : exitPlan.updatedAt;

  return {
    positionId: position.positionId,
    tradePlanId: position.tradePlanId,
    action,
    reason,
    confidence,
    urgency,
    evidenceStrength,
    attention,
    nextEvent,
    protection,
    reconHealth,
    suggestedQty: exitPlan.suggestedQty,
    suggestedStop: exitPlan.suggestedStop,
    primaryReason: exitPlan.primaryReason,
    marketAsOf: stamp,
    expiresAt: null,
  };
}
