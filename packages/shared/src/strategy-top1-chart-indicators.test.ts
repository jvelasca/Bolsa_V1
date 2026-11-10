import { describe, expect, it } from "vitest";
import {
  strategySlotToIndicatorDetails,
  strategySlotToIndicatorLabels,
} from "./strategy-top1-chart-indicators.js";
import type { InstrumentStrategyTopSlotV1 } from "./instrument-strategy-top.js";

function slot(
  overrides: Partial<InstrumentStrategyTopSlotV1> = {},
): InstrumentStrategyTopSlotV1 {
  return {
    rank: 1,
    label: "Cruce SMA 20/50",
    stars: 4,
    score: 82,
    source: "coach",
    ...overrides,
  } as InstrumentStrategyTopSlotV1;
}

describe("strategySlotToIndicatorDetails", () => {
  it("agrupa por indicador y concatena parámetros en orden de catálogo", () => {
    const result = strategySlotToIndicatorDetails({
      slot: slot(),
      definition: {
        indicatorSpecs: [
          { definitionId: "sma", parameters: { period: 20 } },
          { definitionId: "sma", parameters: { period: 50 } },
          { definitionId: "rsi", parameters: { period: 14 } },
          {
            definitionId: "macd",
            parameters: { fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
          },
        ],
      },
    });
    expect(result.source).toBe("definition");
    expect(result.items.map((item) => item.display)).toEqual([
      "SMA 20/50",
      "RSI 14",
      "MACD 12/26/9",
    ]);
    expect(result.items[0].label).toBe("SMA");
  });

  it("usa el preset del strategyType cuando no hay definición", () => {
    const result = strategySlotToIndicatorDetails({
      slot: slot({ strategyType: "sma_crossover" }),
      definition: null,
    });
    expect(result.source).toBe("preset");
    expect(result.items.map((item) => item.display)).toEqual(["SMA 20/50"]);
    expect(result.presetKey).toBe("sma_crossover");
  });

  it("sin fuente devuelve vacío (la superficie declara el hueco)", () => {
    const result = strategySlotToIndicatorDetails({
      slot: slot({ strategyType: null }),
      definition: null,
    });
    expect(result.source).toBe("empty");
    expect(result.items).toEqual([]);
  });

  it("conserva el id como etiqueta cuando la definición es desconocida", () => {
    const result = strategySlotToIndicatorDetails({
      slot: slot(),
      definition: {
        indicatorSpecs: [
          { definitionId: "custom-x", parameters: { period: 5 } },
        ],
      },
    });
    expect(result.items).toEqual([
      { definitionId: "custom-x", label: "custom-x", display: "custom-x" },
    ]);
  });

  it("no rompe la resolución de etiquetas existente", () => {
    const labels = strategySlotToIndicatorLabels({
      slot: slot({ strategyType: "sma_crossover" }),
      definition: null,
    });
    expect(labels.labels).toEqual(["SMA"]);
    expect(labels.source).toBe("preset");
  });
});
