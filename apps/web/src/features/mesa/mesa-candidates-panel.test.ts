import { describe, expect, it } from "vitest";
import { buildOpportunityRanking, ESTUDIO_LIST_ID } from "@bolsa/shared";
import {
  DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
  mesaScreenersUniverseHref,
} from "@/features/mesa/mesa-candidates-panel";

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
});
