/**
 * V1.72 — DecisionExplainPanel layout TOP (score · LONG · factors).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { buildDecisionExplainView } from "@bolsa/shared";
import { DecisionExplainPanel } from "@/features/trading/decision-explain-panel";
import { stubNarrowViewport, stubWideViewport } from "@/lib/test-viewport";

afterEach(() => cleanup());

function triggeredStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
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
    ...overrides,
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

  it("V2.47 — sin economía medida NO aparece la sección (ni un 0 €)", () => {
    const view = buildDecisionExplainView({ study: triggeredStudy() });
    render(<DecisionExplainPanel view={view} />);
    expect(
      screen.queryByTestId("decision-explain-section-expected-value"),
    ).toBeNull();
  });

  it("V2.47 — economía medida se publica con signo y moneda", () => {
    const view = buildDecisionExplainView({
      study: triggeredStudy({ expectedR: 0.8, netExpectedCurrency: 34 }),
    });
    render(<DecisionExplainPanel view={view} />);
    expect(
      screen.getByTestId("decision-explain-section-expected-value"),
    ).toBeTruthy();
    expect(
      screen.getByTestId("decision-explain-expected-currency").textContent,
    ).toBe("+34.00 €");
    expect(screen.getByTestId("decision-explain-expected-r").textContent).toBe(
      "0.80",
    );
  });

  it("V2.47 — una pérdida esperada se pinta con signo negativo (no como ganancia)", () => {
    const view = buildDecisionExplainView({
      study: triggeredStudy({ expectedR: -0.25, netExpectedCurrency: -12.5 }),
    });
    render(<DecisionExplainPanel view={view} />);
    expect(
      screen.getByTestId("decision-explain-expected-currency").textContent,
    ).toBe("−12.50 €");
  });

  it("shows fallback copy when view is empty", () => {
    render(<DecisionExplainPanel view={null} />);
    expect(screen.getByTestId("decision-explain-panel").textContent).toMatch(
      /Sin explicación disponible/i,
    );
  });
});

describe("DecisionExplainPanel V2.47 — móvil", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("en teléfono declara el ancho y apila filas y factores (sin perder secciones)", () => {
    stubNarrowViewport();
    const view = buildDecisionExplainView({
      study: triggeredStudy({ expectedR: 0.8, netExpectedCurrency: 34 }),
    });
    render(<DecisionExplainPanel view={view} />);

    const root = screen.getByTestId("decision-explain-panel");
    expect(root.getAttribute("data-cabin-width")).toBe("narrow");

    const expectedRow = screen.getByTestId(
      "decision-explain-expected-currency",
    ).parentElement!;
    expect(expectedRow.className).toMatch(/flex-col/);
    expect(expectedRow.className).not.toMatch(/justify-between/);

    // Las secciones siguen todas presentes (regla 2: nada se elimina en estrecho).
    for (const section of [
      "decision-explain-section-decision",
      "decision-explain-section-why",
      "decision-explain-section-entry",
      "decision-explain-section-expected-value",
      "decision-explain-section-authorization",
    ]) {
      expect(screen.getByTestId(section)).toBeTruthy();
    }
  });

  it("en escritorio conserva fila a dos extremos y ancho declarado", () => {
    stubWideViewport();
    const view = buildDecisionExplainView({
      study: triggeredStudy({ expectedR: 0.8, netExpectedCurrency: 34 }),
    });
    render(<DecisionExplainPanel view={view} />);
    expect(
      screen
        .getByTestId("decision-explain-panel")
        .getAttribute("data-cabin-width"),
    ).toBe("wide");
    expect(
      screen.getByTestId("decision-explain-expected-currency").parentElement!
        .className,
    ).toMatch(/justify-between/);
  });
});
