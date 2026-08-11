import { describe, expect, it } from "vitest";
import type { ChartTabState } from "@bolsa/shared";
import { dedupeChartTabsByInstrument } from "@/lib/chart-tab-uniqueness";

function tab(id: string, instrumentId: string, label?: string): ChartTabState {
  return {
    id,
    instrumentId,
    label: label ?? instrumentId,
  } as ChartTabState;
}

describe("dedupeChartTabsByInstrument", () => {
  it("keeps a single tab per instrumentId", () => {
    const { charts, activeChartId } = dedupeChartTabsByInstrument(
      [
        tab("a", "meta", "META"),
        tab("b", "meta", "META (copia)"),
        tab("c", "aapl", "AAPL"),
      ],
      "a",
    );
    expect(charts.map((t) => t.id)).toEqual(["a", "c"]);
    expect(activeChartId).toBe("a");
  });

  it("prefers the active duplicate when collapsing", () => {
    const { charts, activeChartId } = dedupeChartTabsByInstrument(
      [tab("a", "meta", "META"), tab("b", "meta", "META (copia)")],
      "b",
    );
    expect(charts).toHaveLength(1);
    expect(charts[0]?.id).toBe("b");
    expect(activeChartId).toBe("b");
  });

  it("retargets activeChartId if the active tab was dropped", () => {
    const { charts, activeChartId } = dedupeChartTabsByInstrument(
      [tab("a", "meta"), tab("b", "meta")],
      "missing",
    );
    expect(charts).toHaveLength(1);
    expect(activeChartId).toBe("a");
  });

  it("allows empty instrumentId tabs (placeholders)", () => {
    const { charts } = dedupeChartTabsByInstrument(
      [tab("empty1", ""), tab("empty2", "")],
      null,
    );
    expect(charts).toHaveLength(2);
  });
});
