/**
 * PositionPolicyDecision — autorización de policy post-entrada (V1.44).
 * ≠ ExitPlan ≠ ExitPermission ≠ ExecutionPlan ≠ auto-exit.
 * decidePositionPolicy no ejecuta, no muta PositionState, no llama al Router.
 */

import type { ExitPlanV1, ExitReasonV1 } from "./exit-plan.js";
import { suggestionFromExitPolicy } from "./exit-policy.js";
import type { OperatingPolicyV1 } from "./operating-policy.js";
import {
  buildPositionEvent,
  isImmediateRiskReason,
  isTargetEventKind,
  positionEventKindFromReason,
  type PositionEventV1,
} from "./position-event.js";
import { clampStopNotWorsen } from "./position-state.js";
import type { PositionStateV1 } from "./position-state.js";

export type PositionPolicyVerdictV1 =
  | "HOLD"
  | "PROTECT"
  | "TRAIL"
  | "REDUCE"
  | "EXIT";

export type PositionPolicyRiskImpactV1 = "none" | "reduce" | "protect" | "exit";

export type PositionPolicyAuthorizationV1 = "human_confirm" | "policy";

export type PositionPolicyDeferReasonV1 = "queue_next_session" | "data_stale";

export type PositionPolicyMarketContextV1 = {
  session?: "open" | "closed" | null;
  stale?: boolean | null;
  stopTouched?: boolean | null;
  asOf?: string | null;
};

export type PositionPolicyDecisionV1 = {
  verdict: PositionPolicyVerdictV1;
  reasonCode: ExitReasonV1 | null;
  event: PositionEventV1 | null;
  quantity: number | null;
  newStop: number | null;
  target: number | null;
  riskImpact: PositionPolicyRiskImpactV1;
  policyId: OperatingPolicyV1["templateId"];
  asOf: string;
  authorization: PositionPolicyAuthorizationV1;
  deferReason: PositionPolicyDeferReasonV1 | null;
};

export const POSITION_POLICY_DECISION_KEY = "positionPolicyDecision";

function nowIso(at?: string | null): string {
  if (typeof at === "string" && at.trim()) return at;
  return new Date().toISOString();
}

function hold(
  policy: OperatingPolicyV1,
  asOf: string,
  reasonCode: ExitReasonV1 | null,
  event: PositionEventV1 | null,
  deferReason: PositionPolicyDeferReasonV1 | null,
): PositionPolicyDecisionV1 {
  return {
    verdict: "HOLD",
    reasonCode,
    event,
    quantity: null,
    newStop: null,
    target: null,
    riskImpact: "none",
    policyId: policy.templateId,
    asOf,
    authorization: "policy",
    deferReason,
  };
}

function echoTarget(
  position: PositionStateV1,
  reason: ExitReasonV1 | null,
): number | null {
  if (reason === "TARGET_1") return position.target1;
  if (reason === "TARGET_2") return position.target2;
  return null;
}

/**
 * Policy authorization from current position + detected ExitPlan + OperatingPolicy.
 * Re-derives qty/stop from OperatingPolicy.exit (not TradePlan-time snapshot).
 */
export function decidePositionPolicy(
  position: PositionStateV1 | null | undefined,
  exitPlan: ExitPlanV1 | null | undefined,
  operatingPolicy: OperatingPolicyV1,
  marketContext?: PositionPolicyMarketContextV1 | null,
): PositionPolicyDecisionV1 {
  const ctx = marketContext ?? {};
  const asOf = nowIso(ctx.asOf ?? exitPlan?.updatedAt);
  const reason = exitPlan?.primaryReason ?? null;
  const event = buildPositionEvent(reason, asOf);
  const kind = positionEventKindFromReason(reason);

  if (!position || !exitPlan || !reason || !kind) {
    return hold(operatingPolicy, asOf, reason, event, null);
  }

  const immediate = isImmediateRiskReason(reason) || ctx.stopTouched === true;

  if (ctx.stale === true && !immediate) {
    return hold(operatingPolicy, asOf, reason, event, "data_stale");
  }

  if (ctx.session === "closed" && isTargetEventKind(kind) && !immediate) {
    return hold(operatingPolicy, asOf, reason, event, "queue_next_session");
  }

  const suggestion = suggestionFromExitPolicy(
    reason,
    position.remainingQuantity,
    operatingPolicy.exit,
    exitPlan.suggestedStop,
  );

  if (suggestion.suggestedAction === "hold") {
    return hold(operatingPolicy, asOf, reason, event, null);
  }

  let newStop: number | null = suggestion.suggestedStop;
  if (newStop != null && newStop > 0) {
    newStop = clampStopNotWorsen(
      position.direction,
      position.currentStop,
      newStop,
    );
  }

  if (suggestion.suggestedAction === "protect") {
    const trail = reason === "TRAIL";
    return {
      verdict: trail ? "TRAIL" : "PROTECT",
      reasonCode: reason,
      event,
      quantity: null,
      newStop,
      target: echoTarget(position, reason),
      riskImpact: "protect",
      policyId: operatingPolicy.templateId,
      asOf,
      authorization: "policy",
      deferReason: null,
    };
  }

  if (suggestion.suggestedAction === "reduce") {
    return {
      verdict: "REDUCE",
      reasonCode: reason,
      event,
      quantity: suggestion.suggestedQty,
      newStop: null,
      target: echoTarget(position, reason),
      riskImpact: "reduce",
      policyId: operatingPolicy.templateId,
      asOf,
      authorization: "policy",
      deferReason: null,
    };
  }

  return {
    verdict: "EXIT",
    reasonCode: reason,
    event,
    quantity: suggestion.suggestedQty ?? position.remainingQuantity,
    newStop: null,
    target: echoTarget(position, reason),
    riskImpact: "exit",
    policyId: operatingPolicy.templateId,
    asOf,
    authorization: "policy",
    deferReason: null,
  };
}
