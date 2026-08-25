import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DecisionJournalEntryV1 } from "@bolsa/shared";

vi.mock("@/lib/api", () => ({
  api: {
    getDecisionJournal: vi.fn(),
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

import { api } from "@/lib/api";
import { DecisionJournalPage } from "@/features/decision-journal/decision-journal-page";

let queryClient: QueryClient;

function renderPage() {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DecisionJournalPage />
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

describe("DecisionJournalPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => cleanup());

  it("muestra el copy UX Session vs Journal", async () => {
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse() as never,
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getByTestId("decision-journal")).toBeTruthy(),
    );
    expect(screen.getByText(/Session = foto del razonamiento/i)).toBeTruthy();
    expect(
      screen.getByText(/Journal = historial de transiciones/i),
    ).toBeTruthy();
  });

  it("renderiza entradas con badges de eventType y actor", async () => {
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse([
        makeEntry({
          entryId: "e1",
          eventType: "human_confirm",
          actor: "human",
        }),
        makeEntry({
          entryId: "e2",
          eventType: "risk_veto",
          actor: "system",
          sessionId: null,
        }),
      ]) as never,
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getAllByTestId("journal-entry")).toHaveLength(2),
    );

    expect(screen.getByTestId("event-human_confirm")).toBeTruthy();
    expect(screen.getByTestId("event-human_confirm").className).toMatch(
      /emerald/,
    );
    expect(screen.getByTestId("actor-human")).toBeTruthy();

    expect(screen.getByTestId("event-risk_veto")).toBeTruthy();
    expect(screen.getByTestId("event-risk_veto").className).toMatch(/rose/);
    expect(screen.getByTestId("actor-system")).toBeTruthy();
  });

  it("muestra Setup line desde payload attribution", async () => {
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
    await waitFor(() =>
      expect(screen.getByTestId("journal-setup")).toBeTruthy(),
    );
    expect(screen.getByText(/wyckoff · ARMED · fase lps/i)).toBeTruthy();
  });

  it("muestra link Abrir Replay cuando hay sessionId", async () => {
    const spy = vi.fn();
    window.addEventListener("bolsa:open-help", spy);

    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse([
        makeEntry({ entryId: "e1", sessionId: "sess-replay-1" }),
      ]) as never,
    );
    renderPage();

    await waitFor(() => expect(screen.getByTestId("open-replay")).toBeTruthy());

    fireEvent.click(screen.getByTestId("open-replay"));
    expect(spy).toHaveBeenCalledOnce();
    const event = spy.mock.calls[0]![0] as CustomEvent;
    expect(event.detail.sessionId).toBe("sess-replay-1");

    window.removeEventListener("bolsa:open-help", spy);
  });

  it("no muestra Abrir Replay sin sessionId", async () => {
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse([
        makeEntry({ entryId: "e1", sessionId: null }),
      ]) as never,
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getByTestId("journal-entry")).toBeTruthy(),
    );
    expect(screen.queryByTestId("open-replay")).toBeNull();
  });

  it("muestra Cargando… mientras isLoading", () => {
    vi.mocked(api.getDecisionJournal).mockImplementation(
      () => new Promise(() => {}) as never,
    );
    renderPage();
    expect(screen.getByText("Cargando…")).toBeTruthy();
  });

  it("muestra mensaje de error cuando la petición falla", async () => {
    vi.mocked(api.getDecisionJournal).mockRejectedValue(new Error("boom"));
    renderPage();

    await waitFor(() =>
      expect(screen.getByTestId("journal-error")).toBeTruthy(),
    );
    expect(screen.getByTestId("journal-error").textContent).toMatch(
      /No se pudo cargar el Decision Journal/i,
    );
  });

  it("muestra estado vacío cuando no hay entradas", async () => {
    vi.mocked(api.getDecisionJournal).mockResolvedValue(
      makeJournalResponse([]) as never,
    );
    renderPage();

    await waitFor(() =>
      expect(screen.getByTestId("journal-empty")).toBeTruthy(),
    );
    expect(screen.getByTestId("journal-empty").textContent).toMatch(
      /Sin entradas en el journal/i,
    );
  });

  it("muestra meta con total de entradas", async () => {
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

    await waitFor(() =>
      expect(screen.getByTestId("journal-meta")).toBeTruthy(),
    );
    expect(screen.getByTestId("journal-meta").textContent).toMatch(
      /42 entradas/,
    );
    expect(screen.getByTestId("journal-meta").textContent).toMatch(
      /mostrando 1/,
    );
  });
});
