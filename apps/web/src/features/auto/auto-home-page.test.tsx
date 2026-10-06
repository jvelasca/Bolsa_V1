/**
 * AUTO · RESUMEN (HOME) — estructura y estados.
 *
 * Comprueba que la HOME expone un `<h1>` y responde las preguntas del usuario básico, que el
 * error se declara distinto del vacío y que las operaciones abiertas enlazan a su ruta canónica.
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

describe("AutoHomePage", () => {
  it("expone un solo h1 y el semáforo no se duplica aquí (lo aporta el layout)", () => {
    renderHome();
    const h1 = screen.queryAllByRole("heading", { level: 1 });
    expect(h1).toHaveLength(1);
    expect(h1[0]?.textContent).toBe("Resumen");
  });

  it("responde las preguntas clave con datos legibles", () => {
    renderHome();
    expect(screen.getByTestId("auto-home-tile-auto").textContent).toContain(
      "Funcionando",
    );
    expect(
      screen.getByTestId("auto-home-tile-operations").textContent,
    ).toContain("1 abierta");
    expect(screen.getByTestId("auto-home-tile-risk").textContent).toContain(
      "Normal",
    );
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
      "Funcionando",
    );
    expect(screen.getByTestId("auto-home-last-activity").textContent).toBe(
      "09:42",
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
  });

  it("enlaza las operaciones abiertas a su ruta canónica", () => {
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

  it("un ciclo cerrado no aparece como operación abierta", () => {
    monitorState.cycles = [{ ...OPEN_CYCLE, cycleId: "cyc-9", closed: true }];
    renderHome();
    expect(screen.queryByTestId("auto-home-operation-link")).toBeNull();
    expect(screen.getByTestId("auto-home-open-empty")).toBeTruthy();
  });

  it("el error se declara distinto del vacío", () => {
    monitorState.isError = true;
    monitorState.header = null;
    monitorState.cycles = [];
    renderHome();
    expect(screen.getByTestId("auto-home-error")).toBeTruthy();
    expect(screen.queryByTestId("auto-home-open-empty")).toBeNull();
  });

  it("la carga no se presenta como vacío", () => {
    monitorState.isLoading = true;
    monitorState.header = null;
    monitorState.cycles = [];
    renderHome();
    expect(screen.getByTestId("auto-home-loading")).toBeTruthy();
    expect(screen.queryByTestId("auto-home-open-empty")).toBeNull();
  });
});
