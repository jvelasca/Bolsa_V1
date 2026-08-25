/**
 * Protect / T1 advisory (ADR-031 Ciclo 5.1 / Golden E).
 * Read-only: no muta structuralStop ni check_opening.
 */

import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type ProtectPlanStatusV1 = "none" | "protect_hint";

export type ProtectPlanWhyV1 = "mfe_ge_1r" | "missing_inputs";

export type ProtectPlanV1 = {
  status: ProtectPlanStatusV1;
  target1: number | null;
  suggestedProtectStop: number | null;
  rMultiple: number | null;
  why: ProtectPlanWhyV1[];
};

export type MapProtectPlanInput = {
  direction?: TradePlanDirectionV1 | null;
  entry?: number | null;
  structuralStop?: number | null;
  lastClose?: number | null;
  /** R-multiple for T1 distance; default 1.0 */
  targetRMultiple?: number | null;
  /** Reserved; unused in mapper. */
  openQty?: number | null;
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/**
 * Golden E thin: MFE ≥ 1R → protect_hint; T1 = entry ± k×R; suggestedProtectStop = entry.
 * Does not mutate structuralStop.
 */
export function mapProtectPlan(input: MapProtectPlanInput): ProtectPlanV1 {
  const direction = input.direction;
  const entry = input.entry;
  const stop = input.structuralStop;
  const lastClose = input.lastClose;
  const k =
    finite(input.targetRMultiple) && input.targetRMultiple > 0
      ? input.targetRMultiple
      : 1;

  if (
    (direction !== "long" && direction !== "short") ||
    !finite(entry) ||
    !finite(stop) ||
    !finite(lastClose)
  ) {
    return {
      status: "none",
      target1: null,
      suggestedProtectStop: null,
      rMultiple: null,
      why: ["missing_inputs"],
    };
  }

  const R = Math.abs(entry - stop);
  if (R <= 0) {
    return {
      status: "none",
      target1: null,
      suggestedProtectStop: null,
      rMultiple: null,
      why: ["missing_inputs"],
    };
  }

  const sign = direction === "long" ? 1 : -1;
  const target1 = entry + sign * k * R;
  const mfeR = ((lastClose - entry) / R) * sign;
  const why: ProtectPlanWhyV1[] = [];
  const protect = mfeR >= 1;
  if (protect) why.push("mfe_ge_1r");

  return {
    status: protect ? "protect_hint" : "none",
    target1,
    suggestedProtectStop: protect ? entry : null,
    rMultiple: Math.round(mfeR * 10000) / 10000,
    why,
  };
}
