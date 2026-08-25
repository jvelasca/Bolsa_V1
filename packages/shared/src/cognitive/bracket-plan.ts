/**
 * Bracket Plan advisory thin (ADR-031 Ciclo 8.2).
 * Structural picture: entry / stop / T1(1R) / T2(2R) + display-only leg fracs.
 * Aligns Protect 5.1 T1 = entry±1R. Does not place OCO, call broker, or auto-exit.
 */

import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type BracketPlanStatusV1 = "none" | "picture";

export type BracketPlanWhyV1 =
  | "missing_inputs"
  | "aligned_protect_t1"
  | "display_only"
  | "not_permission"
  | "hint_only"
  | "no_broker_oco";

export type BracketPlanV1 = {
  status: BracketPlanStatusV1;
  entry: number | null;
  stop: number | null;
  target1: number | null;
  target2: number | null;
  target1R: number;
  target2R: number;
  /** Display-only suggested fraction at T1 (sums with legT2QtyFrac ≈ 1). */
  legT1QtyFrac: number | null;
  legT2QtyFrac: number | null;
  why: BracketPlanWhyV1[];
};

export type MapBracketPlanInput = {
  direction?: TradePlanDirectionV1 | null;
  entry?: number | null;
  structuralStop?: number | null;
};

/** Align Protect 5.1 / Golden E T1 distance. */
export const BRACKET_T1_R = 1.0;
/** Optional second target for picture ladder. */
export const BRACKET_T2_R = 2.0;
/** Display-only default split (not an order qty). */
export const BRACKET_LEG_T1_FRAC = 0.5;
export const BRACKET_LEG_T2_FRAC = 0.5;

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

/**
 * Advisory structural bracket picture. Never places orders.
 */
export function mapBracketPlan(input: MapBracketPlanInput): BracketPlanV1 {
  const direction = input.direction;
  const entry = input.entry;
  const stop = input.structuralStop;
  const base = {
    target1R: BRACKET_T1_R,
    target2R: BRACKET_T2_R,
  } as const;

  if (
    (direction !== "long" && direction !== "short") ||
    !finite(entry) ||
    !finite(stop)
  ) {
    return {
      status: "none",
      entry: null,
      stop: null,
      target1: null,
      target2: null,
      ...base,
      legT1QtyFrac: null,
      legT2QtyFrac: null,
      why: ["missing_inputs"],
    };
  }

  const R = Math.abs(entry - stop);
  if (R <= 0) {
    return {
      status: "none",
      entry: null,
      stop: null,
      target1: null,
      target2: null,
      ...base,
      legT1QtyFrac: null,
      legT2QtyFrac: null,
      why: ["missing_inputs"],
    };
  }

  const sign = direction === "long" ? 1 : -1;
  const target1 = round4(entry + sign * BRACKET_T1_R * R);
  const target2 = round4(entry + sign * BRACKET_T2_R * R);

  return {
    status: "picture",
    entry: round4(entry),
    stop: round4(stop),
    target1,
    target2,
    ...base,
    legT1QtyFrac: BRACKET_LEG_T1_FRAC,
    legT2QtyFrac: BRACKET_LEG_T2_FRAC,
    why: [
      "aligned_protect_t1",
      "display_only",
      "not_permission",
      "hint_only",
      "no_broker_oco",
    ],
  };
}
