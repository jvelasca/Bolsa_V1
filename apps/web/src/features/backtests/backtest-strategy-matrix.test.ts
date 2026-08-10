import { describe, expect, it } from "vitest";
import {
  STRATEGY_MATRIX_MAX_SELECTED,
  annotateStrategyMatrixRowsWithTop,
  buildStrategyMatrixRows,
  exploreBatteryRowIds,
  filterStrategyMatrixRows,
  formatPct,
  strategyMatrixFiltersWithSelection,
} from "@/features/backtests/backtest-strategy-matrix";
import { ALL_PRESET_COACH_KEYS } from "@/features/backtests/backtest-explore-value";

describe("backtest-strategy-matrix", () => {
  it("builds preset rows and merges saved strategies", () => {
    const rows = buildStrategyMatrixRows([
      {
        id: "s1",
        name: "Mi SMA",
        presetKey: "sma_crossover",
        origin: "manual",
        timeframe: "1d",
        kind: "indicator_signals",
        updatedAt: "2026-01-01",
        createdAt: "2026-01-01",
      },
    ]);
    expect(rows.some((r) => r.rowId === "preset:sma_crossover")).toBe(true);
    expect(
      rows.some((r) => r.rowId === "saved:s1" && r.label === "Mi SMA"),
    ).toBe(true);
  });

  it("filters by kind and L0 bucket", () => {
    const rows = buildStrategyMatrixRows([
      {
        id: "s1",
        name: "X",
        origin: "manual",
        timeframe: "1d",
        kind: "indicator_signals",
        updatedAt: "2026-01-01",
        createdAt: "2026-01-01",
      },
      {
        id: "s2",
        name: "Lab clone",
        origin: "preset",
        presetKey: "sma_crossover",
        timeframe: "1d",
        kind: "indicator_signals",
        updatedAt: "2026-01-01",
        createdAt: "2026-01-01",
      },
    ]);
    expect(filterStrategyMatrixRows(rows, "mine")).toHaveLength(1);
    expect(filterStrategyMatrixRows(rows, "optimized")).toHaveLength(1);
    expect(
      filterStrategyMatrixRows(rows, "preset").every(
        (r) => r.kind === "preset",
      ),
    ).toBe(true);
  });

  it("lights carousel filters that contain the current selection", () => {
    const rows = buildStrategyMatrixRows([
      {
        id: "s1",
        name: "X",
        origin: "manual",
        timeframe: "1d",
        kind: "indicator_signals",
        updatedAt: "2026-01-01",
        createdAt: "2026-01-01",
      },
      {
        id: "s2",
        name: "Lab clone",
        origin: "preset",
        presetKey: "sma_crossover",
        timeframe: "1d",
        kind: "indicator_signals",
        updatedAt: "2026-01-01",
        createdAt: "2026-01-01",
      },
    ]);
    const presetId = rows.find((r) => r.kind === "preset")!.rowId;
    const mineId = rows.find((r) => r.savedBucket === "mine")!.rowId;
    const lit = strategyMatrixFiltersWithSelection(
      rows,
      new Set([presetId, mineId]),
    );
    expect(lit.has("all")).toBe(true);
    expect(lit.has("preset")).toBe(true);
    expect(lit.has("mine")).toBe(true);
    expect(lit.has("optimized")).toBe(false);
  });

  it("explore battery ids cover all generic presets within selection cap", () => {
    expect(exploreBatteryRowIds()).toEqual(
      ALL_PRESET_COACH_KEYS.map((key) => `preset:${key}`),
    );
    expect(exploreBatteryRowIds().length).toBe(ALL_PRESET_COACH_KEYS.length);
    expect(exploreBatteryRowIds().length).toBeLessThanOrEqual(
      STRATEGY_MATRIX_MAX_SELECTED,
    );
  });

  it("formats percent", () => {
    expect(formatPct(12.34)).toBe("+12.3%");
    expect(formatPct(-1)).toBe("-1.0%");
    expect(formatPct(null)).toBe("—");
  });

  it("annotates and filters finalists by strategyDefinitionId", () => {
    const rows = buildStrategyMatrixRows([
      {
        id: "acs-sma",
        name: "ACS · Cruce SMA 20/50",
        presetKey: "sma_crossover",
        origin: "manual",
        timeframe: "1d",
        kind: "indicator_signals",
        updatedAt: "2026-01-01",
        createdAt: "2026-01-01",
      },
      {
        id: "acs-gc",
        name: "ACS · Golden",
        presetKey: "golden_cross",
        origin: "manual",
        timeframe: "1d",
        kind: "indicator_signals",
        updatedAt: "2026-01-01",
        createdAt: "2026-01-01",
      },
    ]);
    const annotated = annotateStrategyMatrixRowsWithTop(rows, {
      slots: [
        {
          rank: 1,
          strategyDefinitionId: "acs-sma",
          strategyType: "sma_crossover",
        },
        {
          rank: 2,
          strategyDefinitionId: "acs-gc",
          strategyType: "golden_cross",
        },
      ],
    });
    expect(annotated.find((r) => r.rowId === "saved:acs-sma")?.topRank).toBe(1);
    expect(annotated.find((r) => r.rowId === "saved:acs-gc")?.topRank).toBe(2);
    expect(
      annotated.find((r) => r.rowId === "preset:sma_crossover")?.topRank,
    ).toBeUndefined();
    const finals = filterStrategyMatrixRows(annotated, "finalists");
    expect(finals).toHaveLength(2);
  });
});
