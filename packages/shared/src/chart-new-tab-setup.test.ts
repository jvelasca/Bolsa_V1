import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ChartTabState } from "./chart-defaults.js";
import { DEFAULT_CHART_CONFIG } from "./chart-defaults.js";
import type { ChartIndicatorInstance } from "./indicators-catalog.js";
import {
  applyChartNewTabSeed,
  extractChartNewTabSeed,
} from "./chart-new-tab-setup.js";

const SOURCE_PATH = join(
  dirname(fileURLToPath(import.meta.url)),
  "chart-new-tab-setup.ts",
);

function indicator(
  overrides: Partial<ChartIndicatorInstance> &
    Pick<ChartIndicatorInstance, "instanceId" | "definitionId">,
): ChartIndicatorInstance {
  return {
    visible: true,
    parameters: { period: 20 },
    ...overrides,
  };
}

function tab(overrides: Partial<ChartTabState> = {}): ChartTabState {
  return {
    id: "tab-1",
    instrumentId: "SAN.MC",
    label: "SAN",
    timeframe: "1d",
    seriesType: "candles",
    chart: DEFAULT_CHART_CONFIG,
    indicatorInstances: [],
    drawings: [],
    ...overrides,
  };
}

function cloneChart(config = DEFAULT_CHART_CONFIG) {
  return {
    ...config,
    grid: { ...config.grid },
    cursor: { ...config.cursor },
    colors: { ...config.colors },
    display: { ...config.display },
  };
}

describe("extractChartNewTabSeed / applyChartNewTabSeed", () => {
  it("extracts a seed without drawings and drops finalist-top1 indicators", () => {
    const parameters = { period: 50 };
    const extracted = extractChartNewTabSeed(
      tab({
        timeframe: "15m",
        seriesType: "area",
        indicatorInstances: [
          indicator({
            instanceId: "ind-sma",
            definitionId: "sma",
            parameters,
          }),
          indicator({
            instanceId: "ind-top1",
            definitionId: "rsi",
            origin: "finalist-top1",
          }),
        ],
        drawings: [{ id: "d1" } as ChartTabState["drawings"][number]],
        activeIndicatorTemplateId: "tpl-1",
      }),
    );

    expect(extracted.timeframe).toBe("15m");
    expect(extracted.seriesType).toBe("area");
    expect(extracted.indicatorInstances).toHaveLength(1);
    expect(extracted.indicatorInstances[0]!.instanceId).toBe("ind-sma");
    expect(extracted.indicatorInstances[0]!.parameters).toEqual(parameters);
    expect(extracted.indicatorInstances[0]!.parameters).not.toBe(parameters);
    expect(extracted.activeIndicatorTemplateId).toBe("tpl-1");
    expect(extracted).not.toHaveProperty("drawings");
  });

  it("apply copies seed fields onto the base tab and clears drawings", () => {
    const template = extractChartNewTabSeed(
      tab({
        id: "template",
        timeframe: "1h",
        seriesType: "bars",
        indicatorInstances: [
          indicator({ instanceId: "ind-sma", definitionId: "sma" }),
        ],
        drawings: [{ id: "keep-me-not" } as ChartTabState["drawings"][number]],
        drawingsLayerHidden: true,
      }),
    );
    const applied = applyChartNewTabSeed(tab(), template, cloneChart);

    expect(applied.timeframe).toBe("1h");
    expect(applied.seriesType).toBe("bars");
    expect(applied.indicatorInstances).toHaveLength(1);
    expect(applied.indicatorInstances[0]!.definitionId).toBe("sma");
    expect(applied.indicatorInstances[0]!.instanceId).not.toBe("ind-sma");
    expect(applied.drawings).toEqual([]);
    expect(applied.drawingsLayerHidden).toBe(true);
  });
});

describe("normalizeChartNewTabSeed absence (A2 purge)", () => {
  it("no longer exports normalizeChartNewTabSeed from chart-new-tab-setup.ts", () => {
    const source = readFileSync(SOURCE_PATH, "utf8");
    expect(source).not.toMatch(/export function normalizeChartNewTabSeed/);
  });
});
