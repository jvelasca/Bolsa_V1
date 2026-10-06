/**
 * DÍA-D AUTO · FEEDBACK — regresión de la vista por valor.
 *
 * Invariantes clave:
 * 1. Un valor no medido se pinta `NO MEDIDO`, nunca `0`.
 * 2. La sub-vista NO dispara queries de feedback mientras se está en el sandbox por día.
 3. El catálogo de errores rotula la familia SOFTWARE y su código.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({ setData: vi.fn() }),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove: vi.fn(),
  }),
  ColorType: { Solid: "solid" },
  CrosshairMode: { Magnet: 0 },
  LineSeries: "LineSeries",
}));

const FEEDBACK = {
  available: true,
  readOnly: true,
  schemaVersion: "dia-d-feedback-v2",
  kind: "DIA_D_AUTO_FEEDBACK",
  window: {
    from: "2026-09-29",
    to: "2026-09-30",
    days: ["2026-09-29", "2026-09-30"],
  },
  matrixBasis: "entryDay",
  summary: {
    values: 3,
    oosSupported: 1,
    mixed: 0,
    refuted: 0,
    notMeasured: 2,
    measuredValues: 1,
    byEvidenceQuality: {
      NOT_MEASURED: 2,
      PRELIMINARY: 1,
      SUPPORTED: 0,
      STRONG: 0,
    },
    errors: { SOFTWARE: 1, OPERATIONAL: 0, DATA: 0, total: 1 },
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
      realizedRTotal: 3.0,
      errors: { SOFTWARE: 0, OPERATIONAL: 0, DATA: 0, total: 0 },
      errorTotal: 0,
      byDay: {
        "2026-09-29": { realizedR: 3.0, cycles: 6, errors: 0 },
        "2026-09-30": { realizedR: null, cycles: 0, errors: 0 },
      },
      limits: { minCycles: 5, minHitRate: 0.5 },
    },
    {
      symbol: "BBB",
      verdict: "NOT_MEASURED",
      verdictReason: "insufficient_sample",
      evidenceQuality: "NOT_MEASURED",
      expectancyR: null,
      hitRate: null,
      measuredCycles: 2,
      daysCovered: 1,
      windowDays: 2,
      realizedRTotal: null,
      errors: { SOFTWARE: 0, OPERATIONAL: 0, DATA: 0, total: 0 },
      errorTotal: 0,
      byDay: {
        "2026-09-29": { realizedR: 1.0, cycles: 2, errors: 0 },
        "2026-09-30": { realizedR: null, cycles: 0, errors: 0 },
      },
      limits: { minCycles: 5, minHitRate: 0.5 },
    },
    {
      symbol: "CCC",
      verdict: "REFUTED",
      verdictReason: "software_divergence",
      evidenceQuality: "PRELIMINARY",
      expectancyR: 0.1,
      hitRate: 0.5,
      measuredCycles: 5,
      daysCovered: 1,
      windowDays: 2,
      realizedRTotal: 0.5,
      errors: { SOFTWARE: 1, OPERATIONAL: 0, DATA: 0, total: 1 },
      errorTotal: 1,
      byDay: {
        "2026-09-29": { realizedR: 0.5, cycles: 5, errors: 1 },
        "2026-09-30": { realizedR: null, cycles: 0, errors: 0 },
      },
      limits: { minCycles: 5, minHitRate: 0.5 },
    },
  ],
  matrix: [
    {
      symbol: "AAA",
      cells: [
        {
          day: "2026-09-29",
          realizedR: 3.0,
          cycles: 6,
          errors: 0,
          outcome: "GAIN",
        },
        {
          day: "2026-09-30",
          realizedR: null,
          cycles: 0,
          errors: 0,
          outcome: "NOT_MEASURED",
        },
      ],
    },
    {
      symbol: "BBB",
      cells: [
        {
          day: "2026-09-29",
          realizedR: 1.0,
          cycles: 2,
          errors: 0,
          outcome: "GAIN",
        },
        {
          day: "2026-09-30",
          realizedR: null,
          cycles: 0,
          errors: 0,
          outcome: "NOT_MEASURED",
        },
      ],
    },
    {
      symbol: "CCC",
      cells: [
        {
          day: "2026-09-29",
          realizedR: 0.5,
          cycles: 5,
          errors: 1,
          outcome: "ERROR",
        },
        {
          day: "2026-09-30",
          realizedR: null,
          cycles: 0,
          errors: 0,
          outcome: "NOT_MEASURED",
        },
      ],
    },
  ],
  errors: [
    { day: "2026-09-29", symbol: "CCC", kind: "SOFTWARE", code: "FILL" },
  ],
  gate: {
    verdict: "INCONCLUSIVE",
    days: 2,
    episodes: 1,
    cycles: 6,
    ready: false,
  },
  meta: { account: "acc-1" },
  limits: ["Advisory read-only: no cambia el motor."],
  notes: [],
};

vi.mock("@/lib/api", () => ({
  api: {
    getAutoDiaDFeedbackList: vi.fn(async () => ({
      readOnly: true,
      windows: ["2026-09-29_2026-09-30"],
      latest: "2026-09-29_2026-09-30",
      artifact: FEEDBACK,
      notes: [],
    })),
    getAutoDiaDFeedback: vi.fn(async () => FEEDBACK),
    getAutoDiaDReplayDays: vi.fn(async () => ({
      readOnly: true,
      days: ["2026-09-30"],
      notes: [],
    })),
    getAutoDiaDReplay: vi.fn(async (day: string) => ({
      available: true,
      readOnly: true,
      day,
      schemaVersion: "dia-d-auto-v1",
      summary: {
        verdict: "PARTIAL",
        match: 1,
        divergent: 0,
        notMeasured: 1,
        steps: 2,
      },
      steps: [
        {
          step: "SIGNAL",
          declared: 1,
          executed: 1,
          verdict: "MATCH",
          measurement: "COMPLETE",
        },
        {
          step: "FILL",
          declared: 2,
          executed: null,
          verdict: "NOT_MEASURED",
          measurement: "UNKNOWN",
        },
      ],
      oos: {
        closedCount: 0,
        openCount: 0,
        realizedRTotal: 0,
        unmeasuredCount: 0,
        realized: [],
        open: [],
      },
      meta: { account: "acc-1" },
      limits: ["Sandbox read-only."],
      executedDetail: {},
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

import { api } from "@/lib/api";
import { DiaDAutoFeedbackPanel } from "@/features/auto-monitor/dia-d-auto-feedback-panel";
import { DiaDAutoPanel } from "@/features/auto-monitor/dia-d-auto-panel";

function renderWithClient(
  ui: React.ReactElement,
  entry = "/auto-monitor?mode=dia-d&view=feedback",
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DiaDAutoFeedbackPanel", () => {
  it("rotula NO MEDIDO (nunca 0) y pinta el catálogo de errores", async () => {
    renderWithClient(<DiaDAutoFeedbackPanel />);

    await waitFor(() =>
      expect(screen.getByTestId("dia-d-auto-feedback-values")).toBeTruthy(),
    );

    const rows = screen.getAllByTestId("dia-d-auto-feedback-value");
    const notMeasured = rows.find(
      (row) => row.getAttribute("data-symbol") === "BBB",
    );
    expect(notMeasured?.getAttribute("data-verdict")).toBe("NOT_MEASURED");
    expect(notMeasured?.textContent).toContain("NO MEDIDO");
    expect(notMeasured?.textContent).not.toContain("0.00");

    // El veredicto OOS NO se rotula "Confirmado" y la evidencia es un eje aparte.
    const supported = rows.find(
      (row) => row.getAttribute("data-symbol") === "AAA",
    );
    expect(supported?.getAttribute("data-verdict")).toBe("OOS_SUPPORTED");
    expect(supported?.textContent).toContain("Soportado OOS");
    expect(supported?.textContent).toContain("Preliminar");
    expect(
      screen
        .getAllByTestId("dia-d-auto-feedback-evidence")
        .some((badge) => badge.getAttribute("data-evidence") === "PRELIMINARY"),
    ).toBe(true);

    // El heatmap marca los días sin medición sin pintarlos como ganancia/pérdida.
    const cells = screen.getAllByTestId("dia-d-auto-feedback-cell");
    expect(
      cells.some(
        (cell) => cell.getAttribute("data-outcome") === "NOT_MEASURED",
      ),
    ).toBe(true);
    expect(
      cells.some((cell) => cell.getAttribute("data-outcome") === "ERROR"),
    ).toBe(true);

    // El catálogo rotula la familia SOFTWARE y su código.
    expect(screen.getByTestId("dia-d-auto-error-list").textContent).toContain(
      "Software",
    );
    expect(screen.getByTestId("dia-d-auto-error-list").textContent).toContain(
      "FILL",
    );
    // El panel pinta primero el artefacto del listado (fallback) y sólo después dispara la
    // query de detalle: la aserción debe esperar al EFECTO, no al primer render con valores.
    await waitFor(() =>
      expect(api.getAutoDiaDFeedback).toHaveBeenCalledWith(
        "2026-09-29_2026-09-30",
      ),
    );

    // D35-04: el encabezado evalúa evidencia OOS, ya no habla de "confirmar/refutar".
    const panel = screen.getByTestId("dia-d-auto-feedback-panel");
    expect(panel.textContent).toContain("Evalúa");
    expect(panel.textContent).not.toContain("Confirma");
  });

  it("preselecciona el símbolo de la URL (enlace de EXPLICACIÓN)", async () => {
    renderWithClient(
      <DiaDAutoFeedbackPanel />,
      "/auto-monitor?mode=dia-d&view=feedback&window=2026-09-29_2026-09-30&symbol=BBB",
    );
    await waitFor(() =>
      expect(screen.getByTestId("dia-d-auto-feedback-values")).toBeTruthy(),
    );
    const focused = screen
      .getAllByTestId("dia-d-auto-feedback-value")
      .filter((row) => row.getAttribute("data-focused") === "true");
    expect(focused.map((row) => row.getAttribute("data-symbol"))).toEqual([
      "BBB",
    ]);
  });
});

describe("DiaDAutoPanel view switching", () => {
  it("no dispara queries de feedback en el modo sandbox", async () => {
    renderWithClient(<DiaDAutoPanel />, "/auto-monitor?mode=dia-d");

    await waitFor(() =>
      expect(screen.getByTestId("dia-d-auto-steps")).toBeTruthy(),
    );
    expect(api.getAutoDiaDFeedbackList).not.toHaveBeenCalled();
    expect(api.getAutoDiaDFeedback).not.toHaveBeenCalled();

    // Al cambiar a Feedback por valor sí se consulta el artefacto.
    screen.getByRole("tab", { name: "Feedback por valor" }).click();
    await waitFor(() => expect(api.getAutoDiaDFeedbackList).toHaveBeenCalled());
  });
});
