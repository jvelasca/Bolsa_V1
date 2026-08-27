import { describe, expect, it } from "vitest";
import type { TradePlanV1 } from "./cognitive/trade-plan.js";
import {
  NO_OPERATIONAL_PLAN_COPY,
  buildJournalStudyView,
  formatJournalStudyAge,
  journalStudyConsensusPercents,
  journalStudyGeometry,
  mapJournalStudyOpinion,
  mapJournalStudyPeriod,
  mapJournalStudyStatus,
  mapJournalStudyStrength,
  mapJournalStudyStrengthBand,
  mapJournalStudyVigencia,
} from "./cognitive/decision-journal-study.js";

function watchPlan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "dec-1",
    instrumentId: "inst-1",
    direction: "none",
    status: "WATCH",
    quantity: 0,
    riskPct: 0,
    whyNot: ["no_stop"],
    executionAllowed: false,
    entry: 12.23,
    structuralStop: 10,
    target1: 15.34,
    target2: 18,
    ...overrides,
  };
}

function triggeredPlan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "dec-1",
    instrumentId: "inst-1",
    direction: "long",
    status: "TRIGGERED",
    quantity: 10,
    riskPct: 1,
    whyNot: [],
    executionAllowed: true,
    entry: 150,
    structuralStop: 142.3,
    target1: 158.4,
    target2: 165.8,
    expectedRR: 1.8,
    riskAmount: 420,
    ...overrides,
  };
}

describe("journalStudyGeometry honesty", () => {
  it("WATCH never exposes SL/TP even if fields exist on the plan", () => {
    const geo = journalStudyGeometry(watchPlan());
    expect(geo.hasOperationalPlan).toBe(false);
    expect(geo.entry).toBeNull();
    expect(geo.stop).toBeNull();
    expect(geo.target1).toBeNull();
    expect(geo.target2).toBeNull();
    expect(geo.quantity).toBeNull();
    expect(geo.initialRiskR).toBeNull();
    expect(geo.positionValue).toBeNull();
    expect(NO_OPERATIONAL_PLAN_COPY).toMatch(/plan operativo/i);
  });

  it("missing plan → empty geometry", () => {
    expect(journalStudyGeometry(null).hasOperationalPlan).toBe(false);
  });

  it("TRIGGERED + valid stop exposes entry/SL/TP and TradePlan sizing", () => {
    const geo = journalStudyGeometry(
      triggeredPlan({
        quantity: 10,
        initialRiskR: 0.8,
        positionValue: 1500,
      }),
    );
    expect(geo.hasOperationalPlan).toBe(true);
    expect(geo.entry).toBe(150);
    expect(geo.stop).toBe(142.3);
    expect(geo.target1).toBe(158.4);
    expect(geo.target2).toBe(165.8);
    expect(geo.quantity).toBe(10);
    expect(geo.initialRiskR).toBe(0.8);
    expect(geo.positionValue).toBe(1500);
    expect(geo.direction).toBe("long");
  });

  it("ARMED + valid stop exposes geometry (thesis has a stop, not yet triggered)", () => {
    const geo = journalStudyGeometry(
      triggeredPlan({ status: "ARMED", quantity: 0, executionAllowed: false }),
    );
    expect(geo.hasOperationalPlan).toBe(true);
    expect(geo.stop).toBe(142.3);
  });

  it("TRIGGERED with no_stop hides geometry", () => {
    const geo = journalStudyGeometry(
      triggeredPlan({ whyNot: ["no_stop"], structuralStop: null }),
    );
    expect(geo.hasOperationalPlan).toBe(false);
    expect(geo.stop).toBeNull();
  });
});

