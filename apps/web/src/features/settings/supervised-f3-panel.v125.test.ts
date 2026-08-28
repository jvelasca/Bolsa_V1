/**
 * V1.25 — contrato estructural Confirm (T-SIZE-08, T-SIZE-09).
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const panelPath = join(
  dirname(fileURLToPath(import.meta.url)),
  "supervised-f3-panel.tsx",
);

describe("SupervisedF3Panel V1.25 contract", () => {
  const src = readFileSync(panelPath, "utf8");

  it("T-SIZE-08: assessments gated by advancedOpen", () => {
    expect(src).toMatch(/data-testid="f3-advanced-section"/);
    expect(src).toMatch(/\{ta \? \(/);
    expect(src).toMatch(/data-testid="f3-advanced-toggle"/);
  });

  it("T-SIZE-09: ticket wires riskPct not null for TRIGGERED plan", () => {
    expect(src).toMatch(/riskPct=\{displayRiskPct\}/);
    expect(src).toMatch(/signedLossAtStop=\{riskSignature\.signedLossAtStop\}/);
    expect(src).not.toMatch(/riskPct=\{null\}/);
  });

  it("uses resolveSupervisedOpeningQuantity not suggestQuantityFromCash", () => {
    expect(src).toMatch(/resolveSupervisedOpeningQuantity/);
    expect(src).not.toMatch(/suggestQuantityFromCash/);
  });
});
