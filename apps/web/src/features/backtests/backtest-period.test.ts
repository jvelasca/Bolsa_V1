import { describe, expect, it } from "vitest";
import {
  effectiveDiaD,
  isDiaDInPast,
  resolveBacktestWindow,
} from "@/features/backtests/backtest-period";

describe("resolveBacktestWindow + DÍA D", () => {
  it("all without as-of keeps limit-only window", () => {
    expect(resolveBacktestWindow("all", "", "")).toEqual({ limit: 10_000 });
  });

  it("all with past as-of adds dateTo", () => {
    expect(resolveBacktestWindow("all", "", "", "2024-06-15")).toEqual({
      dateTo: "2024-06-15",
      limit: 10_000,
    });
  });

  it("1y anchors to as-of not calendar today", () => {
    const w = resolveBacktestWindow("1y", "", "", "2024-06-15");
    expect(w.dateTo).toBe("2024-06-15");
    expect(w.dateFrom).toBe("2023-06-15");
  });

  it("custom Hasta is clamped to as-of", () => {
    const w = resolveBacktestWindow(
      "custom",
      "2020-01-01",
      "2025-01-01",
      "2024-06-15",
    );
    expect(w.dateFrom).toBe("2020-01-01");
    expect(w.dateTo).toBe("2024-06-15");
  });

  it("effectiveDiaD rejects future", () => {
    expect(effectiveDiaD("2099-01-01")).toBe(effectiveDiaD(""));
  });

  it("isDiaDInPast", () => {
    expect(isDiaDInPast("2020-01-01")).toBe(true);
    expect(isDiaDInPast("")).toBe(false);
  });
});
