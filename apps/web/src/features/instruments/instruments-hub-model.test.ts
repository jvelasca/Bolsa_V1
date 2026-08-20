import { describe, expect, it } from "vitest";
import type { InstrumentWithMetaDto } from "@bolsa/shared";
import {
  filterAndSortInstrumentsHub,
  instrumentMatchesHubQuery,
  toggleInstrumentsHubSort,
} from "@/features/instruments/instruments-hub-model";

function inst(
  partial: Partial<InstrumentWithMetaDto> &
    Pick<InstrumentWithMetaDto, "id" | "symbol" | "name">,
): InstrumentWithMetaDto {
  return {
    yahooSymbol: `${partial.symbol}.MC`,
    exchange: "MCE",
    country: "ES",
    currency: "EUR",
    sector: null,
    isin: null,
    isActive: true,
    meta: {
      barCount: 100,
      lastSync: null,
      lastClose: 10,
      changePct: 0,
      lastBarDate: null,
      ...(partial.meta ?? {}),
    },
    ...partial,
  } as InstrumentWithMetaDto;
}

describe("instruments-hub-model", () => {
  const catalog = [
    inst({
      id: "1",
      symbol: "SAN",
      name: "Banco Santander",
      meta: {
        changePct: 1.2,
        lastClose: 4.5,
        barCount: 200,
        lastSync: null,
        lastBarDate: null,
      },
    }),
    inst({
      id: "2",
      symbol: "ACS",
      name: "ACS",
      isin: "ES0167050915",
      meta: {
        changePct: -0.5,
        lastClose: 41,
        barCount: 50,
        lastSync: null,
        lastBarDate: null,
      },
    }),
    inst({
      id: "3",
      symbol: "IBE",
      name: "Iberdrola",
      sector: "Utilities",
      meta: {
        changePct: 0.1,
        lastClose: 12,
        barCount: 300,
        lastSync: null,
        lastBarDate: null,
      },
    }),
  ];

  it("matches symbol, name, isin, sector", () => {
    expect(instrumentMatchesHubQuery(catalog[0]!, "san")).toBe(true);
    expect(instrumentMatchesHubQuery(catalog[1]!, "es016705")).toBe(true);
    expect(instrumentMatchesHubQuery(catalog[2]!, "util")).toBe(true);
    expect(instrumentMatchesHubQuery(catalog[0]!, "zzz")).toBe(false);
  });

  it("sorts by symbol asc by default", () => {
    const rows = filterAndSortInstrumentsHub(catalog, {});
    expect(rows.map((r) => r.symbol)).toEqual(["ACS", "IBE", "SAN"]);
  });

  it("filters then sorts by changePct desc", () => {
    const rows = filterAndSortInstrumentsHub(catalog, {
      query: "banco",
      sortKey: "changePct",
      sortDir: "desc",
    });
    expect(rows.map((r) => r.symbol)).toEqual(["SAN"]);
    const byChange = filterAndSortInstrumentsHub(catalog, {
      sortKey: "changePct",
      sortDir: "desc",
    });
    expect(byChange.map((r) => r.symbol)).toEqual(["SAN", "IBE", "ACS"]);
  });

  it("sorts by listCount and filters portfolio", () => {
    const membershipsByInstrument = new Map([
      ["1", [{ listId: "l1", listName: "IBEX", source: "catalog" }]],
      [
        "2",
        [
          { listId: "l1", listName: "IBEX", source: "catalog" },
          { listId: "l2", listName: "Watch", source: "custom" },
        ],
      ],
    ]);
    const positionsByInstrument = new Map([
      [
        "1",
        {
          id: "p1",
          instrumentId: "1",
          symbol: "SAN",
          name: "Banco Santander",
          quantity: 10,
          avgCost: 4,
          lastPrice: 4.5,
          marketValue: 45,
          unrealizedPnl: 5,
          unrealizedPnlPct: 12.5,
        },
      ],
    ]);
    const enrichment = { membershipsByInstrument, positionsByInstrument };
    const byLists = filterAndSortInstrumentsHub(catalog, {
      sortKey: "listCount",
      sortDir: "desc",
      enrichment,
    });
    expect(byLists.map((r) => r.symbol)).toEqual(["ACS", "SAN", "IBE"]);
    const portfolioOnly = filterAndSortInstrumentsHub(catalog, {
      scopeFilter: "portfolio",
      enrichment,
    });
    expect(portfolioOnly.map((r) => r.symbol)).toEqual(["SAN"]);
    expect(
      instrumentMatchesHubQuery(
        catalog[1]!,
        "watch",
        membershipsByInstrument.get("2"),
      ),
    ).toBe(true);
  });

  it("filters Estudio and sorts by scoreIo", () => {
    const ioByInstrument = new Map<string, number | null>([
      ["1", 55],
      ["2", 80],
      ["3", 40],
    ]);
    const rows = filterAndSortInstrumentsHub(catalog, {
      scopeFilter: "estudio",
      estudioIds: new Set(["1", "3"]),
      sortKey: "scoreIo",
      sortDir: "desc",
      enrichment: { ioByInstrument },
    });
    expect(rows.map((r) => r.symbol)).toEqual(["SAN", "IBE"]);
  });

  it("filters by list id", () => {
    const membershipsByInstrument = new Map([
      ["1", [{ listId: "l1", listName: "IBEX", source: "catalog" as const }]],
      ["2", [{ listId: "l2", listName: "Watch", source: "custom" as const }]],
    ]);
    const rows = filterAndSortInstrumentsHub(catalog, {
      scopeFilter: "list",
      listId: "l1",
      enrichment: { membershipsByInstrument },
    });
    expect(rows.map((r) => r.symbol)).toEqual(["SAN"]);
  });

  it("toggles sort direction on same key", () => {
    expect(toggleInstrumentsHubSort("symbol", "asc", "symbol")).toEqual({
      sortKey: "symbol",
      sortDir: "desc",
    });
    expect(toggleInstrumentsHubSort("symbol", "asc", "changePct")).toEqual({
      sortKey: "changePct",
      sortDir: "desc",
    });
  });
});
