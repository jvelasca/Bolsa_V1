/**
 * P2-01 / I-03 — un P&L no medido nunca se colorea como positivo.
 *
 * Falsable: con `(value ?? 0) >= 0` los cuatro primeros casos devuelven
 * `positive` y esta tabla falla. El cero medido tampoco es ganancia.
 */
import { describe, expect, it } from "vitest";
import { PNL_TONE_CLASS, pnlTone } from "@/lib/pnl-tone";

describe("pnlTone", () => {
  it("un hueco no se afirma: null, undefined y NaN son neutrales", () => {
    for (const value of [null, undefined, Number.NaN]) {
      expect(pnlTone(value)).toBe("neutral");
    }
  });

  it("un cero medido es plano, no ganancia", () => {
    expect(pnlTone(0)).toBe("neutral");
    expect(pnlTone(-0)).toBe("neutral");
  });

  it("solo un valor medido distinto de cero declara signo", () => {
    expect(pnlTone(0.01)).toBe("positive");
    expect(pnlTone(50)).toBe("positive");
    expect(pnlTone(-0.01)).toBe("negative");
    expect(pnlTone(-50)).toBe("negative");
  });

  it("Infinity no es una medición válida", () => {
    expect(pnlTone(Number.POSITIVE_INFINITY)).toBe("neutral");
    expect(pnlTone(Number.NEGATIVE_INFINITY)).toBe("neutral");
  });

  it("cada tono tiene su clase y el neutral no es verde", () => {
    expect(PNL_TONE_CLASS.positive).toContain("emerald");
    expect(PNL_TONE_CLASS.negative).toContain("rose");
    expect(PNL_TONE_CLASS.neutral).not.toContain("emerald");
    expect(PNL_TONE_CLASS.neutral).not.toContain("rose");
  });
});
