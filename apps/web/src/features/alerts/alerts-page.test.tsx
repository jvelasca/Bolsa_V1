/**
 * Alertas de precio — alcance de cuenta y errores visibles.
 *
 * `/alerts` es global en backend, pero la caché se ancla a la cuenta activa para no mezclar
 * contextos con `AlertsMonitor`. Un fallo de lectura o de una acción destructiva se declara;
 * nunca se disfraza de «No hay alertas en esta vista».
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { PriceAlertDto } from "@bolsa/shared";

let currentAccount: string | null = "acc-A";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: currentAccount,
    account: currentAccount ? { id: currentAccount } : null,
    isLoading: false,
    accounts: [],
  }),
}));

const getAlerts = vi.fn<() => Promise<{ data: PriceAlertDto[] }>>(async () => ({
  data: [],
}));
const deleteAlert = vi.fn(async (_id: string) => undefined);

vi.mock("@/lib/api", () => ({
  api: {
    getInstruments: vi.fn(async () => ({ data: [] })),
    getAlerts: () => getAlerts(),
    getMarketProviders: vi.fn(async () => ({ data: [] })),
    getSignalAlerts: vi.fn(async () => ({ data: [] })),
    getStrategies: vi.fn(async () => ({ data: [] })),
    createAlert: vi.fn(),
    deleteAlert: (id: string) => deleteAlert(id),
    reactivateAlert: vi.fn(),
    createSignalAlert: vi.fn(),
    deleteSignalAlert: vi.fn(),
    resetSignalAlertDedupe: vi.fn(),
  },
}));

import { AlertsPage } from "@/features/alerts/alerts-page";

function priceAlert(overrides: Partial<PriceAlertDto> = {}): PriceAlertDto {
  return {
    id: "alert-1",
    instrumentId: "inst-1",
    symbol: "AAA",
    condition: "above",
    priceSource: "daily_close",
    targetPrice: 12.5,
    note: null,
    isActive: true,
    triggeredAt: null,
    triggeredPrice: null,
    createdAt: "2026-10-18T10:00:00Z",
    ...overrides,
  } as PriceAlertDto;
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/alerts"]}>
        <AlertsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { client, view };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  currentAccount = "acc-A";
  getAlerts.mockResolvedValue({ data: [] });
  deleteAlert.mockResolvedValue(undefined);
});

describe("AlertsPage · alcance de cuenta y errores", () => {
  it("ancla la caché a la cuenta activa y no consulta sin cuenta", async () => {
    const { client } = renderPage();
    await waitFor(() => expect(getAlerts).toHaveBeenCalled());
    expect(
      client
        .getQueryCache()
        .getAll()
        .some(
          (q) =>
            Array.isArray(q.queryKey) &&
            q.queryKey[0] === "alerts" &&
            q.queryKey[1] === "acc-A",
        ),
    ).toBe(true);

    cleanup();
    vi.clearAllMocks();
    currentAccount = null;
    renderPage();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(getAlerts).not.toHaveBeenCalled();
  });

  it("un error de lectura se declara y NO se pinta como lista vacía", async () => {
    getAlerts.mockRejectedValue(new Error("HTTP 503"));
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/No se pudieron cargar las alertas/i);
    expect(alert).toHaveTextContent(/HTTP 503/);
    expect(
      screen.queryByText(/No hay alertas en esta vista/i),
    ).not.toBeInTheDocument();
  });

  it("muestra el fallo de una acción destructiva en lugar de silenciarlo", async () => {
    getAlerts.mockResolvedValue({ data: [priceAlert()] });
    deleteAlert.mockRejectedValue(new Error("HTTP 409"));
    renderPage();

    const deleteButton = await screen.findByTitle("Eliminar");
    fireEvent.click(deleteButton);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /No se pudo completar la acción/i,
      ),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/HTTP 409/);
  });
});
