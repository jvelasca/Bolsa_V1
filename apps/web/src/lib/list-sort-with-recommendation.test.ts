import { describe, expect, it } from "vitest";
import type { InstrumentWithMetaDto } from "@bolsa/shared";
import { sortInstrumentListWithRecommendation } from "@/lib/list-sort-with-recommendation";
import type { ListRecommendationRow } from "@/features/trading/lists-tab/list-recommendation-scores-context";

function item(id: string, symbol: string): InstrumentWithMetaDto {
  return {
    id,
    symbol,
    yahooSymbol: symbol,
    name: symbol,
    exchange: "BME",
    country: "ES",
    currency: "EUR",
    sector: null,
    isActive: true,
    meta: { barCount: 1, lastSync: null, lastClose: 10, changePct: 0 },
  };
}

function row(
  io: number | null,
  stanceLabel = "Vigilar",
): ListRecommendationRow {
  return {
    io,
    ta: io,
    fa: io,
    dictamenStars: io != null ? Math.min(5, Math.round(io / 20)) : null,
    stance: "hold_watch",
    stanceLabel,
  };
}

describe("sortInstrumentListWithRecommendation", () => {
  const items = [item("a", "AAA"), item("b", "BBB"), item("c", "CCC")];
  const scores = new Map<string, ListRecommendationRow>([
    ["a", row(40)],
    ["b", row(90)],
    ["c", row(70)],
  ]);

  it("sorts by ioScore descending (best first)", () => {
    const sorted = sortInstrumentListWithRecommendation(
      items,
      { column: "ioScore", direction: "desc" },
      scores,
    );
    expect(sorted.map((i) => i.id)).toEqual(["b", "c", "a"]);
  });

  it("sorts by ioScore ascending", () => {
    const sorted = sortInstrumentListWithRecommendation(
      items,
      { column: "ioScore", direction: "asc" },
      scores,
    );
    expect(sorted.map((i) => i.id)).toEqual(["a", "c", "b"]);
  });

  it("falls back to symbol sort when not a recommendation column", () => {
    const sorted = sortInstrumentListWithRecommendation(
      items,
      { column: "symbol", direction: "desc" },
      scores,
    );
    expect(sorted.map((i) => i.symbol)).toEqual(["CCC", "BBB", "AAA"]);
  });

  it("keeps chart order when sort is undefined", () => {
    const sorted = sortInstrumentListWithRecommendation(
      items,
      undefined,
      scores,
    );
    expect(sorted.map((i) => i.id)).toEqual(["a", "b", "c"]);
  });
});
