import { describe, expect, it } from "vitest";
import { strategyTop1ToChartIndicators } from "@bolsa/shared";
import type { InstrumentStrategyTopSlotV1 } from "@bolsa/shared";

const slot1: InstrumentStrategyTopSlotV1 = {
  rank: 1,
  label: "SMA 10/30",
  strategyType: "sma_crossover",
  strategyDefinitionId: "def-1",
  stars: 4,
  score: 0.8,
  source: "coach",
};

describe("strategyTop1ToChartIndicators", () => {
  it("returns empty when no slot", () => {
    expect(strategyTop1ToChartIndicators({ slot: null }).source).toBe("empty");
  });

  it("prefers definition indicatorSpecs", () => {
    const r = strategyTop1ToChartIndicators({
      slot: slot1,
      definition: {
        presetKey: "sma_crossover",
        indicatorSpecs: [
          { definitionId: "sma", parameters: { period: 10 } },
          { definitionId: "sma", parameters: { period: 30 } },
        ],
      },
    });
    expect(r.source).toBe("definition");
    expect(r.specs).toHaveLength(2);
    expect(r.specs[0]?.parameters.period).toBe(10);
  });

  it("falls back to preset when definition has no specs", () => {
    const r = strategyTop1ToChartIndicators({
      slot: { ...slot1, strategyDefinitionId: null },
      definition: null,
    });
    expect(r.source).toBe("preset");
    expect(r.presetKey).toBe("sma_crossover");
    expect(r.specs.length).toBeGreaterThan(0);
  });

  it("overlayOnly drops RSI sub panel", () => {
    const r = strategyTop1ToChartIndicators({
      slot: {
        ...slot1,
        strategyType: "rsi_mean_reversion",
        label: "RSI",
      },
      overlayOnly: true,
    });
    expect(r.specs.every((s) => s.definitionId !== "rsi")).toBe(true);
  });
});
