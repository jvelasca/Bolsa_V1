/**
 * Tests — comparación masiva Q3.3 (plan + ranking + heat norm).
 */

import { describe, expect, it } from "vitest";
import {
  massCompareHeatNorm,
  planMassCompareJobs,
  rankMassCompareByInstrument,
  type MassCompareCell,
} from "@/features/backtests/backtest-mass-compare";

describe("backtest-mass-compare", () => {
  it("plans cells with soft-caps", () => {
    const cells = planMassCompareJobs({
      instrumentIds: ["a", "b", "c"],
      labels: { a: { symbol: "A" }, b: { symbol: "B" }, c: { symbol: "C" } },
      strategies: [
        { key: "sma", label: "SMA", strategyType: "sma_crossover" },
        { key: "rsi", label: "RSI", strategyType: "rsi_mean_reversion" },
      ],
      initialCash: 10_000,
      commissionBps: 10,
      slippageBps: 5,
      timeframe: "1d",
      window: {},
      maxInstruments: 2,
      maxStrategies: 2,
    });
    expect(cells).toHaveLength(4);
    expect(cells.every((c) => c.status === "pending")).toBe(true);
  });

  it("ranks by average sharpe", () => {
    const cells: MassCompareCell[] = [
      {
        instrumentId: "1",
        symbol: "ACS",
        strategyKey: "sma",
        strategyLabel: "SMA",
        status: "ok",
        sharpeRatio: 1.0,
      },
      {
        instrumentId: "1",
        symbol: "ACS",
        strategyKey: "rsi",
        strategyLabel: "RSI",
        status: "ok",
        sharpeRatio: 2.0,
      },
      {
        instrumentId: "2",
        symbol: "TEF",
        strategyKey: "sma",
        strategyLabel: "SMA",
        status: "ok",
        sharpeRatio: 0.2,
      },
    ];
    const rank = rankMassCompareByInstrument(cells);
    expect(rank[0]?.symbol).toBe("ACS");
    expect(rank[0]?.avgSharpe).toBeCloseTo(1.5);
  });

  it("heat norm clamps", () => {
    expect(massCompareHeatNorm(null, 0, 1)).toBeNull();
    expect(massCompareHeatNorm(0.5, 0, 1)).toBeCloseTo(0.5);
  });
});
