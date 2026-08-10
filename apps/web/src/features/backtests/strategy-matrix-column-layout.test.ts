import { describe, expect, it } from "vitest";
import {
  buildStrategyMatrixGridTemplate,
  cycleStrategyMatrixSort,
  normalizeStrategyMatrixLayout,
  sortStrategyMatrixRows,
  toggleStrategyMatrixColumn,
} from "@/features/backtests/strategy-matrix-column-layout";
import type { StrategyMatrixRow } from "@/features/backtests/backtest-strategy-matrix";

function row(
  partial: Partial<StrategyMatrixRow> &
    Pick<StrategyMatrixRow, "rowId" | "label">,
): StrategyMatrixRow {
  return {
    kind: "preset",
    subtitle: "Tendencia",
    status: "idle",
    ...partial,
  };
}

describe("strategy-matrix-column-layout", () => {
  it("normalizes unknown columns and keeps label visible", () => {
    const layout = normalizeStrategyMatrixLayout([
      { id: "excessPct", width: 80, visible: true },
      { id: "label", width: 10, visible: false },
    ] as never);
    expect(layout.find((c) => c.id === "label")?.visible).toBe(true);
    expect(layout.find((c) => c.id === "excessPct")?.width).toBe(80);
  });

  it("sorts by numeric excess desc then clears", () => {
    const rows = [
      row({ rowId: "a", label: "A", status: "ok", excessReturnPct: 1 }),
      row({ rowId: "b", label: "B", status: "ok", excessReturnPct: 5 }),
    ];
    const desc = cycleStrategyMatrixSort(null, "excessPct");
    expect(desc?.direction).toBe("desc");
    expect(sortStrategyMatrixRows(rows, desc)[0]?.rowId).toBe("b");
    const asc = cycleStrategyMatrixSort(desc, "excessPct");
    expect(asc?.direction).toBe("asc");
    expect(cycleStrategyMatrixSort(asc, "excessPct")).toBeNull();
  });

  it("does not hide the last non-actions column", () => {
    const layout = normalizeStrategyMatrixLayout([
      { id: "label", width: 120, visible: true },
      { id: "returnPct", width: 60, visible: false },
      { id: "actions", width: 52, visible: true },
    ]);
    expect(toggleStrategyMatrixColumn(layout, "label")).toEqual(layout);
  });

  it("includes library/remove columns visible by default (toggleable + favoritable)", () => {
    const layout = normalizeStrategyMatrixLayout(undefined);
    expect(layout.find((c) => c.id === "library")?.visible).toBe(true);
    expect(layout.find((c) => c.id === "remove")?.visible).toBe(true);
    expect(layout.find((c) => c.id === "actions")?.visible).toBe(true);
    const hidden = toggleStrategyMatrixColumn(layout, "library");
    expect(hidden.find((c) => c.id === "library")?.visible).toBe(false);
  });

  it("builds grid with select + flexible label", () => {
    const template = buildStrategyMatrixGridTemplate([
      { id: "label", width: 140, visible: true },
      { id: "returnPct", width: 64, visible: true },
    ]);
    expect(template.startsWith("28px ")).toBe(true);
    expect(template).toContain("minmax(140px, 1fr)");
  });
});
