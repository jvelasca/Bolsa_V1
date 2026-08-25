/**
 * Trail Plan advisory thin (ADR-031 Ciclo 8.1).
 * Continuous ratchet from peak MFE; hint only.
 * Does not mutate structuralStop, call broker, or auto-exit.
 * At peakMfeR=1.5 → lockedR=0.5 (aligned with Exit Radar 5.2 tip).
 */

import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type TrailPlanStatusV1 = "none" | "tip" | "ratchet";

export type TrailPlanWhyV1 =
  | "missing_inputs"
  | "mfe_lt_1_5r"
  | "aligned_exit_radar_tip"
  | "ratchet_lock"
  | "not_permission"
  | "hint_only";

export type TrailPlanV1 = {
  status: TrailPlanStatusV1;
  suggestedTrailStop: number | null;
  lockedR: number | null;
  peakMfeR: number | null;
  currentR: number | null;
  trailDistanceR: number;
  why: TrailPlanWhyV1[];
};

export type MapTrailPlanInput = {
  direction?: TradePlanDirectionV1 | null;
  entry?: number | null;
  structuralStop?: number | null;
  /** Peak favorable excursion in R (prefer mfeMae.mfeR). */
  peakMfeR?: number | null;
  currentR?: number | null;
};

/** Cushion from peak MFE; at 1.5R peak → lock 0.5R (= Exit Radar tip). */
export const TRAIL_DISTANCE_R = 1.0;
const TIP_MIN_MFE_R = 1.5;
const RATCHET_MIN_MFE_R = 2.0;

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

/**
 * Advisory continuous trail ratchet. Never writes stops.
 */
export function mapTrailPlan(input: MapTrailPlanInput): TrailPlanV1 {
  const direction = input.direction;
  const entry = input.entry;
  const stop = input.structuralStop;
  const currentR = finite(input.currentR) ? input.currentR : null;
  const base = {
    trailDistanceR: TRAIL_DISTANCE_R,
    currentR,
  } as const;

  if (
    (direction !== "long" && direction !== "short") ||
    !finite(entry) ||
    !finite(stop)
  ) {
    return {
      status: "none",
      suggestedTrailStop: null,
      lockedR: null,
      peakMfeR: null,
      ...base,
      why: ["missing_inputs"],
    };
  }

  const R = Math.abs(entry - stop);
  if (R <= 0) {
    return {
      status: "none",
      suggestedTrailStop: null,
      lockedR: null,
      peakMfeR: null,
      ...base,
      why: ["missing_inputs"],
    };
  }

  let peakMfeR = finite(input.peakMfeR) ? input.peakMfeR : null;
  if (peakMfeR == null && currentR != null) {
    peakMfeR = Math.max(currentR, 0);
  }

  if (peakMfeR == null) {
    return {
      status: "none",
      suggestedTrailStop: null,
      lockedR: null,
      peakMfeR: null,
      ...base,
      why: ["missing_inputs"],
    };
  }

  peakMfeR = round4(Math.max(peakMfeR, 0));

  if (peakMfeR < TIP_MIN_MFE_R) {
    return {
      status: "none",
      suggestedTrailStop: null,
      lockedR: null,
      peakMfeR,
      ...base,
      why: ["mfe_lt_1_5r", "not_permission", "hint_only"],
    };
  }

  const lockedR = round4(peakMfeR - TRAIL_DISTANCE_R);
  const sign = direction === "long" ? 1 : -1;
  const suggestedTrailStop = round4(entry + sign * lockedR * R);

  const why: TrailPlanWhyV1[] = ["not_permission", "hint_only"];
  let status: TrailPlanStatusV1;
  if (peakMfeR >= RATCHET_MIN_MFE_R) {
    status = "ratchet";
    why.push("ratchet_lock");
  } else {
    status = "tip";
    why.push("aligned_exit_radar_tip");
  }

  return {
    status,
    suggestedTrailStop,
    lockedR,
    peakMfeR,
    ...base,
    why,
  };
}
