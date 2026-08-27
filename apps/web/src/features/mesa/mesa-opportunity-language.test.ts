/**
 * Tests — lenguaje de producto del ranking (V1.23 Fase 4).
 * Prioridad ≠ BUY; el embudo habla castellano básico; sin scan → «—».
 */

import { describe, expect, it } from "vitest";
import { buildOpportunityRanking, ESTUDIO_LIST_ID } from "@bolsa/shared";
import type { OpportunityRankRowV1 } from "@bolsa/shared";
import {
  HOY_FUNNEL_STEP_LABELS,
  PRIORITY_NOT_AN_ORDER,
  buildOpportunityFunnelClocks,
  buildOpportunityFunnelSteps,
  buildOpportunityScoreBars,
  formatFunnelClock,
  formatFunnelTitle,
  formatPriorityScore,
  opportunityResultLabel,
} from "@/features/mesa/mesa-opportunity-language";

function rankRow(
  overrides: Partial<OpportunityRankRowV1> & {
    operable?: boolean;
  } = {},
): Pick<OpportunityRankRowV1, "category" | "operationalPriority"> {
  const { operable = true, category = "TOP" } = overrides;
  return {
    category,
    operationalPriority: {
      operability: { operable, blockReasons: [] },
    } as never,
  };
}

describe("ranking score language", () => {
  it("says Prioridad, never Opportunity nor BUY", () => {
    const label = formatPriorityScore(91);
    expect(label).toBe("Prioridad 91/100");
    expect(label).not.toMatch(/opportunity/i);
    expect(label).not.toMatch(/\bbuy\b/i);
    expect(PRIORITY_NOT_AN_ORDER).toBe("NO ES UNA ORDEN");
  });

  it("exposes Calidad / Encaje / Operabilidad as three bars", () => {
    const bars = buildOpportunityScoreBars({
      quality: 91,
      suitability: 60,
      operability: 20,
    });
    expect(bars.map((b) => b.label)).toEqual([
      "Calidad",
      "Encaje",
      "Operabilidad",
    ]);
    expect(bars.map((b) => b.value)).toEqual([91, 60, 20]);
  });
});

describe("opportunityResultLabel", () => {
  it("TOP + operable → PREPARADA", () => {
    expect(opportunityResultLabel(rankRow({ category: "TOP" }))).toBe(
      "PREPARADA",
    );
  });

  it("WATCH / STALE / NOT_FOR_PORTFOLIO → VIGILAR", () => {
    for (const category of ["WATCH", "STALE", "NOT_FOR_PORTFOLIO"] as const) {
      expect(opportunityResultLabel(rankRow({ category }))).toBe("VIGILAR");
    }
  });

  it("BLOCKED category, non-operable or blocked entries → BLOQUEADA", () => {
    expect(opportunityResultLabel(rankRow({ category: "BLOCKED" }))).toBe(
      "BLOQUEADA",
    );
    expect(opportunityResultLabel(rankRow({ operable: false }))).toBe(
      "BLOQUEADA",
    );
    expect(opportunityResultLabel(rankRow({ category: "TOP" }), true)).toBe(
      "BLOQUEADA",
    );
  });

  it("never labels a row as BUY", () => {
    for (const category of [
      "TOP",
      "WATCH",
      "STALE",
      "NOT_FOR_PORTFOLIO",
      "BLOCKED",
    ] as const) {
      expect(opportunityResultLabel(rankRow({ category }))).not.toMatch(
        /buy|comprar/i,
      );
    }
  });
});

describe("funnel language", () => {
  it("names the seven steps in basic Spanish", () => {
    expect([...HOY_FUNNEL_STEP_LABELS]).toEqual([
      "ESTUDIO",
      "FILTRADAS",
      "SEÑALES",
      "ANALIZADAS",
      "BUENAS OPORTUNIDADES",
      "ENCAJAN CARTERA",
      "OPERABLES",
    ]);
  });

  it("maps funnel counts onto the labelled steps", () => {
    const steps = buildOpportunityFunnelSteps({
      universeCount: 180,
      screenedCount: 120,
      hitCount: 40,
      analyzedCount: 12,
      setupCount: 6,
      portfolioFitCount: 3,
      operableCount: 1,
    });
    expect(steps.map((s) => [s.label, s.count])).toEqual([
      ["ESTUDIO", 180],
      ["FILTRADAS", 120],
      ["SEÑALES", 40],
      ["ANALIZADAS", 12],
      ["BUENAS OPORTUNIDADES", 6],
      ["ENCAJAN CARTERA", 3],
      ["OPERABLES", 1],
    ]);
    expect(steps.map((s) => s.label)).toEqual([...HOY_FUNNEL_STEP_LABELS]);
  });

  it("titles the explanation with the remaining count", () => {
    expect(formatFunnelTitle(2)).toBe("¿Por qué quedan sólo 2?");
  });

  it("shows three clocks and renders — when a clock is null", () => {
    const clocks = buildOpportunityFunnelClocks({
      marketDataAsOf: null,
      analysisAsOf: null,
      rankingAsOf: null,
    });
    expect(clocks.map((c) => c.label)).toEqual([
      "Datos de mercado",
      "Análisis",
      "Ranking",
    ]);
    expect(clocks.map((c) => c.value)).toEqual(["—", "—", "—"]);
  });

  it("never invents a clock for a missing scan", () => {
    const ranking = buildOpportunityRanking({
      studies: [],
      universeCount: 0,
      screenedCount: 0,
      universeListId: ESTUDIO_LIST_ID,
      estudioInstrumentIds: [],
    });
    expect(ranking.funnel.asOf).toBeNull();
    const clocks = buildOpportunityFunnelClocks(ranking.funnel);
    expect(clocks.every((c) => c.value === "—")).toBe(true);
  });

  it("formatFunnelClock tolerates null and garbage", () => {
    expect(formatFunnelClock(null)).toBe("—");
    expect(formatFunnelClock(undefined)).toBe("—");
    expect(formatFunnelClock("not-a-date")).toBe("—");
    expect(formatFunnelClock("2026-08-27T09:30:00.000Z")).not.toBe("—");
  });
});
