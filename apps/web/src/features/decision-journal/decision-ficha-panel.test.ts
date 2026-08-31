import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("DecisionFichaPanel honesty wiring (V1.41.2)", () => {
  it("passes entriesBlocked, gateStatus, orderPending and inConfirmQueue into builders", () => {
    const src = readFileSync(
      resolve(__dirname, "decision-ficha-panel.tsx"),
      "utf8",
    );
    expect(src).toMatch(/buildEntryOperatingTruth\(\{/);
    expect(src).toMatch(/entriesBlocked,/);
    expect(src).toMatch(/gateStatus,/);
    expect(src).toMatch(/orderPending,/);
    expect(src).toMatch(/inConfirmQueue,/);
  });

  it("Journal page feeds dictamen gateStatus (same SoT as Mercado cockpit)", () => {
    const src = readFileSync(
      resolve(__dirname, "decision-journal-page.tsx"),
      "utf8",
    );
    expect(src).toMatch(/useInstrumentDailyOpinions/);
    expect(src).toMatch(/gateStatus=\{selectedGateStatus\}/);
    expect(src).toMatch(/inConfirmQueue=\{selectedInConfirmQueue\}/);
    expect(src).toMatch(/useSupervisedF3QueueStore/);
  });
});
