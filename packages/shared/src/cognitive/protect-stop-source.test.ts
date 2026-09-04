import { describe, expect, it } from "vitest";
import {
  BOOTSTRAP_PROTECT_STOP_PCT,
  bootstrapProtectStopLabel,
  isEmergencyBootstrapStop,
  positionLacksStructuralStop,
  resolveBootstrapProtectStop,
  resolveEmergencyBootstrapStopPrice,
} from "./protect-stop-source.js";

describe("protect-stop-source V2.10 / V2.33", () => {
  it("exports 5% constant", () => {
    expect(BOOTSTRAP_PROTECT_STOP_PCT).toBe(0.05);
  });

  it("long → entry × 0.95", () => {
    expect(resolveBootstrapProtectStop({ direction: "long", entry: 100 })).toBe(
      95,
    );
  });

  it("short → entry × 1.05", () => {
    expect(
      resolveBootstrapProtectStop({ direction: "short", entry: 100 }),
    ).toBe(105);
  });

  it("V2.33 — never prefers initialStop (plan stop is kind plan)", () => {
    expect(
      resolveBootstrapProtectStop({
        direction: "long",
        entry: 100,
        initialStop: 97.5,
      }),
    ).toBe(95);
  });

  it("returns null without entry", () => {
    expect(
      resolveBootstrapProtectStop({ direction: "long", entry: null }),
    ).toBe(null);
  });

  it("raw emergency floor ignores planned initialStop", () => {
    expect(
      resolveEmergencyBootstrapStopPrice({ direction: "long", entry: 100 }),
    ).toBe(95);
    expect(
      isEmergencyBootstrapStop({
        direction: "long",
        entry: 100,
        stop: 95,
      }),
    ).toBe(true);
    expect(
      isEmergencyBootstrapStop({
        direction: "long",
        entry: 184.2,
        stop: 176.8,
        protectKind: "plan",
      }),
    ).toBe(false);
    // V2.33 — kind bootstrap alone is not enough; price must match floor.
    expect(
      isEmergencyBootstrapStop({
        direction: "long",
        entry: 184.2,
        stop: 176.8,
        protectKind: "bootstrap",
      }),
    ).toBe(false);
    expect(
      isEmergencyBootstrapStop({
        direction: "long",
        entry: 184.2,
        stop: 174.99,
        protectKind: "bootstrap",
      }),
    ).toBe(true);
  });

  it("positionLacksStructuralStop gates bootstrap kind", () => {
    expect(
      positionLacksStructuralStop({ currentStop: null, initialStop: null }),
    ).toBe(true);
    expect(
      positionLacksStructuralStop({ currentStop: 95, initialStop: null }),
    ).toBe(false);
    expect(
      positionLacksStructuralStop({ currentStop: null, initialStop: 95 }),
    ).toBe(false);
  });

  it("label is emergency language, not strategy stop", () => {
    const label = bootstrapProtectStopLabel();
    expect(label.title).toMatch(/sin protección/i);
    expect(label.suggestedLine).toMatch(/emergencia/i);
    expect(label.suggestedLine).toMatch(/−5 %/);
    expect(label.disclaimer).toMatch(/No sustituye/i);
  });
});
