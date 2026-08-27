import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { buildOpportunityRanking, ESTUDIO_LIST_ID } from "@bolsa/shared";
import {
  DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
  mesaScreenersUniverseHref,
} from "@/features/mesa/mesa-candidates-panel";

function readSource(file: string): string {
  return readFileSync(resolve(__dirname, file), "utf8");
}

describe("mesa opportunity discovery UI helpers", () => {
  it("DAILY-OPS-UNIVERSE-001 — default universe is Estudio, not IBEX", () => {
    expect(DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID).toBe(ESTUDIO_LIST_ID);
    expect(DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID).toBe("estudio");
    expect(mesaScreenersUniverseHref()).toBe("/screeners?listId=estudio");
  });

  it("screeners CTA deep-links listId", () => {
    expect(mesaScreenersUniverseHref("ibex35")).toContain("/screeners");
    expect(mesaScreenersUniverseHref("ibex35")).toContain("listId=ibex35");
  });

  it("ranking empty still exposes funnel denominator for Estudio", () => {
    const ranking = buildOpportunityRanking({
      studies: [],
      universeCount: 0,
      screenedCount: 0,
      universeListId: ESTUDIO_LIST_ID,
      estudioInstrumentIds: [],
    });
    expect(ranking.funnel.universeCount).toBe(0);
    expect(ranking.funnel.universeListId).toBe("estudio");
    expect(ranking.funnel.screenedCount).toBe(0);
    expect(ranking.funnel.scanStale).toBe(true);
    expect(ranking.impliesOperable).toBe(false);
    expect(ranking.discovered).toEqual([]);
  });

  it("funnel asOf is null without a scan — UI must render — not crash", () => {
    const ranking = buildOpportunityRanking({
      studies: [],
      universeCount: 0,
      screenedCount: 0,
      universeListId: ESTUDIO_LIST_ID,
      estudioInstrumentIds: [],
    });
    expect(ranking.funnel.asOf).toBeNull();
    expect(ranking.funnel.marketDataAsOf).toBeNull();
    expect(ranking.funnel.rankingAsOf).toBeNull();
    const src = readSource("mesa-candidates-panel.tsx");
    expect(src).toMatch(/funnel\?\.asOf/);
  });
});

describe("V1.24 — ranking language in the panel and drawer", () => {
  it("panel says Calidad and NO ES UNA ORDEN, never Opportunity NN/100", () => {
    const src = readSource("mesa-candidates-panel.tsx");
    expect(src).toMatch(/formatPriorityScore\(rankRow\.quality\)/);
    expect(src).toMatch(/PRIORITY_NOT_AN_ORDER/);
    expect(src).not.toMatch(/Opportunity \{rankRow\.quality\}/);
  });

  it("panel renders the three scores as bars, not twin numbers", () => {
    const src = readSource("mesa-candidates-panel.tsx");
    expect(src).toMatch(/<OpportunityScoreBars/);
    expect(src).not.toMatch(/Quality \{rankRow\.quality\}/);
    expect(src).not.toMatch(/Portfolio Fit \{rankRow\.suitability\}/);
  });

  it("panel labels the product result, not a score-as-BUY", () => {
    const src = readSource("mesa-candidates-panel.tsx");
    expect(src).toMatch(/opportunityResultLabel\(rankRow, entriesBlocked\)/);
    const buyLines = src.split("\n").filter((line) => /\bBUY\b/.test(line));
    expect(buyLines.every((line) => /≠\s*BUY/.test(line))).toBe(true);
  });

  it("funnel strip uses the Spanish steps plus three clocks", () => {
    const src = readSource("mesa-candidates-panel.tsx");
    expect(src).toMatch(/buildOpportunityFunnelSteps\(funnel\)/);
    expect(src).toMatch(/buildOpportunityFunnelClocks\(funnel\)/);
    expect(src).toMatch(/formatFunnelTitle\(/);
    expect(src).toMatch(/data-testid="mesa-funnel-clocks"/);
    expect(src).not.toMatch(/¿Por qué no aparecen más\?/);
  });

  it("drawer titles with Calidad and shows the result label", () => {
    const src = readSource("opportunity-drawer.tsx");
    expect(src).toMatch(/formatPriorityScore\(rankRow\.quality\)/);
    expect(src).toMatch(/PRIORITY_NOT_AN_ORDER/);
    expect(src).toMatch(/opportunityResultLabel\(rankRow, entriesBlocked\)/);
    expect(src).toMatch(/<OpportunityScoreBars/);
    expect(src).not.toMatch(/Opportunity \$\{rankRow\.quality\}/);
  });
});
