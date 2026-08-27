/**
 * Tests — scan freshness chip (encabezado Hoy / Mercado).
 */

import { describe, expect, it } from "vitest";
import { buildScanFreshnessChip } from "./scan-freshness-chip.js";

describe("buildScanFreshnessChip", () => {
  const now = new Date("2026-08-27T12:00:00Z");

  it("missing when no scan", () => {
    const chip = buildScanFreshnessChip({ scanUpdatedAt: null, now });
    expect(chip.tone).toBe("missing");
    expect(chip.label).toContain("No actualizado");
  });

  it("fresh within 48h", () => {
    const chip = buildScanFreshnessChip({
      scanUpdatedAt: "2026-08-27T08:31:00Z",
      now,
    });
    expect(chip.tone).toBe("fresh");
    expect(chip.label.startsWith("Barrido ·")).toBe(true);
  });

  it("stale after 48h", () => {
    const chip = buildScanFreshnessChip({
      scanUpdatedAt: "2026-08-25T08:00:00Z",
      now,
    });
    expect(chip.tone).toBe("stale");
    expect(chip.label).toMatch(/hace \d+ h/);
  });
});
