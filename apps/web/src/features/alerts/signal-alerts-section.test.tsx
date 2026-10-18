/**
 * Alertas de estrategia — la caché se ancla a la cuenta ACTIVA y los fallos se declaran.
 *
 * El API aísla `/signal-alerts` por `X-Account-Id`; si la clave de React Query no lleva la
 * cuenta, al cambiar A→B se sirven símbolos, notas, email y webhook de A. Un error de lectura
 * tampoco puede presentarse como «No hay suscripciones activas».
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { SignalAlertSubscriptionDto } from "@bolsa/shared";

let currentAccount: string | null = "acc-A";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: currentAccount,
    account: currentAccount ? { id: currentAccount } : null,
    isLoading: false,
    accounts: [],
  }),
}));

const getSignalAlerts = vi.fn<
  () => Promise<{ data: SignalAlertSubscriptionDto[] }>
>(async () => ({ data: [] }));

vi.mock("@/lib/api", () => ({
  api: {
    getInstruments: vi.fn(async () => ({ data: [] })),
    getStrategies: vi.fn(async () => ({ data: [] })),
    getSignalAlerts: () => getSignalAlerts(),
    createSignalAlert: vi.fn(),
    deleteSignalAlert: vi.fn(),
    resetSignalAlertDedupe: vi.fn(),
  },
}));

import { SignalAlertsSection } from "@/features/alerts/signal-alerts-section";

function subscription(
  overrides: Partial<SignalAlertSubscriptionDto> = {},
): SignalAlertSubscriptionDto {
  return {
    id: "sub-1",
    instrumentId: "inst-1",
    symbol: "AAA",
    strategyDefinitionId: null,
    presetKey: "sma_crossover",
    timeframe: "1d",
    signalKinds: ["entry_long"],
    channels: ["toast"],
    isActive: true,
    lastTriggeredAt: null,
    lastBarTimestamp: null,
    lastSignalKind: null,
    ...overrides,
  };
}

function sectionTree(client: QueryClient) {
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SignalAlertsSection />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function renderSection() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = render(sectionTree(client));
  return {
    client,
    /** Re-render tras cambiar la cuenta mockeada (la clave de caché debe cambiar). */
    rerenderWithAccount: () => view.rerender(sectionTree(client)),
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  currentAccount = "acc-A";
  getSignalAlerts.mockResolvedValue({ data: [] });
});

describe("SignalAlertsSection · alcance de cuenta", () => {
  it("usa la cuenta activa en la clave y no consulta sin cuenta", async () => {
    const { client } = renderSection();
    await waitFor(() => expect(getSignalAlerts).toHaveBeenCalled());

    const keys = client
      .getQueryCache()
      .getAll()
      .map((q) => q.queryKey);
    expect(
      keys.some(
        (k) => Array.isArray(k) && k[0] === "signal-alerts" && k[1] === "acc-A",
      ),
    ).toBe(true);

    cleanup();
    vi.clearAllMocks();
    currentAccount = null;
    renderSection();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(getSignalAlerts).not.toHaveBeenCalled();
    expect(screen.getByText(/Sin cuenta activa/i)).toBeInTheDocument();
  });

  it("no muestra las suscripciones de la cuenta anterior tras el cambio A→B", async () => {
    getSignalAlerts.mockResolvedValue({
      data: [subscription({ symbol: "AAA", note: "nota de A" })],
    });
    const { rerenderWithAccount } = renderSection();
    expect(await screen.findByText("AAA")).toBeInTheDocument();

    // Cambio de cuenta: la clave cambia y la caché de A no se reutiliza.
    currentAccount = "acc-B";
    getSignalAlerts.mockResolvedValue({
      data: [subscription({ id: "sub-2", symbol: "BBB" })],
    });
    rerenderWithAccount();

    expect(await screen.findByText("BBB")).toBeInTheDocument();
    expect(screen.queryByText("AAA")).not.toBeInTheDocument();
    expect(screen.queryByText("nota de A")).not.toBeInTheDocument();
  });

  it("un error de lectura se declara y NO se pinta como lista vacía", async () => {
    getSignalAlerts.mockRejectedValue(new Error("HTTP 500"));
    renderSection();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/No se pudieron cargar las suscripciones/i);
    expect(alert).toHaveTextContent(/HTTP 500/);
    expect(
      screen.queryByText(/No hay suscripciones activas/i),
    ).not.toBeInTheDocument();
  });
});
