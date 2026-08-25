import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MesaOperationalBar } from "@/features/operations/mesa-operational-bar";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({ effectiveAccountId: "acc-1" }),
}));

vi.mock("@/stores/active-account-store", () => ({
  useActiveAccountQueryKey: () => "acc-1",
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAccountSummary: vi.fn(async () => ({
      data: { cash: 10000, totalEquity: 15000, totalUnrealizedPnl: 500 },
    })),
    getPortfolio: vi.fn(async () => ({
      data: {
        positions: [{ id: "p1" }, { id: "p2" }],
        totalEquity: 15000,
        totalUnrealizedPnl: 500,
      },
    })),
    getDecisionBoard: vi.fn(async () => ({
      data: {
        accountId: "acc-1",
        generatedAt: "2026-08-25T12:00:00Z",
        buckets: {
          pendingConfirm: 2,
          vetoed: 1,
          deferred: 1,
          autoWaiting: 0,
          total: 4,
        },
        semiF3Queue: [],
        decisionSessions: [],
      },
    })),
    getRiskKillSwitch: vi.fn(async () => ({
      effective: false,
      env: false,
      runtimeMemory: false,
      redis: null,
      paperDExecuteEnv: false,
    })),
  },
}));

function renderBar() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MesaOperationalBar />
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("MesaOperationalBar P4.2", () => {
  it("shows full operational state labels", async () => {
    renderBar();
    const bar = await screen.findByTestId("mesa-operational-bar");
    await waitFor(() => {
      const text = bar.textContent ?? "";
      expect(text).toMatch(/Confirm \(2\)/i);
    });
    const text = bar.textContent ?? "";
    expect(text).toMatch(/Patrimonio/i);
    expect(text).toMatch(/P&L/i);
    expect(text).toMatch(/Excepciones \(1\)/i);
    expect(text).toMatch(/Veto entradas \(1\)/i);
    expect(text).toMatch(/Posiciones\s+2/i);
  });
});
