/**
 * V2.27 — DecisionFichaPanel spine + RESULTADO render smoke.
 */
import { describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { DecisionFichaPanel } from "./decision-ficha-panel";

vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({
      setData: vi.fn(),
      createPriceLine: vi.fn(() => ({})),
      removePriceLine: vi.fn(),
    }),
    applyOptions: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove: vi.fn(),
  }),
  ColorType: { Solid: "solid" },
  LineStyle: { Solid: 0, Dashed: 2 },
  CandlestickSeries: "Candlestick",
}));

vi.mock("@/features/decision-journal/decision-study-chart", () => ({
  DecisionStudyChart: () => <div data-testid="mock-study-chart" />,
}));

function study(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "ART-DECISION-JOURNAL-STUDY",
    schemaVersion: "1.0.0",
    sessionId: "sess-spine",
    decisionId: "dec-spine",
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    name: "Apple",
    studiedAt: "2026-09-02T08:00:00.000Z",
    ageMs: 0,
    period: "daily",
    timeframe: "1d",
    opinion: "bullish",
    status: "closed",
    strength: 7,
    strengthBand: "strong",
    vigencia: "current",
    entry: 184.2,
    stop: 176.8,
    target1: 195,
    target2: 205,
    expectedRR: 1.5,
    riskAmount: 400,
    quantity: 62,
    initialRiskR: 1,
    positionValue: 11420,
    direction: "long",
    hasOperationalPlan: true,
    userThesis: null,
    decisionSummary: "Tendencia alcista",
    analysisNotes: ["Tendencia alcista"],
    trends: [],
    consensus: { bullish: 1, bearish: 0, neutral: 0, total: 1 },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: "TRIGGERED",
    action: "buy",
    mfeMae: {
      status: "favorable",
      mfeR: 1.8,
      maeR: 0.2,
      currentR: 0.9,
      why: ["peak_from_bars", "mfe_ge_1_5r"],
      source: "bars",
    },
    learningVerdict: "hit",
    ...overrides,
  };
}

describe("DecisionFichaPanel V2.27 spine + RESULTADO", () => {
  it("renders journal-spine and journal-mfe-mae on closed ficha", () => {
    render(
      <DecisionFichaPanel
        study={study()}
        onClose={() => undefined}
        onCollapse={() => undefined}
      />,
    );

    expect(screen.getByTestId("journal-spine")).toBeTruthy();
    expect(screen.getByTestId("journal-spine-step-tesis")).toBeTruthy();
    expect(screen.getByTestId("journal-spine-step-resultado")).toBeTruthy();
    expect(screen.getByTestId("journal-result-metrics")).toBeTruthy();
    expect(screen.getByTestId("journal-mfe-mae-mfe").textContent).toMatch(
      /\+1\.8R/,
    );
    expect(screen.getByTestId("journal-mfe-mae-mae").textContent).toMatch(
      /0\.2R/,
    );
    expect(screen.getByTestId("journal-initial-risk-r").textContent).toMatch(
      /1R/,
    );
    expect(screen.getByTestId("journal-final-r").textContent).toBe("—");
    expect(screen.getByTestId("journal-learning-verdict").textContent).toMatch(
      /Acierto/,
    );
    expect(screen.getByTestId("ficha-trade-story")).toBeTruthy();

    cleanup();
  });
});
