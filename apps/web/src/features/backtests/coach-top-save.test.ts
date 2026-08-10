import { describe, expect, it, vi } from "vitest";
import {
  buildCoachTopSlots,
  coachTopStrategyName,
  filterFinalistStrategies,
  mergeStrategiesWithTopSlots,
} from "@/features/backtests/coach-top-save";
import type { TechnicalRecommendation } from "@/features/backtests/backtest-deep-coach";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";
import type { StrategyDefinitionSummaryDto } from "@bolsa/shared";

function rec(
  rank: number,
  strategyType: ExplorePresetRow["strategyType"],
  label: string,
): TechnicalRecommendation {
  return {
    rank,
    score: 70 - rank,
    stars: 3,
    starsCapped: true,
    futureBias: 0.7,
    lateReturnPct: 10,
    row: {
      strategyType,
      label,
      category: "trend",
      categoryLabel: "Tendencia",
      status: "ok",
      totalReturnPct: 20,
      excessReturnPct: 5,
    },
    reasons: [],
  };
}

describe("coach-top-save", () => {
  it("names strategy as symbol · label", () => {
    expect(coachTopStrategyName("ACS", "SMA 20/50")).toBe("ACS · SMA 20/50");
  });

  it("creates missing presets and keeps 3 unique types", async () => {
    const create = vi.fn(
      async (input: { name: string; presetKey: string }) => ({
        id: `id-${input.presetKey}`,
        name: input.name,
        presetKey: input.presetKey as StrategyDefinitionSummaryDto["presetKey"],
        origin: "preset" as const,
        timeframe: "1d",
        kind: "rules" as const,
        updatedAt: "t",
        createdAt: "t",
      }),
    );

    const slots = await buildCoachTopSlots({
      recommendations: [
        rec(1, "sma_crossover", "SMA"),
        rec(2, "rsi_mean_reversion", "RSI"),
        rec(3, "macd_signal_cross", "MACD"),
      ],
      symbol: "TEF",
      timeframe: "1d",
      lookup: { existing: [], createFromPreset: create },
    });

    expect(slots).toHaveLength(3);
    expect(create).toHaveBeenCalledTimes(3);
    expect(slots.map((s) => s.rank)).toEqual([1, 2, 3]);
  });

  it("reuses existing by exact name + presetKey", async () => {
    const existing: StrategyDefinitionSummaryDto[] = [
      {
        id: "existing-sma",
        name: "ACS · SMA",
        presetKey: "sma_crossover",
        origin: "preset",
        timeframe: "1d",
        kind: "rules",
        updatedAt: "t",
        createdAt: "t",
      },
    ];
    const create = vi.fn();
    const slots = await buildCoachTopSlots({
      recommendations: [rec(1, "sma_crossover", "SMA")],
      symbol: "ACS",
      timeframe: "1d",
      lookup: { existing, createFromPreset: create },
    });
    expect(slots[0]?.strategyDefinitionId).toBe("existing-sma");
    expect(create).not.toHaveBeenCalled();
  });

  it("requireRunId skips candidates without run and errors if none", async () => {
    const create = vi.fn(
      async (input: { name: string; presetKey: string }) => ({
        id: `id-${input.presetKey}`,
        name: input.name,
        presetKey: input.presetKey as StrategyDefinitionSummaryDto["presetKey"],
        origin: "preset" as const,
        timeframe: "1d",
        kind: "rules" as const,
        updatedAt: "t",
        createdAt: "t",
      }),
    );
    const withRun = rec(1, "sma_crossover", "SMA");
    withRun.row.runId = "run-1";
    const slots = await buildCoachTopSlots({
      recommendations: [withRun, rec(2, "rsi_mean_reversion", "RSI")],
      symbol: "AENA",
      timeframe: "1d",
      requireRunId: true,
      slotSource: "optimized",
      lookup: { existing: [], createFromPreset: create },
    });
    expect(slots).toHaveLength(1);
    expect(slots[0]?.runId).toBe("run-1");

    await expect(
      buildCoachTopSlots({
        recommendations: [rec(1, "sma_crossover", "SMA")],
        symbol: "AENA",
        timeframe: "1d",
        requireRunId: true,
        lookup: { existing: [], createFromPreset: create },
      }),
    ).rejects.toThrow(/runId/i);
  });

  it("mergeStrategiesWithTopSlots fetches missing finalist ids", async () => {
    const merged = await mergeStrategiesWithTopSlots({
      strategies: [
        {
          id: "a",
          name: "A",
          origin: "manual",
          timeframe: "1d",
          kind: "rules",
          updatedAt: "t",
          createdAt: "t",
        },
      ],
      slots: [
        { strategyDefinitionId: "a" },
        { strategyDefinitionId: "missing" },
      ],
      getById: async (id) =>
        id === "missing"
          ? {
              id: "missing",
              name: "Finalist",
              origin: "preset",
              timeframe: "1d",
              kind: "rules",
              updatedAt: "t",
              createdAt: "t",
            }
          : null,
    });
    expect(merged.map((s) => s.id).sort()).toEqual(["a", "missing"]);
    expect(filterFinalistStrategies(merged, new Set(["missing"]))).toHaveLength(
      1,
    );
  });
});
