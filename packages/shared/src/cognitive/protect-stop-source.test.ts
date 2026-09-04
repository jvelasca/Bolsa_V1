import { describe, expect, it } from "vitest";
import {
  BOOTSTRAP_PROTECT_STOP_PCT,
  bootstrapProtectStopLabel,
  isEmergencyBootstrapStop,
  resolveBootstrapProtectStop,
  resolveEmergencyBootstrapStopPrice,
} from "./protect-stop-source.js";

describe("protect-stop-source V2.10", () => {
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

  it("prefers initialStop when present", () => {
    expect(
      resolveBootstrapProtectStop({
        direction: "long",
        entry: 100,
        initialStop: 97.5,
      }),
    ).toBe(97.5);
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
    expect(
      isEmergencyBootstrapStop({
        direction: "long",
        entry: 184.2,
        stop: 174.99,
        protectKind: "bootstrap",
      }),
    ).toBe(true);
  });

  it("label is emergency language, not strategy stop", () => {
    const label = bootstrapProtectStopLabel();
    expect(label.title).toMatch(/sin protección/i);
    expect(label.suggestedLine).toMatch(/emergencia/i);
    expect(label.suggestedLine).toMatch(/−5 %/);
    expect(label.disclaimer).toMatch(/No sustituye/i);
  });
});
