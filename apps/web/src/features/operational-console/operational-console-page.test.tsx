import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OperationalConsolePage } from "@/features/operational-console/operational-console-page";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1", name: "Demo" },
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getOpsSelfEval: vi.fn(),
    getEstudioAutoTelemetry: vi.fn(),
    getDecisionBoard: vi.fn(),
    getActiveOperationalIncidents: vi.fn(),
    resolveOperationalIncident: vi.fn(),
    clearOperationalIncident: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const mockSelfEval = {
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
      p5: { tradeLike: 0, cashMaxDdFrac: 0.002, mark: "WARN", note: null },
    },
  },
  runtime: {
    killSwitchEffective: false,
    brokerVenue: "paper",
    accountVenuePreference: null,
    paperDExecuteEnv: false,
    confirmPathHonesty: "SEMI",
  },
  portfolioReconciliation: { status: "drift", note: "OI-6" },
  operationalReadiness: {
    state: "PAPER_DEGRADED",
    venue: "paper",
    reasons: ["recon_not_certified"],
    notes: [],
    rule: "no averaging",
  },
};

function renderConsole() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <OperationalConsolePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("OperationalConsolePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getOpsSelfEval).mockResolvedValue(mockSelfEval as never);
    vi.mocked(api.getEstudioAutoTelemetry).mockResolvedValue({
      data: {
        schemaVersion: "estudio_auto_telemetry_v0",
        rule: "measure ≠ Accept",
        asOf: "2026-08-30",
        lookbackDays: 120,
        funnel: {
          opinionRows: 10,
          daysWithOpinions: 28,
          candidatesAlarma: 2,
          candidatesDictamen: 3,
          candidatesTotal: 5,
          notCandidate: 5,
          allowedSources: ["estudio_alarma", "estudio_dictamen"],
          excludedSources: ["paper_d", "radar", "hoy"],
        },
        edgeReport: {
          paperAutoRequiresEdgeReport: true,
          parityWithSemi: true,
          mark: "PASS",
          note: "EdgeReport",
        },
        p1p5: {
          mark: "FAIL",
          strictAcceptReady: false,
          source: "oe1_auto_lane",
        },
        lastPropose: null,
        recentProposes: [],
        gates: {
          expandSourcesReady: false,
          sourcesShouldContract: true,
          thawEstrictoReady: false,
          paperDExecuteEnv: false,
          blockers: ["p1_p5_not_green"],
        },
        caveats: [],
      },
    } as never);
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        accountId: "acc-1",
        generatedAt: "2026-08-26T10:00:00Z",
        buckets: {
          pendingConfirm: 2,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
          total: 2,
        },
        semiF3Queue: [],
        decisionSessions: [],
      },
    } as never);
    vi.mocked(api.getActiveOperationalIncidents).mockResolvedValue({
      data: { accountId: "acc-1", incidents: [], total: 0 },
    } as never);
  });

  it("renderiza shell y secciones OE-1/readiness", async () => {
    renderConsole();
    expect(await screen.findByTestId("operational-console")).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByTestId("ops-readiness-state").textContent).toMatch(
        /PAPER_DEGRADED/,
      ),
    );
    expect(screen.getByTestId("ops-semi-lane").textContent).toMatch(/WARN/);
    expect(screen.getByTestId("ops-auto-lane").textContent).toMatch(/FAIL/);
    expect(screen.getByTestId("ops-recon-status").textContent).toMatch(
      /drift/i,
    );
    expect(screen.getByTestId("ops-a6-expand-gate").textContent).toMatch(
      /bloqueado/i,
    );
  });

  it("muestra error cuando ops-self-eval falla", async () => {
    vi.mocked(api.getOpsSelfEval).mockRejectedValue(new Error("boom"));
    renderConsole();
    expect(await screen.findByTestId("ops-console-error")).toBeTruthy();
  });

  it("muestra incidentes y abre panel resolve", async () => {
    vi.mocked(api.getActiveOperationalIncidents).mockResolvedValue({
      data: {
        accountId: "acc-1",
        incidents: [
          {
            incidentId: "inc-1",
            accountId: "acc-1",
            kind: "portfolio_drift",
            status: "open",
            snapshot: "portfolio_drift",
            openedAt: "2026-08-26T10:00:00Z",
            reviewedAt: null,
            reviewedBy: null,
            resolvedAt: null,
            resolvedBy: null,
            resolutionNote: null,
            clearedAt: null,
          },
        ],
        total: 1,
      },
    } as never);
    renderConsole();
    await screen.findByTestId("ops-incident-row");
    fireEvent.click(screen.getByTestId("ops-incident-resolve-link"));
    expect(await screen.findByTestId("mesa-incident-panel")).toBeTruthy();
  });

  it("quick links incluyen board y confirm count", async () => {
    renderConsole();
    await screen.findByTestId("ops-quick-links-section");
    await waitFor(() =>
      expect(screen.getByTestId("ops-link-confirm").textContent).toMatch(
        /2 pendientes/,
      ),
    );
    expect(screen.getByTestId("ops-link-board")).toBeTruthy();
  });
});
