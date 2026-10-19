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
    expect(global.textContent).toContain("INCONCLUSIVE");
    expect(global.textContent).not.toContain("CONFIRMED ");
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
    expect(strategy?.textContent).toContain("Indicador ganador: no declarado");

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
});