describe("mapJournalStudyStatus precedence", () => {
  it("CLOSED position → closed", () => {
    expect(mapJournalStudyStatus({ positionStatus: "CLOSED" })).toBe("closed");
  });

  it("rejected proposal → cancelled (before WATCH)", () => {
    expect(
      mapJournalStudyStatus({
        proposalStatus: "rejected",
        tradePlanStatus: "WATCH",
        action: "wait",
      }),
    ).toBe("cancelled");
  });

  it("THESIS_INVALIDATION → invalidated", () => {
    expect(
      mapJournalStudyStatus({
        exitPrimaryReason: "THESIS_INVALIDATION",
        tradePlanStatus: "TRIGGERED",
        hasLivePlan: true,
      }),
    ).toBe("invalidated");
  });

  it("TARGET_1 → target_reached", () => {
    expect(
      mapJournalStudyStatus({
        exitPrimaryReason: "TARGET_1",
        tradePlanStatus: "TRIGGERED",
        hasOpenPosition: true,
      }),
    ).toBe("target_reached");
  });

  it("TRIGGERED + live plan → target_active", () => {
    expect(
      mapJournalStudyStatus({
        tradePlanStatus: "TRIGGERED",
        hasLivePlan: true,
        action: "recommend_long",
        bias: "bullish",
      }),
    ).toBe("target_active");
  });

  it("wait without operational plan → neutral", () => {
    expect(
      mapJournalStudyStatus({
        action: "wait",
        bias: "neutral",
        tradePlanStatus: "WATCH",
        tradePlanWhyNot: ["no_stop"],
        hasOperationalPlan: false,
      }),
    ).toBe("neutral");
  });

  it("WATCH + no_stop + directional → no_target", () => {
    expect(
      mapJournalStudyStatus({
        action: "recommend_long",
        bias: "bullish",
        tradePlanStatus: "WATCH",
        tradePlanWhyNot: ["no_stop"],
        hasOperationalPlan: false,
      }),
    ).toBe("no_target");
  });

  it("ARMED + directional → in_progress", () => {
    expect(
      mapJournalStudyStatus({
        action: "recommend_long",
        bias: "bullish",
        tradePlanStatus: "ARMED",
        hasOperationalPlan: true,
      }),
    ).toBe("in_progress");
  });

  it("WATCH + directional + stop (no no_stop) → in_progress", () => {
    expect(
      mapJournalStudyStatus({
        action: "recommend_long",
        bias: "bullish",
        tradePlanStatus: "WATCH",
        tradePlanWhyNot: ["entry"],
        hasOperationalPlan: false,
      }),
    ).toBe("in_progress");
  });
});

describe("opinion / period / strength / vigencia", () => {
  it("prefers TA bias over action", () => {
    expect(
      mapJournalStudyOpinion({ bias: "bearish", action: "recommend_long" }),
    ).toBe("bearish");
  });

  it("maps action when bias is missing", () => {
    expect(mapJournalStudyOpinion({ action: "recommend_long" })).toBe(
      "bullish",
    );
    expect(mapJournalStudyOpinion({ action: "wait" })).toBe("neutral");
  });

  it("maps timeframe 1d/1wk/1mo and refuses horizon labels", () => {
    expect(mapJournalStudyPeriod("1d")).toBe("daily");
    expect(mapJournalStudyPeriod("1wk")).toBe("weekly");
    expect(mapJournalStudyPeriod("1mo")).toBe("monthly");
    expect(mapJournalStudyPeriod("swing")).toBeNull();
    expect(mapJournalStudyPeriod("intraday")).toBeNull();
  });

  it("strength 0–1 → 0–10 and bands", () => {
    expect(mapJournalStudyStrength(0.82)).toBe(8.2);
    expect(mapJournalStudyStrengthBand(8.2)).toBe("very_strong");
    expect(mapJournalStudyStrengthBand(6)).toBe("strong");
    expect(mapJournalStudyStrengthBand(4)).toBe("moderate");
    expect(mapJournalStudyStrengthBand(2)).toBe("weak");
    expect(mapJournalStudyStrengthBand(0.4)).toBe("very_weak");
  });

  it("vigencia from expiresAt only (no invent)", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    expect(mapJournalStudyVigencia({ now, expiresAt: null })).toBeNull();
    expect(
      mapJournalStudyVigencia({ now, expiresAt: "2026-08-25T12:00:00Z" }),
    ).toBe("expired");
    expect(
      mapJournalStudyVigencia({ now, expiresAt: "2026-08-26T20:00:00Z" }),
    ).toBe("expiring_soon");
    expect(
      mapJournalStudyVigencia({ now, expiresAt: "2026-09-01T12:00:00Z" }),
    ).toBe("current");
  });

  it("formats age", () => {
    expect(formatJournalStudyAge(2 * 3600_000)).toBe("2h");
    expect(formatJournalStudyAge(8 * 24 * 3600_000)).toBe("8 días");
  });
});

