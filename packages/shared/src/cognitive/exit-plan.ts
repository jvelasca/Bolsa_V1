/**
 * ExitPlan — plan condicional de salida (ADR-032 F3).
 * Simétrico a TradePlan, post-entrada. ≠ execution ≠ ExitPermission.
 * Thin exitRadar / trail / protect siguen advisory aparte; no se promocionan.
 */

import { createRandomId } from "../create-id.js";
import type { PositionStateV1 } from "./position-state.js";
import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type ExitReasonV1 =
  | "STRUCTURAL_STOP"
  | "THESIS_INVALIDATION"
  | "TARGET_1"
  | "TARGET_2"
  | "TRAIL"
  | "TIME_STOP"
  | "PORTFOLIO_RISK"
  | "MANUAL";

export type ExitPlanStatusV1 = "IDLE" | "HINT" | "ARMED" | "TRIGGERED" | "DONE";

export type ExitSuggestedActionV1 = "hold" | "protect" | "reduce" | "full_exit";

export type ExitPlanV1 = {
  exitPlanId: string;
  positionId: string;
  tradePlanId: string;
  instrumentId: string;
  direction: TradePlanDirectionV1;
  status: ExitPlanStatusV1;
  reasons: ExitReasonV1[];
  primaryReason: ExitReasonV1 | null;
  suggestedAction: ExitSuggestedActionV1;
  suggestedQty: number | null;
  suggestedStop: number | null;
  createdAt: string;
  updatedAt: string;
};

/** Señales explícitas — no se leen mappers thin. */
export type ExitPlanSignalsV1 = {
  markPrice?: number | null;
  now?: string | null;
  expiresAt?: string | null;
  thesisInvalid?: boolean | null;
  portfolioRisk?: boolean | null;
  manual?: boolean | null;
  trailHint?: boolean | null;
  trailStop?: number | null;
  exitPlanId?: string | null;
  at?: string | null;
};

export const EXIT_PLAN_KEY = "exitPlan";

/** Precedencia D3 — primera que dispare gana primaryReason. */
export const EXIT_REASON_PRECEDENCE: readonly ExitReasonV1[] = [
  "MANUAL",
  "STRUCTURAL_STOP",
  "THESIS_INVALIDATION",
  "PORTFOLIO_RISK",
  "TARGET_1",
  "TARGET_2",
  "TRAIL",
  "TIME_STOP",
] as const;

const HARD_TRIGGER: ReadonlySet<ExitReasonV1> = new Set([
  "MANUAL",
  "STRUCTURAL_STOP",
  "THESIS_INVALIDATION",
  "PORTFOLIO_RISK",
  "TARGET_1",
  "TARGET_2",
]);

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

function stopTouched(
  direction: TradePlanDirectionV1,
  mark: number,
  stop: number,
): boolean {
  if (direction === "long") return mark <= stop;
  if (direction === "short") return mark >= stop;
  return false;
}

function targetTouched(
  direction: TradePlanDirectionV1,
  mark: number,
  target: number,
): boolean {
  if (direction === "long") return mark >= target;
  if (direction === "short") return mark <= target;
  return false;
}

function collectReasons(
  position: PositionStateV1,
  signals: ExitPlanSignalsV1,
): ExitReasonV1[] {
  const fired = new Set<ExitReasonV1>();

  if (signals.manual === true) fired.add("MANUAL");
  if (signals.thesisInvalid === true) fired.add("THESIS_INVALIDATION");
  if (signals.portfolioRisk === true) fired.add("PORTFOLIO_RISK");
  if (signals.trailHint === true) fired.add("TRAIL");

  const mark = signals.markPrice;
  if (finite(mark) && mark > 0) {
    if (
      finite(position.currentStop) &&
      position.currentStop > 0 &&
      stopTouched(position.direction, mark, position.currentStop)
    ) {
      fired.add("STRUCTURAL_STOP");
    }
    if (
      finite(position.target1) &&
      targetTouched(position.direction, mark, position.target1)
    ) {
      fired.add("TARGET_1");
    }
    if (
      finite(position.target2) &&
      targetTouched(position.direction, mark, position.target2)
    ) {
      fired.add("TARGET_2");
    }
    // H2: T2 no interpreta T1 a ciegas (no reduce mitad por atajo T1).
    if (fired.has("TARGET_2")) fired.delete("TARGET_1");
  }

  const now = typeof signals.now === "string" ? signals.now.trim() : "";
  const expires =
    typeof signals.expiresAt === "string" ? signals.expiresAt.trim() : "";
  if (now && expires && now >= expires) {
    fired.add("TIME_STOP");
  }

  return EXIT_REASON_PRECEDENCE.filter((r) => fired.has(r));
}

function deriveStatus(
  position: PositionStateV1,
  primary: ExitReasonV1 | null,
  signals: ExitPlanSignalsV1,
): ExitPlanStatusV1 {
  if (position.status === "CLOSED" || position.remainingQuantity <= 0) {
    return "DONE";
  }
  if (!primary) return "IDLE";
  if (HARD_TRIGGER.has(primary)) return "TRIGGERED";
  if (
    primary === "TRAIL" &&
    finite(signals.trailStop) &&
    signals.trailStop > 0
  ) {
    return "ARMED";
  }
  return "HINT";
}

function deriveSuggestion(
  status: ExitPlanStatusV1,
  primary: ExitReasonV1 | null,
  remaining: number,
  signals: ExitPlanSignalsV1,
): {
  suggestedAction: ExitSuggestedActionV1;
  suggestedQty: number | null;
  suggestedStop: number | null;
} {
  if (status === "DONE" || status === "IDLE" || !primary) {
    return { suggestedAction: "hold", suggestedQty: null, suggestedStop: null };
  }
  if (primary === "TARGET_1") {
    return {
      suggestedAction: "reduce",
      suggestedQty: round4(remaining / 2),
      suggestedStop: null,
    };
  }
  if (primary === "TRAIL") {
    const stop =
      finite(signals.trailStop) && signals.trailStop > 0
        ? round4(signals.trailStop)
        : null;
    return {
      suggestedAction: "protect",
      suggestedQty: null,
      suggestedStop: stop,
    };
  }
  return {
    suggestedAction: "full_exit",
    suggestedQty: round4(remaining),
    suggestedStop: null,
  };
}

/**
 * Factory F3: PositionState + señales explícitas → ExitPlan.
 * Sin posición válida → null. No muta PositionState. No ejecuta.
 */
export function buildExitPlanFromPosition(
  position: PositionStateV1 | null | undefined,
  signals?: ExitPlanSignalsV1 | null,
): ExitPlanV1 | null {
  if (!position) return null;
  if (position.direction !== "long" && position.direction !== "short") {
    return null;
  }

  const sig = signals ?? {};
  const reasons = collectReasons(position, sig);
  const primaryReason = reasons[0] ?? null;
  const status = deriveStatus(position, primaryReason, sig);
  const suggestion = deriveSuggestion(
    status,
    primaryReason,
    position.remainingQuantity,
    sig,
  );
  const stamp = nowIso(sig.at);

  return {
    exitPlanId: sig.exitPlanId?.trim() || createRandomId(),
    positionId: position.positionId,
    tradePlanId: position.tradePlanId,
    instrumentId: position.instrumentId,
    direction: position.direction,
    status,
    reasons,
    primaryReason,
    suggestedAction: suggestion.suggestedAction,
    suggestedQty: suggestion.suggestedQty,
    suggestedStop: suggestion.suggestedStop,
    createdAt: stamp,
    updatedAt: stamp,
  };
}
