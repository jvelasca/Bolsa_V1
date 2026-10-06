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
});

describe("AutoOperationStoryPanel", () => {
  it("pinta las 10 filas de operación (OPPORTUNITY fuera, POSITION y EXIT plegados, EXPLANATION aparte)", async () => {
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
    // EXIT se pliega en SETTLEMENT: no es una fila independiente…
    expect(byStage.has("EXIT")).toBe(false);
    // …y deja su intención como NOTA de la liquidación (una sola fila por hecho).
    expect(byStage.get("SETTLEMENT")?.textContent).toContain("liquidación");

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
