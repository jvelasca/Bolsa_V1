import { describe, expect, it } from "vitest";

import {
  DEFAULT_BACKTEST_COSTS,
  formatCostBpsSummary,
  optionalCostBps,
  resolveCostBpsText,
} from "@/features/backtests/lib/backtest-cost-defaults";

describe("backtest-cost-defaults", () => {
  it("usa los mismos costes que CampaignCosts (10/5/2)", () => {
    expect(DEFAULT_BACKTEST_COSTS).toEqual({
      commissionBps: 10,
      slippageBps: 5,
      spreadBps: 2,
    });
  });

  it("un campo vacío resuelve al default y un 0 explícito se respeta", () => {
    expect(resolveCostBpsText("", 10)).toBe(10);
    expect(resolveCostBpsText("   ", 5)).toBe(5);
    expect(resolveCostBpsText("0", 10)).toBe(0);
    expect(resolveCostBpsText("12,5", 10)).toBe(10);
    expect(resolveCostBpsText("12.5", 10)).toBe(12.5);
    expect(resolveCostBpsText("-1", 10)).toBe(10);
  });

  it("optionalCostBps deja undefined para que el backend aplique el default", () => {
    expect(optionalCostBps("")).toBeUndefined();
    expect(optionalCostBps("0")).toBe(0);
    expect(optionalCostBps("10")).toBe(10);
    expect(optionalCostBps("basura")).toBeUndefined();
  });

  it("el resumen muestra los bps efectivos, no el texto crudo", () => {
    expect(formatCostBpsSummary("", "")).toBe("10/5 bps");
    expect(formatCostBpsSummary("0", "0")).toBe("0/0 bps");
  });
});
