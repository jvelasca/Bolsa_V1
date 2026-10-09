/**
 * P4 — validación de extremo a extremo de «Por qué AUTO no operó».
 *
 * Monta el contenedor REAL (`AutoNoTradePanel`) cableado a sus tres fuentes ya existentes
 * (monitor del motor, veto de mesa e informe diario de PAPER) y comprueba, a través del
 * pipeline completo DTO → hechos → read-model → render, lo que el audit `P4` pide verificar:
 *
 * 1. **Causa ↔ registro.** Cada causa declarada enlaza con el ciclo que la demuestra.
 * 2. **Filtro por día.** Un ciclo de otro día NO contamina la causa del día explicado.
 * 3. **Ausencia real ≠ falta de trazabilidad.** `ORDER absent` declara la causa 4; `ORDER
 *    unknown` (no durable) la deja en hueco, nunca afirmada.
 * 4. **Errores de lectura.** Un fallo del monitor deja la cadena del motor en «Sin dato
 *    todavía»; un fallo de incidentes deja el veto en hueco — jamás «No aplica».
 * 5. **Universo `unavailable` ≠ `empty`.**
 *
 * El contrato de paridad `absent`/`unknown` del backend ya está sellado por
 * `packages/py/application/tests/test_auto_operational_monitor.py`; aquí se valida que el
 * frontend lo consume sin reinterpretarlo.
 *
 * @see docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md (P4)
 */

import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const state = vi.hoisted(() => ({
  monitor: {
    view: null as unknown,
    isLoading: false,
    isError: false,
  },
  blocked: {
    entriesBlocked: false,
    killOn: false,
    vetoed: 0,
    incidentCount: 0,
    incidentsFailed: false,
    paperDExecuteEnv: false,
  },
  daily: null as unknown,
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
  }),
}));

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => state.monitor,
}));

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: () => state.blocked,
}));

vi.mock("@/lib/api", () => ({
  api: { getPaperDeskDailyReport: vi.fn() },
}));

import { api } from "@/lib/api";
import { AutoNoTradePanel } from "@/features/auto/auto-no-trade-panel";

type DailyResp = Awaited<ReturnType<typeof api.getPaperDeskDailyReport>>;

