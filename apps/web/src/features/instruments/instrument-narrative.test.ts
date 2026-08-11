import { describe, expect, it } from "vitest";
import {
  isInstrumentNarrativeFresh,
  validateInstrumentNarrativeBody,
} from "@bolsa/shared";

describe("instrument-narrative", () => {
  it("rejects more than 20 lines", () => {
    const body = Array.from({ length: 21 }, (_, i) => `L${i}`).join("\n");
    const v = validateInstrumentNarrativeBody(body);
    expect(v.ok).toBe(false);
    expect(v.lines).toBe(21);
  });

  it("accepts short body and freshness window", () => {
    expect(validateInstrumentNarrativeBody("OK\nsegunda").ok).toBe(true);
    expect(isInstrumentNarrativeFresh(new Date().toISOString())).toBe(true);
    expect(isInstrumentNarrativeFresh("2020-01-01T00:00:00Z")).toBe(false);
  });
});
