/**
 * Asesor → Diario · panel tolerante a un parte parcial (H-22).
 *
 * Lo que debe morder:
 *   - un parte completo sigue pintando lo mismo (no hay regresión);
 *   - un parte **sin** `tradesToday`, `notes`, `week`, `channels`, `opinions` ni
 *     `summary` se declara ausente en vez de romper la pantalla;
 *   - un `tradesToday: []` real **sí** afirma cero («Sin compras/ventas
 *     registradas hoy»), porque ahí el cero se midió.
 *
 * La diferencia entre los dos últimos casos es todo el punto: `UNKNOWN ≠ 0`.
 *
 * @see docs/engineering/auditoria-operativa-asesor-2026-11-15.md §6.b (H-22)
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";

const state = vi.hoisted(() => ({
  payload: undefined as unknown,
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1", name: "Cuenta DEMO" },
    isLoading: false,
    accounts: [],
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getDailyOpsReport: () => Promise.resolve({ data: state.payload }),
    getHealth: () =>
      Promise.resolve({
        status: "ok",
        service: "api",
        timestamp: "2026-11-15T20:00:00Z",
        components: {},
      }),
    downloadDailyOpsDigestPdf: () => Promise.resolve(new Blob()),
    sendDailyOpsDigestEmail: () => Promise.resolve({ data: { sent: false } }),
  },
}));

const { AsesorDailyOpsPanel } = await import("./asesor-daily-ops-panel");

afterEach(() => cleanup());

const FULL = {
  schemaVersion: "daily_ops_report_v1",
  asOf: "2026-11-15",
  generatedAt: "2026-11-15T20:00:00Z",
  accountId: "acc-1",
  summary: {
    totalEquity: 25430.55,
    cash: 10120.4,
    totalUnrealizedPnl: -186.2,
    positionsCount: 3,
  },
  ledgerToday: [
    {
      id: "l-1",
      type: "BUY",
      symbol: "AAA",
      instrumentId: "inst-1",
      quantity: 10,
      price: 10.5,
      amount: 105,
    },
  ],
  tradesToday: [
    {
      id: "t-1",
      type: "BUY",
      symbol: "AAA",
      instrumentId: "inst-1",
      quantity: 10,
      price: 10.5,
      amount: 105,
    },
  ],
  week: [
    {
      date: "2026-11-10",
      tradeCount: 1,
      ledgerCount: 1,
      balanceAfter: 25300,
      netAmount: 120,
    },
  ],
  f3PendingCount: 2,
  channels: { alarma: 1, aviso: 2, none: 0 },
  opinions: [],
  notes: ["El resumen no autoriza operaciones."],
  estudioStatus: "ok",
  estudioCount: 3,
};

/** Parte recortado: solo los campos que siempre llegan. */
const PARTIAL = {
  schemaVersion: "daily_ops_report_v1",
  asOf: "2026-11-15",
  generatedAt: "2026-11-15T20:00:00Z",
  accountId: "acc-1",
  estudioStatus: "ok",
  estudioCount: 0,
};

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AsesorDailyOpsPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Espera a que el parte esté aplicado. El contenedor existe desde el primer
 * render, así que esperar por él no prueba nada: se espera por el bloque que
 * solo se pinta cuando `report` llegó.
 */
async function waitForReport() {
  await screen.findByText("Actividad del día (lectura)");
}

describe("AsesorDailyOpsPanel · parte completo", () => {
  it("pinta la actividad, la semana y las notas sin cambios", async () => {
    state.payload = FULL;
    renderPanel();

    await waitForReport();
    const panel = screen.getByTestId("asesor-daily-ops");
    expect(panel.textContent).toContain("Trades 1");
    expect(panel.textContent).toContain("F3 pendiente 2");
    expect(panel.textContent).toContain("AAA");
    expect(panel.textContent).toContain("El resumen no autoriza operaciones.");
    expect(
      screen.getByRole("img", { name: /Evolución semanal/i }),
    ).toBeTruthy();
    expect(screen.queryByTestId("asesor-week-absent")).toBeNull();
  });
});

describe("AsesorDailyOpsPanel · parte parcial (H-22)", () => {
  it("no rompe y declara la ausencia en vez de afirmar cero", async () => {
    state.payload = PARTIAL;
    renderPanel();

    await waitForReport();
    const panel = screen.getByTestId("asesor-daily-ops");
    // Nada de pantalla de error ni de excepción: el panel existe.
    expect(panel).toBeTruthy();
    expect(panel.textContent).toContain(ABSENT_DATA_NOT_MEASURED);
    // Un hueco NO puede leerse como «cero operaciones».
    expect(panel.textContent).not.toContain(
      "Sin compras/ventas registradas hoy.",
    );
    expect(panel.textContent).not.toContain("Sin dictámenes para el Estudio");
    // El gráfico declara en vez de dibujar un SVG sin datos.
    expect(screen.getByTestId("asesor-week-absent")).toBeTruthy();
    expect(
      screen.queryByRole("img", { name: /Evolución semanal/i }),
    ).toBeNull();
    // Las notas ausentes no se renderizan como lista vacía con título.
    expect(panel.textContent).not.toContain("El resumen no autoriza");
  });

  it("un `null` explícito del backend también se declara", async () => {
    state.payload = { ...PARTIAL, tradesToday: null, week: null, notes: null };
    renderPanel();

    await waitForReport();
    const panel = screen.getByTestId("asesor-daily-ops");
    expect(panel.textContent).not.toContain(
      "Sin compras/ventas registradas hoy.",
    );
    expect(screen.getByTestId("asesor-week-absent")).toBeTruthy();
  });
});

describe("AsesorDailyOpsPanel · cero medido", () => {
  it("un array vacío de verdad sí afirma cero operaciones", async () => {
    state.payload = { ...FULL, tradesToday: [], ledgerToday: [], opinions: [] };
    renderPanel();

    await waitForReport();
    const panel = screen.getByTestId("asesor-daily-ops");
    expect(panel.textContent).toContain("Trades 0");
    expect(panel.textContent).toContain("Sin compras/ventas registradas hoy.");
    expect(panel.textContent).toContain("Sin dictámenes para el Estudio");
  });

  it("una semana vacía declara sin movimientos y no dibuja el SVG", async () => {
    state.payload = { ...FULL, week: [] };
    renderPanel();

    await waitForReport();
    const absent = screen.getByTestId("asesor-week-absent");
    expect(absent.textContent).toContain("Sin movimientos registrados");
    expect(
      screen.queryByRole("img", { name: /Evolución semanal/i }),
    ).toBeNull();
  });
});