describe("buildJournalStudyView", () => {
  it("WATCH study hides levels and keeps userThesis null", () => {
    const view = buildJournalStudyView({
      sessionId: "s1",
      decisionId: "d1",
      instrumentId: "inst-1",
      symbol: "AAPL",
      name: "Apple Inc.",
      studiedAt: "2026-08-26T09:32:00Z",
      now: "2026-08-26T11:32:00Z",
      timeframe: "1d",
      action: "wait",
      bias: "neutral",
      overallConfidence: 0.61,
      tradePlan: watchPlan(),
      notes: ["Sin ventaja suficiente en el rango actual."],
    });
    expect(view.hasOperationalPlan).toBe(false);
    expect(view.stop).toBeNull();
    expect(view.target1).toBeNull();
    expect(view.entry).toBeNull();
    expect(view.userThesis).toBeNull();
    expect(view.status).toBe("neutral");
    expect(view.opinion).toBe("neutral");
    expect(view.period).toBe("daily");
    expect(view.strength).toBe(6.1);
    expect(view.ageMs).toBe(2 * 3600_000);
  });

  it("TRIGGERED study exposes geometry and invalidation from stop", () => {
    const view = buildJournalStudyView({
      sessionId: "s2",
      instrumentId: "inst-1",
      studiedAt: "2026-08-26T09:32:00Z",
      now: "2026-08-26T09:32:00Z",
      timeframe: "1d",
      action: "recommend_long",
      bias: "bullish",
      overallConfidence: 0.82,
      tradePlan: triggeredPlan(),
      hasOpenPosition: true,
      assessments: [
        { metadata: { bias: "bullish" } },
        { bias: "bullish" },
        { bias: "neutral" },
      ],
      facts: [
        {
          key: "trend.primary",
          value: "strong_bullish",
          refs: { adx: "28", plus_di: "22" },
        },
        {
          key: "structure.sma",
          value: "bullish_stack",
          refs: { sma_20: "1", sma_50: "1" },
        },
        { key: "momentum", value: "strong", refs: { rsi: "62" } },
      ],
      invalidators: ["exhaustion"],
    });
    expect(view.hasOperationalPlan).toBe(true);
    expect(view.status).toBe("target_active");
    expect(view.stop).toBe(142.3);
    expect(view.target1).toBe(158.4);
    expect(view.invalidation.some((line) => line.startsWith("Cierre <"))).toBe(
      true,
    );
    expect(view.invalidation).toContain("Agotamiento del movimiento");
    expect(view.indicators.primary).toContain("ADX");
    expect(view.indicators.confirmation).toContain("RSI");
    expect(view.trends).toHaveLength(2);
    const pct = journalStudyConsensusPercents(view.consensus);
    expect(view.consensus.total).toBe(3);
    expect(pct.bullish).toBe(67);
    expect(pct.neutral).toBe(33);
  });

  it("does not invent SuperTrend, MACD, entry range or user thesis", () => {
    const view = buildJournalStudyView({
      sessionId: "s3",
      instrumentId: "inst-1",
      studiedAt: "2026-08-26T09:32:00Z",
      now: "2026-08-26T09:32:00Z",
      action: "recommend_long",
      bias: "bullish",
      tradePlan: triggeredPlan(),
    });
    const blob = JSON.stringify(view);
    expect(blob.toLowerCase()).not.toContain("supertrend");
    expect(blob.toLowerCase()).not.toContain("macd");
    expect(view.userThesis).toBeNull();
    expect(view.entry).toBe(150);
  });
});
