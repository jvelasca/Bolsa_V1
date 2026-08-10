import { describe, expect, it } from "vitest";
import { instrumentTopBacktestsHref } from "@/features/backtests/instrument-strategy-top-panel";
import { PAPER_PATH_LAB } from "@/features/settings/paper-paths-copy";

describe("instrumentTopBacktestsHref", () => {
  it("deep-links to Finalistas with instrument and focus", () => {
    const href = instrumentTopBacktestsHref("inst-acs", "1d");
    expect(href).toContain("/backtests?");
    expect(href).toContain("instrumentId=inst-acs");
    expect(href).toContain("focus=finalists");
    expect(href).toContain("tab=run");
  });
});

describe("Finalistas → paper copy", () => {
  it("documents checklist handoff without auto-deploy", () => {
    expect(PAPER_PATH_LAB.finalistsHint).toMatch(/Checklist/i);
    expect(PAPER_PATH_LAB.finalistsHint).toMatch(/no es auto/i);
    expect(PAPER_PATH_LAB.finalistsHint.toLowerCase()).not.toContain(
      "desplegar sin",
    );
  });
});
