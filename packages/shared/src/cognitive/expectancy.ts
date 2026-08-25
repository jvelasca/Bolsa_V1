/**
 * Expectancy advisory thin (ADR-031 Ciclo 8.0).
 * Pure aggregate over setup+R samples. Read-only; never a fill gate.
 */

import type { EntrySetupV1 } from "./trade-plan.js";

export type ExpectancyStatusV1 = "none" | "thin" | "ready";

export type ExpectancyWhyV1 =
  | "missing_inputs"
  | "thin_sample"
  | "live_proxy"
  | "aggregated"
  | "not_permission";

export type ExpectancySampleV1 = {
  entrySetup?: EntrySetupV1 | string | null;
  rMultiple?: number | null;
};

export type ExpectancyV1 = {
  status: ExpectancyStatusV1;
  entrySetup: string | null;
  n: number;
  expectancyR: number | null;
  winRate: number | null;
  avgWinR: number | null;
  avgLossR: number | null;
  currentR: number | null;
  why: ExpectancyWhyV1[];
};

export type MapExpectancyInput = {
  samples?: readonly ExpectancySampleV1[] | null;
  focusSetup?: string | null;
  currentR?: number | null;
};

const READY_MIN_N = 5;

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

/**
 * Aggregate expectancy in R for a setup focus.
 * expectancyR = mean(rMultiple) among matching samples.
 */
export function mapExpectancy(input: MapExpectancyInput): ExpectancyV1 {
  let focus =
    typeof input.focusSetup === "string" && input.focusSetup.trim()
      ? input.focusSetup.trim()
      : null;
  if (focus === "none") focus = null;

  const matched: number[] = [];
  const samples = input.samples;
  if (Array.isArray(samples)) {
    for (const raw of samples) {
      const setup =
        typeof raw?.entrySetup === "string" ? raw.entrySetup.trim() : "";
      if (!setup || setup === "none") continue;
      if (focus != null && setup !== focus) continue;
      if (!finite(raw?.rMultiple)) continue;
      matched.push(raw.rMultiple);
    }
  }

  const currentR = finite(input.currentR) ? input.currentR : null;

  if (matched.length === 0) {
    return {
      status: "none",
      entrySetup: focus,
      n: 0,
      expectancyR: null,
      winRate: null,
      avgWinR: null,
      avgLossR: null,
      currentR,
      why: ["missing_inputs"],
    };
  }

  const n = matched.length;
  const wins = matched.filter((r) => r > 0);
  const losses = matched.filter((r) => r < 0);
  const expectancyR = round4(matched.reduce((a, b) => a + b, 0) / n);
  const winRate = round4(wins.length / n);
  const avgWinR =
    wins.length > 0
      ? round4(wins.reduce((a, b) => a + b, 0) / wins.length)
      : null;
  const avgLossR =
    losses.length > 0
      ? round4(losses.reduce((a, b) => a + b, 0) / losses.length)
      : null;

  const why: ExpectancyWhyV1[] = ["not_permission"];
  if (n === 1 && currentR != null && Math.abs(matched[0]! - currentR) < 1e-9) {
    why.push("live_proxy");
  } else if (n >= 2) {
    why.push("aggregated");
  }
  let status: ExpectancyStatusV1;
  if (n < READY_MIN_N) {
    why.push("thin_sample");
    status = "thin";
  } else {
    status = "ready";
  }

  return {
    status,
    entrySetup: focus,
    n,
    expectancyR,
    winRate,
    avgWinR,
    avgLossR,
    currentR,
    why,
  };
}
