import { beforeEach, describe, expect, it } from "vitest";
import {
  BACKTEST_RUN_CONTEXT_KEY,
  loadBacktestRunContext,
  saveBacktestRunContext,
} from "@/features/backtests/backtest-run-context";

describe("backtest-run-context", () => {
  beforeEach(() => {
    localStorage.removeItem(BACKTEST_RUN_CONTEXT_KEY);
  });

  it("persists period/cash across load (post-reinicio)", () => {
    saveBacktestRunContext({
      periodPreset: "1y",
      customDateFrom: "",
      customDateTo: "",
      diaD: "2024-06-15",
      initialCash: "25000",
      commissionBps: "10",
      slippageBps: "5",
      timeframe: "1d",
    });
    const loaded = loadBacktestRunContext();
    expect(loaded.periodPreset).toBe("1y");
    expect(loaded.initialCash).toBe("25000");
    expect(loaded.commissionBps).toBe("10");
    expect(loaded.diaD).toBe("2024-06-15");
  });
});
