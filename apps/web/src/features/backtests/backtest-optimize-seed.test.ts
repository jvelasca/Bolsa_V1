import { describe, expect, it } from "vitest";
import {
  buildSmaPeriodLists,
  isOptimizableStrategy,
  optimizeFamilyForStrategy,
  optimizeFamilyProxyNote,
  rsiAnchorParams,
  smaAnchorPeriods,
} from "@/features/backtests/backtest-optimize-seed";
import { STRATEGY_PRESET_KEYS } from "@bolsa/shared";

describe("optimizeFamilyForStrategy · coach coverage", () => {
  it("maps Death/Golden/EMA/stack to SMA lab", () => {
    expect(optimizeFamilyForStrategy("death_cross")).toBe("sma_crossover");
    expect(optimizeFamilyForStrategy("golden_cross")).toBe("sma_crossover");
    expect(optimizeFamilyForStrategy("ema_crossover")).toBe("sma_crossover");
    expect(optimizeFamilyForStrategy("ma_stack_bullish")).toBe("sma_crossover");
    expect(isOptimizableStrategy("death_cross")).toBe(true);
  });

  it("maps oscillators / pullback to RSI lab", () => {
    expect(optimizeFamilyForStrategy("stoch_oversold")).toBe(
      "rsi_mean_reversion",
    );
    expect(optimizeFamilyForStrategy("cci_oversold")).toBe(
      "rsi_mean_reversion",
    );
    expect(optimizeFamilyForStrategy("pullback_in_uptrend")).toBe(
      "rsi_mean_reversion",
    );
  });

  it("maps Bollinger / SMA200 via proxy lab families", () => {
    expect(optimizeFamilyForStrategy("bollinger_lower_bounce")).toBe(
      "rsi_mean_reversion",
    );
    expect(optimizeFamilyForStrategy("bollinger_upper_breakout")).toBe(
      "sma_crossover",
    );
    expect(optimizeFamilyForStrategy("price_above_sma200")).toBe(
      "sma_crossover",
    );
    expect(isOptimizableStrategy("bollinger_lower_bounce")).toBe(true);
  });

  it("anchors Death cross at 50/200 and EMA at 12/26", () => {
    expect(smaAnchorPeriods("death_cross")).toEqual({ fast: 50, slow: 200 });
    expect(smaAnchorPeriods("ema_crossover")).toEqual({ fast: 12, slow: 26 });
    expect(smaAnchorPeriods("ma_stack_bullish")).toEqual({
      fast: 20,
      slow: 50,
    });
    expect(smaAnchorPeriods("price_above_sma200")).toEqual({
      fast: 50,
      slow: 200,
    });
    expect(smaAnchorPeriods("bollinger_upper_breakout")).toEqual({
      fast: 10,
      slow: 20,
    });
  });

  it("builds a long-horizon neighbourhood for Death cross", () => {
    const lists = buildSmaPeriodLists("death_cross");
    expect(lists.anchorFast).toBe(50);
    expect(lists.anchorSlow).toBe(200);
    expect(lists.slowPeriods.split(",").map(Number)).toContain(200);
  });

  it("reads Stoch/pullback RSI anchors", () => {
    expect(rsiAnchorParams("stoch_oversold")).toEqual({
      period: 14,
      oversold: 20,
      overbought: 80,
    });
    expect(rsiAnchorParams("pullback_in_uptrend")).toEqual({
      period: 14,
      oversold: 42,
      overbought: 65,
    });
  });

  it("exposes proxy notes for non-native presets", () => {
    expect(optimizeFamilyProxyNote("death_cross")).toMatch(/Death cross/i);
    expect(optimizeFamilyProxyNote("bollinger_lower_bounce")).toMatch(/proxy/i);
    expect(optimizeFamilyProxyNote("sma_crossover")).toBeNull();
  });

  it("maps Donchian / ADX / Ichimoku / VWAP / SuperTrend to SMA lab", () => {
    expect(optimizeFamilyForStrategy("donchian_breakout")).toBe(
      "sma_crossover",
    );
    expect(optimizeFamilyForStrategy("adx_di_trend")).toBe("sma_crossover");
    expect(optimizeFamilyForStrategy("ichimoku_tk_cross")).toBe(
      "sma_crossover",
    );
    expect(optimizeFamilyForStrategy("vwap_reclaim")).toBe("sma_crossover");
    expect(optimizeFamilyForStrategy("supertrend_follow")).toBe(
      "sma_crossover",
    );
    expect(smaAnchorPeriods("ichimoku_tk_cross")).toEqual({
      fast: 9,
      slow: 26,
    });
    expect(smaAnchorPeriods("donchian_breakout")).toEqual({
      fast: 10,
      slow: 20,
    });
    expect(optimizeFamilyProxyNote("supertrend_follow")).toMatch(/SuperTrend/i);
  });

  it("covers all catalog presets via native or proxy lab", () => {
    const uncovered = STRATEGY_PRESET_KEYS.filter(
      (k) => !isOptimizableStrategy(k),
    );
    expect(uncovered).toEqual([]);
  });
});
