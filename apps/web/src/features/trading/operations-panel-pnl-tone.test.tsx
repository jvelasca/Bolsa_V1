/**
 * P2-01 / I-03 — la celda P&L de Operaciones no afirma un tono sin medición.
 *
 * Falsable: si vuelve `(pos.unrealizedPnl ?? 0) >= 0`, la posición sin mark
 * observable sale `positive` y esta prueba falla.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import { OperationsPanel } from "@/features/trading/operations-panel";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    account: null,
    effectiveAccountId: "acc-1",
    accounts: [],
    isLoading: false,
  }),
  useActivateAccount: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/stores/active-account-store", () => ({
  useActiveAccountQueryKey: () => "acc-1",
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: (selector: (state: unknown) => unknown) =>
    selector({ workspace: { charts: [], activeChartId: null } }),
}));

vi.mock("@/features/trading/use-pending-orders", () => ({
  usePendingOrders: () => ({
    pendingOrders: [],
    removePendingOrder: vi.fn(),
    isError: false,
  }),
}));

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({ data: null, isLoading: false, isError: false }),
  portfolioReconStatusFromReport: () => null,
}));

vi.mock("@/features/operations/use-in-flight-submit-intents", () => ({
  useInFlightSubmitIntents: () => ({ data: null, isLoading: false }),
  pickSubmitIntentForInstrument: () => null,
}));

vi.mock("@/features/trading/position-exit-drawer-actions", () => ({
  PositionExitDrawerActions: () => null,
}));

vi.mock("@/features/mesa/position-route-panel", () => ({
  PositionRoutePanel: () => null,
}));

const getPortfolio = vi.fn();
const getDecisionBoard = vi.fn();
const getDecisionStudies = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getPortfolio: (...args: unknown[]) => getPortfolio(...args),
    getDecisionBoard: (...args: unknown[]) => getDecisionBoard(...args),
    getDecisionStudies: (...args: unknown[]) => getDecisionStudies(...args),
  },
}));

beforeAll(() => {
  // jsdom no implementa matchMedia; el panel no lo usa, pero un hijo compartido podría.
  if (!window.matchMedia) {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    });
  }
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function position(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-1",
    symbol: "AAPL",
    name: "Apple",
    quantity: 10,
    avgCost: 100,
    lastPrice: 105,
    marketValue: 1050,
    unrealizedPnl: 50,
    unrealizedPnlPct: 5,
    ...overrides,
  };
}

function renderPanel(pos: PositionDto) {
  getPortfolio.mockResolvedValue({ data: { positions: [pos] } });
  getDecisionBoard.mockResolvedValue({ data: { decisionSessions: [] } });
  getDecisionStudies.mockResolvedValue({ data: { studies: [] } });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OperationsPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OperationsPanel · P&L (P2-01)", () => {
  it("sin mark observable declara el hueco y no se pinta como ganancia", async () => {
    renderPanel(position({ unrealizedPnl: null, unrealizedPnlPct: null }));

    const cell = await screen.findByTestId("ops-pnl-AAPL");
    await waitFor(() => expect(cell.textContent).toContain("Sin dato todavía"));
    expect(cell.dataset.tone).toBe("neutral");
    expect(cell.className).not.toContain("emerald");
  });

  it("un valor medido conserva su signo en el tono", async () => {
    renderPanel(position({ unrealizedPnl: -12.5 }));
    const cell = await screen.findByTestId("ops-pnl-AAPL");
    await waitFor(() => expect(cell.dataset.tone).toBe("negative"));
    expect(cell.textContent).toContain("-12.5");
  });
});
