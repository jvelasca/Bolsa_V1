import { describe, expect, it } from "vitest";
import { buildOpportunityRanking } from "@bolsa/shared";
import { mesaScreenersUniverseHref } from "@/features/mesa/mesa-candidates-panel";

describe("mesa opportunity discovery UI helpers", () => {
  it("screeners CTA deep-links listId", () => {
    expect(mesaScreenersUniverseHref("ibex35")).toContain("/screeners");
    expect(mesaScreenersUniverseHref("ibex35")).toContain("listId=ibex35");
  });

  it("ranking empty still exposes funnel denominator", () => {
    const ranking = buildOpportunityRanking({
      studies: [],
      universeCount: 35,
      screenedCount: 0,
      universeListId: "ibex35",
    });
    expect(ranking.funnel.universeCount).toBe(35);
    expect(ranking.funnel.screenedCount).toBe(0);
    expect(ranking.funnel.scanStale).toBe(true);
    expect(ranking.impliesOperable).toBe(false);
  });
});
