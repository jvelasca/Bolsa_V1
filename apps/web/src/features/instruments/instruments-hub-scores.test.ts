import { describe, expect, it } from "vitest";
import type { CompositeChipDto, FundamentalChipDto } from "@bolsa/shared";
import {
  chunkIds,
  indexFaScores,
  indexTaScores,
} from "@/features/instruments/instruments-hub-scores";
import { filterAndSortInstrumentsHub } from "@/features/instruments/instruments-hub-model";
import type { InstrumentWithMetaDto } from "@bolsa/shared";

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

describe("instruments-hub-scores", () => {
  it("chunks ids", () => {
    expect(chunkIds(["a", "b", "c", "d"], 2)).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("indexes FA and TA scores", () => {
    const fa = indexFaScores([
      {
        instrumentId: "1",
        ticker: "SAN",
        scoreDisplay100: 72,
        confidence: "HIGH",
        isStale: true,
        distress: false,
      },
    ] as FundamentalChipDto[]);
    expect(fa.get("1")?.scoreDisplay100).toBe(72);
    expect(fa.get("1")?.isStale).toBe(true);

    const ta = indexTaScores([
      {
        instrumentId: "1",
        ticker: "SAN",
        scoreDisplay100: 55,
        confidence: "MEDIUM",
        combinedScore: 0.1,
        regime: "neutral",
        paperDUnlocked: true,
        technicalDisplay100: 61,
      },
    ] as CompositeChipDto[]);
    expect(ta.get("1")?.technicalDisplay100).toBe(61);
    expect(ta.get("1")?.compositeDisplay100).toBe(55);
    expect(ta.get("1")?.indiceOperativo).toBeNull();

    const taIo = indexTaScores([
      {
        instrumentId: "2",
        ticker: "ACS",
        scoreDisplay100: 80,
        indiceOperativo: 40,
        confidence: "LOW",
        combinedScore: 0.2,
        regime: "neutral",
        paperDUnlocked: true,
        technicalDisplay100: 70,
      },
    ] as CompositeChipDto[]);
    expect(taIo.get("2")?.indiceOperativo).toBe(40);
  });

  it("sorts hub by scoreFa", () => {
    const catalog = [
      inst({ id: "1", symbol: "SAN", name: "Santander" }),
      inst({ id: "2", symbol: "ACS", name: "ACS" }),
    ];
    const faByInstrument = new Map([
      ["1", { scoreDisplay100: 40, isStale: false, distress: false }],
      ["2", { scoreDisplay100: 80, isStale: false, distress: false }],
    ]);
    const rows = filterAndSortInstrumentsHub(catalog, {
      sortKey: "scoreFa",
      sortDir: "desc",
      enrichment: { faByInstrument },
    });
    expect(rows.map((r) => r.symbol)).toEqual(["ACS", "SAN"]);
  });
});
