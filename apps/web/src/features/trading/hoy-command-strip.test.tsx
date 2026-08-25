import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { DecisionBoardV1 } from "@bolsa/shared";

vi.mock("@/lib/api", () => ({
  api: { getDecisionBoard: vi.fn() },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc1",
    account: { id: "acc1" },
    isLoading: false,
  }),
}));

import { api } from "@/lib/api";
import { HoyCommandStrip } from "./hoy-command-strip";

function board(): DecisionBoardV1 {
  return {
    accountId: "acc1",
    generatedAt: "2026-08-24T09:30:00Z",
    buckets: {
      pendingConfirm: 1,
      vetoed: 0,
      deferred: 0,
      autoWaiting: 0,
      total: 1,
    },
    semiF3Queue: [
      {
        instrumentId: "i1",
        symbol: "SAN",
        status: "pending_confirm",
        extra: {
          payload: {
            tradePlan: {
              decisionId: "d1",
              instrumentId: "i1",
              direction: "long",
              status: "ARMED",
              quantity: 0,
              riskPct: 0,
              whyNot: ["entry"],
              executionAllowed: false,
              entrySetup: "wyckoff",
            },
            wyckoffSpringAnchor: {
              phase: "reclaim",
              effort: "result_ok",
            },
          },
        },
      },
    ],
    decisionSessions: [],
  };
}

