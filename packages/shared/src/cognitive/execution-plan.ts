/**
 * ExecutionPlan — plan de envío PAPER (ADR-032 F4).
 * Cadena PAPER → Journal → Replay → Validation. ≠ broker ≠ ExecuteTrade ≠ ExitPermission.
 */

import { createRandomId } from "../create-id.js";
import type {
  ExitPlanV1,
  ExitReasonV1,
  ExitSuggestedActionV1,
} from "./exit-plan.js";
import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type ExecutionVenueV1 = "PAPER" | "BROKER";

export type ExecutionPlanStatusV1 =
  | "DRAFT"
  | "PAPER_READY"
  | "JOURNALED"
  | "REPLAYED"
  | "VALIDATED"
  | "BLOCKED";

export type ExecutionIntentKindV1 = "market_exit" | "reduce" | "stop_amend";

export type ExecutionSideV1 = "buy" | "sell" | "none";

export type ExecutionBlockedReasonV1 =
  | "broker_not_allowed"
  | "not_actionable"
  | null;

export type PaperProjectionV1 = {
  price: number;
  qty: number;
  at: string;
};

export type ExecutionPlanV1 = {
  executionPlanId: string;
  exitPlanId: string;
  positionId: string;
  tradePlanId: string;
  instrumentId: string;
  direction: TradePlanDirectionV1;
  venue: ExecutionVenueV1;
  status: ExecutionPlanStatusV1;
  intentKind: ExecutionIntentKindV1 | null;
  side: ExecutionSideV1;
  quantity: number | null;
  limitPrice: number | null;
  sourceReason: ExitReasonV1 | null;
  sourceAction: ExitSuggestedActionV1 | null;
  blockedReason: ExecutionBlockedReasonV1;
  journalRef: string | null;
  replayRef: string | null;
  validationRef: string | null;
  paperProjection: PaperProjectionV1 | null;
  createdAt: string;
  updatedAt: string;
};

export type BuildExecutionPlanOptsV1 = {
  markPrice?: number | null;
  at?: string | null;
  executionPlanId?: string | null;
  /** F4: BROKER → BLOCKED (broker_not_allowed). Default PAPER. */
  forceVenue?: ExecutionVenueV1 | null;
};

export const EXECUTION_PLAN_KEY = "executionPlan";

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

function closingSide(direction: TradePlanDirectionV1): "buy" | "sell" {
  return direction === "short" ? "buy" : "sell";
}

type Actionable =
  | {
      kind: "order";
      intentKind: "market_exit" | "reduce";
      side: "buy" | "sell";
      quantity: number;
      status: "PAPER_READY";
    }
  | {
      kind: "amend";
      intentKind: "stop_amend";
      side: "none";
      quantity: null;
      limitPrice: number | null;
      status: "DRAFT";
    };

function resolveActionable(exitPlan: ExitPlanV1): Actionable | null {
  if (
    exitPlan.status === "TRIGGERED" &&
    (exitPlan.suggestedAction === "full_exit" ||
      exitPlan.suggestedAction === "reduce")
  ) {
    const qty = finite(exitPlan.suggestedQty) ? exitPlan.suggestedQty : null;
    if (qty == null || qty <= 0) return null;
    return {
      kind: "order",
      intentKind:
        exitPlan.suggestedAction === "reduce" ? "reduce" : "market_exit",
      side: closingSide(exitPlan.direction),
      quantity: round4(qty),
      status: "PAPER_READY",
    };
  }
  if (exitPlan.status === "ARMED" && exitPlan.suggestedAction === "protect") {
    return {
      kind: "amend",
      intentKind: "stop_amend",
      side: "none",
      quantity: null,
      limitPrice:
        finite(exitPlan.suggestedStop) && exitPlan.suggestedStop > 0
          ? round4(exitPlan.suggestedStop)
          : null,
      status: "DRAFT",
    };
  }
  return null;
}

function projection(
  markPrice: number | null | undefined,
  qty: number | null,
  at: string,
): PaperProjectionV1 | null {
  if (!finite(markPrice) || markPrice <= 0) return null;
  if (!finite(qty) || qty <= 0) return null;
  return { price: round4(markPrice), qty: round4(qty), at };
}

/**
 * Factory F4: ExitPlan → ExecutionPlan PAPER.
 * Sin acción enviable → null. BROKER forzado → BLOCKED. No ejecuta.
 */
