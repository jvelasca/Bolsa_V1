import { describe, expect, it } from "vitest";
import type { ChartIndicatorInstance } from "@bolsa/shared";
import {
  chartIndicatorInstancesToSpecs,
  inferPresetFromIndicatorSpecs,
} from "@bolsa/shared";

describe("chart-strategy-bridge", () => {
  it("maps instances to specs without color", () => {
    const instances: ChartIndicatorInstance[] = [
      {
        instanceId: "a",
        definitionId: "sma",
        parameters: { period: 20, color: "#ff0000" },
        visible: true,
      },
    ];
    const specs = chartIndicatorInstancesToSpecs(instances);
    expect(specs).toHaveLength(1);
    expect(specs[0]!.definitionId).toBe("sma");
    expect(specs[0]!.parameters.period).toBe(20);
    expect(specs[0]!.parameters.color).toBeUndefined();
  });

  it("infers sma_crossover preset", () => {
    const specs = chartIndicatorInstancesToSpecs([
      {
        instanceId: "1",
        definitionId: "sma",
        parameters: { period: 20 },
        visible: true,
      },
      {
        instanceId: "2",
        definitionId: "sma",
        parameters: { period: 50 },
        visible: true,
      },
    ]);
    expect(inferPresetFromIndicatorSpecs(specs)).toBe("sma_crossover");
  });

  it("infers rsi_mean_reversion preset", () => {
    const specs = chartIndicatorInstancesToSpecs([
      {
        instanceId: "1",
        definitionId: "rsi",
        parameters: { period: 14 },
        visible: true,
      },
    ]);
    expect(inferPresetFromIndicatorSpecs(specs)).toBe("rsi_mean_reversion");
  });
});
