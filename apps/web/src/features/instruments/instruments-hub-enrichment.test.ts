import { describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import {
  indexPositionsByInstrument,
  invertListMemberships,
  pickListChips,
} from "@/features/instruments/instruments-hub-enrichment";

describe("instruments-hub-enrichment", () => {
  it("inverts list memberships by instrument", () => {
    const map = invertListMemberships([
      { id: "l1", name: "IBEX", source: "catalog", instrumentIds: ["a", "b"] },
      { id: "l2", name: "Watch", source: "custom", instrumentIds: ["a"] },
    ]);
    expect(map.get("a")?.map((m) => m.listName)).toEqual(["IBEX", "Watch"]);
    expect(map.get("b")).toHaveLength(1);
    expect(map.get("c")).toBeUndefined();
  });

  it("indexes open positions only", () => {
    const positions = [
      { instrumentId: "a", quantity: 10, unrealizedPnl: 5 },
      { instrumentId: "b", quantity: 0, unrealizedPnl: 0 },
    ] as PositionDto[];
    const map = indexPositionsByInstrument(positions);
    expect(map.has("a")).toBe(true);
    expect(map.has("b")).toBe(false);
  });

  it("picks chips with custom first and overflow", () => {
    const { visible, overflow } = pickListChips(
      [
        { listId: "1", listName: "Zebra", source: "catalog" },
        { listId: "2", listName: "Mine", source: "custom" },
        { listId: "3", listName: "Alpha", source: "catalog" },
      ],
      2,
    );
    expect(visible.map((v) => v.listName)).toEqual(["Mine", "Alpha"]);
    expect(overflow).toBe(1);
  });
});