/** Fecha local `YYYY-MM-DD`, idéntica a la del panel (sin desplazamiento de zona). */
function localToday(): string {
  const date = new Date();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function cycle(
  cycleId: string,
  day: string,
  steps: Array<{ id: string; state: string }>,
  extra: Record<string, unknown> = {},
) {
  return {
    cycleId,
    closed: null,
    closedMeasurement: "COMPLETE",
    result: null,
    steps: steps.map((step) => ({
      ...step,
      measurement: "COMPLETE",
      note: null,
      at: `${day}T10:00:00Z`,
    })),
    ...extra,
  };
}

function daily(over: Record<string, unknown> = {}) {
  return {
    estudioStatus: "ok",
    estudioCount: 35,
    autoDesk: {
      entry: {
        status: "executed",
        proposed: 1,
        executed: 1,
        candidates: null,
        skipped: [],
      },
      jitDenies: {},
    },
    ...over,
  };
}

function resetState() {
  state.monitor = { view: null, isLoading: false, isError: false };
  state.blocked = {
    entriesBlocked: false,
    killOn: false,
    vetoed: 0,
    incidentCount: 0,
    incidentsFailed: false,
    paperDExecuteEnv: false,
  };
  state.daily = daily();
}

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AutoNoTradePanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function row(cause: string): HTMLElement {
  const element = screen
    .getAllByTestId("auto-no-trade-row")
    .find((item) => item.dataset.cause === cause);
  if (!element) throw new Error(`fila no encontrada: ${cause}`);
  return element;
}

beforeEach(() => {
  resetState();
  vi.mocked(api.getPaperDeskDailyReport).mockImplementation(
    async () => ({ data: state.daily }) as unknown as DailyResp,
  );
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("P4 · causa ↔ registro y filtro por día", () => {
  it("la causa del motor enlaza con el ciclo del día y descarta el de otro día", async () => {
    // El ciclo ajeno va PRIMERO: si el filtro por día fallara, el enlace apuntaría a él.
    state.monitor = {
      view: {
        cycles: [
          cycle("cyc-ayer", "2020-01-01", [
            { id: "ORDER", state: "reached" },
            { id: "FILL", state: "pending" },
          ]),
          cycle("cyc-hoy", localToday(), [
            { id: "ORDER", state: "reached" },
            { id: "FILL", state: "pending" },
          ]),
        ],
      },
      isLoading: false,
      isError: false,
    };

    renderPanel();

    const target = await waitFor(() => {
      const element = row("order_without_fill");
      expect(element.dataset.status).toBe("occurred");
      return element;
    });
    const links = within(target).getAllByTestId("auto-no-trade-evidence-link");
    expect(links).toHaveLength(1);
    expect(links[0]?.getAttribute("href")).toBe(
      "/auto/operar/operacion/cyc-hoy",
    );
  });

  it("una ejecución sin cierre confirmado enlaza con su propio ciclo", async () => {
    state.monitor = {
      view: {
        cycles: [
          cycle(
            "cyc-fill",
            localToday(),
            [
              { id: "ORDER", state: "reached" },
              { id: "FILL", state: "reached" },
            ],
            { closed: false, closedMeasurement: "COMPLETE" },
          ),
        ],
      },
      isLoading: false,
      isError: false,
    };

    renderPanel();

    const target = await waitFor(() => {
      const element = row("execution_unconfirmed");
      expect(element.dataset.status).toBe("occurred");
      return element;
    });
    expect(
      within(target)
        .getByTestId("auto-no-trade-evidence-link")
        .getAttribute("href"),
    ).toBe("/auto/operar/operacion/cyc-fill");
  });
});

describe("P4 · ausencia real ≠ falta de trazabilidad (causa 4)", () => {
  function withOrderState(orderState: string) {
    state.monitor = {
      view: {
        cycles: [
          cycle("cyc-1", localToday(), [
            { id: "RISK", state: "reached" },
            { id: "ORDER", state: orderState },
          ]),
        ],
      },
      isLoading: false,
      isError: false,
    };
  }

  it("ORDER 'absent' declara la causa con enlace al ciclo", async () => {
    withOrderState("absent");
    renderPanel();

    const target = await waitFor(() => {
      const element = row("decision_without_order");
      expect(element.dataset.status).toBe("occurred");
      return element;
    });
    const links = within(target).getAllByTestId("auto-no-trade-evidence-link");
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link.getAttribute("href")).toBe("/auto/operar/operacion/cyc-1");
    }
  });

  it("ORDER 'unknown' deja la causa en hueco, nunca afirmada", async () => {
    withOrderState("unknown");
    renderPanel();

    await waitFor(() => {
      expect(row("decision_without_order").dataset.status).toBe("unknown");
    });
    expect(
      within(row("decision_without_order")).queryByTestId(
        "auto-no-trade-evidence-link",
      ),
    ).toBeNull();
  });
});

describe("P4 · errores de lectura", () => {
  it("un fallo del monitor deja la cadena del motor en «Sin dato todavía»", async () => {
    state.monitor = { view: null, isLoading: false, isError: true };
    renderPanel();

    await waitFor(() => {
      for (const cause of [
        "decision_without_order",
        "order_without_fill",
        "execution_unconfirmed",
      ]) {
        const element = row(cause);
        expect(element.dataset.status).toBe("unknown");
        expect(
          within(element).getByTestId("auto-no-trade-row-status").textContent,
        ).toBe("Sin dato todavía");
      }
    });
    // El fallo es del motor: la capa de descubrimiento sigue medida (universo `ok`).
    await waitFor(() => {
      expect(row("no_opportunity").dataset.status).toBe("not_applicable");
    });
  });

  it("un fallo de incidentes deja el veto en hueco, no en «No aplica»", async () => {
    state.blocked = {
      ...state.blocked,
      incidentsFailed: true,
      incidentCount: -1,
    };
    renderPanel();

    // La capa ya está cargada (universo `ok`) y, aun así, el veto queda en hueco.
    await waitFor(() => {
      expect(row("no_opportunity").dataset.status).toBe("not_applicable");
    });
    expect(row("risk_regime_veto").dataset.status).toBe("unknown");
  });

  it("sin vetoes ni fallo de lectura el veto se declara «No aplica»", async () => {
    renderPanel();

    await waitFor(() => {
      expect(row("risk_regime_veto").dataset.status).toBe("not_applicable");
    });
  });

  it("un fallo del informe diario deja el descubrimiento en hueco", async () => {
    vi.mocked(api.getPaperDeskDailyReport).mockRejectedValue(new Error("boom"));
    renderPanel();

    await waitFor(() => {
      expect(row("no_opportunity").dataset.status).toBe("unknown");
    });
  });
});

describe("P4 · universo unavailable ≠ empty", () => {
  it("universo no disponible ⇒ hueco, no cero candidatos", async () => {
    state.daily = daily({ estudioStatus: "unavailable" });
    renderPanel();

    const target = await waitFor(() => {
      const element = row("no_opportunity");
      expect(within(element).getByText(/no está disponible/)).toBeTruthy();
      return element;
    });
    expect(target.dataset.status).toBe("unknown");
  });

  it("universo vacío ⇒ «No apareció una oportunidad»", async () => {
    state.daily = daily({ estudioStatus: "empty" });
    renderPanel();

    await waitFor(() => {
      expect(row("no_opportunity").dataset.status).toBe("occurred");
    });
  });
});
