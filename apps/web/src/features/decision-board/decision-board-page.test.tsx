import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DecisionBoardV1 } from "@bolsa/shared";

vi.mock("@/lib/api", () => ({
  api: {
    getDecisionBoard: vi.fn(),
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
import { DecisionBoardPage } from "@/features/decision-board/decision-board-page";

let queryClient: QueryClient;

function renderPage() {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DecisionBoardPage />
    </QueryClientProvider>,
  );
}

function makeBoard(overrides: Partial<DecisionBoardV1> = {}): DecisionBoardV1 {
  return {
    accountId: "acc1",
    generatedAt: "2026-08-24T09:30:00Z",
    buckets: {
      pendingConfirm: 2,
      vetoed: 1,
      deferred: 3,
      autoWaiting: 4,
      total: 10,
    },
    semiF3Queue: [
      { instrumentId: "inst-semi-1", symbol: "SAN", status: "pending_confirm" },
    ],
    decisionSessions: [
      {
        sessionId: "s1",
        kind: "confirm",
        status: "open",
        instrumentId: "inst-1",
        symbol: "BBVA",
        decisionId: "d1",
        createdAt: "2026-08-24T08:12:00Z",
        gate: "PASS",
      },
      {
        sessionId: "s2",
        kind: "propose",
        status: "closed",
        instrumentId: "inst-2",
        symbol: "ITX",
        decisionId: null,
        createdAt: "2026-08-24T07:00:00Z",
        gate: "VETO",
      },
    ],
    equity: 12500,
    freeMargin: 3200,
    ...overrides,
  };
}

describe("DecisionBoardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => cleanup());

  it("renderiza los buckets como KPIs", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: makeBoard(),
    } as never);
    renderPage();

    await waitFor(() =>
      expect(screen.getByTestId("board-buckets")).toBeTruthy(),
    );

    expect(screen.getByText("Por confirmar")).toBeTruthy();
    expect(screen.getByText("Vetadas")).toBeTruthy();
    expect(screen.getByText("Diferidas")).toBeTruthy();
    expect(screen.getByText("Auto en espera")).toBeTruthy();
    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.getByTestId("bucket-por-confirmar").textContent).toContain(
      "2",
    );
    expect(screen.getByTestId("bucket-vetadas").textContent).toContain("1");
    expect(screen.getByTestId("bucket-total").textContent).toContain("10");
  });

  it("renderiza la cola SEMI_F3 y las decision sessions con badge de gate", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: makeBoard(),
    } as never);
    renderPage();

    await waitFor(() =>
      expect(screen.getByTestId("semi-f3-item")).toBeTruthy(),
    );

    expect(screen.getByText("SAN")).toBeTruthy();
    expect(screen.getByText("pending_confirm")).toBeTruthy();
    expect(screen.getByText("BBVA")).toBeTruthy();
    expect(screen.getByText("ITX")).toBeTruthy();

    const passBadge = screen.getByTestId("gate-PASS");
    expect(passBadge.textContent).toBe("PASS");
    expect(passBadge.className).toMatch(/emerald/);

    const vetoBadge = screen.getByTestId("gate-VETO");
    expect(vetoBadge.textContent).toBe("VETO");
    expect(vetoBadge.className).toMatch(/rose/);
  });

  it("muestra equity y margen libre cuando vienen", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: makeBoard(),
    } as never);
    renderPage();

    await waitFor(() => expect(screen.getByText("Equity")).toBeTruthy());
    expect(screen.getByText("12500.00")).toBeTruthy();
    expect(screen.getByText("Margen libre")).toBeTruthy();
    expect(screen.getByText("3200.00")).toBeTruthy();
  });

  it("muestra Cargando… mientras isLoading", () => {
    let resolveFn: (v: never) => void = () => {};
    vi.mocked(api.getDecisionBoard).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve as (v: never) => void;
        }) as never,
    );
    renderPage();
    expect(screen.getByText("Cargando…")).toBeTruthy();
    resolveFn({} as never);
  });

  it("muestra mensaje de error cuando la petición falla", async () => {
    vi.mocked(api.getDecisionBoard).mockRejectedValue(new Error("boom"));
    renderPage();

    await waitFor(() => expect(screen.getByTestId("board-error")).toBeTruthy());
    expect(screen.getByTestId("board-error").textContent).toMatch(
      /No se pudo cargar el Decision Board/i,
    );
  });

  it("muestra estado vacío cuando no hay cola ni sessions", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: makeBoard({
        semiF3Queue: [],
        decisionSessions: [],
      }),
    } as never);
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Sin decisiones pendientes.")).toBeTruthy(),
    );
  });
});
