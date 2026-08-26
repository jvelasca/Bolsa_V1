import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type {
  DecisionJournalEntryV1,
  DecisionJournalStudyViewV1,
} from "@bolsa/shared";
import { NO_OPERATIONAL_PLAN_COPY } from "@bolsa/shared";

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

vi.mock("@/lib/api", () => ({
  api: {
    getDecisionJournal: vi.fn(),
    getDecisionStudies: vi.fn(),
    getLists: vi.fn(),
    getOhlcv: vi.fn(),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    account: { id: "acc1", name: "Demo" },
    effectiveAccountId: "acc1",
    isLoading: false,
    accounts: [],
  }),
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: (
    selector: (s: { openChartTab: () => string }) => unknown,
  ) => selector({ openChartTab: vi.fn(() => "tab-1") }),
}));

import { api } from "@/lib/api";
import { DecisionJournalPage } from "@/features/decision-journal/decision-journal-page";

let queryClient: QueryClient;

function renderPage() {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DecisionJournalPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeEntry(
  overrides: Partial<DecisionJournalEntryV1> = {},
): DecisionJournalEntryV1 {
  return {
    schemaVersion: "1.0.0",
    entryId: "e1",
    decisionId: "d1",
    sessionId: "s1",
    accountId: "acc1",
    instrumentId: "inst-1",
    eventType: "human_confirm",
    actor: "human",
    payload: { gate: "PASS" },
    createdAt: "2026-08-24T09:00:00Z",
    ...overrides,
  };
}

function makeJournalResponse(
  entries: DecisionJournalEntryV1[] = [makeEntry()],
) {
  return {
    data: {
      accountId: "acc1",
      entries,
      limit: 50,
      offset: 0,
      total: entries.length,
    },
  };
}

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
    hasOperationalPlan: false,
    userThesis: null,
    decisionSummary: "Sin ventaja suficiente.",
    analysisNotes: ["Sin ventaja suficiente."],
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

describe("DecisionJournalPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
        unobserve() {}
      },
    );
    vi.clearAllMocks();
    vi.mocked(api.getLists).mockResolvedValue({ data: [] } as never);
    vi.mocked(api.getDecisionStudies).mockResolvedValue({
      data: { accountId: "acc1", studies: [], total: 0, limit: 50, offset: 0 },
    } as never);
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse() as never,
    );
    vi.mocked(api.getOhlcv).mockResolvedValue({
      data: [],
      meta: { timeframe: "1d", count: 0 },
    } as never);
  });

  afterEach(() => cleanup());

  it("muestra Tesis como pestaña por defecto y copy de seguimiento", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("decision-journal")).toBeTruthy(),
    );
    expect(screen.getByText(/Seguimiento de análisis y tesis/i)).toBeTruthy();
    expect(screen.getByTestId("tab-tesis")).toBeTruthy();
    expect(screen.getByTestId("journal-study-filters")).toBeTruthy();
  });

  it("WATCH no pinta objetivos operativos", async () => {
    vi.mocked(api.getDecisionStudies).mockResolvedValue({
      data: {
        accountId: "acc1",
        studies: [makeStudy()],
        total: 1,
        limit: 50,
        offset: 0,
      },
    } as never);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("study-row")).toBeTruthy());
    expect(screen.getByText("AAPL")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByTestId("study-row"));
    await waitFor(() =>
      expect(screen.getByTestId("decision-ficha")).toBeTruthy(),
    );
    expect(screen.getByTestId("no-operational-plan").textContent).toBe(
      NO_OPERATIONAL_PLAN_COPY,
    );
    expect(screen.queryByTestId("ficha-invalidation")).toBeNull();
    expect(screen.queryByText(/mi tesis/i)).toBeNull();
    expect(screen.queryByText(/supertrend/i)).toBeNull();
    expect(screen.queryByText(/12 indicadores/i)).toBeNull();
    expect(screen.getByTestId("ficha-analysis")).toBeTruthy();
  });

  it("Historial técnico conserva Replay y oculta IDs bajo información técnica", async () => {
    const spy = vi.fn();
    window.addEventListener("bolsa:open-help", spy);
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse([
        makeEntry({ entryId: "e1", sessionId: "sess-replay-1" }),
      ]) as never,
    );
    renderPage();
    fireEvent.click(screen.getByTestId("tab-historial"));
    await waitFor(() => expect(screen.getByTestId("open-replay")).toBeTruthy());
    expect(screen.getByTestId("journal-technical-details")).toBeTruthy();
    fireEvent.click(screen.getByTestId("open-replay"));
    expect(spy).toHaveBeenCalledOnce();
    window.removeEventListener("bolsa:open-help", spy);
  });

  it("muestra Setup line en historial", async () => {
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse([
        makeEntry({
          payload: {
            entrySetup: "wyckoff",
            tradePlanStatus: "ARMED",
            phase: "lps",
          },
        }),
      ]) as never,
    );
    renderPage();
    fireEvent.click(screen.getByTestId("tab-historial"));
    await waitFor(() =>
      expect(screen.getByTestId("journal-setup")).toBeTruthy(),
    );
    expect(screen.getByText(/wyckoff · ARMED · fase lps/i)).toBeTruthy();
  });

  it("muestra estado vacío de tesis", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("studies-empty")).toBeTruthy(),
    );
  });

  it("muestra error de tesis", async () => {
    vi.mocked(api.getDecisionStudies).mockRejectedValue(new Error("boom"));
    renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("studies-error")).toBeTruthy(),
    );
  });

  it("muestra Cargando… en historial", () => {
    vi.mocked(api.getDecisionJournal).mockImplementation(
      () => new Promise(() => {}) as never,
    );
    renderPage();
    fireEvent.click(screen.getByTestId("tab-historial"));
    expect(screen.getByText("Cargando…")).toBeTruthy();
  });

  it("muestra mensaje de error del journal técnico", async () => {
    vi.mocked(api.getDecisionJournal).mockRejectedValue(new Error("boom"));
    renderPage();
    fireEvent.click(screen.getByTestId("tab-historial"));
    await waitFor(() =>
      expect(screen.getByTestId("journal-error")).toBeTruthy(),
    );
  });

  it("muestra meta con total de entradas en historial", async () => {
    vi.mocked(api.getDecisionJournal).mockResolvedValue({
      data: {
        accountId: "acc1",
        entries: [makeEntry()],
        limit: 50,
        offset: 0,
        total: 42,
      },
    } as never);
    renderPage();
    fireEvent.click(screen.getByTestId("tab-historial"));
    await waitFor(() =>
      expect(screen.getByTestId("journal-meta")).toBeTruthy(),
    );
    expect(screen.getByTestId("journal-meta").textContent).toMatch(
      /42 entradas/,
    );
  });
});
