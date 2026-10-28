/**
 * Secciones AUTO (ADR-044) — estructura mínima.
 *
 * Comprueba que cada página de sección expone exactamente un `<h1>` (título de
 * página) y los enlaces/operaciones clave. El story panel se mockea para aislar la
 * estructura de la sección del I/O de red; el monitor se controla desde `monitorState`
 * para ejercitar carga/error/vacío.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

vi.mock("@/features/auto-monitor/auto-operation-story-panel", () => ({
  AutoOperationStoryPanel: () => <div data-testid="story-stub" />,
}));

const monitorState = vi.hoisted(() => ({
  cycles: [] as Array<Record<string, unknown>>,
  signalHolds: [] as Array<Record<string, unknown>>,
  isLoading: false,
  isError: false,
  readState: undefined as string | undefined,
}));

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => ({
    view:
      monitorState.readState === "not_consulted"
        ? null
        : {
            cycles: monitorState.cycles,
            signalHolds: monitorState.signalHolds,
          },
    isLoading: monitorState.isLoading,
    isError: monitorState.isError,
    isFetching: false,
    readState: monitorState.readState,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/auto/use-auto-top3-opportunities", () => ({
  useAutoTop3Opportunities: () => ({
    view: null,
    isLoading: false,
    isError: false,
  }),
}));

// P2 — la lanzadera de verificación tiene su propio test; aquí se aísla la estructura de la
// sección (evita montar las queries de estrategia/TOP en este test de páginas).
vi.mock("@/features/auto/auto-operar-verify-action", () => ({
  AutoOperarVerifyAction: () => null,
}));

import { AutoOperarPage } from "@/features/auto/auto-operar-page";
import { AutoOperacionPage } from "@/features/auto/auto-operacion-page";

const CYCLES = [
  {
    cycleId: "cyc-1",
    instrumentId: "AAPL",
    directionLabel: "Largo",
    statusLabel: "Precio aplicado",
    steps: [{ id: "SIGNAL", at: "2026-10-03T09:00:00Z" }],
  },
  {
    cycleId: "cyc-2",
    instrumentId: "MSFT",
    directionLabel: "Largo",
    statusLabel: "Orden anotada",
    steps: [{ id: "SIGNAL", at: "2026-10-04T09:00:00Z" }],
  },
  {
    cycleId: "cyc-3",
    instrumentId: "AAPL",
    directionLabel: "Corto",
    statusLabel: "Cerrada",
    steps: [{ id: "SIGNAL", at: "2026-10-05T09:00:00Z" }],
  },
];

beforeEach(() => {
  monitorState.cycles = CYCLES;
  monitorState.signalHolds = [];
  monitorState.isLoading = false;
  monitorState.isError = false;
  monitorState.readState = undefined;
});

afterEach(cleanup);

function singleH1() {
  return screen.queryAllByRole("heading", { level: 1 });
}

function renderOperar() {
  return render(
    <MemoryRouter initialEntries={["/auto/operar"]}>
      <AutoOperarPage />
    </MemoryRouter>,
  );
}

describe("AutoOperarPage", () => {
  it("expone un h1 y enlaza cada operación a la ruta canónica", () => {
    renderOperar();
    expect(singleH1()).toHaveLength(1);
    expect(singleH1()[0]?.textContent).toBe("Operar");
    const links = screen.getAllByTestId("auto-operar-operation-link");
    expect(links).toHaveLength(3);
    expect(
      links
        .find((l) => l.getAttribute("data-cycle-id") === "cyc-1")
        ?.getAttribute("href"),
    ).toBe("/auto/operar/operacion/cyc-1");
    // Una sola fuente de selección: la lista. La historia vive en su ruta canónica.
    expect(screen.queryByTestId("story-stub")).toBeNull();
  });

  it("identifica dos ciclos del mismo símbolo de forma distinguible", () => {
    renderOperar();
    const links = screen.getAllByTestId("auto-operar-operation-link");
    const aapl = links
      .filter((l) => l.textContent?.includes("AAPL"))
      .map((l) => l.textContent ?? "");
    expect(aapl).toHaveLength(2);
    // Mismo símbolo, distinta entrada → etiquetas humanas distintas (no `cycleId`).
    expect(aapl[0]).not.toBe(aapl[1]);
    expect(aapl[0]).toContain("03 oct");
    expect(aapl[1]).toContain("05 oct");
  });

  it("marca cada operación con su modo y su peldaño (UI5-10/09)", () => {
    renderOperar();
    const badges = screen.getAllByTestId(/^auto-operar-mode-/);
    expect(badges).toHaveLength(3);
    for (const badge of badges) {
      expect(badge.textContent).toBe("AUTO · SIMULADO");
      expect(badge.dataset.channel).toBe("SIMULADO");
    }
    // Sin evidencia de fill, el peldaño se declara; jamás se salta a «Posición creada».
    for (const link of screen.getAllByTestId("auto-operar-operation-link")) {
      expect(link.textContent).not.toContain("Posición creada");
    }
  });

  it("muestra el bloque Oportunidades como lanzadera a la Mesa", () => {
    renderOperar();
    expect(screen.getByTestId("auto-operar-opportunities")).toBeTruthy();
    expect(
      screen.getByTestId("auto-operar-opportunities-link").getAttribute("href"),
    ).toContain("oportunidades");
  });

  it("el error se declara distinto del vacío", () => {
    monitorState.isError = true;
    monitorState.cycles = [];
    renderOperar();
    expect(screen.getByTestId("auto-operar-error")).toBeTruthy();
    expect(screen.queryByTestId("auto-operar-empty")).toBeNull();
  });

  it("el vacío real sólo aparece sin carga ni error", () => {
    monitorState.cycles = [];
    renderOperar();
    expect(screen.getByTestId("auto-operar-empty")).toBeTruthy();
    expect(screen.queryByTestId("auto-operar-error")).toBeNull();
  });

  it("el vacío declara qué pasó con la señal y enlaza a la explicación (B-5)", () => {
    monitorState.cycles = [];
    monitorState.signalHolds = [
      {
        instrumentId: "AAA",
        reason: "warmup_unmeasurable",
        measurement: "COMPLETE",
        facts: [],
      },
      {
        instrumentId: "BBB",
        reason: "no_signal",
        measurement: "COMPLETE",
        facts: [],
      },
    ];
    renderOperar();

    const silence = screen.getByTestId("auto-operar-silence");
    expect(silence.textContent).toContain("1 sin señal");
    expect(silence.textContent).toContain("1 HOLD no evaluable");
    expect(silence.textContent).toContain("faltan datos");
    const link = screen.getByTestId("auto-operar-why-link");
    expect(link.getAttribute("href")).toBe("/auto/actividad");
    expect(link.textContent).toBe("Ver por qué AUTO no operó");
  });

  it("sin declaraciones el vacío no afirma «sin señal» (declara el hueco)", () => {
    monitorState.cycles = [];
    monitorState.signalHolds = [];
    renderOperar();

    expect(screen.getByTestId("auto-operar-silence").textContent).toBe(
      "Sin HOLD declarados en la ventana",
    );
    expect(screen.getByTestId("auto-operar-silence").textContent).not.toContain(
      "sin señal",
    );
    expect(screen.getByTestId("auto-operar-why-link")).toBeTruthy();
  });

  it("con operaciones en curso el silencio de la señal sigue visible (B-5)", () => {
    monitorState.signalHolds = [
      {
        instrumentId: "AAA",
        reason: "gated_unavailable",
        measurement: "COMPLETE",
        facts: [],
      },
    ];
    renderOperar();

    // No se oculta el HOLD porque haya actividad: es un hecho de la señal, no de la operación.
    expect(
      screen.getByTestId("auto-operar-hold-summary").textContent,
    ).toContain("Ningún HOLD con señal evaluada");
    // El enlace a Actividad no se duplica en la lista de operaciones.
    expect(screen.queryByTestId("auto-operar-why-link")).toBeNull();
    expect(screen.getByTestId("auto-operar-activity-link")).toBeTruthy();
  });

  it("sin declaraciones y con operaciones no inventa un titular de silencio", () => {
    monitorState.signalHolds = [];
    renderOperar();

    expect(screen.queryByTestId("auto-operar-hold-summary")).toBeNull();
  });

  it("UI5-04: el HOLD se declara una sola vez y siempre antes de la lista", () => {
    monitorState.signalHolds = [
      {
        instrumentId: "AAA",
        reason: "gated_unavailable",
        measurement: "COMPLETE",
        facts: [],
      },
    ];
    renderOperar();

    const hold = screen.getByTestId("auto-operar-hold-summary");
    const list = screen
      .getAllByTestId("auto-operar-operation-link")[0]
      ?.closest("ul");
    expect(list).toBeTruthy();
    expect(
      hold.compareDocumentPosition(list!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // Un hecho, una posición: no hay dos titulares de silencio en la página.
    expect(
      screen.getAllByTestId(/^auto-operar-(silence|hold-summary)$/),
    ).toHaveLength(1);
  });

  it("UI5-04: sin operaciones el HOLD también va antes del vacío", () => {
    monitorState.cycles = [];
    monitorState.signalHolds = [];
    renderOperar();

    const silence = screen.getByTestId("auto-operar-silence");
    const empty = screen.getByTestId("auto-operar-empty");
    expect(
      silence.compareDocumentPosition(empty) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen.getAllByTestId(/^auto-operar-(silence|hold-summary)$/),
    ).toHaveLength(1);
  });

  it("la carga se declara, no se presenta como vacío", () => {
    monitorState.isLoading = true;
    monitorState.cycles = [];
    renderOperar();
    expect(screen.getByTestId("auto-operar-loading")).toBeTruthy();
    expect(screen.queryByTestId("auto-operar-empty")).toBeNull();
  });

  it("una consulta no ejecutada no se presenta como ventana sin operaciones", () => {
    monitorState.readState = "not_consulted";
    renderOperar();

    expect(
      screen.getByTestId("auto-operar-not-consulted").textContent,
    ).toContain("no se pudieron leer las operaciones");
    // Ni el vacío de operaciones ni el titular de HOLD se afirman sin lectura.
    expect(screen.queryByTestId("auto-operar-empty")).toBeNull();
    expect(screen.queryByTestId("auto-operar-silence")).toBeNull();
  });
});

function renderOperacion(cycleId: string) {
  return render(
    <MemoryRouter initialEntries={[`/auto/operar/operacion/${cycleId}`]}>
      <Routes>
        <Route
          path="/auto/operar/operacion/:cycleId"
          element={<AutoOperacionPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AutoOperacionPage", () => {
  it("expone un h1 con el instrumento del ciclo seleccionado", () => {
    renderOperacion("cyc-2");
    expect(singleH1()).toHaveLength(1);
    expect(singleH1()[0]?.textContent).toContain("MSFT");
  });

  it("un cycleId inexistente se declara con el id pedido, sin inventar otro ciclo", () => {
    renderOperacion("does-not-exist");
    expect(singleH1()).toHaveLength(1);
    expect(singleH1()[0]?.textContent).toContain("does-not-exist");
    expect(singleH1()[0]?.textContent).not.toContain("AAPL");
    expect(singleH1()[0]?.textContent).not.toContain("MSFT");
  });

  it("un ciclo fuera de la ventana se distingue del id ausente y declara el id pedido", () => {
    monitorState.isLoading = false;
    monitorState.cycles = CYCLES; // solo cyc-1..cyc-3
    renderOperacion("cyc-viejo");
    const hole = screen.getByTestId("auto-operacion-sheet-hole");
    expect(hole.textContent).toContain("cyc-viejo");
    expect(hole.textContent).toContain("ventana");
    // No cae a la ficha de otro ciclo ni se presenta como «cargando».
    expect(screen.queryByTestId("auto-operacion-loading")).toBeNull();
    expect(screen.queryByTestId("auto-operacion-page")).toBeTruthy();
  });

  it("mientras el monitor carga NO declara un falso hueco", () => {
    monitorState.isLoading = true;
    monitorState.cycles = [];
    renderOperacion("cyc-2");
    expect(screen.getByTestId("auto-operacion-loading")).toBeTruthy();
    expect(screen.queryByTestId("auto-operacion-sheet-hole")).toBeNull();
  });
});
