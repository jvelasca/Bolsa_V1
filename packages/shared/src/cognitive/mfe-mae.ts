/**
 * MFE/MAE excursion advisory (ADR-031 Ciclo 5.3).
 * Read-only metrics: peak favorable/adverse in R. No protect/exit tips, no fill gate.
 */

import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type MfeMaeStatusV1 = "none" | "observe" | "favorable" | "adverse";

export type MfeMaeWhyV1 =
  | "peak_from_bars"
  | "close_proxy"
  | "mae_ge_1r"
  | "mfe_ge_1_5r"
  | "missing_inputs";

export type MfeMaeBarV1 = {
  high?: number | null;
  low?: number | null;
};

export type MfeMaeV1 = {
  status: MfeMaeStatusV1;
  mfeR: number | null;
  maeR: number | null;
  currentR: number | null;
  why: MfeMaeWhyV1[];
};

export type MapMfeMaeInput = {
  direction?: TradePlanDirectionV1 | null;
  entry?: number | null;
  structuralStop?: number | null;
  lastClose?: number | null;
  bars?: readonly MfeMaeBarV1[] | null;
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

/**
 * Peak MFE/MAE in R from bars when available; else lastClose proxy.
 * Does not emit protect/trail suggestions.
 */
export function mapMfeMae(input: MapMfeMaeInput): MfeMaeV1 {
  const direction = input.direction;
  const entry = input.entry;
  const stop = input.structuralStop;
  const lastClose = input.lastClose;

  if (
    (direction !== "long" && direction !== "short") ||
    !finite(entry) ||
    !finite(stop)
  ) {
    return {
      status: "none",
      mfeR: null,
      maeR: null,
      currentR: null,
      why: ["missing_inputs"],
    };
  }

  const R = Math.abs(entry - stop);
  if (R <= 0) {
    return {
      status: "none",
      mfeR: null,
      maeR: null,
      currentR: null,
      why: ["missing_inputs"],
    };
  }

  const sign = direction === "long" ? 1 : -1;
  const why: MfeMaeWhyV1[] = [];

  let currentR: number | null = null;
  if (finite(lastClose)) {
    currentR = round4(((lastClose - entry) / R) * sign);
  }

  const bars = input.bars;
  let usedBars = false;
  let peakFav = 0;
  let peakAdv = 0;

  if (Array.isArray(bars) && bars.length > 0) {
    for (const bar of bars) {
      const high = bar?.high;
      const low = bar?.low;
      if (!finite(high) || !finite(low)) continue;
      usedBars = true;
      if (direction === "long") {
        peakFav = Math.max(peakFav, high - entry);
        peakAdv = Math.max(peakAdv, entry - low);
      } else {
        peakFav = Math.max(peakFav, entry - low);
        peakAdv = Math.max(peakAdv, high - entry);
      }
    }
  }

  let mfeR: number;
  let maeR: number;

  if (usedBars) {
    why.push("peak_from_bars");
    mfeR = round4(Math.max(peakFav, 0) / R);
    maeR = round4(Math.max(peakAdv, 0) / R);
  } else if (currentR != null) {
    why.push("close_proxy");
    mfeR = round4(Math.max(currentR, 0));
    maeR = round4(Math.max(-currentR, 0));
  } else {
    return {
      status: "none",
      mfeR: null,
      maeR: null,
      currentR: null,
      why: ["missing_inputs"],
    };
  }

  if (maeR >= 1) why.push("mae_ge_1r");
  if (mfeR >= 1.5) why.push("mfe_ge_1_5r");

  let status: MfeMaeStatusV1 = "observe";
  if (maeR >= 1) status = "adverse";
  else if (mfeR >= 1.5) status = "favorable";

  return {
    status,
    mfeR,
    maeR,
    currentR,
    why,
  };
}
