/**
 * AUTO UI REFACTOR 3.0 — operación única en tres bloques.
 *
 * Monta el panel real con la API mockeada y comprueba que los hechos de OPERACIÓN se pintan en
 * orden (sin OPPORTUNITY, que va al bloque `context`, y sin EXPLANATION, que va a «Qué
 * aprendemos»), que un paso sin traza se rotula, y que la etapa EXPLANATION enlaza al heatmap
 * DÍA-D con símbolo/ventana preseleccionados.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";

vi.mock("@/lib/api", () => ({
  api: {
    getAutoOperationalMonitor: vi.fn(async () => ({
      key: "auto_operational_monitor_v1",
      readOnly: true,
      accountId: "acc-1",
      asOf: "2026-10-01T00:00:00Z",
      header: {
        engineId: "auto-sim",
        state: "RUNNING",
        venue: "paper",
        granularity: { decision: "1d", execution: "signal_bar" },
        decisionClock: "CLOSED BAR",
        executionDeclared: "next_bar_open",
        executionEnabled: false,
        protectionModel: "bar_ohlc",
        heartbeatSeconds: 60,
        graceSeconds: 61,
        lastHeartbeatAt: "2026-10-01T09:00:00Z",
        lastHeartbeatMeasurement: "COMPLETE",
        lastDecisionAt: "2026-09-30T23:00:00Z",
        lastDecisionMeasurement: "COMPLETE",
        nextDecisionAt: "2026-10-01T00:01:00Z",
        realPriceEnabled: false,
        heartbeatsPersisted: 42,
        asOf: "2026-10-01T00:00:00Z",
      },
      cycles: [
        {
          cycleId: "cyc-1",
          instrumentId: "AAA",
          strategyPresetKey: "sma_crossover",
          strategyVersion: "sv-1",
          direction: "long",
          closed: true,
          closedMeasurement: "COMPLETE",
          steps: [
            {
              id: "SIGNAL",
              state: "reached",
              at: "2026-09-29T20:00:00Z",
              measurement: "COMPLETE",
              facts: [{ key: "rank", value: 1, measurement: "COMPLETE" }],
              note: null,
            },
            {
              id: "TOP_N",
              state: "reached",
              at: "2026-09-29T20:00:01Z",
              measurement: "COMPLETE",
              facts: [],
              note: null,
            },
            {
              id: "FILL",
              state: "reached",
              at: "2026-09-30T09:00:00Z",
              measurement: "COMPLETE",
              facts: [],
              note: null,
            },
          ],
          result: { pnl: 250, closedAt: "2026-10-01T15:00:00Z" },
          notes: [],
        },
      ],
      reservations: [],
      concurrency: {
        activeSessions: 0,
        activeSessionsMeasurement: "COMPLETE",
        heartbeatsPersisted: 42,
        claimAttempts: 0,
        claimAttemptsMeasurement: "COMPLETE",
        successfulClaims: 0,
        successfulClaimsMeasurement: "COMPLETE",
        lostClaims: 0,
        lostClaimsMeasurement: "COMPLETE",
        raceConflicts: 0,
        raceConflictsMeasurement: "COMPLETE",
        reconciliations: 0,
        reconciliationsMeasurement: "COMPLETE",
        graceWindowKeeps: 0,
        graceWindowKeepsMeasurement: "COMPLETE",
        forcedReleases: 0,
        forcedReleasesMeasurement: "COMPLETE",
        lastConflict: null,
        lastConflictMeasurement: "COMPLETE",
      },
      notes: [],
    })),
    getAutoDiaDFeedbackList: vi.fn(async () => ({
      readOnly: true,
      windows: ["2026-09-29_2026-09-30"],
      latest: "2026-09-29_2026-09-30",
      artifact: {
        available: true,
        window: {
          from: "2026-09-29",
          to: "2026-09-30",
          days: ["2026-09-29", "2026-09-30"],
        },
        values: [
          {
            symbol: "AAA",
            verdict: "OOS_SUPPORTED",
            verdictReason: "positive_expectancy",
            evidenceQuality: "PRELIMINARY",
            expectancyR: 0.5,
            hitRate: 0.67,
            measuredCycles: 6,
            daysCovered: 1,
            windowDays: 2,
            errorTotal: 0,
          },
        ],
        cycles: [
          {
            cycleId: "cyc-1",
            symbol: "AAA",
            entryDay: "2026-09-29",
            exitDay: "2026-09-30",
            strategyVersion: "sv-1",
            realizedR: 0.5,
          },
        ],
      },
      notes: [],
    })),
    // Puente P3/P4: resolución ticker → UUID → TOP de Finalistas → definición de la estrategia #1.
    getInstruments: vi.fn(async () => ({
      data: [{ id: "uuid-aaa", symbol: "AAA", name: "AAA Corp" }],
    })),
    getInstrumentStrategyTop: vi.fn(async () => ({
      data: {
        id: "top-aaa",
        instrumentId: "uuid-aaa",
        symbol: "AAA",
        timeframe: "1d",
        status: "active",
        version: 1,
        evidenceLevel: "lab_validated",
        slots: [
          {
            rank: 1,
            label: "SMA cross",
            stars: 3,
            score: 70,
            source: "coach",
            strategyDefinitionId: "def-1",
            strategyType: "sma_crossover",
          },
        ],
        coachFacts: {
          recommendations: [{ rank: 1, reasons: ["Estrellas 3/5", "DD -12%"] }],
        },
        createdAt: "2026-10-01T00:00:00Z",
        updatedAt: "2026-10-01T00:00:00Z",
      },
    })),
    getStrategy: vi.fn(async () => ({
      data: {
        definition: {
          indicatorSpecs: [{ definitionId: "rsi", parameters: { period: 14 } }],
          presetKey: "sma_crossover",
        },
      },
    })),
    // P2 — registro durable que enlaza la verificación D→hoy con el ciclo.
    listDiaDCycleVerifications: vi.fn(
      async (): Promise<
        import("@bolsa/shared").DiaDCycleVerificationListV1Dto
      > => ({
        data: [],
        total: 0,
        notes: [],
      }),
    ),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
    accounts: [],
  }),
}));

import {
  AutoOperationStoryPanel,
  resolveAutoOperationSelection,
  resolveExplanationForCycle,
} from "@/features/auto-monitor/auto-operation-story-panel";
import { useDiaDTradingSessionStore } from "@/stores/dia-d-trading-session-store";
import { api } from "@/lib/api";

function LocationProbe() {
  const location = useLocation();
  return (
    <span data-testid="story-location">
      {location.pathname}
      {location.search}
    </span>
  );
}

function renderPanel(options?: {
  cycleIdOverride?: string | null;
  initialEntries?: string[];
}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={
          options?.initialEntries ?? ["/auto-monitor?mode=operation"]
        }
      >
        <AutoOperationStoryPanel cycleIdOverride={options?.cycleIdOverride} />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useDiaDTradingSessionStore.getState().exitSession();
});

describe("AutoOperationStoryPanel", () => {
  it("pinta las 11 filas de operación (OPPORTUNITY fuera, POSITION plegada, EXPLANATION aparte)", async () => {
    renderPanel();

    // El selector de ciclos sólo aparece con el monitor cargado: esperar a él evita asertar
    // sobre la historia vacía del primer render.
    await waitFor(() =>
      expect(screen.getByTestId("auto-operation-story-cycles")).toBeTruthy(),
    );

    const stages = screen.getAllByTestId("auto-operation-story-stage");
    expect(stages.map((stage) => stage.getAttribute("data-stage"))).toEqual([
      "SIGNAL",
      "SELECTION",
      "DECISION",
      "RISK",
      "RESERVATION",
      "ORDER",
      "FILL",
      "PROTECTION",
      "EXIT",
      "SETTLEMENT",
      "RESULT",
    ]);
    // Todas son hechos de la operación: OPPORTUNITY vive en el bloque `context` y EXPLANATION
    // (cross-ciclo) vive en su propio bloque «¿Qué aprendemos?».
    expect(
      stages.every((stage) => stage.getAttribute("data-group") === "OPERATION"),
    ).toBe(true);

    const byStage = new Map(
      stages.map((stage) => [stage.getAttribute("data-stage"), stage]),
    );
    // POSITION se pliega en FILL: el precio no se pinta como posición hecha.
    expect(byStage.has("POSITION")).toBe(false);
    expect(byStage.get("FILL")?.textContent).toContain("no afirma la posición");
    expect(byStage.get("FILL")?.textContent).toContain("Precio aplicado");
    // EXIT es fila PROPIA (H3). El mock de este test no trae paso SETTLEMENT, así que la salida
    // se declara NO MEDIDA (hueco), nunca inventada.
    expect(byStage.has("EXIT")).toBe(true);
    expect(byStage.get("EXIT")?.getAttribute("data-state")).toBe(
      "NOT_MEASURED",
    );

    expect(byStage.get("SIGNAL")?.getAttribute("data-state")).toBe("REACHED");
    expect(byStage.get("SELECTION")?.getAttribute("data-state")).toBe(
      "REACHED",
    );
    // PROTECTION no está en el ciclo ⇒ NO MEDIDO (jamás `reached` ni `0`).
    expect(byStage.get("PROTECTION")?.getAttribute("data-state")).toBe(
      "NOT_MEASURED",
    );
    // DECISION no se iguala a TOP_N: no hay traza durable ⇒ NO MEDIDO.
    expect(byStage.get("DECISION")?.getAttribute("data-state")).toBe(
      "NOT_MEASURED",
    );
  });

  it("enciende la etapa DECISION con los reasonCodes durables del ciclo (H4)", async () => {
    const monitor = await vi.mocked(api.getAutoOperationalMonitor)();
    vi.mocked(api.getAutoOperationalMonitor).mockResolvedValueOnce({
      ...monitor,
      cycles: (monitor.cycles ?? []).map((cycle, index) =>
        index === 0
          ? {
              ...cycle,
              decision: {
                decisionId: "dec-cyc-1",
                approved: true,
                action: "OPEN",
                opportunityId: "opp-1",
                reasonCodes: ["approved", "trend"],
                at: "2026-09-29T20:00:00Z",
                measurement: "COMPLETE",
              },
            }
          : cycle,
      ),
    });

    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("auto-operation-story-cycles")).toBeTruthy(),
    );

    const decisions = screen
      .getAllByTestId("auto-operation-story-stage")
      .filter((stage) => stage.getAttribute("data-stage") === "DECISION");
    expect(decisions).toHaveLength(1);
    // El hecho durable de cartera enciende la etapa y publica el motivo (no «sin traza»).
    expect(decisions[0].getAttribute("data-state")).toBe("REACHED");
    expect(decisions[0].textContent).toContain("reasonCodes");
    expect(decisions[0].textContent).toContain("approved");
  });

  it("declara el contexto que originó la operación (universo PIT sin medir)", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("auto-operation-story-cycles")).toBeTruthy(),
    );

    const pit = screen
      .getAllByTestId("auto-operation-story-context-item")
      .find((item) => item.getAttribute("data-context-id") === "PIT_UNIVERSE");
    expect(pit?.getAttribute("data-measurement")).toBe("UNKNOWN");
    expect(pit?.textContent).toContain("NO MEDIDO");
  });

  it("muestra la estrategia #1 con sus indicadores y razones (P3)", async () => {
    renderPanel();
    const chain = await screen.findByTestId("auto-operation-strategy");
    // Identidad del instrumento + estrategia #1 (no un score abstracto). La cadena se resuelve
    // de forma asíncrona (ticker → UUID → TOP), por eso se espera al valor resuelto.
    await waitFor(() =>
      expect(
        screen.getByTestId("auto-operation-strategy-label").textContent,
      ).toContain("#1 SMA cross"),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("auto-operation-strategy-indicators").textContent,
      ).toContain("RSI"),
    );
    expect(
      screen.getByTestId("auto-operation-strategy-reason").textContent,
    ).toContain("Estrellas 3/5");
    // La clave EXACTA declarada por el ciclo (que empareja con el #1) y su sello opaco se
    // pintan por separado (honesto: la identidad no se confunde con el sello).
    expect(
      screen.getByTestId("auto-operation-strategy-preset-key").textContent,
    ).toContain("sma_crossover");
    expect(
      screen.getByTestId("auto-operation-strategy-match").textContent,
    ).toContain("sv-1");
    expect(chain.getAttribute("data-match")).toBe("same");
    expect(screen.queryByTestId("auto-operation-strategy-gap")).toBeNull();
  });

  it("lanza la verificación DÍA-D desde la operación (P4) con el instrumento y la #1", async () => {
    renderPanel();
    const button = await screen.findByTestId(
      "auto-operation-strategy-verify-dia-d",
    );
    await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
    expect(button.textContent).toContain("Verificar D→hoy");

    fireEvent.click(button);

    await waitFor(() =>
      expect(screen.getByTestId("story-location").textContent).toContain(
        "/backtests?",
      ),
    );
    const location = screen.getByTestId("story-location").textContent ?? "";
    const params = new URLSearchParams(location.split("?")[1] ?? "");
    expect(params.get("instrumentId")).toBe("uuid-aaa");
    expect(params.get("focus")).toBe("detail");
    expect(params.get("verify")).toBe("1");

    // La sesión DÍA-D LAB queda precargada con la estrategia #1 (sandbox, no producción).
    const session = useDiaDTradingSessionStore.getState().session;
    expect(session?.instrumentId).toBe("uuid-aaa");
    expect(session?.strategyDefinitionId).toBe("def-1");
    expect(session?.mode).toBe("auto");
  });

  it("verifica la estrategia EJECUTADA del ciclo (no el #1) cuando divergen", async () => {
    const monoTop = await vi.mocked(api.getInstrumentStrategyTop)();
    vi.mocked(api.getInstrumentStrategyTop).mockResolvedValueOnce({
      ...monoTop,
      data: {
        ...monoTop.data!,
        slots: [
          {
            rank: 1,
            label: "SMA cross",
            stars: 3,
            score: 70,
            source: "coach",
            strategyDefinitionId: "def-1",
            strategyType: "sma_crossover",
          },
          {
            rank: 2,
            label: "RSI rev",
            stars: 3,
            score: 65,
            source: "coach",
            strategyDefinitionId: "def-2",
            strategyType: "rsi_reversion",
          },
          {
            rank: 3,
            label: "F-D exp",
            stars: 2,
            score: 60,
            source: "coach",
            strategyDefinitionId: "def-3",
            strategyType: "fib_extension",
          },
        ],
      },
    });
    // El ciclo declara como EJECUTADA la estrategia #3 (`fib_extension`), distinta del #1.
    const monitor = await vi.mocked(api.getAutoOperationalMonitor)();
    vi.mocked(api.getAutoOperationalMonitor).mockResolvedValueOnce({
      ...monitor,
      cycles: (monitor.cycles ?? []).map((cycle) => ({
        ...cycle,
        strategyPresetKey: "fib_extension",
      })),
    });

    renderPanel();
    const button = await screen.findByTestId(
      "auto-operation-strategy-verify-dia-d",
    );
    await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
    // La tarjeta declara que se verifica la EJECUTADA, en su puesto REAL (#3).
    await waitFor(() =>
      expect(
        screen.getByTestId("auto-operation-strategy-executed").textContent,
      ).toContain("#3 F-D exp"),
    );

    fireEvent.click(button);

    await waitFor(() =>
      expect(useDiaDTradingSessionStore.getState().session).not.toBeNull(),
    );
    const session = useDiaDTradingSessionStore.getState().session;
    // La sesión LAB queda precargada con la EJECUTADA, no con el #1 de Finalistas.
    expect(session?.strategyDefinitionId).toBe("def-3");
    expect(session?.rank).toBe(3);
    expect(session?.cycleId).toBe("cyc-1");
    expect(session?.strategyPresetKey).toBe("fib_extension");
    expect(session?.mode).toBe("auto");
  });

  it("declara el hueco y no ofrece verificación cuando no hay TOP (fail-closed)", async () => {
    vi.mocked(api.getInstrumentStrategyTop).mockResolvedValueOnce({
      data: null,
    });

    renderPanel();
    // Primero se resuelve el instrumento (hueco transitorio); luego el TOP nulo declara el hueco.
    await waitFor(() =>
      expect(
        screen.getByTestId("auto-operation-strategy-gap").textContent,
      ).toContain("no hay Finalistas"),
    );
    const button = screen.getByTestId("auto-operation-strategy-verify-dia-d");
    expect(button.hasAttribute("disabled")).toBe(true);
  });

  it("un ciclo seleccionado sin instrumentId declara el hueco y no oculta la tarjeta (fail-closed)", async () => {
    // El monitor puede exponer un ciclo cuyo `instrumentId` (ticker) sea `null`: la tarjeta
    // del puente debe seguir visible y declarar el hueco, nunca desaparecer en silencio.
    const monitor = await vi.mocked(api.getAutoOperationalMonitor)();
    vi.mocked(api.getAutoOperationalMonitor).mockResolvedValueOnce({
      ...monitor,
      cycles: (monitor.cycles ?? []).map((cycle, index) =>
        index === 0 ? { ...cycle, instrumentId: null } : cycle,
      ),
    });

    renderPanel();
    const card = await screen.findByTestId("auto-operation-strategy");
    await waitFor(() =>
      expect(
        screen.getByTestId("auto-operation-strategy-gap").textContent,
      ).toContain("no se pudo resolver el instrumento"),
    );
    expect(card).toBeTruthy();
    const button = screen.getByTestId("auto-operation-strategy-verify-dia-d");
    expect(button.hasAttribute("disabled")).toBe(true);
  });

  it("resuelve la explicación por cycleId (índice `cycles[]`) y la lleva a «Qué aprendemos»", async () => {
    renderPanel();

    await waitFor(() =>
      expect(
        screen
          .getByTestId("auto-operation-story-explanation")
          .getAttribute("data-state"),
      ).toBe("REACHED"),
    );

    const explanation = screen.getByTestId("auto-operation-story-explanation");
    // Vive en su propio bloque, no entre los hechos de la operación.
    expect(explanation.getAttribute("data-group")).toBe("EXPLANATION");
    expect(
      screen.getByTestId("auto-operation-story-learning").textContent,
    ).toContain("¿Qué aprendemos?");
    expect(explanation.textContent).toContain("OOS_SUPPORTED");
    // Identidad de la operación: ejes copiados del ciclo + NO MEDIDO en lo no material.
    expect(explanation.textContent).toContain("cycleId");
    expect(explanation.textContent).toContain("cyc-1");
    expect(explanation.textContent).toContain("2026-09-29");
    expect(explanation.textContent).toContain("NO MEDIDO");
    // El índice `cycles[]` ata el ciclo a su valor: resolución EXACTA por cycleId (no por símbolo).
    expect(explanation.textContent).toContain("resolución");
    expect(explanation.textContent).toContain("por ciclo (cycleId)");
  });

  it("la clave EXACTA del ciclo llega a la fila EXPLANATION (no solo el sello opaco)", async () => {
    renderPanel();
    await waitFor(() =>
      expect(
        screen
          .getByTestId("auto-operation-story-explanation")
          .getAttribute("data-state"),
      ).toBe("REACHED"),
    );

    // `strategyPresetKey` viaja en la identidad: es el único término con el que se puede afirmar
    // que la estrategia de la explicación es la MISMA que declara el ciclo.
    const explanation = screen.getByTestId("auto-operation-story-explanation");
    expect(explanation.textContent).toContain("estrategia (clave)");
    expect(explanation.textContent).toContain("sma_crossover");
  });

  it("el bloque P4 declara la evidencia del VALOR, la verificación y las cuatro capas", async () => {
    renderPanel();
    // La atribución se resuelve de forma asíncrona (ticker → UUID → TOP): se espera a que la
    // clave EXACTA del ciclo empareje con el TOP antes de asertar sobre el bloque.
    await waitFor(() =>
      expect(
        screen
          .getByTestId("auto-strategy-dia-d")
          .getAttribute("data-strategy-declared"),
      ).toBe("true"),
    );
    const block = screen.getByTestId("auto-strategy-dia-d");
    // El bloque declara el alcance del valor con su propia nota de atribución.
    expect(
      screen.getByTestId("auto-strategy-dia-d-attribution").textContent,
    ).toContain("NO es atribuible a una estrategia");
    // La evidencia agregada es del VALOR: nunca se presenta como de la estrategia.
    expect(
      screen.getByTestId("auto-strategy-dia-d-scope").textContent,
    ).toContain("Del valor (no de la estrategia)");
    expect(
      screen.getByTestId("auto-strategy-dia-d-strategy").textContent,
    ).toContain("sma_crossover");
    // El bloque se identifica como el de la explicación P3→P4 (no confunde tarjeta con bloque).
    expect(block.getAttribute("data-verified")).toBe("not-verified");
    // Cuatro capas, sin promoción: PAPER es hueco por contrato.
    const layers = screen.getAllByTestId("auto-strategy-dia-d-layer");
    expect(layers.map((layer) => layer.getAttribute("data-layer"))).toEqual([
      "window",
      "reconciliation",
      "oos",
      "paper",
    ]);
    expect(
      layers
        .find((layer) => layer.getAttribute("data-layer") === "paper")
        ?.getAttribute("data-state"),
    ).toBe("gap");
    // La muestra del valor y sus suelos declarados se pintan (o su hueco, nunca un 0).
    expect(
      screen.getByTestId("auto-strategy-dia-d-counts").textContent,
    ).toContain("ciclos");
    // La sesión LAB se declara LOCAL (no durable) y sin sesión abierta.
    const lab = screen.getByTestId("auto-strategy-dia-d-lab");
    expect(lab.getAttribute("data-lab-active")).toBe("false");
    expect(lab.textContent).toContain("no es evidencia durable");
  });

  it("rotula «Verificación vinculada» cuando existe el registro durable del ciclo (P2)", async () => {
    vi.mocked(api.listDiaDCycleVerifications).mockResolvedValueOnce({
      data: [
        {
          id: "ver-1",
          cycleId: "cyc-1",
          accountId: "acc-1",
          instrumentId: "uuid-aaa",
          symbol: "AAA",
          diaD: "2026-09-29",
          endDate: "2026-09-30",
          mode: "auto",
          createdAt: "2026-09-30T16:00:00Z",
          strategyPresetKey: "sma_crossover",
          strategyVersion: "sv-1",
          strategyDefinitionId: null,
          band: null,
          result: null,
          researchEvidenceId: null,
        },
      ],
      total: 1,
      notes: [],
    });

    renderPanel();
    const block = await screen.findByTestId("auto-strategy-dia-d");
    await waitFor(() =>
      expect(block.getAttribute("data-verified")).toBe("linked"),
    );
    const verification = screen.getByTestId("auto-strategy-dia-d-verification");
    expect(verification.textContent).toContain("Verificación vinculada");
    expect(verification.textContent).toContain("2026-09-30T16:00:00Z");
  });

  it("una sesión LAB de OTRA cuenta no se atribuye a esta operación (fail-closed)", async () => {
    useDiaDTradingSessionStore.getState().enterSession({
      instrumentId: "uuid-aaa",
      symbol: "AAA",
      strategyDefinitionId: "def-1",
      strategyLabel: "SMA cross",
      rank: 1,
      diaD: "2026-09-29",
      endDate: "2026-09-30",
      accountId: "acc-OTRA",
      strategyPresetKey: "sma_crossover",
      strategyVersion: "sv-1",
      cycleId: "cyc-1",
    });

    renderPanel();
    await screen.findByTestId("auto-strategy-dia-d");
    await waitFor(() =>
      expect(
        screen
          .getByTestId("auto-strategy-dia-d-lab")
          .getAttribute("data-lab-active"),
      ).toBe("false"),
    );
    expect(screen.getByTestId("auto-strategy-dia-d-lab").textContent).toContain(
      "no vinculada",
    );
    expect(screen.getByTestId("auto-strategy-dia-d-lab").textContent).toContain(
      "no es evidencia durable",
    );
  });

  it("una sesión LAB de la MISMA operación (cuenta + instrumento + clave) sí se atribuye", async () => {
    useDiaDTradingSessionStore.getState().enterSession({
      instrumentId: "uuid-aaa",
      symbol: "AAA",
      strategyDefinitionId: "def-1",
      strategyLabel: "SMA cross",
      rank: 1,
      diaD: "2026-09-29",
      endDate: "2026-09-30",
      accountId: "acc-1",
      strategyPresetKey: "sma_crossover",
      strategyVersion: "sv-1",
      cycleId: "cyc-1",
    });

    renderPanel();
    await screen.findByTestId("auto-strategy-dia-d");
    await waitFor(() =>
      expect(
        screen
          .getByTestId("auto-strategy-dia-d-lab")
          .getAttribute("data-lab-active"),
      ).toBe("true"),
    );
    expect(screen.getByTestId("auto-strategy-dia-d-lab").textContent).toContain(
      "2026-09-29",
    );
  });

  it("enlaza la EXPLICACIÓN al heatmap DÍA-D canónico (workspace AUTO) con símbolo y ventana", async () => {
    renderPanel();
    await waitFor(() =>
      expect(
        screen.getByTestId("auto-operation-story-open-heatmap"),
      ).toBeTruthy(),
    );

    fireEvent.click(screen.getByTestId("auto-operation-story-open-heatmap"));
    await waitFor(() =>
      expect(screen.getByTestId("story-location").textContent).toContain(
        "/auto/analisis",
      ),
    );
    const location = screen.getByTestId("story-location").textContent ?? "";
    const params = new URLSearchParams(location.split("?")[1] ?? "");
    expect(params.get("tab")).toBe("dia-d");
    expect(params.get("view")).toBe("feedback");
    expect(params.get("symbol")).toBe("AAA");
    expect(params.get("window")).toBe("2026-09-29_2026-09-30");
  });

  it("lleva al detalle técnico canónico (monitor experto) con el ciclo de la operación", async () => {
    renderPanel();
    // La cabecera (y su botón) se pinta antes de que cargue el monitor: hay que esperar a
    // que el ciclo seleccionado exista para que el deep-link lleve su `cycleId`.
    await waitFor(() =>
      expect(screen.getByTestId("auto-operation-story-cycles")).toBeTruthy(),
    );

    fireEvent.click(screen.getByTestId("auto-operation-story-open-technical"));
    // El entry inicial ya es `/auto-monitor?mode=operation`: hay que esperar al CAMBIO.
    await waitFor(() =>
      expect(screen.getByTestId("story-location").textContent).toContain(
        "mode=current",
      ),
    );
    const location = screen.getByTestId("story-location").textContent ?? "";
    expect(location).toContain("/auto-monitor");
    const params = new URLSearchParams(location.split("?")[1] ?? "");
    expect(params.get("mode")).toBe("current");
    expect(params.get("cycle")).toBe("cyc-1");
  });

  it("un cycleId de ruta inexistente NO cae a cycles[0] (declara 'no encontrada')", async () => {
    renderPanel({ cycleIdOverride: "does-not-exist" });

    const notFound = await screen.findByTestId(
      "auto-operation-story-not-found",
    );
    expect(notFound.getAttribute("data-cycle-id")).toBe("does-not-exist");
    expect(notFound.textContent).toContain("does-not-exist");

    // Jamás se pinta la historia de OTRO ciclo real.
    expect(screen.queryAllByTestId("auto-operation-story-stage")).toHaveLength(
      0,
    );
    expect(screen.queryByText("OOS_SUPPORTED")).toBeNull();
    expect(screen.queryByTestId("auto-operation-story-context")).toBeNull();
    // Sin ciclo válido no hay destino técnico que ofrecer.
    expect(
      screen.queryByTestId("auto-operation-story-open-technical"),
    ).toBeNull();
    // El selector sigue como vía de recuperación, sin ningún ciclo presionado.
    expect(
      screen
        .getAllByTestId("auto-operation-story-cycle")
        .every((button) => button.getAttribute("aria-pressed") === "false"),
    ).toBe(true);
  });

  it("un ?cycle= explícito inexistente tampoco cae a cycles[0]", async () => {
    renderPanel({
      initialEntries: ["/auto-monitor?mode=operation&cycle=does-not-exist"],
    });

    const notFound = await screen.findByTestId(
      "auto-operation-story-not-found",
    );
    expect(notFound.getAttribute("data-cycle-id")).toBe("does-not-exist");
    expect(screen.queryAllByTestId("auto-operation-story-stage")).toHaveLength(
      0,
    );
  });

  it("separa «no evaluable» de «sin señal» en los HOLD declarados (.168)", async () => {
    const monitor = await api.getAutoOperationalMonitor();
    vi.mocked(api.getAutoOperationalMonitor).mockResolvedValueOnce({
      ...monitor,
      signalHolds: [
        {
          instrumentId: "AAA",
          barTimestamp: "2026-09-30T00:00:00Z",
          at: "2026-09-30T00:00:01Z",
          reason: "warmup_unmeasurable",
          measurement: "COMPLETE",
          facts: [],
        },
        {
          instrumentId: "BBB",
          barTimestamp: "2026-09-30T00:00:00Z",
          at: "2026-09-30T00:00:01Z",
          reason: "no_signal",
          measurement: "COMPLETE",
          facts: [],
        },
      ],
    });

    renderPanel();

    const block = await screen.findByTestId("auto-decision-silence");
    // El panel se monta ya en carga: se espera al titular, no a la sección.
    const headline = await screen.findByTestId(
      "auto-decision-silence-headline",
    );
    // El titular cuenta ambos hechos por separado: una señal evaluada y un hueco.
    expect(headline.textContent).toContain("1 sin señal");
    expect(headline.textContent).toContain("1 HOLD no evaluable");

    const items = screen.getAllByTestId("auto-decision-silence-item");
    expect(items.map((item) => item.getAttribute("data-cause"))).toEqual([
      "not_evaluable",
      "no_signal",
    ]);
    // El hueco se nombra con su motivo, no con prosa genérica.
    expect(items[0]?.textContent).toContain("warmup no medible");
    expect(items[1]?.textContent).toContain("sin señal");

    // El aviso sólo lista los no evaluables (uno de dos).
    const attention = screen.getByTestId("auto-decision-silence-attention");
    expect(attention.textContent).toContain("1 de 2");
    expect(attention.textContent).toContain("AAA");
    expect(attention.textContent).not.toContain("BBB");
    expect(block.getAttribute("data-silence-headline")).toBeTruthy();
  });

  it("la carga y el error del monitor son estados alcanzables del panel de HOLD", async () => {
    vi.mocked(api.getAutoOperationalMonitor).mockRejectedValueOnce(
      new Error("boom"),
    );
    renderPanel();

    // El panel se monta aunque no haya `view`: el fallo no se lee como «sin HOLD».
    const error = await screen.findByTestId("auto-decision-silence-error");
    expect(error.textContent).toContain("No se pudieron leer");
    expect(screen.queryByTestId("auto-decision-silence-empty")).toBeNull();
    expect(screen.queryByTestId("auto-decision-silence-headline")).toBeNull();
  });

  it("sin HOLD declarados no afirma «sin señal» (declara el hueco)", async () => {
    renderPanel();

    const empty = await screen.findByTestId("auto-decision-silence-empty");
    expect(empty.textContent).toContain("no");
    expect(empty.textContent).toContain("consta el motivo");
    expect(screen.queryAllByTestId("auto-decision-silence-item")).toHaveLength(
      0,
    );
  });

  it("muestra la procedencia declarada del HOLD y conserva el crudo en el detalle técnico", async () => {
    const monitor = await api.getAutoOperationalMonitor();
    vi.mocked(api.getAutoOperationalMonitor).mockResolvedValueOnce({
      ...monitor,
      signalHolds: [
        {
          instrumentId: "AAA",
          barTimestamp: "2026-09-30T00:00:00Z",
          at: "2026-09-30T00:00:01Z",
          reason: "warmup_unmeasurable",
          measurement: "COMPLETE",
          facts: [
            { key: "featureSource", value: "real", measurement: "COMPLETE" },
            { key: "signalWindowBars", value: 120, measurement: "COMPLETE" },
            { key: "warmupBars", value: 201, measurement: "COMPLETE" },
            {
              key: "gatedState",
              value: { holdsLong: null, source: "unavailable" },
              measurement: "COMPLETE",
            },
          ],
        },
      ],
    });

    renderPanel();

    const values = await screen.findAllByTestId(
      "auto-decision-silence-provenance-value",
    );
    expect(values.map((node) => node.textContent)).toEqual([
      "datos reales",
      "120 barras",
      "201 barras",
      "no se sabe si había posición · libro no legible",
    ]);

    // Primer nivel: símbolo reconocible y fecha legible (sin el sello ISO completo).
    const item = screen.getByTestId("auto-decision-silence-item");
    expect(
      screen.getByTestId("auto-decision-silence-item-symbol").textContent,
    ).toBe("AAA");
    const bar = screen.getByTestId("auto-decision-silence-item-bar");
    expect(bar.textContent).toContain("2026");
    expect(bar.textContent).not.toContain("T00:00:00Z");

    // Y los datos de auditoría siguen disponibles bajo el detalle técnico.
    const details = screen.getByTestId("auto-decision-silence-item-technical");
    expect(
      details.querySelector('[data-fact-key="gatedState"]')?.textContent,
    ).toContain("holdsLong");
    expect(item.getAttribute("data-cause")).toBe("not_evaluable");
  });
});

describe("resolveAutoOperationSelection", () => {
  const cycles = [
    { cycleId: "cyc-1", instrumentId: "AAA" },
    { cycleId: "cyc-2", instrumentId: "BBB" },
  ];

  it("sin selección explícita conserva el fallback a cycles[0]", () => {
    const result = resolveAutoOperationSelection({ cycles, hasLoaded: true });
    expect(result.requestedCycleId).toBeNull();
    expect(result.notFound).toBe(false);
    expect(result.selectedCycle?.cycleId).toBe("cyc-1");
  });

  it("un override válido selecciona ese ciclo (no el primero)", () => {
    const result = resolveAutoOperationSelection({
      cycles,
      overrideCycleId: "cyc-2",
      hasLoaded: true,
    });
    expect(result.selectedCycle?.cycleId).toBe("cyc-2");
    expect(result.notFound).toBe(false);
  });

  it("un id explícito inexistente NO cae a cycles[0]", () => {
    const result = resolveAutoOperationSelection({
      cycles,
      overrideCycleId: "does-not-exist",
      hasLoaded: true,
    });
    expect(result.requestedCycleId).toBe("does-not-exist");
    expect(result.notFound).toBe(true);
    expect(result.selectedCycle).toBeNull();
  });

  it("un ?cycle= explícito inexistente se comporta igual", () => {
    const result = resolveAutoOperationSelection({
      cycles,
      queryCycleId: "does-not-exist",
      hasLoaded: true,
    });
    expect(result.notFound).toBe(true);
    expect(result.selectedCycle).toBeNull();
  });

  it("durante la carga NO declara notFound (evita un falso negativo)", () => {
    const result = resolveAutoOperationSelection({
      cycles,
      overrideCycleId: "does-not-exist",
      hasLoaded: false,
    });
    expect(result.notFound).toBe(false);
  });

  it("la ruta canónica tiene prioridad sobre ?cycle=", () => {
    const result = resolveAutoOperationSelection({
      cycles,
      overrideCycleId: "cyc-2",
      queryCycleId: "cyc-1",
      hasLoaded: true,
    });
    expect(result.selectedCycle?.cycleId).toBe("cyc-2");
  });

  it("recorta espacios alrededor de un id válido", () => {
    const result = resolveAutoOperationSelection({
      cycles,
      overrideCycleId: "  cyc-1  ",
      hasLoaded: true,
    });
    expect(result.selectedCycle?.cycleId).toBe("cyc-1");
  });
});

describe("resolveExplanationForCycle", () => {
  const value = (symbol: string) => ({
    symbol,
    verdict: "OOS_SUPPORTED",
    evidenceQuality: "PRELIMINARY",
    expectancyR: 0.5,
    hitRate: 0.67,
    measuredCycles: 6,
    daysCovered: 1,
    windowDays: 2,
    errorTotal: 0,
  });
  const cycle = {
    cycleId: "cyc-1",
    instrumentId: "AAA",
    strategyVersion: "strat-x",
    direction: "long",
    entryDay: "2026-09-29",
  };

  it("resuelve por cycleId cuando el índice lo contiene y usa sus ejes", () => {
    const explanation = resolveExplanationForCycle({
      cycle,
      values: [value("AAA")],
      cycles: [
        {
          cycleId: "cyc-1",
          symbol: "AAA",
          entryDay: "2026-09-28",
          strategyVersion: "sv-9",
        },
      ],
    });
    expect(explanation?.resolution).toBe("cycleId");
    // Los ejes del ÍNDICE (identidad del ciclo) mandan sobre los copiados del monitor.
    expect(explanation?.identity?.entryDay).toBe("2026-09-28");
    expect(explanation?.identity?.strategyVersion).toBe("sv-9");
    expect(explanation?.identity?.instrument).toBe("AAA");
  });

  it("si el ciclo no está en el índice, cae al instrumento (parcial) y lo declara", () => {
    const explanation = resolveExplanationForCycle({
      cycle,
      values: [value("AAA")],
      cycles: [{ cycleId: "otro", symbol: "AAA" }],
    });
    expect(explanation?.resolution).toBe("instrument");
    expect(explanation?.identity?.entryDay).toBe("2026-09-29");
    expect(explanation?.identity?.strategyVersion).toBe("strat-x");
    expect(explanation?.identity?.instrument).toBe("AAA");
  });

  it("declara NO MEDIDO (null) si no hay valor para el instrumento", () => {
    const explanation = resolveExplanationForCycle({
      cycle,
      values: [value("BBB")],
      cycles: [],
    });
    expect(explanation).toBeNull();
  });

  it("sin ciclo no hay explicación", () => {
    expect(
      resolveExplanationForCycle({ cycle: null, values: [], cycles: [] }),
    ).toBeNull();
  });
});
