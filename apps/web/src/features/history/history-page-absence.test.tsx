/**
 * P1-01 — Historial: un error de la API no es «sin movimientos» ni «sin operaciones».
 *
 * Falsable: si `MovementsTable`/`TradesTable` vuelven a recibir `data ?? []` sin
 * mirar `isError`, el hueco deja de declararse y estas pruebas fallan.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { HistoryPage } from "@/features/history/history-page";

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

const getAccountLedger = vi.fn();
const getTransactions = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getAccountLedger: (...args: unknown[]) => getAccountLedger(...args),
    getTransactions: (...args: unknown[]) => getTransactions(...args),
  },
}));

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Historial — error de lectura ≠ colección vacía", () => {
  it("movimientos caídos declaran «No disponible» y no «Sin movimientos»", async () => {
    getAccountLedger.mockRejectedValue(new Error("network"));
    getTransactions.mockRejectedValue(new Error("network"));

    renderPage();

    const absence = await screen.findByTestId("history-movements-absence");
    await waitFor(() => expect(absence).toHaveTextContent("No disponible"));
    expect(absence).toHaveAttribute("data-absence-state", "error");
    expect(screen.queryByText(/Sin movimientos contables/)).toBeNull();
  });

  it("operaciones caídas declaran «No disponible» y no «Sin operaciones ejecutadas»", async () => {
    getAccountLedger.mockRejectedValue(new Error("network"));
    getTransactions.mockRejectedValue(new Error("network"));

    renderPage();

    await screen.findByTestId("history-movements-absence");
    screen.getByRole("button", { name: /Operaciones/ }).click();

    const absence = await screen.findByTestId("history-trades-absence");
    expect(absence).toHaveTextContent("No disponible");
    expect(screen.queryByText(/Sin operaciones ejecutadas/)).toBeNull();
  });

  it("una colección leída y vacía sí dice «Sin movimientos contables»", async () => {
    getAccountLedger.mockResolvedValue({ data: [], tradeFeesTotal: 0 });
    getTransactions.mockResolvedValue({ data: { data: [] } });

    renderPage();

    expect(await screen.findByText(/Sin movimientos contables/)).toBeTruthy();
    expect(screen.queryByTestId("history-movements-absence")).toBeNull();
  });
});
