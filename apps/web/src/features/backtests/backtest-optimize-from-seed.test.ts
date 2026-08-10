import { describe, expect, it } from "vitest";
import {
  buildOptimizeRequestFromSeed,
  buildOptimizeRequestsFromSeed,
} from "@/features/backtests/backtest-optimize-from-seed";
import type { OptimizeSeed } from "@/features/backtests/backtest-optimize-seed";

function seed(
  partial: Partial<OptimizeSeed> & Pick<OptimizeSeed, "strategyType">,
): OptimizeSeed {
  return {
    instrumentId: "inst",
    strategyLabel: "Test",
    initialCash: 10_000,
    timeframe: "1d",
    source: "explore_best",
    barLimit: 500,
    ...partial,
  };
}

describe("buildOptimizeRequestsFromSeed", () => {
  it("enqueues H0 + Optuna for SMA-family (matches Play default)", () => {
    const bodies = buildOptimizeRequestsFromSeed(
      seed({ strategyType: "sma_crossover", anchorFast: 20, anchorSlow: 50 }),
    );
    expect(bodies.map((b) => b.engine)).toEqual(["h0", "optuna"]);
    expect(bodies[0]?.maxTrials).toBe(200);
    expect(bodies[1]?.maxTrials).toBe(100);
    expect(bodies.every((b) => b.oosPct === 0.2)).toBe(true);
  });

  it("keeps single H0 grid for RSI family", () => {
    const bodies = buildOptimizeRequestsFromSeed(
      seed({ strategyType: "rsi_mean_reversion", anchorPeriod: 14 }),
    );
    expect(bodies).toHaveLength(1);
    expect(bodies[0]?.engine).toBe("h0");
  });

  it("maps Donchian proxy to SMA H0+Optuna", () => {
    const bodies = buildOptimizeRequestsFromSeed(
      seed({ strategyType: "donchian_breakout" }),
    );
    expect(bodies[0]?.strategyFamily).toBe("sma_crossover");
    expect(bodies.map((b) => b.engine)).toEqual(["h0", "optuna"]);
  });

  it("walk-forward hint forces single H0", () => {
    const bodies = buildOptimizeRequestsFromSeed(
      seed({
        strategyType: "sma_crossover",
        validationHint: { mode: "walkforward", walkForwardFolds: 3 },
      }),
    );
    expect(bodies).toHaveLength(1);
    expect(bodies[0]?.engine).toBe("h0");
    expect(bodies[0]?.walkForwardFolds).toBe(3);
  });
});

describe("buildOptimizeRequestFromSeed", () => {
  it("returns first of the batch (H0 for SMA)", () => {
    const body = buildOptimizeRequestFromSeed(
      seed({ strategyType: "sma_crossover", anchorFast: 20, anchorSlow: 50 }),
    );
    expect(body?.engine).toBe("h0");
  });
});
