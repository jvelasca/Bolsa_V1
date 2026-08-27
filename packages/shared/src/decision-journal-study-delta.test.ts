import { describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "./cognitive/decision-journal-study.js";
import {
  EMPTY_DELTA_COPY,
  FIRST_THESIS_COPY,
  buildJournalStudySparklinePath,
  buildJournalStudySparklinePoints,
  mapJournalStudyDelta,
} from "./cognitive/decision-journal-study-delta.js";

function baseStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "ART-DECISION-JOURNAL-STUDY",
    schemaVersion: "1.0.0",
    sessionId: "s1",
    decisionId: "d1",
    instrumentId: "inst-1",
    symbol: "AAPL",
    name: "Apple",
    studiedAt: "2026-08-24T09:00:00Z",
    ageMs: 0,
    period: "daily",
    timeframe: "1d",
    opinion: "neutral",
    status: "neutral",
    strength: 5,
    strengthBand: "moderate",
    vigencia: null,
    entry: null,
    stop: null,
    target1: null,
    target2: null,
    expectedRR: null,
    riskAmount: null,
    quantity: null,
    initialRiskR: null,
    positionValue: null,
    direction: null,
    hasOperationalPlan: false,
    userThesis: null,
    decisionSummary: "Wait",
    analysisNotes: [],
    trends: [],
    consensus: { bullish: 0, bearish: 0, neutral: 1, total: 1 },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: "WATCH",
    action: "wait",
    ...overrides,
  };
}

describe("mapJournalStudyDelta", () => {
  it("first snapshot → Primera tesis registrada", () => {
    const delta = mapJournalStudyDelta(null, baseStudy());
    expect(delta.isFirst).toBe(true);
    expect(delta.summary).toBe(FIRST_THESIS_COPY);
    expect(delta.fields).toHaveLength(0);
  });

  it("empty diff when snapshots match", () => {
    const prev = baseStudy({ sessionId: "s-old" });
    const next = baseStudy({ sessionId: "s-new" });
    const delta = mapJournalStudyDelta(prev, next);
    expect(delta.isEmpty).toBe(true);
    expect(delta.summary).toBe(EMPTY_DELTA_COPY);
  });

  it("opinion flip appears in motor bucket", () => {
    const prev = baseStudy({ opinion: "neutral", sessionId: "s1" });
    const next = baseStudy({ opinion: "bullish", sessionId: "s2" });
    const delta = mapJournalStudyDelta(prev, next);
    expect(delta.fields.some((f) => f.label === "Opinión")).toBe(true);
    expect(delta.fields.find((f) => f.label === "Opinión")?.bucket).toBe(
      "motor",
    );
  });

  it("WATCH→ARMED does not fabricate SL/TP when no operational plan", () => {
    const prev = baseStudy({
      sessionId: "s1",
      tradePlanStatus: "WATCH",
      hasOperationalPlan: false,
      stop: null,
      target1: null,
    });
    const next = baseStudy({
      sessionId: "s2",
      tradePlanStatus: "ARMED",
      hasOperationalPlan: false,
      stop: null,
      target1: null,
    });
    const delta = mapJournalStudyDelta(prev, next);
    expect(delta.fields.some((f) => f.label === "Stop")).toBe(false);
    expect(delta.fields.some((f) => f.label === "Objetivo 1")).toBe(false);
  });

  it("geometry diff only when hasOperationalPlan", () => {
    const prev = baseStudy({
      sessionId: "s1",
      hasOperationalPlan: true,
      entry: 100,
      stop: 95,
      target1: 110,
      tradePlanStatus: "TRIGGERED",
    });
    const next = baseStudy({
      sessionId: "s2",
      hasOperationalPlan: true,
      entry: 102,
      stop: 96,
      target1: 112,
      tradePlanStatus: "TRIGGERED",
    });
    const delta = mapJournalStudyDelta(prev, next);
    expect(delta.fields.some((f) => f.label === "Stop")).toBe(true);
    expect(delta.fields.some((f) => f.label === "Objetivo 1")).toBe(true);
  });
});

describe("sparkline helpers", () => {
  it("orders points chronologically", () => {
    const points = buildJournalStudySparklinePoints([
      baseStudy({ studiedAt: "2026-08-26T09:00:00Z", strength: 8 }),
      baseStudy({ studiedAt: "2026-08-24T09:00:00Z", strength: 5 }),
    ]);
    expect(points[0]?.studiedAt).toBe("2026-08-24T09:00:00Z");
    expect(points[1]?.studiedAt).toBe("2026-08-26T09:00:00Z");
  });

  it("builds svg path for non-empty series", () => {
    const points = buildJournalStudySparklinePoints([
      baseStudy({ strength: 4 }),
      baseStudy({ strength: 8, studiedAt: "2026-08-26T09:00:00Z" }),
    ]);
    const { line, dots } = buildJournalStudySparklinePath(points, 120, 40);
    expect(line.startsWith("M")).toBe(true);
    expect(dots).toHaveLength(2);
  });
});
