/**
 * ADR-040 §10 thaw V2.1 — strip compacto Hoy → enlace only.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { MESA_PATH } from "@/features/confirm/daily-nav";

vi.mock("@/lib/api", () => ({
  api: {
    getDecisionBoard: vi.fn(async () => ({
      data: {
        accountId: "acc-1",
        generatedAt: "2026-09-04T12:00:00Z",
        buckets: {
          pendingConfirm: 0,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
          total: 0,
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
    getScanJobs: vi.fn(async () => ({ data: [] })),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
  }),
}));

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({ data: undefined, isLoading: false }),
  portfolioReconStatusFromReport: () => "ok",
}));

import { TradingHealthStrip } from "./trading-health-strip";

function renderStrip() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TradingHealthStrip />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TradingHealthStrip ADR-040 Hoy enlace", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders health strip and Hoy → link to MESA_PATH", () => {
    renderStrip();
    expect(screen.getByTestId("trading-health-strip")).toBeTruthy();
    const hoy = screen.getByTestId("trading-hoy-strip");
    expect(hoy.getAttribute("href")).toBe(MESA_PATH);
    expect(hoy.textContent).toBe("Hoy →");
  });
});
