import { beforeEach, describe, expect, it } from "vitest";
import {
  BACKTEST_RUN_CONTEXT_KEY,
  defaultBacktestRunContext,
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

  it("el default ya no es 0/0 bps (techo optimista)", () => {
    const fallback = defaultBacktestRunContext();
    expect(fallback.commissionBps).toBe("10");
    expect(fallback.slippageBps).toBe("5");

    const loaded = loadBacktestRunContext();
    expect(loaded.commissionBps).toBe("10");
    expect(loaded.slippageBps).toBe("5");
  });

  it("migra UNA vez el contexto legado 0/0 sin marca de costes", () => {
    localStorage.setItem(
      BACKTEST_RUN_CONTEXT_KEY,
      JSON.stringify({
        periodPreset: "all",
        initialCash: "10000",
        commissionBps: "0",
        slippageBps: "0",
        timeframe: "1d",
      }),
    );

    const loaded = loadBacktestRunContext();
    // El 0 legado era el default anterior, no una elección: se eleva al de campaña.
    expect(loaded.commissionBps).toBe("10");
    expect(loaded.slippageBps).toBe("5");
  });

  it("respeta un 0 explícito guardado con la marca de costes actual", () => {
    saveBacktestRunContext({
      periodPreset: "all",
      customDateFrom: "",
      customDateTo: "",
      diaD: "",
      initialCash: "10000",
      commissionBps: "0",
      slippageBps: "0",
      timeframe: "1d",
    });

    const loaded = loadBacktestRunContext();
    expect(loaded.commissionBps).toBe("0");
    expect(loaded.slippageBps).toBe("0");
  });
});
