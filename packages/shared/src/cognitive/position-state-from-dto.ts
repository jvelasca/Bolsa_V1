/**
 * Reconstruye PositionStateV1 mínimo desde PositionDto wire (V1.36 cockpit).
 * Proyección cliente; la autoridad sigue en backend persistido.
 */

import type { PositionDto } from "../types.js";
import {
  buildPositionDecision,
  type PositionDecisionV1,
} from "./position-decision.js";
import type { PositionStateV1, PositionStatusV1 } from "./position-state.js";

const VALID_STATUS = new Set<PositionStatusV1>([
  "OPEN",
  "PARTIAL",
  "PROTECTED",
  "CLOSED",
]);

export function positionStateFromPositionDto(
  position: PositionDto,
): PositionStateV1 | null {
  const op = position.operational;
  if (!op?.tradePlanId) return null;
  const direction = op.direction === "short" ? "short" : "long";
  const qty = Math.abs(Number(position.quantity ?? 0));
  if (qty <= 0) return null;
  const status = VALID_STATUS.has(op.status as PositionStatusV1)
    ? (op.status as PositionStatusV1)
    : "OPEN";
  const now = new Date().toISOString();
  const decisionId =
    typeof op.decisionId === "string" && op.decisionId.trim()
      ? op.decisionId.trim()
      : typeof op.originThesis?.decisionId === "string" &&
          op.originThesis.decisionId.trim()
        ? op.originThesis.decisionId.trim()
        : null;
  return {
    positionId: position.id,
    decisionId,
    tradePlanId: op.tradePlanId,
    instrumentId: position.instrumentId,
    direction,
    status,
    plannedEntry:
      typeof op.plannedEntry === "number" ? op.plannedEntry : position.avgCost,
    actualEntry:
      typeof op.actualEntry === "number" ? op.actualEntry : position.avgCost,
    initialStop: op.initialStop ?? null,
    currentStop: op.currentStop ?? null,
    target1: op.target1 ?? null,
    target2: op.target2 ?? null,
    quantity: qty,
    remainingQuantity: qty,
    initialRisk: null,
    realizedR: 0,
    unrealizedR: op.unrealizedR ?? null,
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

export type BuildPositionDecisionFromDtoInputV1 = {
  portfolioReconStatus?: string | null;
  at?: string | null;
};

/** PositionDto wire → PositionDecisionV1 (cockpit / Hoy / Journal). */
export function buildPositionDecisionFromDto(
  position: PositionDto,
  input: BuildPositionDecisionFromDtoInputV1 = {},
): PositionDecisionV1 | null {
  const state = positionStateFromPositionDto(position);
  if (!state) return null;
  const templateId =
    position.operational?.exitPlan?.policyTemplateId ?? "moderate";
  return buildPositionDecision({
    position: state,
    signals: {
      markPrice:
        typeof position.lastPrice === "number" ? position.lastPrice : null,
    },
    templateId,
    portfolioReconStatus: input.portfolioReconStatus ?? undefined,
    at: input.at,
  });
}
