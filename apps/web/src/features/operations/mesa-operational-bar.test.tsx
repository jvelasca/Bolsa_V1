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
      brokerVenue: "paper",
    })),
    getBrokerVenue: vi.fn(async () => ({
      brokerVenue: "paper",
      env: "paper",
      runtimeMemory: null,
      redis: null,
    })),
    setBrokerVenue: vi.fn(async (venue: "paper" | "live") => ({
      brokerVenue: venue,
      env: "paper",
      runtimeMemory: venue,
      redis: venue,
    })),
    getOpsSelfEval: vi.fn(async () => ({
      schemaVersion: "ops_self_eval_v0",
      rule: "measure ≠ Accept",
      accountId: "acc-1",
      lookbackDays: 120,
      lanes: {
        semi: {
          mark: "WARN",
          confirmSeed: 1,
          journalSeed: 8,
          buysSeed: 0,
          tradeLike: 0,
        },
        auto: {
          mark: "FAIL",
          paperDExecuteEnv: false,
          executeOptIn: false,
          strictAcceptReady: false,
          p1: { daysWithOpinions: 28, mark: "FAIL", need: 60 },
          p2: { confirmSeed: 1, mark: "FAIL", need: 50 },
          p3: {
            buyPrecision5d: null,
            alarmaBuyCount: 0,
            matureBuySample: 0,
            mark: "FAIL",
            need: 0.7,
          },
          p4: { buyRecall5d: 0, mark: "FAIL", need: 0.55 },
          p5: {
            tradeLike: 0,
            cashMaxDdFrac: 0.002,
            mark: "WARN",
            note: null,
          },
        },
      },
      runtime: {
        killSwitchEffective: false,
        brokerVenue: "paper",
        accountVenuePreference: null,
        paperDExecuteEnv: false,
        confirmPathHonesty: "SEMI",
      },
      portfolioReconciliation: { status: "not_wired" },
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

  it("shows OE-1 Autoeval SEMI/AUTO marks", async () => {
    renderBar();
    const chip = await screen.findByTestId("mesa-ops-self-eval");
    await waitFor(() => {
      expect(chip.textContent ?? "").toMatch(/SEMI WARN/i);
    });
    expect(chip.textContent ?? "").toMatch(/AUTO FAIL/i);
  });

  it("shows Paper|Live venue toggle (VS-1)", async () => {
    renderBar();
    const venue = await screen.findByTestId("mesa-broker-venue");
    expect(venue).toBeTruthy();
    expect(screen.getByTestId("mesa-broker-venue-paper")).toBeTruthy();
    expect(screen.getByTestId("mesa-broker-venue-live")).toBeTruthy();
  });
});