describe("HoyCommandStrip", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({ data: board() });
  });

  it("renders Hoy strip with queue item", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByTestId("hoy-command-strip")).toBeTruthy();
    expect(await screen.findByTestId("hoy-item-SAN")).toBeTruthy();
  });

  it("Ciclo 4.8: dialog shows Setup block from F3 echo", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    expect(await screen.findByTestId("hoy-setup")).toBeTruthy();
    expect(
      screen.getByText(/wyckoff · fase reclaim · result ok/i),
    ).toBeTruthy();
  });

  it("Ciclo 4.9: WhyNot labels regime/orphan/rr", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "BLOCKED",
                  quantity: 0,
                  riskPct: 0,
                  whyNot: ["regime", "orphan", "rr"],
                  executionAllowed: false,
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    expect(await screen.findByText("Régimen no admite longs")).toBeTruthy();
    expect(screen.getByText("Sin paquete de decisión")).toBeTruthy();
    expect(screen.getByText("Riesgo/beneficio insuficiente")).toBeTruthy();
  });

  it("Ciclo 5.0: dialog shows Revisar tesis when thesisHealth.status=review", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "WATCH",
                  quantity: 0,
                  riskPct: 0,
                  whyNot: ["entry"],
                  executionAllowed: false,
                },
                thesisHealth: {
                  hint: "reduce",
                  status: "review",
                  why: ["confidence_degraded", "stop_intact"],
                  confidence: 0.3,
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    expect(await screen.findByTestId("hoy-thesis-review")).toBeTruthy();
    expect(screen.getByText(/Revisar tesis/i)).toBeTruthy();
    expect(screen.getByText(/reduce · confidence_degraded/i)).toBeTruthy();
  });

  it("Ciclo 5.1: dialog shows Proteger when protectPlan.status=protect_hint", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "TRIGGERED",
                  quantity: 10,
                  riskPct: 1,
                  whyNot: [],
                  executionAllowed: true,
                  entry: 100,
                  structuralStop: 90,
                },
                protectPlan: {
                  status: "protect_hint",
                  target1: 110,
                  suggestedProtectStop: 100,
                  rMultiple: 1,
                  why: ["mfe_ge_1r"],
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    const protect = await screen.findByTestId("hoy-protect");
    expect(protect).toBeTruthy();
    expect(protect.textContent).toMatch(/Proteger/i);
    expect(protect.textContent).toMatch(/1R · T1 110 · proteger @ 100/i);
  });

  it("Ciclo 5.2: dialog shows Salida when exitRadar.status!=none", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "TRIGGERED",
                  quantity: 10,
                  riskPct: 1,
                  whyNot: [],
                  executionAllowed: true,
                },
                exitRadar: {
                  status: "trail_hint",
                  suggestedTrailStop: 105,
                  target1: 110,
                  rMultiple: 1.5,
                  why: ["mfe_ge_1_5r"],
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    const salida = await screen.findByTestId("hoy-exit-radar");
    expect(salida).toBeTruthy();
    expect(salida.textContent).toMatch(/Salida/i);
    expect(salida.textContent).toMatch(/trail hint/i);
  });

  it("Ciclo 5.3: dialog shows Excursión metrics when mfeMae.status!=none", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "TRIGGERED",
                  quantity: 10,
                  riskPct: 1,
                  whyNot: [],
                  executionAllowed: true,
                },
                mfeMae: {
                  status: "favorable",
                  mfeR: 1.8,
                  maeR: 0.2,
                  currentR: 0.8,
                  why: ["peak_from_bars", "mfe_ge_1_5r"],
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    const metrics = await screen.findByTestId("hoy-mfe-mae");
    expect(metrics).toBeTruthy();
    expect(metrics.textContent).toMatch(/Excursión/i);
    expect(metrics.textContent).toMatch(/MFE 1\.8R · MAE 0\.2R · favorable/i);
  });

  it("Ciclo 8.0: dialog shows Expectativa when expectancy.status!=none", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "TRIGGERED",
                  quantity: 10,
                  riskPct: 1,
                  whyNot: [],
                  executionAllowed: true,
                  entrySetup: "breakout",
                },
                expectancy: {
                  status: "thin",
                  entrySetup: "breakout",
                  n: 1,
                  expectancyR: 0.8,
                  winRate: 1,
                  avgWinR: 0.8,
                  avgLossR: null,
                  currentR: 0.8,
                  why: ["not_permission", "live_proxy", "thin_sample"],
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    const exp = await screen.findByTestId("hoy-expectancy");
    expect(exp).toBeTruthy();
    expect(exp.textContent).toMatch(/Expectativa/i);
    expect(exp.textContent).toMatch(/breakout/i);
    expect(exp.textContent).toMatch(/≠ permiso/);
  });

  it("Ciclo 8.1: dialog shows Trail when trailPlan.status!=none", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "TRIGGERED",
                  quantity: 10,
                  riskPct: 1,
                  whyNot: [],
                  executionAllowed: true,
                },
                trailPlan: {
                  status: "ratchet",
                  suggestedTrailStop: 115,
                  lockedR: 1.5,
                  peakMfeR: 2.5,
                  currentR: 2.0,
                  trailDistanceR: 1,
                  why: ["not_permission", "hint_only", "ratchet_lock"],
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    const trail = await screen.findByTestId("hoy-trail-plan");
    expect(trail).toBeTruthy();
    expect(trail.textContent).toMatch(/Trail/i);
    expect(trail.textContent).toMatch(/ratchet/i);
    expect(trail.textContent).toMatch(/hint only/i);
  });

  it("Ciclo 8.2: dialog shows Bracket when bracketPlan.status!=none", async () => {
    vi.mocked(api.getDecisionBoard).mockResolvedValue({
      data: {
        ...board(),
        semiF3Queue: [
          {
            instrumentId: "i1",
            symbol: "SAN",
            status: "pending_confirm",
            extra: {
              payload: {
                tradePlan: {
                  decisionId: "d1",
                  instrumentId: "i1",
                  direction: "long",
                  status: "TRIGGERED",
                  quantity: 10,
                  riskPct: 1,
                  whyNot: [],
                  executionAllowed: true,
                },
                bracketPlan: {
                  status: "picture",
                  entry: 100,
                  stop: 90,
                  target1: 110,
                  target2: 120,
                  target1R: 1,
                  target2R: 2,
                  legT1QtyFrac: 0.5,
                  legT2QtyFrac: 0.5,
                  why: [
                    "aligned_protect_t1",
                    "display_only",
                    "not_permission",
                    "hint_only",
                    "no_broker_oco",
                  ],
                },
              },
            },
          },
        ],
      },
    });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <HoyCommandStrip />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("hoy-item-SAN"));
    const bracket = await screen.findByTestId("hoy-bracket-plan");
    expect(bracket).toBeTruthy();
    expect(bracket.textContent).toMatch(/Bracket/i);
    expect(bracket.textContent).toMatch(/T1 110/);
    expect(bracket.textContent).toMatch(/T2 120/);
    expect(bracket.textContent).toMatch(/display only/i);
  });
});
