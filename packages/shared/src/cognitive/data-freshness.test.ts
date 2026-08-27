import { describe, expect, it } from "vitest";
import {
  buildDataFreshness,
  DATA_FRESHNESS_THRESHOLD_MINUTES,
} from "./data-freshness.js";

describe("data-freshness", () => {
  it("unknown when no lastBarDate", () => {
    expect(buildDataFreshness({}).status).toBe("unknown");
  });

  it("fresh when recent", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    expect(buildDataFreshness({ lastBarDate: last, now }).status).toBe("fresh");
  });

  it("stale when beyond threshold", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-01T12:00:00Z").toISOString();
    const f = buildDataFreshness({ lastBarDate: last, now });
    expect(f.status).toBe("stale");
    expect(f.thresholdMinutes).toBe(DATA_FRESHNESS_THRESHOLD_MINUTES);
  });

  it("error on query failed", () => {
    expect(buildDataFreshness({ queryFailed: true }).status).toBe("error");
  });

  it("partial sample never claims portfolio-wide fresh", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    const f = buildDataFreshness({
      lastBarDate: last,
      now,
      partialSample: { probed: 1, total: 3 },
    });
    expect(f.status).not.toBe("fresh");
    expect(f.label).toMatch(/muestra parcial \(1\/3\)/i);
  });

  it("single-position probe can stay fresh", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    expect(
      buildDataFreshness({
        lastBarDate: last,
        now,
        partialSample: { probed: 1, total: 1 },
      }).status,
    ).toBe("fresh");
  });
});
