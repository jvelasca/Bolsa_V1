import { describe, expect, it } from "vitest";
import type { InstrumentDailyOpinionHintV1 } from "@bolsa/shared";
import { instrumentDailyOpinionHintKey } from "@/features/trading/use-instrument-daily-opinions";

function hint(
  overrides: Partial<InstrumentDailyOpinionHintV1> = {},
): InstrumentDailyOpinionHintV1 {
  return {
    instrumentId: "AAA",
    ioScore: 70,
    distress: false,
    allowTrading: true,
    hasEodBar: true,
    ...overrides,
  };
}

describe("instrumentDailyOpinionHintKey", () => {
  it("un hint sin posición medida no comparte clave con «sin posición»", () => {
    expect(
      instrumentDailyOpinionHintKey(hint({ positionOpen: null })),
    ).not.toBe(instrumentDailyOpinionHintKey(hint({ positionOpen: false })));
  });

  it("ausente y null son el mismo estado (no medido)", () => {
    expect(instrumentDailyOpinionHintKey(hint())).toBe(
      instrumentDailyOpinionHintKey(hint({ positionOpen: null })),
    );
  });

  it("true, false y null producen tres claves distintas", () => {
    const keys = new Set([
      instrumentDailyOpinionHintKey(hint({ positionOpen: true })),
      instrumentDailyOpinionHintKey(hint({ positionOpen: false })),
      instrumentDailyOpinionHintKey(hint({ positionOpen: null })),
    ]);
    expect(keys.size).toBe(3);
  });

  it("el resto del hint sigue diferenciando la clave", () => {
    expect(instrumentDailyOpinionHintKey(hint())).not.toBe(
      instrumentDailyOpinionHintKey(hint({ ioScore: 90 })),
    );
    expect(instrumentDailyOpinionHintKey(hint())).not.toBe(
      instrumentDailyOpinionHintKey(hint({ allowTrading: false })),
    );
    expect(instrumentDailyOpinionHintKey(hint())).not.toBe(
      instrumentDailyOpinionHintKey(hint({ hasEodBar: undefined })),
    );
  });
});
