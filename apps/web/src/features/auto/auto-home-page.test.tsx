/**
 * AUTO · RESUMEN (HOME) — estructura y estados.
 *
 * Comprueba que la HOME expone un `<h1>` y responde las preguntas del usuario básico, que el
 * error se declara distinto del vacío y que las operaciones en curso enlazan a su ruta canónica.
 * Los hooks de red se mockean; el helper de resumen es real.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

const monitorState = vi.hoisted(() => ({
  header: null as Record<string, unknown> | null,
  cycles: [] as Array<Record<string, unknown>>,
  isLoading: false,
  isError: false,
}));

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => ({
    view: monitorState.header
      ? { header: monitorState.header, cycles: monitorState.cycles }
      : null,
    isLoading: monitorState.isLoading,
    isError: monitorState.isError,
    isFetching: false,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1", type: "simulated" },
    isLoading: false,
    accounts: [],
  }),
}));

const financialState = vi.hoisted(() => ({
  operationalState: "OK" as string | null,
}));

const accountSummary = vi.hoisted(() => ({
  data: null as {
    positionsCount: number;
    cash: number;
    totalUnrealizedPnl: number;
  } | null,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: accountSummary.data }),
}));

vi.mock("@/features/operational-console/use-financial-integrity", () => ({
  useFinancialIntegrity: () => ({
    data: { operationalState: financialState.operationalState },
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

import { AutoHomePage } from "@/features/auto/auto-home-page";

const OPEN_CYCLE = {
  cycleId: "cyc-1",
  instrumentId: "AAPL",
  directionLabel: "Largo",
  statusLabel: "Precio aplicado",
  closed: false,
  closedMeasurement: "COMPLETE",
  steps: [
    { id: "SIGNAL", state: "reached", at: "2026-10-03T09:00:00Z" },
    { id: "FILL", state: "reached", at: "2026-10-03T09:05:00Z" },
  ],
};

beforeEach(() => {
  monitorState.header = {
    state: "RUNNING",
    lastDecisionAt: "2026-10-06T09:42:00Z",
    nextDecisionAt: "2026-10-06T10:00:00Z",
  };
  monitorState.cycles = [OPEN_CYCLE];
  monitorState.isLoading = false;
  monitorState.isError = false;
  financialState.operationalState = "OK";
  accountSummary.data = null;
});

afterEach(cleanup);

function renderHome() {
  return render(
    <MemoryRouter initialEntries={["/auto"]}>
      <AutoHomePage />
    </MemoryRouter>,
  );
}

function countOccurrences(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

describe("AutoHomePage", () => {
  it("expone un solo h1 y el semáforo no se duplica aquí (lo aporta el layout)", () => {
    renderHome();
    const h1 = screen.queryAllByRole("heading", { level: 1 });
    expect(h1).toHaveLength(1);
    expect(h1[0]?.textContent).toBe("Resumen");
  });

  it("pinta cada hecho una sola vez (UI5-04): sin tiles ni bloque duplicados", () => {
    renderHome();
    // Se retiraron la fila de tiles y el bloque «¿Qué está haciendo AUTO?».
    expect(screen.queryByTestId("auto-home-tile-auto")).toBeNull();
    expect(screen.queryByTestId("auto-home-tile-risk")).toBeNull();
    // El estado del motor se afirma una sola vez en el primer nivel (la insignia usa otra caja).
    const text = document.body.textContent ?? "";
    expect(countOccurrences(text, "Funcionando")).toBe(1);
    // Las operaciones en curso se cuentan en un único lugar.
    expect(countOccurrences(text, "1 en curso")).toBe(1);
  });

  it("responde las preguntas clave con datos legibles", () => {
    renderHome();
    expect(
      screen.getByTestId("auto-home-tile-operations").textContent,
    ).toContain("1 en curso");
    expect(
      screen.getByTestId("auto-home-tile-operations").textContent,
    ).not.toContain("abierta");
    expect(screen.getByTestId("auto-home-q-working").textContent).toContain(
      "Funcionando",
    );
    expect(screen.getByTestId("auto-home-q-doing").textContent).toContain(
      "Sin dato todavía",
    );
    expect(screen.getByTestId("auto-home-q-asset").textContent).toContain(
      "AAPL",
    );
    expect(screen.getByTestId("auto-home-q-decision").textContent).toContain(
      "Sin dato todavía",
    );
    expect(screen.getByTestId("auto-home-q-happened").textContent).toContain(
      "Sin dato todavía",
    );
    expect(screen.getByTestId("auto-home-q-money").textContent).toContain(
      "SIMULACIÓN — DINERO VIRTUAL",
    );
    expect(
      screen.getByTestId("auto-home-figure-position").textContent,
    ).toContain("Sin dato todavía");
    expect(screen.getByTestId("auto-home-figure-risk").textContent).toContain(
      "Normal",
    );
    const card = screen.getByTestId("auto-operation-card");
    expect(card.getAttribute("data-cycle-id")).toBe("cyc-1");
    expect(screen.getByTestId("auto-card-slot-decision").textContent).toContain(
      "Sin dato todavía",
    );
    expect(
      screen.getByTestId("auto-card-slot-simulation").textContent,
    ).toContain("Sin dato todavía");
    expect(
      screen.getByTestId("auto-operation-card-details").getAttribute("href"),
    ).toBe("/auto-monitor?mode=current&cycle=cyc-1");
    expect(screen.getByTestId("auto-home-activity").textContent).toContain(
      "Ver actividad",
    );
    expect(screen.getByTestId("auto-home-doing").textContent).toBe(
      "Sin dato todavía",
    );
    expect(screen.getByTestId("auto-home-last-activity").textContent).toBe(
      "Última decisión: 09:42 · Próxima decisión: 10:00",
    );
    expect(
      screen.getByTestId("auto-home-last-activity").textContent,
    ).not.toContain("Esperando nueva señal");
    expect(
      screen.getByTestId("auto-home-last-activity").textContent,
    ).not.toContain("análisis");
  });

  it("la fase operacional del tick se pinta sin inventar desde RUNNING", () => {
    monitorState.header = {
      ...monitorState.header,
      currentActivity: "ANALYZING",
      currentActivityMeasurement: "COMPLETE",
      currentActivityAt: "2026-10-06T09:42:00Z",
      currentActivityAtMeasurement: "COMPLETE",
      asOf: "2026-10-06T09:43:00Z",
    };
    renderHome();
    expect(screen.getByTestId("auto-home-q-doing").textContent).toContain(
      "Analizando",
    );
    expect(screen.getByTestId("auto-home-doing").textContent).toBe(
      "Analizando",
    );

    cleanup();
    monitorState.header = {
      state: "RUNNING",
      lastDecisionAt: "2026-10-06T09:42:00Z",
      nextDecisionAt: "2026-10-06T10:00:00Z",
      currentActivity: "NO_ACTIVITY",
      currentActivityMeasurement: "COMPLETE",
      currentActivityAt: "2026-10-06T09:42:00Z",
      currentActivityAtMeasurement: "COMPLETE",
      asOf: "2026-10-06T09:43:00Z",
    };
    renderHome();
    expect(screen.getByTestId("auto-home-q-doing").textContent).toContain(
      "Sin actividad",
    );
    expect(screen.getByTestId("auto-home-doing").textContent).toBe(
      "Sin actividad",
    );
    expect(screen.getByTestId("auto-home-doing").textContent).not.toContain(
      "Analizando",
    );
  });

  it("copia las cifras de cuenta y no marca la simulación con el fill", () => {
    accountSummary.data = {
      positionsCount: 2,
      cash: 10000,
      totalUnrealizedPnl: 12.5,
    };
    monitorState.cycles = [
      {
        ...OPEN_CYCLE,
        steps: [
          {
            id: "ORDER",
            state: "reached",
            measurement: "COMPLETE",
            facts: [
              {
                key: "entryOrder",
                measurement: "COMPLETE",
                value: { requestedQty: 10, appliedQty: 10 },
              },
            ],
          },
          { id: "FILL", state: "reached", measurement: "COMPLETE" },
        ],
      },
    ];
    renderHome();
    expect(
      screen.getByTestId("auto-home-figure-position").textContent,
    ).toContain("2 posiciones en la cuenta simulada");
    expect(screen.getByTestId("auto-home-figure-cash").textContent).toContain(
      "10000.00 €",
    );
    expect(
      screen.getByTestId("auto-card-slot-execution").textContent,
    ).toContain("10/10");
    expect(
      screen.getByTestId("auto-card-slot-simulation").textContent,
    ).toContain("Sin dato todavía");
    expect(screen.getByTestId("auto-card-slot-money").textContent).toContain(
      "en la cuenta simulada",
    );
    expect(
      screen.getByTestId("auto-card-slot-money").textContent,
    ).not.toContain("DINERO REAL");
    expect(screen.getByTestId("auto-operation-card").textContent).toContain(
      "Precio aplicado",
    );
    const pageText = document.body.textContent ?? "";
    expect(pageText).not.toContain("Posición abierta");
    expect(pageText).not.toContain("Materializada");
    expect(pageText).not.toContain("Completada");
    expect(
      screen.getByTestId("auto-home-tile-operations").textContent,
    ).toContain("1 en curso");
  });

  it("una orden sin fill es en curso y no se llama abierta", () => {
    monitorState.cycles = [
      {
        cycleId: "cyc-ord",
        instrumentId: "AAPL",
        directionLabel: "Largo",
        closed: false,
        closedMeasurement: "COMPLETE",
        steps: [
          { id: "ORDER", state: "reached", measurement: "COMPLETE" },
          { id: "FILL", state: "pending" },
        ],
      },
    ];
    renderHome();
    const tile =
      screen.getByTestId("auto-home-tile-operations").textContent ?? "";
    expect(tile).toContain("1 en curso");
    expect(tile).not.toContain("abierta");
    expect(screen.getByTestId("auto-operation-card").textContent).toContain(
      "Orden pendiente",
    );
    expect(screen.getByTestId("auto-home-operation-link")).toBeTruthy();
    expect(screen.queryByTestId("auto-home-in-course-empty")).toBeNull();
    expect(document.body.textContent).not.toContain("Sin operaciones abiertas");
  });

  it("una reserva, un cierre no medido o un ciclo cerrado no entran en el contador", () => {
    monitorState.cycles = [
      {
        cycleId: "cyc-res",
        instrumentId: "AAPL",
        closed: false,
        closedMeasurement: "COMPLETE",
        steps: [{ id: "RESERVATION", state: "reached" }],
      },
    ];
    renderHome();
    expect(
      screen.getByTestId("auto-home-tile-operations").textContent,
    ).toContain("Sin operaciones en curso");
    expect(screen.queryByTestId("auto-operation-card")).toBeNull();
    expect(screen.getByTestId("auto-home-in-course-empty")).toBeTruthy();

    cleanup();
    monitorState.cycles = [
      {
        ...OPEN_CYCLE,
        cycleId: "cyc-gap",
        closed: null,
        closedMeasurement: "UNKNOWN",
      },
    ];
    renderHome();
    expect(screen.queryByTestId("auto-operation-card")).toBeNull();
    expect(
      screen.getByTestId("auto-home-tile-operations").textContent,
    ).toContain("Sin operaciones en curso");
  });

  it("enlaza las operaciones en curso a su ruta canónica", () => {
    renderHome();
    const links = screen.getAllByTestId("auto-home-operation-link");
    expect(links).toHaveLength(1);
    expect(links[0]?.getAttribute("href")).toBe("/auto/operar/operacion/cyc-1");
    expect(links[0]?.textContent).toContain("AAPL");
    expect(
      screen.getByTestId("auto-home-opportunities-link").getAttribute("href"),
    ).toContain("oportunidades");
    expect(
      screen.getByTestId("auto-home-link-dia-d").getAttribute("href"),
    ).toContain("tab=dia-d");
  });

  it("un ciclo cerrado no aparece como operación en curso", () => {
    monitorState.cycles = [{ ...OPEN_CYCLE, cycleId: "cyc-9", closed: true }];
    renderHome();
    expect(screen.queryByTestId("auto-home-operation-link")).toBeNull();
    expect(screen.queryByTestId("auto-operation-card")).toBeNull();
    expect(screen.getByTestId("auto-home-in-course-empty")).toBeTruthy();
    expect(
      screen.getByTestId("auto-home-tile-operations").textContent,
    ).toContain("Sin operaciones en curso");
  });

  it("el error se declara distinto del vacío", () => {
    monitorState.isError = true;
    monitorState.header = null;
    monitorState.cycles = [];
    renderHome();
    expect(screen.getByTestId("auto-home-error")).toBeTruthy();
    expect(screen.queryByTestId("auto-home-in-course-empty")).toBeNull();
  });

  it("la carga no se presenta como vacío", () => {
    monitorState.isLoading = true;
    monitorState.header = null;
    monitorState.cycles = [];
    renderHome();
    expect(screen.getByTestId("auto-home-loading")).toBeTruthy();
    expect(screen.queryByTestId("auto-home-in-course-empty")).toBeNull();
  });
});
