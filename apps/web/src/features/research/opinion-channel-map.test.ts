import { describe, expect, it } from "vitest";
import { buildOpinionChannelItems, mapOpinionToChannel } from "@bolsa/shared";
import type { InstrumentDailyOpinionV1 } from "@bolsa/shared";

function opinion(
  partial: Partial<InstrumentDailyOpinionV1> &
    Pick<InstrumentDailyOpinionV1, "instrumentId" | "stance" | "dictamenStars">,
): InstrumentDailyOpinionV1 {
  return {
    id: partial.id ?? `id-${partial.instrumentId}`,
    instrumentId: partial.instrumentId,
    asOfBarDate: partial.asOfBarDate ?? "2026-08-04",
    stance: partial.stance,
    dictamenStars: partial.dictamenStars,
    strategyStars: partial.strategyStars ?? null,
    ioScore: partial.ioScore ?? null,
    faScore: null,
    taScore: null,
    distress: false,
    reasons: partial.reasons ?? [],
    gateStatus: "PASS",
    topId: null,
    topVersion: null,
    source: "on_demand",
    engineVersion: "opinion_v1",
    idempotencyKey: "k",
    computedAt: "2026-08-04T18:00:00Z",
    createdAt: "2026-08-04T18:00:00Z",
    updatedAt: "2026-08-04T18:00:00Z",
  };
}

describe("mapOpinionToChannel", () => {
  it("maps buy ★4+ to alarma and buy ★2–3 to aviso", () => {
    expect(mapOpinionToChannel({ stance: "buy", dictamenStars: 5 })).toBe(
      "alarma",
    );
    expect(mapOpinionToChannel({ stance: "buy", dictamenStars: 4 })).toBe(
      "alarma",
    );
    expect(mapOpinionToChannel({ stance: "buy", dictamenStars: 3 })).toBe(
      "aviso",
    );
    expect(mapOpinionToChannel({ stance: "buy", dictamenStars: 1 })).toBe(
      "silent",
    );
  });

  it("maps sell/reduce ★≥3 to alarma", () => {
    expect(mapOpinionToChannel({ stance: "sell_exit", dictamenStars: 3 })).toBe(
      "alarma",
    );
    expect(mapOpinionToChannel({ stance: "reduce", dictamenStars: 2 })).toBe(
      "aviso",
    );
  });

  it("silences hold_watch / no_trade", () => {
    expect(
      mapOpinionToChannel({ stance: "hold_watch", dictamenStars: 5 }),
    ).toBe("silent");
    expect(mapOpinionToChannel({ stance: "no_trade", dictamenStars: 1 })).toBe(
      "silent",
    );
  });
});

describe("buildOpinionChannelItems", () => {
  it("drops silent and sorts alarmas first", () => {
    const items = buildOpinionChannelItems([
      {
        symbol: "IBE",
        opinion: opinion({
          instrumentId: "1",
          stance: "hold_watch",
          dictamenStars: 4,
        }),
      },
      {
        symbol: "SAN",
        opinion: opinion({
          instrumentId: "2",
          stance: "buy",
          dictamenStars: 5,
        }),
      },
      {
        symbol: "TEF",
        opinion: opinion({
          instrumentId: "3",
          stance: "overbought",
          dictamenStars: 3,
        }),
      },
    ]);
    expect(items.map((i) => i.symbol)).toEqual(["SAN", "TEF"]);
    expect(items[0]!.level).toBe("alarma");
    expect(items[0]!.actionable).toBe(true);
    expect(items[1]!.level).toBe("aviso");
    expect(items[1]!.actionable).toBe(false);
  });
});
