/**
 * AUTO · Operativa diaria por valor — contrato de la vista por valor.
 *
 * Invariantes:
 * - carga / vacío / error: un fallo NO se pinta como lista vacía;
 * - los cuatro estados se muestran separados y un hueco es «Sin dato todavía»;
 * - solo se publican niveles del `TradePlan` (target2 ausente ⇒ no es 0);
 * - la validación se une con la auditoría por símbolo y el estado global no emite
 *   `CONFIRMED`;
 * - el botón encola el job y muestra su progreso;
 * - cambiar de cuenta no reutiliza el parte de la cuenta anterior.
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

const state = vi.hoisted(() => ({ accountId: "acc-1" as string | null }));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: state.accountId,
    account: state.accountId ? { id: state.accountId } : null,
    isLoading: false,
    accounts: [],
  }),
}));

const REPORT = {
  asOf: "2026-10-18",
  accountId: "acc-1",
  status: "ok",
  scannedCount: 4,
  counts: { ok: 1, no_signal: 1, no_plan: 1, error: 1 },
  values: [
    {
      instrumentId: "inst-1",
      symbol: "AAA",
      status: "ok",
      reason: null,
      asOfBarDate: "2026-10-17",
      computedAt: "2026-10-18T20:00:00+00:00",
      positionOpen: true,
      selector: {
        measured: true,
        runId: "top3-acc-1-2026-10-18T08:00:00Z",
        bar: "2026-10-18T08:00:00Z",
        assetId: "inst-1",
        presetKey: "estudio_auto",
        strategyVersion: "1",
        isWinner: true,
        reason: null,
      },
      opinion: {
        stance: "buy",
        dictamenStars: 4,
        channel: "alarma",
        autoSource: "estudio",
        reasons: ["momentum"],
        gateStatus: "PASS",
        engineVersion: "opinion_v1",
      },
      indicators: {
        io: 72,
        fa: 55,
        ta: 61,
        confidence: "HIGH",
        regime: "neutral",
      },
      plan: {
        status: "TRIGGERED",
        direction: "long",
        entry: 100,
        structuralStop: 95,
        target1: 110,
        target2: null,
        riskAmount: 250,
        expectedRR: 2,
        whyNot: [],
      },
      whyNot: [],
      strategy: {
        presetKey: "estudio_auto",
        strategyDefinitionId: null,
        strategyVersion: 1,
        planId: "plan-1",
      },
    },
    {
      instrumentId: "inst-2",
      symbol: "BBB",
      status: "no_plan",
      reason: "no_tradeplan",
      asOfBarDate: "2026-10-17",
      computedAt: "2026-10-18T20:00:00+00:00",
      opinion: {
        stance: "buy",
        dictamenStars: 3,
        channel: "aviso",
        autoSource: "estudio",
        reasons: [],
        gateStatus: "PASS",
        engineVersion: "opinion_v1",
      },
      indicators: { io: 50, fa: null, ta: 40, confidence: null, regime: null },
      plan: null,
      whyNot: ["gap_risk"],
      strategy: null,
    },
    {
      instrumentId: "inst-3",
      symbol: "CCC",
      status: "no_signal",
      reason: "stance:hold_watch",
      asOfBarDate: "2026-10-17",
      computedAt: "2026-10-18T20:00:00+00:00",
      opinion: {
        stance: "hold_watch",
        dictamenStars: 2,
        channel: "none",
        autoSource: null,
        reasons: [],
        gateStatus: "PASS",
        engineVersion: "opinion_v1",
      },
      indicators: {
        io: null,
        fa: null,
        ta: null,
        confidence: null,
        regime: null,
      },
      plan: null,
      whyNot: [],
      strategy: null,
    },
    {
      instrumentId: "inst-4",
      symbol: "DDD",
      status: "error",
      reason: "opinion_error:boom",
      asOfBarDate: null,
      computedAt: null,
      opinion: {
        stance: null,
        dictamenStars: null,
        channel: null,
        autoSource: null,
        reasons: [],
        gateStatus: null,
        engineVersion: null,
      },
      indicators: {
        io: null,
        fa: null,
        ta: null,
        confidence: null,
        regime: null,
      },
      plan: null,
      whyNot: [],
      strategy: null,
    },
  ],
  notes: [],
  generatedAt: "2026-10-18T20:00:00+00:00",
  truncated: false,
  countsConsistent: true,
};

const AUDIT = {
  available: true,
  readOnly: true,
  serving: "PRECOMPUTED_ARTIFACT",
  window: "2026-10-16_2026-10-17",
  audit: {
    kind: "AUTO_ESTUDIO_AUDIT_V1",
    readOnly: true,
    pointCitable: false,
    pointCitableReason: "Banda, no punto.",
    summary: {
      values: 1,
      measured: 1,
      unmeasured: 0,
      withPresetKey: 1,
      withoutPresetKey: 0,
    },
    values: [
      {
        symbol: "AAA",
        strategy: { presetKey: "estudio_auto", version: "v1" },
        why: { indicatorSpecs: null, recommendations: null },
        signal: {
          cycles: 2,
          linkedCycles: 2,
          unlinkedCycles: 0,
          duplicateCycles: 0,
          measuredCycles: 8,
          daysCovered: 2,
        },
        cycles: [
          {
            cycleId: "cyc-aaa-1",
            entryDay: "2026-10-16",
            exitDay: "2026-10-17",
            strategyPresetKey: "estudio_auto",
            strategyVersion: "v1",
            realizedR: 0.4,
          },
        ],
        resultR: {
          verdict: "MIXED",
          verdictReason: "preliminary_sample",
          evidenceQuality: "SUPPORTED",
          expectancyR: 0.4,
          hitRate: 0.55,
          realizedRTotal: 1.2,
          measuredCycles: 8,
          daysCovered: 2,
          measured: true,
          sampleFloor: 5,
        },
        money: {
          trades: 12,
          netReturnPct: 2.5,
          netReturnPctAtStress: 1.8,
          maxDrawdownPct: 3,
          hitRate: 0.6,
          committedCapital: 1000,
          measured: true,
          sampleFloor: 10,
        },
        measured: true,
        unmeasured: [],
      },
    ],
    notes: [],
  },
  notes: [],
};

const CHAIN = {
  available: true,
  readOnly: true,
  accountId: "acc-1",
  asOf: "2026-10-18T20:00:00Z",
  engineId: "auto-sim",
  estudio: { status: "ok", values: 4 },
  summary: {
    values: 4,
    measured: 1,
    complete: 0,
    cycles: 1,
    cyclesComplete: 0,
    bestScoredPresent: true,
  },
  bestScored: {
    runId: "top3-acc-1-1",
    assetId: "inst-1",
    rank: 1,
    combined: 0.81,
    bestScoredPresetKey: null,
    strategyMeasurement: "UNKNOWN",
    rows: [
      { assetId: "inst-1", rank: 1, combined: 0.81, components: { io: 0.7 } },
      { assetId: "inst-2", rank: 2, combined: 0.62, components: {} },
    ],
  },
  values: [
    {
      instrumentId: "inst-1",
      measured: true,
      complete: false,
      unmeasured: [],
      strategy: {
        presetKey: "estudio_auto",
        version: "v1",
        presetKeyAmbiguous: false,
        versionAmbiguous: false,
      },
      strategyDiaD: {
        presetKey: null,
        version: null,
        presetKeyAmbiguous: false,
        versionAmbiguous: false,
        verifications: 0,
      },
      cycles: [
        {
          cycleId: "cyc-aaa-1",
          instrumentId: "inst-1",
          direction: "long",
          closed: true,
          opportunityId: "opp-1",
          entryDay: "2026-10-16",
          exitDay: "2026-10-17",
          executed: {
            strategyPresetKey: "estudio_auto",
            strategyVersion: "v1",
            rank: 1,
            score: 0.71,
            measurement: "COMPLETE",
          },
          bestScored: null,
          executedVsBest: {
            executedIsTopRanked: true,
            executedIsBestScoredAsset: true,
            executedRank: 1,
            bestScoredAssetId: "inst-1",
            bestScoredPresetKey: null,
            presetMatch: null,
            measurement: "COMPLETE",
          },
          steps: {
            SIGNAL: 1,
            TOP_N: 1,
            RISK: 1,
            RESERVATION: 1,
            ORDER: 1,
            FILL: 1,
            PROTECTION: 1,
            SETTLEMENT: null,
            CYCLE_CLOSED: 1,
          },
          chain: {
            reached: [
              "SIGNAL",
              "TOP_N",
              "RISK",
              "RESERVATION",
              "ORDER",
              "FILL",
              "PROTECTION",
              "CYCLE_CLOSED",
            ],
            notReached: { SETTLEMENT: "unknown" },
            complete: false,
            steps: 9,
          },
          pnl: {
            cycleClosedPnl: "12.5",
            settlementPnl: null,
            reconciled: null,
            measurement: "UNKNOWN",
          },
          diaD: null,
          executedVsDiaD: {
            matches: null,
            cyclePresetKey: "estudio_auto",
            diaDPresetKey: null,
            measurement: "UNKNOWN",
          },
          diaDLink: { linkable: false, draft: null, measurement: "UNKNOWN" },
          result: { pnl: "12.5", closedAt: "2026-10-17T15:00:00Z" },
          notes: ["settlement_not_durable"],
        },
      ],
    },
    {
      instrumentId: "inst-2",
      measured: false,
      complete: false,
      unmeasured: ["no_cycles_for_value"],
      strategy: {
        presetKey: null,
        version: null,
        presetKeyAmbiguous: false,
        versionAmbiguous: false,
      },
      strategyDiaD: {
        presetKey: null,
        version: null,
        presetKeyAmbiguous: false,
        versionAmbiguous: false,
        verifications: 0,
      },
      cycles: [],
    },
  ],
  cyclesOutsideEstudio: [],
  meta: { engineId: "auto-sim", limit: 200 },
  limits: ["Read-only"],
  notes: [],
  error: null,
};

const DIA_D_VALUE_ARTIFACT = {
  available: true,
  readOnly: true,
  day: "2026-10-16",
  symbol: "AAA",
  artifactModifiedAt: "2026-10-19T09:00:00Z",
  schemaVersion: "dia-d-auto-v1",
  summary: {
    verdict: "PARTIAL",
    match: 1,
    divergent: 0,
    notMeasured: 1,
    steps: 2,
  },
  steps: [],
  oos: null,
  meta: { account: "acc-1", watch: ["AAA"] },
  limits: [],
  executedDetail: {},
  notes: [],
};

vi.mock("@/lib/api", () => ({
  api: {
    getAutoEstudioDaily: vi.fn(async () => ({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: REPORT,
      notes: [],
    })),
    createAutoEstudioDailyJob: vi.fn(async () => ({
      id: "job-1",
      status: "queued",
    })),
    getAutoOpsJob: vi.fn(),
    listAutoOpsJobs: vi.fn(async () => ({ jobs: [], notes: [] })),
    getAutoEstudioAudit: vi.fn(async () => AUDIT),
    getAutoEstudioChain: vi.fn(async () => CHAIN),
    createAutoDiaDValueReplayJob: vi.fn(async () => ({
      id: "value-job-1",
      kind: "dia_d_value_replay",
      status: "queued",
      day: "2026-10-16",
      accountId: "acc-1",
      payload: { symbol: "AAA" },
    })),
    getAutoDiaDReplayValue: vi.fn(async () => DIA_D_VALUE_ARTIFACT),
  },
}));

import { api } from "@/lib/api";
import { EstudioDailyOpsPanel } from "@/features/auto-monitor/estudio-daily-ops-panel";

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EstudioDailyOpsPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return {
    ...view,
    // El árbol debe recrearse en cada rerender: un elemento idéntico hace que
    // React corte el render y la nueva cuenta nunca llegaría a consultarse.
    rerenderPanel: () =>
      view.rerender(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <EstudioDailyOpsPanel />
          </MemoryRouter>
        </QueryClientProvider>,
      ),
  };
}

afterEach(() => {
  cleanup();
  state.accountId = "acc-1";
  vi.clearAllMocks();
});

describe("EstudioDailyOpsPanel", () => {
  it("pinta los cuatro estados por valor con los niveles del TradePlan", async () => {
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    expect(rows).toHaveLength(4);

    const bySymbol = (symbol: string) =>
      rows.find((row) => row.getAttribute("data-symbol") === symbol);

    const aaa = bySymbol("AAA");
    expect(aaa?.getAttribute("data-status")).toBe("ok");
    // El plan es un dry-run: NUNCA se rotula como «disparado» ni «ejecutado».
    expect(aaa?.textContent).toContain("Plan propuesto");
    expect(aaa?.textContent).not.toContain("Plan disparado");
    expect(aaa?.textContent).toContain("100.00");
    expect(aaa?.textContent).toContain("95.00");
    expect(aaa?.textContent).toContain("110.00");
    // target2 ausente ⇒ «Sin dato todavía», jamás 0.
    expect(
      aaa?.querySelector('[data-testid="estudio-daily-value-plan"]')
        ?.textContent,
    ).toContain("Sin dato todavía");
    expect(aaa?.textContent).toContain("4★");

    const bbb = bySymbol("BBB");
    expect(bbb?.textContent).toContain("Sin plan");
    expect(bbb?.textContent).toContain("gap_risk");

    expect(bySymbol("CCC")?.textContent).toContain("Sin señal");
    expect(bySymbol("DDD")?.textContent).toContain("Error");

    // La vela diaria se declara: verificada con su fecha, o «no verificada» (nunca supuesta).
    expect(
      aaa
        ?.querySelector('[data-testid="estudio-daily-value-bar"]')
        ?.getAttribute("data-bar-verified"),
    ).toBe("true");
    expect(aaa?.textContent).toContain("vela 2026-10-17");
    const ddd = bySymbol("DDD");
    expect(
      ddd
        ?.querySelector('[data-testid="estudio-daily-value-bar"]')
        ?.getAttribute("data-bar-verified"),
    ).toBe("false");
    expect(ddd?.textContent).toContain("vela no verificada");

    expect(screen.getByTestId("estudio-daily-counts").textContent).toContain(
      "4 valores",
    );
  });

  it("une la validación por símbolo y nunca emite CONFIRMED", async () => {
    renderPanel();

    await screen.findAllByTestId("estudio-daily-value");
    const aaa = screen
      .getAllByTestId("estudio-daily-value")
      .find((row) => row.getAttribute("data-symbol") === "AAA");

    const validation = aaa?.querySelector(
      '[data-testid="estudio-daily-value-validation"]',
    );
    expect(validation?.textContent).toContain("K=8");
    expect(validation?.textContent).toContain("+0.40R");
    expect(validation?.textContent).toContain("MIXED");
    expect(
      aaa?.querySelectorAll('[data-testid="estudio-daily-value-cycle"]'),
    ).toHaveLength(1);

    const bbb = screen
      .getAllByTestId("estudio-daily-value")
      .find((row) => row.getAttribute("data-symbol") === "BBB");
    expect(
      bbb?.querySelector(
        '[data-testid="estudio-daily-value-validation-absent"]',
      ),
    ).toBeTruthy();

    const global = screen.getByTestId("estudio-daily-global-validation");
    // O-4: la ventana publica lo que el gate declaró en el DTO; no es texto fijo.
    expect(global.getAttribute("data-verdict")).toBe("MIXED");
    expect(global.textContent).toContain("MIXED");
    expect(global.textContent).toContain("1 de 1 valores");
    expect(global.textContent).not.toContain("CONFIRMED ");
  });

  // O-4 — el veredicto de la ventana es DATO del gate, no una constante de la vista.
  it("lee el veredicto de la ventana del gate y cambia cuando el gate cambia", async () => {
    const withVerdict = (verdict: string) => {
      const audit = structuredClone(AUDIT);
      audit.audit.values = [audit.audit.values[0]];
      audit.audit.values[0].resultR.verdict = verdict;
      return audit;
    };

    vi.mocked(api.getAutoEstudioAudit).mockResolvedValueOnce(
      withVerdict("INCONCLUSIVE") as never,
    );
    renderPanel();
    const measured = await screen.findByTestId(
      "estudio-daily-global-validation",
    );
    expect(measured.getAttribute("data-verdict")).toBe("INCONCLUSIVE");
    expect(measured.textContent).toContain("INCONCLUSIVE");
    expect(measured.textContent).not.toContain("READY");

    cleanup();

    vi.mocked(api.getAutoEstudioAudit).mockResolvedValueOnce(
      withVerdict("READY") as never,
    );
    renderPanel();
    await waitFor(() =>
      expect(
        screen
          .getByTestId("estudio-daily-global-validation")
          .getAttribute("data-verdict"),
      ).toBe("READY"),
    );
    expect(
      screen.getByTestId("estudio-daily-global-validation").textContent,
    ).not.toContain("INCONCLUSIVE");
  });

  it("sin veredicto medido declara NO MEDIDO y no asume el veredicto del gate", async () => {
    const unmeasured = structuredClone(AUDIT);
    unmeasured.audit.values = [unmeasured.audit.values[0]];
    unmeasured.audit.values[0].resultR.measured = false;

    vi.mocked(api.getAutoEstudioAudit).mockResolvedValueOnce(
      unmeasured as never,
    );
    renderPanel();

    const global = await screen.findByTestId("estudio-daily-global-validation");
    expect(global.getAttribute("data-verdict")).toBe("NOT_MEASURED");
    expect(global.getAttribute("data-verdict-measurement")).toBe("UNKNOWN");
    expect(global.textContent).toContain("NO MEDIDO");
    expect(global.textContent).toContain("Sin medición");
    expect(global.textContent).not.toContain("INCONCLUSIVE");
  });

  it("el veredicto del bloque de cadena también se lee del gate", async () => {
    renderPanel();

    const verdicts = await screen.findAllByTestId(
      "estudio-chain-global-validation",
    );
    const measured = verdicts.find(
      (element) => element.getAttribute("data-verdict") === "MIXED",
    );
    expect(measured).toBeTruthy();
    expect(measured?.textContent).toContain("MIXED");
    expect(measured?.textContent).not.toContain("INCONCLUSIVE");
    expect(measured?.textContent).not.toContain("global de la ventana");

    // Un valor sin medición declara el hueco: no hereda el veredicto del vecino.
    const gaps = verdicts.filter(
      (element) => element.getAttribute("data-verdict") === "NOT_MEASURED",
    );
    expect(gaps.length).toBeGreaterThan(0);
    for (const gap of gaps) {
      expect(gap.textContent).toContain("Sin dato todavía");
      expect(gap.textContent).not.toContain("MIXED");
    }
  });

  it("declara la identidad real y no atribuye el histórico por ticker", async () => {
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");

    const strategy = aaa?.querySelector(
      '[data-testid="estudio-daily-value-strategy"]',
    );
    // `presetKey` es el preset de origen, no la identidad de la estrategia.
    expect(strategy?.textContent).toContain("plan-1");
    expect(strategy?.textContent).toContain("preset de origen estudio_auto");
    // R-2: el nivel 1 declara el selector como CLASIFICACIÓN (no como validación).
    expect(strategy?.textContent).toContain(
      "Clasificación del selector: #1 de la foto",
    );

    const scope = aaa?.querySelector(
      '[data-testid="estudio-daily-value-operation-scope"]',
    );
    expect(scope?.getAttribute("data-attributed")).toBe("false");
    expect(scope?.textContent).toContain(
      "Histórico del valor; no atribuido a esta señal",
    );
    // La ventana de la auditoría es visible: no se hace pasar por la del parte.
    expect(scope?.textContent).toContain("2026-10-16_2026-10-17");

    // Enlace contextual al DÍA-D con el día de la vela y el valor.
    const link = aaa?.querySelector<HTMLAnchorElement>(
      '[data-testid="estudio-daily-value-dia-d"]',
    );
    expect(link?.getAttribute("href")).toContain("mode=dia-d");
    expect(link?.getAttribute("href")).toContain("day=2026-10-17");
    expect(link?.getAttribute("href")).toContain("symbol=AAA");
  });

  it("atribuye el histórico por identidad cuando el ciclo publica planId/signalId", async () => {
    const audit = structuredClone(AUDIT);
    const cycle = audit.audit.values[0]!.cycles[0]!;
    cycle.planId = "plan-1";
    cycle.signalId = "sig-inst-1";
    vi.mocked(api.getAutoEstudioAudit).mockResolvedValueOnce(audit as never);

    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const scope = aaa?.querySelector(
      '[data-testid="estudio-daily-value-operation-scope"]',
    );
    // Gap 2: el contrato ya trae la identidad estable y la atribución deja de ser un hueco.
    expect(scope?.getAttribute("data-attributed")).toBe("true");
    expect(scope?.textContent).toContain(
      "Vinculado por identidad (planId/signalId)",
    );
  });

  it("un fallo de la auditoría no se declara como «sin dato»", async () => {
    vi.mocked(api.getAutoEstudioAudit).mockRejectedValueOnce(
      new Error("audit caída"),
    );
    renderPanel();

    const error = await screen.findByTestId("estudio-daily-audit-error");
    expect(error.getAttribute("role")).toBe("alert");
    expect(error.textContent).toContain("audit caída");
    expect(
      screen.queryAllByTestId("estudio-daily-value-validation-absent"),
    ).toHaveLength(0);
    const failed = await screen.findAllByTestId(
      "estudio-daily-value-validation-error",
    );
    expect(failed.length).toBeGreaterThan(0);
  });

  it("declara la cobertura cuando el universo está recortado", async () => {
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: {
        ...REPORT,
        universeCount: 6,
        truncated: true,
        notes: ["Universo recortado a 4 valores (el ESTUDIO tiene más)"],
      },
      notes: [],
    } as never);

    renderPanel();

    const coverage = await screen.findByTestId("estudio-daily-coverage");
    expect(coverage.getAttribute("data-truncated")).toBe("true");
    expect(coverage.textContent).toContain("4 de 6");
    expect(
      screen.getByTestId("estudio-daily-coverage-warning").textContent,
    ).toContain("NO cubre todos los valores");
    expect(
      screen.getByTestId("estudio-daily-report-notes").textContent,
    ).toContain("Universo recortado");
  });

  it("sin parte declara «Sin dato todavía» (no una tabla vacía)", async () => {
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: null,
      notes: ["no_job_for_day"],
    });

    renderPanel();

    const empty = await screen.findByTestId("estudio-daily-empty");
    expect(empty.textContent).toContain("Sin dato todavía");
    expect(screen.queryAllByTestId("estudio-daily-value")).toHaveLength(0);
  });

  it("un error de lectura no se pinta como lista vacía", async () => {
    vi.mocked(api.getAutoEstudioDaily).mockRejectedValueOnce(
      new Error("api caída"),
    );

    renderPanel();

    const error = await screen.findByTestId("estudio-daily-error");
    expect(error.getAttribute("role")).toBe("alert");
    expect(error.textContent).toContain("api caída");
    expect(screen.queryByTestId("estudio-daily-empty")).toBeNull();
  });

  it("el botón encola el job y muestra su progreso", async () => {
    vi.mocked(api.getAutoOpsJob).mockResolvedValue({
      id: "job-1",
      kind: "estudio_daily",
      status: "running",
      day: "2026-10-18",
      accountId: "acc-1",
      payload: {},
      progress: { phase: "opinions", done: 5, total: 10, percent: 50 },
      result: {},
      error: null,
      attempt: 1,
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      heartbeatAt: null,
    } as never);

    renderPanel();

    const run = await screen.findByTestId("estudio-daily-run");
    fireEvent.click(run);

    await waitFor(() =>
      expect(api.createAutoEstudioDailyJob).toHaveBeenCalledWith({
        day: expect.any(String),
      }),
    );
    const progress = await screen.findByTestId("estudio-daily-job-progress");
    expect(progress.getAttribute("data-phase")).toBe("opinions");
    expect(progress.textContent).toContain("50%");
  });

  it("rehidrata el job durable del día al montar (sin volver a encolarlo)", async () => {
    vi.mocked(api.listAutoOpsJobs).mockResolvedValueOnce({
      jobs: [
        {
          id: "job-7",
          kind: "estudio_daily",
          status: "running",
          day: "2026-10-18",
          accountId: "acc-1",
          payload: {},
          progress: { phase: "opinions", done: 4, total: 10, percent: 40 },
          result: {},
          error: null,
          attempt: 1,
          createdAt: null,
          startedAt: null,
          finishedAt: null,
          heartbeatAt: null,
        },
      ],
      notes: [],
    } as never);
    vi.mocked(api.getAutoOpsJob).mockResolvedValue({
      id: "job-7",
      kind: "estudio_daily",
      status: "running",
      day: "2026-10-18",
      accountId: "acc-1",
      payload: {},
      progress: { phase: "opinions", done: 4, total: 10, percent: 40 },
      result: {},
      error: null,
      attempt: 1,
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      heartbeatAt: null,
    } as never);

    renderPanel();

    const progress = await screen.findByTestId("estudio-daily-job-progress");
    expect(progress.getAttribute("data-phase")).toBe("opinions");
    expect(progress.textContent).toContain("40%");
    expect(api.createAutoEstudioDailyJob).not.toHaveBeenCalled();
    expect(api.getAutoOpsJob).toHaveBeenCalledWith("job-7");
  });

  it("cambiar de cuenta no reutiliza el parte de la cuenta anterior", async () => {
    const { rerenderPanel } = renderPanel();
    await screen.findAllByTestId("estudio-daily-value");
    const callsBefore = vi.mocked(api.getAutoEstudioDaily).mock.calls.length;

    state.accountId = "acc-2";
    rerenderPanel();

    await waitFor(() =>
      expect(
        vi.mocked(api.getAutoEstudioDaily).mock.calls.length,
      ).toBeGreaterThan(callsBefore),
    );
    // La clave de la query incluye la cuenta (no hay caché compartida).
    expect(api.getAutoEstudioDaily).toHaveBeenCalled();
  });

  it("sin cuenta activa deshabilita el cálculo y lo declara", async () => {
    state.accountId = null;
    renderPanel();

    const run = await screen.findByTestId("estudio-daily-run");
    expect((run as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId("estudio-daily-no-account")).toBeTruthy();
  });

  it("pinta la cadena durable: nueve etapas, huecos declarados y P&L sin inventar", async () => {
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const chainSection = aaa?.querySelector(
      '[data-testid="estudio-daily-value-chain"]',
    );
    expect(chainSection).toBeTruthy();
    expect(chainSection?.getAttribute("data-chain-measured")).toBe("true");
    expect(chainSection?.textContent).toContain("Cadena histórica del valor");
    expect(chainSection?.textContent).toContain("plan-1");

    // Las NUEVE etapas se enumeran siempre; la ausente viaja como hueco, nunca como 0.
    const steps = aaa?.querySelectorAll('[data-testid="estudio-chain-step"]');
    expect(steps).toHaveLength(9);
    const settlement = aaa?.querySelector(
      '[data-testid="estudio-chain-step"][data-step="SETTLEMENT"]',
    );
    expect(settlement?.getAttribute("data-reached")).toBe("false");
    expect(settlement?.textContent).toContain("sin dato");

    const operation = aaa?.querySelector(
      '[data-testid="estudio-chain-operation"]',
    );
    expect(operation?.textContent).toContain("2026-10-16 → 2026-10-17");
    // Sin liquidación no se puede afirmar la conciliación: «Sin dato», no «No».
    expect(operation?.textContent).toContain("Sin dato (no se puede afirmar)");

    // Un valor sin ciclos declara el hueco en vez de una cadena vacía «correcta».
    const bbb = rows.find((row) => row.getAttribute("data-symbol") === "BBB");
    expect(
      bbb
        ?.querySelector('[data-testid="estudio-daily-value-chain"]')
        ?.getAttribute("data-chain-measured"),
    ).toBe("false");
    expect(
      bbb?.querySelector('[data-testid="estudio-chain-absent"]'),
    ).toBeNull();
    expect(
      bbb?.querySelector('[data-testid="estudio-chain-operation"]')
        ?.textContent,
    ).toContain("no_cycles_for_value");
  });

  it("declara el hueco cuando la foto no sella la identidad del ganador", async () => {
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const why = aaa?.querySelector('[data-testid="estudio-chain-why"]');

    expect(why?.textContent).toContain("puesto 1");
    expect(why?.textContent).toContain("top del ranking: Sí");
    expect(why?.textContent).toContain("activo mejor puntuado: Sí");
    // Nunca se supone que la #1 fue la ejecutada sin término de comparación.
    expect(why?.textContent).toContain("no se empareja por estrategia");
    expect(why?.textContent).toContain(
      "misma estrategia que la ejecutada: Sin dato (no se puede afirmar)",
    );
    expect(
      aaa?.querySelector('[data-testid="estudio-chain-top3"]')?.textContent,
    ).toContain("#1 inst-1");

    const attribution = aaa?.querySelector(
      '[data-testid="estudio-chain-attribution"]',
    );
    expect(attribution?.textContent).toBe(
      "Cadena histórica del valor; no atribuida a esta señal",
    );
  });

  it("publica la identidad del ganador y contrasta el preset (coincidencia)", async () => {
    const withIdentity = structuredClone(CHAIN);
    withIdentity.bestScored = {
      ...withIdentity.bestScored,
      bestScoredPresetKey: "estudio_auto",
      bestScoredStrategyVersion: "v1",
      strategyMeasurement: "COMPLETE",
      rows: [
        {
          assetId: "inst-1",
          rank: 1,
          combined: 0.81,
          components: { io: 0.7 },
          strategyPresetKey: "estudio_auto",
          strategyVersion: "v1",
        },
        { assetId: "inst-2", rank: 2, combined: 0.62, components: {} },
      ],
    };
    const compare = withIdentity.values[0].cycles[0].executedVsBest;
    compare.bestScoredPresetKey = "estudio_auto";
    compare.bestScoredStrategyVersion = "v1";
    compare.presetMatch = true;
    compare.versionMatch = true;
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce(
      withIdentity as never,
    );

    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const why = aaa?.querySelector('[data-testid="estudio-chain-why"]');
    expect(why?.textContent).toContain("preset estudio_auto");
    expect(why?.textContent).toContain("estudio_auto v1");
    expect(why?.textContent).not.toContain("vv1");
    expect(why?.textContent).toContain("misma estrategia que la ejecutada: Sí");
    expect(why?.textContent).toContain("misma versión: Sí");
    // La línea TOP3 anexa la identidad SOLO si la foto la declara.
    const top3 = aaa?.querySelector(
      '[data-testid="estudio-chain-top3"]',
    )?.textContent;
    expect(top3).toContain("#1 inst-1");
    expect(top3).toContain("estudio_auto v1");
  });

  it("no duplica el prefijo de versión en la estrategia EJECUTADA (v1 y 1)", async () => {
    const executedLine = () =>
      screen.getByTestId("estudio-chain-executed-strategy").textContent ?? "";

    // El fixture ya declara `v1`: el rótulo no debe convertirlo en `vv1`.
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce(
      structuredClone(CHAIN) as never,
    );
    renderPanel();
    await screen.findAllByTestId("estudio-daily-value");
    expect(executedLine()).toContain("estudio_auto · v1");
    expect(executedLine()).not.toContain("vv1");
    cleanup();

    // Una versión desnuda (`1`) recibe UN prefijo, nunca dos.
    const bare = structuredClone(CHAIN);
    bare.values[0].cycles[0].executed.strategyVersion = "1";
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce(bare as never);
    renderPanel();
    await screen.findAllByTestId("estudio-daily-value");
    expect(executedLine()).toContain("estudio_auto · v1");
    expect(executedLine()).not.toContain("v1v1");
    cleanup();

    // Un hueco se rotula como tal: no se fabrica un `vSin dato todavía`.
    const withoutVersion = structuredClone(CHAIN);
    withoutVersion.values[0].cycles[0].executed.strategyVersion = null;
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce(
      withoutVersion as never,
    );
    renderPanel();
    await screen.findAllByTestId("estudio-daily-value");
    expect(executedLine()).toContain("Sin dato todavía");
    expect(executedLine()).not.toContain("vSin");
  });

  it("declara un preset distinto como divergencia MEDIDA, no como hueco", async () => {
    const divergent = structuredClone(CHAIN);
    divergent.bestScored = {
      ...divergent.bestScored,
      bestScoredPresetKey: "trend_other",
      bestScoredStrategyVersion: "v9",
      strategyMeasurement: "COMPLETE",
    };
    const compare = divergent.values[0].cycles[0].executedVsBest;
    compare.bestScoredPresetKey = "trend_other";
    compare.bestScoredStrategyVersion = "v9";
    compare.presetMatch = false;
    compare.versionMatch = false;
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce(
      divergent as never,
    );

    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const why = aaa?.querySelector('[data-testid="estudio-chain-why"]');
    expect(why?.textContent).toContain("preset trend_other");
    expect(why?.textContent).toContain("misma estrategia que la ejecutada: No");
    expect(why?.textContent).toContain("misma versión: No");
    // Un False medido NO se disfraza de «no se empareja por estrategia».
    expect(why?.textContent).not.toContain("no se empareja por estrategia");
  });

  it("declara identidad PARCIAL cuando solo se pudo contrastar uno de los dos términos", async () => {
    const partial = structuredClone(CHAIN);
    partial.bestScored = {
      ...partial.bestScored,
      bestScoredPresetKey: "estudio_auto",
      strategyMeasurement: "PARTIAL",
    };
    const compare = partial.values[0].cycles[0].executedVsBest;
    compare.bestScoredPresetKey = "estudio_auto";
    compare.presetMatch = true;
    compare.versionMatch = null;
    compare.strategyMeasurement = "PARTIAL";
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce(partial as never);

    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const why = aaa?.querySelector('[data-testid="estudio-chain-why"]');
    expect(why?.textContent).toContain("misma estrategia que la ejecutada: Sí");
    // La media identidad se declara: no se disfraza de COMPLETE ni de hueco.
    expect(why?.textContent).toContain("identidad: parcial");
    expect(why?.textContent).not.toContain("no se empareja por estrategia");
  });

  it("el botón verifica el DÍA-D del valor y declara el día usado", async () => {
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const verify = aaa?.querySelector<HTMLButtonElement>(
      '[data-testid="estudio-chain-dia-d-verify"]',
    );
    expect(verify).toBeTruthy();
    // Día = entryDay del ciclo (hecho durable), declarado como tal.
    const block = aaa?.querySelector('[data-testid="estudio-chain-dia-d"]');
    expect(block?.getAttribute("data-day")).toBe("2026-10-16");
    expect(block?.getAttribute("data-day-source")).toBe("cycle");

    fireEvent.click(verify as HTMLButtonElement);

    await waitFor(() =>
      expect(api.createAutoDiaDValueReplayJob).toHaveBeenCalledTimes(1),
    );
    expect(api.createAutoDiaDValueReplayJob).toHaveBeenCalledWith({
      day: "2026-10-16",
      symbol: "AAA",
    });
    // El artefacto por valor se lee aparte, con el símbolo exacto.
    await waitFor(() =>
      expect(api.getAutoDiaDReplayValue).toHaveBeenCalledWith(
        "2026-10-16",
        "AAA",
      ),
    );
    const artifact = await screen.findByTestId("estudio-chain-dia-d-artifact");
    expect(artifact.textContent).toContain("PARTIAL");
    expect(artifact.textContent).toContain("AAA");
  });

  it("declara la verificación ocupada por otro valor del mismo día", async () => {
    vi.mocked(api.createAutoDiaDValueReplayJob).mockResolvedValueOnce({
      id: "value-job-other",
      kind: "dia_d_value_replay",
      status: "running",
      day: "2026-10-16",
      accountId: "acc-1",
      payload: { symbol: "BBB" },
    } as never);
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    fireEvent.click(
      aaa?.querySelector(
        '[data-testid="estudio-chain-dia-d-verify"]',
      ) as HTMLButtonElement,
    );

    const occupied = await screen.findByTestId("estudio-chain-dia-d-occupied");
    expect(occupied.textContent).toContain("BBB");
    expect(
      aaa?.querySelector('[data-testid="estudio-chain-dia-d-job"]'),
    ).toBeNull();
  });

  it("la cola se explica con la verdad de servidor y declara el alcance del artefacto", async () => {
    vi.mocked(api.createAutoDiaDValueReplayJob).mockResolvedValueOnce({
      id: "value-job-other",
      kind: "dia_d_value_replay",
      status: "running",
      day: "2026-10-16",
      accountId: "acc-1",
      payload: { symbol: "BBB" },
      slot: {
        state: "active_other_symbol",
        activeJobId: "value-job-other",
        activeSymbol: "BBB",
        requestedSymbol: "AAA",
        matchesRequest: false,
        startedAt: "2026-10-16T09:00:00Z",
        message:
          "Verificación en curso para BBB (job value-job-other, iniciada 2026-10-16T09:00:00Z). La cola admite una por cuenta y día: AAA NO se ha encolado; vuelve a pedirlo cuando termine la actual.",
      },
    } as never);
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    fireEvent.click(
      aaa?.querySelector(
        '[data-testid="estudio-chain-dia-d-verify"]',
      ) as HTMLButtonElement,
    );

    const occupied = await screen.findByTestId("estudio-chain-dia-d-occupied");
    // El mensaje lo compone el servidor; la UI no deduce la verdad de la cola.
    expect(occupied.getAttribute("data-slot-state")).toBe(
      "active_other_symbol",
    );
    expect(occupied.textContent).toContain(
      "La cola admite una por cuenta y día",
    );
    expect(occupied.textContent).toContain("AAA NO se ha encolado");

    const scope = aaa?.querySelector(
      '[data-testid="estudio-chain-dia-d-scope"]',
    );
    expect(scope?.textContent).toContain("Día solicitado 2026-10-16");
    expect(scope?.textContent).toContain("origen: cycle");
    expect(scope?.textContent).toContain("solo lectura");
  });

  it("un fallo de la cadena no se pinta como lista vacía", async () => {
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce({
      ...CHAIN,
      available: false,
      summary: null,
      values: [],
      notes: ["read_failed"],
      error: "RuntimeError: db caída",
    } as never);
    renderPanel();

    const error = await screen.findByTestId("estudio-chain-error");
    expect(error.getAttribute("role")).toBe("alert");
    expect(error.textContent).toContain("db caída");
  });

  it("la cadena se consulta UNA vez por informe, no una por valor", async () => {
    renderPanel();

    await screen.findAllByTestId("estudio-daily-value");
    await waitFor(() =>
      expect(api.getAutoEstudioChain).toHaveBeenCalledTimes(1),
    );
  });

  it("un payload sin forma (mock/proxy) no tumba la ficha: se declara el hueco", async () => {
    // Un fallback `{ data: [] }` (mock E2E sin ruta, proxy o versión antigua) no es
    // `EstudioChainResponseV1`: antes se leía como objeto y `notes.join` rompía el informe.
    vi.mocked(api.getAutoEstudioChain).mockResolvedValueOnce([] as never);
    renderPanel();

    const values = await screen.findAllByTestId("estudio-daily-value");
    expect(values.length).toBeGreaterThan(0);
    expect((await screen.findAllByTestId("estudio-chain-absent")).length).toBe(
      values.length,
    );
    expect(screen.queryByTestId("estudio-chain-error")).toBeNull();
  });

  it("R-2: la nota cruda no se pinta en nivel 1 y sí en el detalle técnico", async () => {
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: {
        ...REPORT,
        notes: ["composite_chips_unavailable:3_ids"],
      },
      notes: ["positions_unavailable"],
    } as never);

    renderPanel();

    const responseNotes = await screen.findByTestId("estudio-daily-notes");
    // La frase de nivel 1 no expone el código crudo (la lista visible, no el disclosure)…
    const level1 = responseNotes.querySelector("ul");
    expect(level1?.textContent).toContain("No se pudo leer tu cartera");
    expect(level1?.textContent).not.toContain("positions_unavailable");
    // …pero el crudo sigue accesible dentro del disclosure técnico.
    const technical = screen.getByTestId("estudio-daily-notes-technical");
    expect(technical.textContent).toContain("positions_unavailable");

    const reportNotes = screen.getByTestId("estudio-daily-report-notes");
    const reportLevel1 = reportNotes.querySelector("ul");
    expect(reportLevel1?.textContent).toContain(
      "No se pudieron leer los indicadores del motor en 3 valores",
    );
    expect(reportLevel1?.textContent).not.toContain(
      "composite_chips_unavailable:3_ids",
    );
  });

  it("R-3: un parte partial se pinta con su banner y sus valores", async () => {
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: {
        ...REPORT,
        status: "partial",
        degraded: true,
        degradedReasons: ["positions_unavailable"],
        coverage: { positionsMeasured: false },
      },
      notes: [],
    } as never);

    renderPanel();

    const banner = await screen.findByTestId("estudio-daily-partial");
    expect(banner.textContent).toContain("Parte parcial");
    expect(banner.textContent).toContain("No se pudo leer tu cartera");
    // El parte NO se oculta por ser parcial: los valores siguen visibles.
    expect(
      (await screen.findAllByTestId("estudio-daily-value")).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByTestId("estudio-daily-universe-gap")).toBeNull();
  });

  it("H-145-1: la cartera sin medir se declara «Cartera sin medida», no «sin posición»", async () => {
    const withUnknown = structuredClone(REPORT);
    withUnknown.values[2] = {
      ...withUnknown.values[2]!,
      positionOpen: null,
    };
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: withUnknown,
      notes: [],
    } as never);

    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const ccc = rows.find((row) => row.getAttribute("data-symbol") === "CCC");
    const position = ccc?.querySelector(
      '[data-testid="estudio-daily-value-position"]',
    );
    expect(position?.getAttribute("data-position-open")).toBe("unknown");
    expect(position?.textContent).toContain("Cartera sin medida");
    expect(position?.textContent).not.toContain("Sin posición abierta");
    expect(
      ccc?.querySelector('[data-testid="estudio-daily-value-position-gap"]')
        ?.textContent,
    ).toContain("Sin dato de cartera");
  });

  it("Gap 1: distingue planId (plan) de proposeRunId (corrida de propuesta)", async () => {
    const withRun = structuredClone(REPORT);
    withRun.values[0] = {
      ...withRun.values[0]!,
      strategy: {
        ...withRun.values[0]!.strategy!,
        planId: "tp-plan-1",
        proposeRunId: "scan-9",
      },
    };
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: withRun,
      notes: [],
    } as never);

    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const identity = aaa?.querySelector(
      '[data-testid="estudio-daily-value-strategy-identity"]',
    );
    expect(identity?.textContent).toContain("plan tp-plan-1");
    expect(identity?.textContent).toContain("corrida de propuesta scan-9");
  });

  it("Gap 1: un valor que no es el ganador lo declara sin cambiar la propuesta", async () => {
    const notWinner = structuredClone(REPORT);
    notWinner.values[1] = {
      ...notWinner.values[1]!,
      selector: {
        measured: true,
        runId: "top3-acc-1-2026-10-18T08:00:00Z",
        bar: "2026-10-18T08:00:00Z",
        assetId: "inst-1",
        presetKey: "estudio_auto",
        strategyVersion: "1",
        isWinner: false,
        reason: null,
      },
    };
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: notWinner,
      notes: [],
    } as never);

    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const bbb = rows.find((row) => row.getAttribute("data-symbol") === "BBB");
    const winner = bbb?.querySelector(
      '[data-testid="estudio-daily-value-strategy-winner"]',
    );
    expect(winner?.getAttribute("data-selector-winner")).toBe("false");
    expect(winner?.textContent).toContain(
      "Clasificación del selector: no es la primera de la foto",
    );
    // El estado del valor NO se degrada por no ser el ganador del selector.
    expect(bbb?.getAttribute("data-status")).toBe("no_plan");
  });

  it("responde las cuatro preguntas en la ficha y deja las ids en el desplegable", async () => {
    renderPanel();

    const rows = await screen.findAllByTestId("estudio-daily-value");
    const aaa = rows.find((row) => row.getAttribute("data-symbol") === "AAA");
    const summary = aaa?.querySelector(
      '[data-testid="estudio-daily-value-summary"]',
    );
    expect(summary).not.toBeNull();

    const proposal = aaa?.querySelector(
      '[data-testid="estudio-daily-value-summary-proposal"]',
    );
    expect(proposal?.textContent).toContain("Propone una compra");
    expect(proposal?.textContent).toContain("100");
    expect(proposal?.textContent).toContain("¿Qué propone?");

    const why = aaa?.querySelector(
      '[data-testid="estudio-daily-value-summary-why"]',
    );
    expect(why?.textContent).toContain("¿Por qué?");
    expect(why?.textContent).toContain("momentum");

    const missing = aaa?.querySelector(
      '[data-testid="estudio-daily-value-summary-missing"]',
    );
    expect(missing?.textContent).toContain("¿Qué falta para actuar?");

    const validation = aaa?.querySelector(
      '[data-testid="estudio-daily-value-summary-validation"]',
    );
    expect(validation?.textContent).toContain("¿Está validada?");
    // La ficha NO afirma validación: dice «no validada» con la K del audit.
    expect(validation?.textContent).toContain("no validada");
    expect(validation?.textContent).toContain("K=8");
    expect(validation?.textContent).not.toContain("estadística: validada");
    expect(summary?.getAttribute("data-validation")).toBe("false");

    const classification = aaa?.querySelector(
      '[data-testid="estudio-daily-value-summary-classification"]',
    );
    expect(classification?.textContent).toContain("#1 de la foto");
    expect(classification?.textContent).toContain("NO una validación");
    expect(classification?.getAttribute("data-rank")).toBe("1");

    // Los ids técnicos viven detrás del disclosure cerrado por defecto.
    const technical = aaa?.querySelector<HTMLDetailsElement>(
      '[data-testid="estudio-daily-value-technical"]',
    );
    expect(technical).not.toBeNull();
    expect(technical?.open).toBe(false);
    expect(technical?.textContent).toContain("plan-1");
  });

  it("separación explícita: la leyenda no usa «mejor» como sinónimo de validada", async () => {
    renderPanel();

    const legend = await screen.findByTestId("estudio-daily-legend");
    expect(legend.textContent).toContain("Clasificación ≠ validación");
    const separation = screen.getByTestId("estudio-daily-legend-separation");
    expect(separation.textContent).toContain("ranking del día");
    // O-4: la leyenda explica la separación; NO escribe el veredicto del gate.
    expect(separation.textContent).toContain("lo emite el gate");
    expect(separation.textContent).not.toContain("INCONCLUSIVE");
  });

  it("publica la cobertura reconciliable con los ausentes y su motivo", async () => {
    const withUniverse = structuredClone(REPORT);
    Object.assign(withUniverse, {
      universeCount: 6,
      universe: {
        expectedCount: 6,
        expectedIds: [
          "inst-1",
          "inst-2",
          "inst-3",
          "inst-4",
          "inst-5",
          "inst-6",
        ],
        scannedIds: ["inst-1", "inst-2", "inst-3", "inst-4"],
        excluded: [{ instrumentId: "inst-6", reason: "max_values_truncated" }],
        missing: [{ instrumentId: "inst-5", reason: "no_terminal_state" }],
        reconciled: false,
        complete: false,
        reason: "universe_truncated",
      },
    });
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: withUniverse,
      notes: [],
    } as never);

    renderPanel();

    const coverage = await screen.findByTestId("estudio-daily-coverage");
    expect(coverage.textContent).toContain("Cobertura: 4 de 6");
    expect(coverage.textContent).toContain("faltan 1");
    expect(coverage.getAttribute("data-reconciled")).toBe("false");

    const missing = screen.getByTestId("estudio-daily-universe-missing");
    expect(missing.textContent).toContain("inst-5");
    expect(missing.textContent).toContain("no_terminal_state");
    const excluded = screen.getByTestId("estudio-daily-universe-excluded");
    expect(excluded.textContent).toContain("inst-6");
    expect(excluded.textContent).toContain("max_values_truncated");
  });

  it("un parte reconciliado no declara hueco de cobertura", async () => {
    const withUniverse = structuredClone(REPORT);
    Object.assign(withUniverse, {
      universeCount: 4,
      universe: {
        expectedCount: 4,
        expectedIds: ["inst-1", "inst-2", "inst-3", "inst-4"],
        scannedIds: ["inst-1", "inst-2", "inst-3", "inst-4"],
        excluded: [],
        missing: [],
        reconciled: true,
        complete: true,
        reason: null,
      },
    });
    vi.mocked(api.getAutoEstudioDaily).mockResolvedValueOnce({
      asOf: "2026-10-18",
      accountId: "acc-1",
      job: null,
      latestJob: null,
      report: withUniverse,
      notes: [],
    } as never);

    renderPanel();

    const coverage = await screen.findByTestId("estudio-daily-coverage");
    expect(coverage.textContent).toContain("conjunto reconciliado");
    expect(coverage.getAttribute("data-reconciled")).toBe("true");
    expect(screen.queryByTestId("estudio-daily-coverage-warning")).toBeNull();
  });
});
