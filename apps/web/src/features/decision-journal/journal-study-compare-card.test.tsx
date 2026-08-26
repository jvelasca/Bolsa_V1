import { describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { mapJournalStudyDelta } from "@bolsa/shared";
import { JournalStudyCompareCard } from "@/features/decision-journal/journal-study-compare-card";
import { render, screen } from "@testing-library/react";

function study(
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
    studiedAt: "2026-08-26T09:32:00Z",
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
    hasOperationalPlan: false,
    userThesis: null,
    decisionSummary: null,
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

describe("JournalStudyCompareCard", () => {
  it("shows first thesis copy when no previous snapshot", () => {
    render(<JournalStudyCompareCard prev={null} next={study()} />);
    expect(screen.getByTestId("journal-study-compare").textContent).toMatch(
      /Primera tesis registrada/i,
    );
  });

  it("shows opinion change rows", () => {
    const prev = study({ sessionId: "s-old", opinion: "neutral" });
    const next = study({ sessionId: "s-new", opinion: "bullish" });
    render(<JournalStudyCompareCard prev={prev} next={next} />);
    const delta = mapJournalStudyDelta(prev, next);
    expect(delta.fields.some((f) => f.label === "Opinión")).toBe(true);
    expect(screen.getByText(/Neutra → Alcista/i)).toBeTruthy();
  });
});
