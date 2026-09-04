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

  it("feeds orderPending into Position/Entry summaries for ExecutionState (V1.42 F2)", () => {
    const src = readFileSync(
      resolve(__dirname, "decision-ficha-panel.tsx"),
      "utf8",
    );
    expect(src).toMatch(/PositionOperatingSummary/);
    expect(src).toMatch(/orderPending=\{orderPending\}/);
    expect(src).toMatch(/orderPendingFill=\{orderPending\}/);
  });

  it("feeds submitIntent into Position/Entry summaries (V1.42 F2b)", () => {
    const src = readFileSync(
      resolve(__dirname, "decision-ficha-panel.tsx"),
      "utf8",
    );
    expect(src).toMatch(/submitIntent=\{submitIntent\}/);
    const page = readFileSync(
      resolve(__dirname, "decision-journal-page.tsx"),
      "utf8",
    );
    expect(page).toMatch(/useInFlightSubmitIntents/);
    expect(page).toMatch(/submitIntent=\{selectedSubmitIntent\}/);
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

  it("builds TradeStory in ficha and page passes journalEntries (V1.42 F4)", () => {
    const ficha = readFileSync(
      resolve(__dirname, "decision-ficha-panel.tsx"),
      "utf8",
    );
    expect(ficha).toMatch(/buildTradeStory\(\{/);
    expect(ficha).toMatch(/data-testid="ficha-trade-story"/);
    expect(ficha).toMatch(/Eventos con marca de tiempo/);
    expect(ficha).toMatch(/journalEntries/);
    const page = readFileSync(
      resolve(__dirname, "decision-journal-page.tsx"),
      "utf8",
    );
    expect(page).toMatch(/journalEntries=\{selectedJournalEntries\}/);
    expect(page).toMatch(/decision-journal-story/);
  });

  it("V2.27 wires journal spine + RESULTADO metrics (display-only)", () => {
    const ficha = readFileSync(
      resolve(__dirname, "decision-ficha-panel.tsx"),
      "utf8",
    );
    expect(ficha).toMatch(/buildJournalSpineView\(\{/);
    expect(ficha).toMatch(/data-testid="journal-spine"/);
    expect(ficha).toMatch(/journal-spine-step-\$/);
    expect(ficha).toMatch(/data-testid="journal-result-metrics"/);
    expect(ficha).toMatch(/data-testid="journal-mfe-mae"/);
    expect(ficha).toMatch(/journal-mfe-mae-mfe/);
    expect(ficha).toMatch(/positionState: null/);
  });
});