export function buildExecutionPlanFromExitPlan(
  exitPlan: ExitPlanV1 | null | undefined,
  opts?: BuildExecutionPlanOptsV1 | null,
): ExecutionPlanV1 | null {
  if (!exitPlan) return null;
  if (exitPlan.direction !== "long" && exitPlan.direction !== "short") {
    return null;
  }

  const actionable = resolveActionable(exitPlan);
  if (!actionable) return null;

  const o = opts ?? {};
  const stamp = nowIso(o.at);
  const id = o.executionPlanId?.trim() || createRandomId();
  const wantBroker = o.forceVenue === "BROKER";

  const base = {
    executionPlanId: id,
    exitPlanId: exitPlan.exitPlanId,
    positionId: exitPlan.positionId,
    tradePlanId: exitPlan.tradePlanId,
    instrumentId: exitPlan.instrumentId,
    direction: exitPlan.direction,
    sourceReason: exitPlan.primaryReason,
    sourceAction: exitPlan.suggestedAction,
    journalRef: null as string | null,
    replayRef: null as string | null,
    validationRef: null as string | null,
    createdAt: stamp,
    updatedAt: stamp,
  };

  if (wantBroker) {
    return {
      ...base,
      venue: "BROKER",
      status: "BLOCKED",
      intentKind: actionable.intentKind,
      side: actionable.side,
      quantity: actionable.quantity,
      limitPrice: actionable.kind === "amend" ? actionable.limitPrice : null,
      blockedReason: "broker_not_allowed",
      paperProjection: null,
    };
  }

  if (actionable.kind === "order") {
    return {
      ...base,
      venue: "PAPER",
      status: "PAPER_READY",
      intentKind: actionable.intentKind,
      side: actionable.side,
      quantity: actionable.quantity,
      limitPrice: null,
      blockedReason: null,
      paperProjection: projection(o.markPrice, actionable.quantity, stamp),
    };
  }

  return {
    ...base,
    venue: "PAPER",
    status: "DRAFT",
    intentKind: "stop_amend",
    side: "none",
    quantity: null,
    limitPrice: actionable.limitPrice,
    blockedReason: null,
    paperProjection: null,
  };
}

function stampUpdate(
  plan: ExecutionPlanV1,
  patch: Partial<ExecutionPlanV1>,
  at?: string | null,
): ExecutionPlanV1 {
  return { ...plan, ...patch, updatedAt: nowIso(at) };
}

/** PAPER_READY → JOURNALED (ref opcional; sin I/O). */
export function stageExecutionJournal(
  plan: ExecutionPlanV1 | null | undefined,
  journalRef?: string | null,
  at?: string | null,
): ExecutionPlanV1 | null {
  if (!plan || plan.status !== "PAPER_READY") return null;
  if (plan.venue !== "PAPER") return null;
  return stampUpdate(
    plan,
    {
      status: "JOURNALED",
      journalRef:
        typeof journalRef === "string" && journalRef.trim()
          ? journalRef.trim()
          : plan.journalRef,
    },
    at,
  );
}

/** JOURNALED → REPLAYED. */
export function stageExecutionReplay(
  plan: ExecutionPlanV1 | null | undefined,
  replayRef?: string | null,
  at?: string | null,
): ExecutionPlanV1 | null {
  if (!plan || plan.status !== "JOURNALED") return null;
  return stampUpdate(
    plan,
    {
      status: "REPLAYED",
      replayRef:
        typeof replayRef === "string" && replayRef.trim()
          ? replayRef.trim()
          : plan.replayRef,
    },
    at,
  );
}

/** REPLAYED → VALIDATED. No abre broker. */
export function stageExecutionValidate(
  plan: ExecutionPlanV1 | null | undefined,
  validationRef?: string | null,
  at?: string | null,
): ExecutionPlanV1 | null {
  if (!plan || plan.status !== "REPLAYED") return null;
  return stampUpdate(
    plan,
    {
      status: "VALIDATED",
      validationRef:
        typeof validationRef === "string" && validationRef.trim()
          ? validationRef.trim()
          : plan.validationRef,
    },
    at,
  );
}

/** Cualquier intento broker → BLOCKED. Invariante F4. */
export function attemptExecutionBroker(
  plan: ExecutionPlanV1 | null | undefined,
  at?: string | null,
): ExecutionPlanV1 | null {
  if (!plan) return null;
  if (
    plan.status === "BLOCKED" &&
    plan.blockedReason === "broker_not_allowed"
  ) {
    return plan;
  }
  return stampUpdate(
    plan,
    {
      venue: "BROKER",
      status: "BLOCKED",
      blockedReason: "broker_not_allowed",
    },
    at,
  );
}
