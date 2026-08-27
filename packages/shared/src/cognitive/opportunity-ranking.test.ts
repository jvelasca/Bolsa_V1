import { describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { DecisionBoardV1 } from "../decision-board.js";
import {
  buildOpportunityRanking,
  OPPORTUNITY_HIGH_QUALITY_THRESHOLD,
  opportunityQualityBandCounts,
} from "./opportunity-ranking.js";
import { projectOpportunityEvidence } from "./opportunity-evidence.js";
import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";

function study(
  partial: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    sessionId: "s1",
    instrumentId: "i1",
    symbol: "SAN",
    studiedAt: "2026-08-27T10:00:00Z",
    status: "active",
    strength: 9,
    hasOperationalPlan: true,
    expectedRR: 2.5,
    tradePlanStatus: "TRIGGERED",
    vigencia: "current",
    invalidation: [],
    ...partial,
  } as DecisionJournalStudyViewV1;
}

describe("opportunity-ranking", () => {
  it("does not use Action Queue — empty board still ranks studies", () => {
    const ranking = buildOpportunityRanking({
      studies: [
        study({
          symbol: "SAN",
          instrumentId: "i-san",
          strength: 9,
          expectedRR: 3,
        }),
        study({
          symbol: "BBVA",
          instrumentId: "i-bbva",
          sessionId: "s2",
          strength: 8,
          expectedRR: 2,
        }),
      ],
      screenedCount: 35,
      hitCount: 5,
      universeCount: 35,
      universeListId: "ibex35",
      scanUpdatedAt: "2026-08-27T09:00:00Z",
      scanHits: [
        { instrumentId: "i-san", symbol: "SAN" },
        { instrumentId: "i-bbva", symbol: "BBVA" },
        { instrumentId: "i-tef", symbol: "TEF" },
      ],
      now: new Date("2026-08-27T12:00:00Z"),
      priorityCtx: { entriesBlocked: false },
    });

    expect(ranking.impliesOperable).toBe(false);
    expect(ranking.provisional).toBe(true);
    expect(ranking.funnel.universeCount).toBe(35);
    expect(ranking.funnel.screenedCount).toBe(35);
    expect(ranking.funnel.hitCount).toBe(5);
    expect(ranking.funnel.analyzedCount).toBeGreaterThanOrEqual(2);
    expect(ranking.funnel.scanStale).toBe(false);
    // TEF hit without study still appears
    expect(ranking.all.some((r) => r.symbol === "TEF")).toBe(true);
  });

  it("funnel shows screening 0 when no scan — does not invent universe depth", () => {
    const ranking = buildOpportunityRanking({
      studies: [study()],
      universeCount: 35,
      universeListId: "ibex35",
      screenedCount: 0,
      now: new Date("2026-08-27T12:00:00Z"),
    });
    expect(ranking.funnel.screenedCount).toBe(0);
    expect(ranking.funnel.scanStale).toBe(true);
    expect(ranking.funnel.asOf).toBeNull();
    expect(ranking.funnel.rankingAsOf).toBeNull();
  });

  it("funnel.asOf is scan time — never wall-clock when scan missing", () => {
    const ranking = buildOpportunityRanking({
      studies: [study()],
      universeCount: 10,
      screenedCount: 0,
      scanUpdatedAt: null,
      now: new Date("2026-08-27T12:00:00Z"),
    });
    expect(ranking.funnel.asOf).toBeNull();
    expect(ranking.funnel.analysisAsOf).toBe("2026-08-27T10:00:00Z");
  });

  it("funnel.asOf equals scanUpdatedAt when scan present", () => {
    const ranking = buildOpportunityRanking({
      studies: [study()],
      universeCount: 10,
      screenedCount: 10,
      scanUpdatedAt: "2026-08-27T08:31:00Z",
      marketDataAsOf: "2026-08-27T00:00:00Z",
      now: new Date("2026-08-27T12:00:00Z"),
    });
    expect(ranking.funnel.asOf).toBe("2026-08-27T08:31:00Z");
    expect(ranking.funnel.rankingAsOf).toBe("2026-08-27T08:31:00Z");
    expect(ranking.funnel.marketDataAsOf).toBe("2026-08-27T00:00:00Z");
  });

  it("categorizes NOT_FOR_PORTFOLIO when quality high and suitability low", () => {
    const ranking = buildOpportunityRanking({
      studies: [
        study({
          symbol: "TSLA",
          instrumentId: "i-tsla",
          strength: 9.5,
          expectedRR: 3,
          hasOperationalPlan: true,
          tradePlanStatus: "TRIGGERED",
        }),
      ],
      board: {
        accountId: "a1",
        generatedAt: "2026-08-27T12:00:00Z",
        buckets: {
          pendingConfirm: 0,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
          total: 0,
        },
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s1",
            kind: "propose",
            status: "open",
            instrumentId: "i-tsla",
            symbol: "TSLA",
            createdAt: "2026-08-27T10:00:00Z",
            gate: "PASS",
            tradePlan: {
              status: "TRIGGERED",
              hasOperationalPlan: true,
            } as never,
          },
        ],
      } as DecisionBoardV1,
      screenedCount: 35,
      universeCount: 35,
      scanUpdatedAt: "2026-08-27T09:00:00Z",
      now: new Date("2026-08-27T12:00:00Z"),
      priorityCtx: {
        entriesBlocked: false,
        candidateSector: "Consumer Cyclical",
        sectorExposurePct: { "Consumer Cyclical": 45 },
        maxSectorExposurePct: 40,
        portfolioRisk: {
          portfolioPnLR: 0,
          portfolioOpenRiskR: 1,
          portfolioStressRiskR: null,
          portfolioRiskLimitR: 5,
        },
      },
    });

    const tsla = ranking.all.find((r) => r.symbol === "TSLA");
    expect(tsla?.category).toBe("NOT_FOR_PORTFOLIO");
    expect(tsla?.quality).toBeGreaterThanOrEqual(70);
  });

  it("categorizes STALE when analysis is old but quality/fit ok", () => {
    const ranking = buildOpportunityRanking({
      studies: [
        study({
          symbol: "AMZN",
          instrumentId: "i-amzn",
          studiedAt: "2026-08-01T10:00:00Z",
          vigencia: "expired",
          strength: 9,
          expectedRR: 2.5,
          hasOperationalPlan: true,
          tradePlanStatus: "TRIGGERED",
        }),
      ],
      screenedCount: 35,
      universeCount: 35,
      scanUpdatedAt: "2026-08-27T09:00:00Z",
      now: new Date("2026-08-27T12:00:00Z"),
      priorityCtx: {
        entriesBlocked: false,
        portfolioRisk: {
          portfolioPnLR: 0,
          portfolioOpenRiskR: 1,
          portfolioStressRiskR: null,
          portfolioRiskLimitR: 5,
        },
      },
    });
    const amzn = ranking.all.find((r) => r.symbol === "AMZN");
    expect(amzn?.category).toBe("STALE");
  });

  it("TOP surface is at most 5 and impliesOperable is false", () => {
    const studies = Array.from({ length: 8 }, (_, i) =>
      study({
        sessionId: `s${i}`,
        instrumentId: `i${i}`,
        symbol: `S${i}`,
        strength: 9,
        expectedRR: 3,
        hasOperationalPlan: true,
        tradePlanStatus: "TRIGGERED",
      }),
    );
    const ranking = buildOpportunityRanking({
      studies,
      screenedCount: 35,
      universeCount: 35,
      scanUpdatedAt: "2026-08-27T09:00:00Z",
      now: new Date("2026-08-27T12:00:00Z"),
      priorityCtx: { entriesBlocked: false },
    });
    expect(ranking.top.length).toBeLessThanOrEqual(5);
    expect(ranking.impliesOperable).toBe(false);
    expect(ranking.highQualityThreshold).toBe(
      OPPORTUNITY_HIGH_QUALITY_THRESHOLD,
    );
  });

  it("quality bands cover Excelente…No atractiva", () => {
    const row = (strength: number, rr: number): MesaCandidateRowV1 => ({
      symbol: "X",
      status: "WATCH",
      statusLabel: "Vigilar",
      gate: "PASS",
      instrumentId: "ix",
      study: study({ strength, expectedRR: rr }),
    });
    expect(projectOpportunityEvidence(row(10, 4)).qualityValue).toBe(100);
    expect(projectOpportunityEvidence(row(10, 4)).label).toBe("Excelente");
    // 9.5*6 + 2.5*10 = 57+25 = 82 → Alta
    expect(
      projectOpportunityEvidence(row(9.5, 2.5)).qualityValue,
    ).toBeGreaterThanOrEqual(80);
    expect(projectOpportunityEvidence(row(9.5, 2.5)).label).toBe("Alta");
    const bands = opportunityQualityBandCounts([
      { quality: 95 },
      { quality: 85 },
      { quality: 75 },
      { quality: 65 },
      { quality: 40 },
    ]);
    expect(bands.Excelente).toBe(1);
    expect(bands.Alta).toBe(1);
    expect(bands.Buena).toBe(1);
    expect(bands.Débil).toBe(1);
    expect(bands["No atractiva"]).toBe(1);
  });

  it("Quality no longer includes TRIGGERED/plan bonuses via Priority", async () => {
    const { computeOperationalPriority } =
      await import("./operational-priority.js");
    const withTrigger = computeOperationalPriority({
      symbol: "AAA",
      status: "TRIGGERED",
      statusLabel: "Listo",
      gate: "PASS",
      instrumentId: "i1",
      study: study({
        strength: 8,
        expectedRR: 2,
        hasOperationalPlan: true,
        tradePlanStatus: "TRIGGERED",
      }),
    });
    const watch = computeOperationalPriority({
      symbol: "AAA",
      status: "WATCH",
      statusLabel: "Vigilar",
      gate: "PASS",
      instrumentId: "i1",
      study: study({
        strength: 8,
        expectedRR: 2,
        hasOperationalPlan: false,
        tradePlanStatus: "WATCH",
      }),
    });
    expect(withTrigger.quality.value).toBe(watch.quality.value);
    expect(
      withTrigger.quality.factors.some((f) =>
        /trigger|plan operativo/i.test(f),
      ),
    ).toBe(false);
  });

  it("DAILY-OPS-UNIVERSE-001 — only Estudio members enter operable ranking", () => {
    const ranking = buildOpportunityRanking({
      studies: [
        study({
          symbol: "AAPL",
          instrumentId: "i-aapl",
          sessionId: "s-a",
          strength: 9,
          expectedRR: 3,
        }),
        study({
          symbol: "MSFT",
          instrumentId: "i-msft",
          sessionId: "s-m",
          strength: 8,
          expectedRR: 2,
        }),
        study({
          symbol: "OUT",
          instrumentId: "i-out",
          sessionId: "s-o",
          strength: 9.5,
          expectedRR: 4,
        }),
      ],
      scanHits: [
        { instrumentId: "i-aapl", symbol: "AAPL" },
        { instrumentId: "i-out", symbol: "OUT" },
        { instrumentId: "i-disc", symbol: "DISC" },
      ],
      screenedCount: 3,
      hitCount: 3,
      universeCount: 2,
      universeListId: "estudio",
      estudioInstrumentIds: ["i-aapl", "i-msft"],
      scanUpdatedAt: "2026-08-27T09:00:00Z",
      now: new Date("2026-08-27T12:00:00Z"),
      priorityCtx: { entriesBlocked: false },
    });

    expect(
      ranking.all.every(
        (r) => r.instrumentId === "i-aapl" || r.instrumentId === "i-msft",
      ),
    ).toBe(true);
    expect(ranking.all.some((r) => r.symbol === "OUT")).toBe(false);
    expect(
      ranking.top.every(
        (r) => r.instrumentId === "i-aapl" || r.instrumentId === "i-msft",
      ),
    ).toBe(true);
    expect(ranking.funnel.universeListId).toBe("estudio");
    expect(ranking.funnel.universeCount).toBe(2);
    expect(ranking.discovered.some((r) => r.symbol === "OUT")).toBe(true);
  });

  it("DAILY-OPS-UNIVERSE-002 / OP-07 — outside Estudio → discovered, never TOP BUY", () => {
    const ranking = buildOpportunityRanking({
      studies: [
        study({
          symbol: "OUT",
          instrumentId: "i-out",
          strength: 9.9,
          expectedRR: 5,
          hasOperationalPlan: true,
          tradePlanStatus: "TRIGGERED",
        }),
      ],
      scanHits: [{ instrumentId: "i-disc", symbol: "DISC" }],
      screenedCount: 10,
      universeCount: 0,
      universeListId: "estudio",
      estudioInstrumentIds: [],
      scanUpdatedAt: "2026-08-27T09:00:00Z",
      now: new Date("2026-08-27T12:00:00Z"),
      priorityCtx: { entriesBlocked: false },
    });

    expect(ranking.all).toHaveLength(0);
    expect(ranking.top).toHaveLength(0);
    expect(ranking.discovered.length).toBeGreaterThanOrEqual(1);
    expect(
      ranking.discovered.every((r) =>
        Boolean(r.categoryReason?.includes("fuera de Estudio")),
      ),
    ).toBe(true);
    expect(ranking.impliesOperable).toBe(false);
  });
});
