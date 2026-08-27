import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { NO_OPERATIONAL_PLAN_COPY } from "@bolsa/shared";

const createPriceLine = vi.fn(() => ({}));

vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({
      setData: vi.fn(),
      createPriceLine,
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

vi.mock("@/lib/api", () => ({
  api: {
    getOhlcv: vi.fn().mockResolvedValue({
      data: [
        {
          timestamp: "2026-08-25",
          open: 150,
          high: 152,
          low: 149,
          close: 151,
          volume: 1,
        },
      ],
      meta: { timeframe: "1d", count: 1 },
    }),
  },
}));

import { DecisionStudyChart } from "@/features/decision-journal/decision-study-chart";

function makeStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "ART-DECISION-JOURNAL-STUDY",
    schemaVersion: "1.0.0",
    sessionId: "s-watch",
    decisionId: "d1",
    instrumentId: "inst-1",
    symbol: "AAPL",
    name: "Apple Inc.",
    studiedAt: "2026-08-26T09:32:00Z",
    ageMs: 7200000,
    period: "daily",
    timeframe: "1d",
    opinion: "neutral",
    status: "neutral",
    strength: 6.1,
    strengthBand: "strong",
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
    decisionSummary: "Sin ventaja suficiente.",
    analysisNotes: [],
    trends: [],
    consensus: { bullish: 0, bearish: 0, neutral: 1, total: 1 },
    indicators: { primary: "ADX + DI", confirmation: "RSI + SMA" },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: "WATCH",
    action: "wait",
    ...overrides,
  };
}

function renderChart(study: DecisionJournalStudyViewV1) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DecisionStudyChart study={study} />
    </QueryClientProvider>,
  );
}

describe("DecisionStudyChart honesty", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
        unobserve() {}
      },
    );
    createPriceLine.mockClear();
  });

  afterEach(() => cleanup());

  it("WATCH / sin plan: cero priceLines y copy de no-plan", async () => {
    const { getByTestId } = renderChart(makeStudy());
    await waitFor(() =>
      expect(getByTestId("no-operational-plan").textContent).toBe(
        NO_OPERATIONAL_PLAN_COPY,
      ),
    );
    expect(createPriceLine).not.toHaveBeenCalled();
  });

  it("plan operativo: priceLines de entrada / SL / TP1", async () => {
    renderChart(
      makeStudy({
        sessionId: "s-armed",
        hasOperationalPlan: true,
        tradePlanStatus: "ARMED",
        action: "recommend_long",
        opinion: "bullish",
        status: "in_progress",
        entry: 150,
        stop: 142.3,
        target1: 158.4,
        target2: 165.8,
      }),
    );
    await waitFor(() => expect(createPriceLine.mock.calls.length).toBe(4));
    const titles = createPriceLine.mock.calls.map(
      (call) => (call[0] as { title?: string }).title,
    );
    expect(titles).toEqual(["Entrada", "SL ↓", "TP1 ↑", "TP2"]);
  });
});
