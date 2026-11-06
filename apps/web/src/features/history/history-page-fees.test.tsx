/**
 * P1-03 — la cifra de comisiones NO depende del tamaño de página.
 *
 * Falsable: si la tarjeta vuelve a sumar las filas `fee` de la página de 100
 * movimientos, el caso «1 fila visible y total histórico 1.234,50» pinta 5,00 y
 * esta prueba falla; además el error de la API debe declararse, no caer a 0.
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
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const feeRow = {
  id: "l1",
  accountId: "acc-1",
  portfolioId: null,
  type: "fee",
  amount: -5,
  currency: "EUR",
  balanceAfter: 995,
  instrumentId: null,
  symbol: null,
  quantity: null,
  price: null,
  referenceType: null,
  referenceId: null,
  description: "Comisión de operación",
  executedAt: "2026-10-20T10:00:00Z",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Historial · comisiones del histórico", () => {
  it("usa el agregado del servidor, no la suma de la página", async () => {
    getAccountLedger.mockResolvedValue({
      data: [feeRow],
      tradeFeesTotal: 1234.5,
    });
    getTransactions.mockResolvedValue({ data: { data: [] } });

    renderPage();

    const card = await screen.findByTestId("history-trade-fees-total");
    await waitFor(() => expect(card).toHaveTextContent("1234.50 €"));
    expect(card).not.toHaveTextContent("5.00 €");
    expect(card).toHaveTextContent("Comisiones de operaciones (histórico)");
  });

  it("un total medido de cero se pinta como 0,00 €, no como hueco", async () => {
    getAccountLedger.mockResolvedValue({ data: [], tradeFeesTotal: 0 });
    getTransactions.mockResolvedValue({ data: { data: [] } });

    renderPage();

    const card = await screen.findByTestId("history-trade-fees-total");
    await waitFor(() => expect(card).toHaveTextContent("0.00"));
    expect(screen.getByText("0.00")).toHaveAttribute(
      "data-fees-state",
      "measured",
    );
  });

  it("con la consulta caída declara «No disponible» en vez de 0", async () => {
    getAccountLedger.mockRejectedValue(new Error("network"));
    getTransactions.mockRejectedValue(new Error("network"));

    renderPage();

    const card = await screen.findByTestId("history-trade-fees-total");
    await waitFor(() => expect(card).toHaveTextContent("No disponible"));
    expect(card).not.toHaveTextContent("0.00");
  });
});
