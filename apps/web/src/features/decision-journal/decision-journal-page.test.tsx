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
    getDecisionStudyHistory: vi.fn(),
    getLists: vi.fn(),
    getOhlcv: vi.fn(),
    getPortfolio: vi.fn(),
    queryInstrumentDailyOpinions: vi.fn(),
  },
}));

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: () => ({
    entriesBlocked: false,
    killOn: false,
    vetoed: 0,
    incidentCount: 0,
    incidentsFailed: false,
  }),
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
    quantity: null,
    initialRiskR: null,
    positionValue: null,
    direction: null,
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
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("min-width"),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    vi.clearAllMocks();
    vi.mocked(api.getLists).mockResolvedValue({ data: [] } as never);
    vi.mocked(api.getDecisionStudies).mockResolvedValue({
      data: { accountId: "acc1", studies: [], total: 0, limit: 50, offset: 0 },
    } as never);
    vi.mocked(api.getDecisionStudyHistory).mockResolvedValue({
      data: {
        accountId: "acc1",
        instrumentId: "inst-1",
        symbol: "AAPL",
        name: "Apple Inc.",
        studies: [],
        total: 0,
        limit: 20,
        offset: 0,
      },
    } as never);
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse() as never,
    );
    vi.mocked(api.getOhlcv).mockResolvedValue({
      data: [],
      meta: { timeframe: "1d", count: 0 },
    } as never);
    vi.mocked(api.getPortfolio).mockResolvedValue({
      data: { positions: [] },
    } as never);
    vi.mocked(api.queryInstrumentDailyOpinions).mockResolvedValue({
      data: [],
    } as never);
  });

  afterEach(() => cleanup());

  it("muestra Tesis como pestaña por defecto y copy de seguimiento", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("decision-journal")).toBeTruthy(),
    );
    expect(screen.getByText(/Estudios con análisis \(propose\)/i)).toBeTruthy();
    expect(screen.getByTestId("tab-tesis")).toBeTruthy();
    expect(screen.getByTestId("journal-study-filters")).toBeTruthy();
    expect((screen.getByTestId("filter-list") as HTMLSelectElement).value).toBe(
      "estudio",
    );
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

  it("muestra pestaña Evolución y estado vacío", async () => {
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
    fireEvent.click(screen.getByTestId("tab-evolucion"));
    await waitFor(() =>
      expect(screen.getByTestId("evolution-panel")).toBeTruthy(),
    );
    expect(screen.getByText(/Evolución de análisis IA/i)).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByTestId("evolution-empty")).toBeTruthy(),
    );
  });

  it("Evolución carga historial y compare card", async () => {
    vi.mocked(api.getDecisionStudies).mockResolvedValue({
      data: {
        accountId: "acc1",
        studies: [makeStudy()],
        total: 1,
        limit: 50,
        offset: 0,
      },
    } as never);
    vi.mocked(api.getDecisionStudyHistory).mockResolvedValue({
      data: {
        accountId: "acc1",
        instrumentId: "inst-1",
        symbol: "AAPL",
        name: "Apple Inc.",
        studies: [
          makeStudy({
            sessionId: "s-new",
            studiedAt: "2026-08-26T09:32:00Z",
            opinion: "bullish",
          }),
          makeStudy({
            sessionId: "s-old",
            studiedAt: "2026-08-20T09:00:00Z",
            opinion: "neutral",
          }),
        ],
        total: 2,
        limit: 20,
        offset: 0,
      },
    } as never);
    renderPage();
    fireEvent.click(screen.getByTestId("tab-evolucion"));
    await waitFor(() =>
      expect(screen.getByTestId("journal-study-compare")).toBeTruthy(),
    );
    expect(screen.getAllByTestId("evolution-version-row").length).toBe(2);
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

  it("ficha con plan + gate VETO muestra frase y CTA none alineadas con Mercado", async () => {
    vi.mocked(api.getDecisionStudies).mockResolvedValue({
      data: {
        accountId: "acc1",
        studies: [
          makeStudy({
            hasOperationalPlan: true,
            tradePlanStatus: "ARMED",
            entry: 100,
            stop: 94,
            target1: 112,
            target2: 124,
            expectedRR: 2,
            riskAmount: 250,
            quantity: 10,
            initialRiskR: 1,
            positionValue: 1000,
          }),
        ],
        total: 1,
        limit: 50,
        offset: 0,
      },
    } as never);
    vi.mocked(api.queryInstrumentDailyOpinions).mockResolvedValue({
      data: [
        {
          instrumentId: "inst-1",
          gateStatus: "VETO",
          stance: "hold_watch",
          dictamenStars: 2,
        },
      ],
    } as never);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("study-row")).toBeTruthy());
    fireEvent.click(screen.getByTestId("study-row"));
    await waitFor(() =>
      expect(screen.getByTestId("entry-operating-phrase").textContent).toMatch(
        /veto/i,
      ),
    );
    expect(screen.getByTestId("entry-operating-action").textContent).toBe(
      "Gate en veto",
    );
  });
});
