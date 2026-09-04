import { describe, expect, it } from "vitest";
import {
  BOOTSTRAP_PROTECT_STOP_PCT,
  bootstrapProtectStopLabel,
  resolveBootstrapProtectStop,
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

  it("label is emergency language, not strategy stop", () => {
    const label = bootstrapProtectStopLabel();
    expect(label.title).toMatch(/sin protección/i);
    expect(label.suggestedLine).toMatch(/emergencia/i);
    expect(label.suggestedLine).toMatch(/−5 %/);
    expect(label.disclaimer).toMatch(/No sustituye/i);
  });
});
