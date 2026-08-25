/**
 * Thesis Health advisory (ADR-031 Ciclo 5.0 / Golden F).
 * Read-only: no cambia TradePlan.status ni check_opening.
 * Cola Hoy REVIEW (de EXPIRED) ≠ thesisHealth.status === "review".
 */

import { hintForConfidence, type ConfidenceHint } from "./confidence-state.js";
import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type ThesisHealthStatusV1 = "ok" | "review";

export type ThesisHealthWhyV1 =
  | "confidence_degraded"
  | "stop_intact"
  | "hard_exit"
  | "expired";

export type ThesisHealthV1 = {
  hint: ConfidenceHint;
  status: ThesisHealthStatusV1;
  why: ThesisHealthWhyV1[];
  confidence: number;
};

export type MapThesisHealthInput = {
  confidence: number;
  direction?: TradePlanDirectionV1 | null;
  lastClose?: number | null;
  structuralStop?: number | null;
  expired?: boolean;
  hardExit?: boolean;
  /** Reserved for 5.0b surface priority; unused in mapper logic. */
  openQty?: number | null;
};

function stopIntact(
  direction: TradePlanDirectionV1 | null | undefined,
  lastClose: number | null | undefined,
  structuralStop: number | null | undefined,
): boolean {
  if (direction !== "long" && direction !== "short") {
    return false;
  }
  if (
    typeof lastClose !== "number" ||
    !Number.isFinite(lastClose) ||
    typeof structuralStop !== "number" ||
    !Number.isFinite(structuralStop)
  ) {
    return false;
  }
  // Golden F: precio aún no ha roto el SL.
  if (direction === "long") return lastClose > structuralStop;
  return lastClose < structuralStop;
}

/**
 * Golden F thin: hint ∈ {tighten,reduce,exit} (o expire/hardExit) + stop intacto → review.
 */
export function mapThesisHealth(input: MapThesisHealthInput): ThesisHealthV1 {
  const confidence = Number.isFinite(input.confidence)
    ? Math.min(1, Math.max(0, input.confidence))
    : 0;
  const expired = Boolean(input.expired);
  const hardExit = Boolean(input.hardExit);
  const hint = hintForConfidence(confidence, { expired, hardExit });
  const why: ThesisHealthWhyV1[] = [];

  if (expired) why.push("expired");
  if (hardExit) why.push("hard_exit");

  const degraded =
    hint === "tighten" ||
    hint === "reduce" ||
    hint === "exit" ||
    hint === "expire";
  if (degraded) why.push("confidence_degraded");

  const intact = stopIntact(
    input.direction,
    input.lastClose,
    input.structuralStop,
  );
  if (intact) why.push("stop_intact");

  // Golden F: tesis degrada y precio > SL (stop intacto).
  const status: ThesisHealthStatusV1 = degraded && intact ? "review" : "ok";

  return { hint, status, why, confidence };
}

export function isThesisHealthReview(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  return (value as { status?: unknown }).status === "review";
}
