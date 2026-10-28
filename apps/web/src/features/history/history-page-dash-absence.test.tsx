/**
 * P2-04 — el hueco de la columna «Saldo» se prueba sobre el TEXTO RENDERIZADO.
 *
 * El gate de fuente (`findFirstLevelDashes`) solo ve literales `—` en el código; esta
 * prueba falsa la representación real: con `balanceAfter` ausente en el payload, la celda
 * debe decir «Sin dato todavía» y el contenedor **no** puede contener el comodín `—`
 * (ni un `0.00` fabricado).
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

const ACTUAL_ACCOUNT_ID = "acc-1";

function ledgerRow(overrides: Record<string, unknown> = {}) {
  return {
    id: "l1",
    accountId: ACTUAL_ACCOUNT_ID,
    portfolioId: null,
    type: "buy",
    amount: -1000,
    currency: "EUR",
    balanceAfter: 0,
    instrumentId: "ins-1",
    symbol: "SAN",
    quantity: 10,
    price: 100,
    referenceType: null,
    referenceId: null,
    description: null,
    executedAt: "2026-10-20T10:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Historial · el hueco de Saldo se declara, no se disfraza de guion", () => {
  it("sin balanceAfter pinta «Sin dato todavía» y no el literal —", async () => {
    // Payload con la clave ausente (hueco de lectura, no violación de contrato):
    // el comodín `—` estaba reservado a nivel 3 y aquí no debe aparecer.
    getAccountLedger.mockResolvedValue({
      data: [ledgerRow({ balanceAfter: null })],
      tradeFeesTotal: 0,
    });
    getTransactions.mockResolvedValue({ data: { data: [] } });

    renderPage();

    const region = await screen.findByRole("region", {
      name: "Movimientos contables",
    });
    await waitFor(() => expect(region).toHaveTextContent("Sin dato todavía"));
    const cells = region.querySelectorAll("td");
    expect(cells[cells.length - 1].textContent).toBe("Sin dato todavía");
    expect(screen.queryByText("—")).toBeNull();
  });

  it("con balanceAfter medido conserva la cifra y no el rótulo de hueco", async () => {
    getAccountLedger.mockResolvedValue({
      data: [ledgerRow({ balanceAfter: 995.25 })],
      tradeFeesTotal: 0,
    });
    getTransactions.mockResolvedValue({ data: { data: [] } });

    renderPage();

    const region = await screen.findByRole("region", {
      name: "Movimientos contables",
    });
    await waitFor(() => expect(region).toHaveTextContent("995.25"));
    expect(region).not.toHaveTextContent("Sin dato todavía");
  });
});
