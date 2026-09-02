/**
 * V1.66 — DecisionExplainPanel render básico.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { buildDecisionExplainView } from "@bolsa/shared";
import { DecisionExplainPanel } from "@/features/trading/decision-explain-panel";

afterEach(() => cleanup());

function triggeredStudy(): DecisionJournalStudyViewV1 {
  return {
    instrumentId: "inst-nvda",
    symbol: "NVDA",
    hasOperationalPlan: true,
    tradePlanStatus: "TRIGGERED",
    studiedAt: "2026-08-31T09:00:00.000Z",
    opinion: "bullish",
    strengthBand: "strong",
    decisionSummary: "Ruptura con volumen sobre resistencia.",
    direction: "long",
    status: "target_active",
    entry: 421.5,
    stop: 408,
    target1: 448,
    target2: 470,
    expectedRR: 2,
    riskAmount: 250,
    initialRiskR: 1,
    positionValue: 4215,
    quantity: 10,
    invalidation: ["Cierre bajo 408"],
    trends: [
      {
        key: "short_term",
        label: "Corto plazo",
        value: "strong_bullish",
        display: "Fuertemente alcista",
      },
    ],
    consensus: { bullish: 3, bearish: 0, neutral: 1, total: 4 },
    indicators: { primary: "ADX + DI", confirmation: "RSI" },
  } as DecisionJournalStudyViewV1;
}

describe("DecisionExplainPanel V1.66", () => {
  it("renders canonical sections from explain view", () => {
    const view = buildDecisionExplainView({
      study: triggeredStudy(),
      gateStatus: "open",
      source: "daily_scan",
    });

    render(<DecisionExplainPanel view={view} />);

    expect(screen.getByTestId("decision-explain-panel")).toBeTruthy();
    expect(screen.getByTestId("decision-explain-section-thesis")).toBeTruthy();
    expect(screen.getByTestId("decision-explain-section-signals")).toBeTruthy();
    expect(
      screen.getByTestId("decision-explain-section-conditions"),
    ).toBeTruthy();
    expect(
      screen.getByTestId("decision-explain-section-invalidators"),
    ).toBeTruthy();
    expect(screen.getByTestId("decision-explain-section-policy")).toBeTruthy();
    expect(
      screen.getByTestId("decision-explain-section-traceability"),
    ).toBeTruthy();
    expect(screen.getByText("Alcista")).toBeTruthy();
    expect(screen.getByText("Cierre bajo 408")).toBeTruthy();
    expect(screen.getByText("open")).toBeTruthy();
  });

  it("shows fallback copy when view is empty", () => {
    render(<DecisionExplainPanel view={null} />);
    expect(screen.getByTestId("decision-explain-panel").textContent).toMatch(
      /Sin explicación disponible/i,
    );
  });
});
