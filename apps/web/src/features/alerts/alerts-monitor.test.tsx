/**
 * v111 — monitor de alertas anclado a la cuenta ACTIVA.
 *
 * La auditoría detectó que el monitor consultaba con claves sin cuenta (`["alerts","active"]`),
 * de modo que al cambiar de cuenta servía la caché de la anterior. Esta guarda fija que las
 * claves llevan `effectiveAccountId` y que el monitor no consulta sin cuenta activa.
 */

import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let currentAccount: string | null = "acc-A";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: currentAccount,
    account: currentAccount ? { id: currentAccount } : null,
    isLoading: false,
    accounts: [],
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAlerts: vi.fn(async () => ({ data: [] })),
    getSignalAlerts: vi.fn(async () => ({ data: [] })),
    evaluateAlerts: vi.fn(async () => ({ data: [] })),
    evaluateSignalAlerts: vi.fn(async () => ({ data: [], dispatches: [] })),
  },
}));

import { api } from "@/lib/api";
import { AlertsMonitor } from "@/features/alerts/alerts-monitor";

function renderMonitor() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AlertsMonitor />
    </QueryClientProvider>,
  );
  return client;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  currentAccount = "acc-A";
});

describe("AlertsMonitor · v111 account scope", () => {
  it("consulta con la cuenta activa en la clave y no consulta sin cuenta", async () => {
    const client = renderMonitor();

    await waitFor(() => expect(api.getAlerts).toHaveBeenCalledWith(true));

    const keys = client
      .getQueryCache()
      .getAll()
      .map((q) => q.queryKey);
    expect(
      keys.some(
        (k) =>
          Array.isArray(k) &&
          k[0] === "alerts" &&
          k[1] === "active" &&
          k[2] === "acc-A",
      ),
    ).toBe(true);
    expect(
      keys.some(
        (k) =>
          Array.isArray(k) &&
          k[0] === "signal-alerts" &&
          k[1] === "active" &&
          k[2] === "acc-A",
      ),
    ).toBe(true);
  });

  it("sin cuenta activa no dispara ninguna query", async () => {
    currentAccount = null;
    renderMonitor();

    // Deja correr el microtask del render antes de afirmar la ausencia.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api.getAlerts).not.toHaveBeenCalled();
    expect(api.getSignalAlerts).not.toHaveBeenCalled();
  });
});
