/**
 * P1-04 — el color del asiento lo decide su papel, no el signo del importe.
 *
 * Falsable: con `amount >= 0 ? emerald : red`, una comisión (coste) y una compra
 * (neutral) se pintaban igual que una venta; aquí se fija `data-tone`.
 */
import { cleanup, render, screen } from "@testing-library/react";
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

function row(overrides: Record<string, unknown>) {
  return {
    accountId: "acc-1",
    portfolioId: null,
    currency: "EUR",
    balanceAfter: 1000,
    instrumentId: null,
    symbol: null,
    quantity: null,
    price: null,
    referenceType: null,
    referenceId: null,
    description: null,
    executedAt: "2026-10-20T10:00:00Z",
    ...overrides,
  };
}

const entries = [
  // El motor registra la comisión con importe POSITIVO (`append_fee(amount=fees.total)`);
  // con la regla vieja salía en verde, como un ingreso.
  row({ id: "f1", type: "fee", amount: 4.5, symbol: "SAN" }),
  row({ id: "b1", type: "buy", amount: -1000, symbol: "SAN" }),
  row({ id: "s1", type: "sell", amount: 1010, symbol: "SAN" }),
];

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

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Historial · tono del importe", () => {
  it("comisión = coste, compra = neutral, venta = entrada", async () => {
    getAccountLedger.mockResolvedValue({ data: entries, tradeFeesTotal: 4.5 });
    getTransactions.mockResolvedValue({ data: { data: [] } });

    renderPage();

    const fee = await screen.findByText("4.50 EUR");
    expect(fee).toHaveAttribute("data-tone", "cost");
    expect(fee.className).toContain("text-red-400");
    expect(fee.className).not.toContain("text-emerald-400");

    const buy = screen.getByText("-1000.00 EUR");
    expect(buy).toHaveAttribute("data-tone", "neutral");
    expect(buy.className).not.toContain("text-emerald-400");
    expect(buy.className).not.toContain("text-red-400");

    const sell = screen.getByText("1010.00 EUR");
    expect(sell).toHaveAttribute("data-tone", "in");
    expect(sell.className).toContain("text-emerald-400");
  });

  it("la custodia es coste aunque el asiento no sea de tipo fee", async () => {
    getAccountLedger.mockResolvedValue({
      data: [
        row({
          id: "c1",
          type: "deposit",
          referenceType: "custody",
          amount: -12,
          description: "Custodia anual",
        }),
      ],
      tradeFeesTotal: 0,
    });
    getTransactions.mockResolvedValue({ data: { data: [] } });

    renderPage();

    const custody = await screen.findByText("-12.00 EUR");
    expect(custody).toHaveAttribute("data-tone", "cost");
  });
});
