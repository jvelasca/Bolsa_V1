/**
 * V1.72 — DecisionExplainPanel layout TOP (score · LONG · factors).
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
    strength: 8.7,
    strengthBand: "strong",
    decisionSummary: "Ruptura con volumen sobre resistencia.",
    direction: "long",
    status: "target_active",
    action: "recommend_long",
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

describe("DecisionExplainPanel V1.72", () => {
  it("renders TOP layout: score, LONG, factors, no COMPRAR", () => {
    const view = buildDecisionExplainView({
      study: triggeredStudy(),
      gateStatus: "open",
      source: "daily_scan",
      markPrice: 425,
    });

    render(<DecisionExplainPanel view={view} />);

    expect(screen.getByTestId("decision-explain-panel")).toBeTruthy();
    expect(screen.getByTestId("decision-explain-score").textContent).toMatch(
      /NVDA · 8,7\/10/,
    );
    expect(screen.getByTestId("decision-explain-direction").textContent).toBe(
      "LONG",
    );
    expect(
      screen.getByTestId("decision-explain-direction").textContent,
    ).not.toMatch(/COMPRAR|BUY/i);
    expect(
      screen.getByTestId("decision-explain-factor-tendencia"),
    ).toBeTruthy();
    expect(
      screen
        .getByTestId("decision-explain-factor-momentum")
        .getAttribute("data-state"),
    ).toBe("unknown");
    expect(screen.getByTestId("decision-explain-entry-distance")).toBeTruthy();
    expect(
      screen.getByTestId("decision-explain-section-authorization"),
    ).toBeTruthy();
    expect(screen.getByText(/no es autorización/i)).toBeTruthy();
    expect(screen.queryByText(/Ideal/i)).toBeNull();
    expect(screen.queryByText(/Máxima/i)).toBeNull();
    expect(screen.getByTestId("decision-explain-section-thesis")).toBeTruthy();
    expect(screen.getAllByText("Alcista").length).toBeGreaterThan(0);
    expect(screen.getByText("Cierre bajo 408")).toBeTruthy();
  });

  it("omits distance when mark is missing", () => {
    const view = buildDecisionExplainView({
      study: triggeredStudy(),
    });
    render(<DecisionExplainPanel view={view} />);
    expect(screen.queryByTestId("decision-explain-entry-distance")).toBeNull();
  });

  it("shows fallback copy when view is empty", () => {
    render(<DecisionExplainPanel view={null} />);
    expect(screen.getByTestId("decision-explain-panel").textContent).toMatch(
      /Sin explicación disponible/i,
    );
  });
});
