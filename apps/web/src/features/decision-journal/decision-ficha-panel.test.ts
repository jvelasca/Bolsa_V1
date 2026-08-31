import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("DecisionFichaPanel honesty wiring (V1.41.2)", () => {
  it("passes entriesBlocked, gateStatus and orderPending into builders", () => {
    const src = readFileSync(
      resolve(__dirname, "decision-ficha-panel.tsx"),
      "utf8",
    );
    expect(src).toMatch(/buildEntryOperatingTruth\(\{/);
    expect(src).toMatch(/entriesBlocked,/);
    expect(src).toMatch(/gateStatus,/);
    expect(src).toMatch(/orderPending,/);
  });
});
