/**
 * DÍA-D AUTO — regresión del panel declarado vs ejecutado.
 *
 * Invariante clave: un valor no medido se pinta `NO MEDIDO`, nunca `0`. Y el panel consume el
 * DTO directo del endpoint (sin envoltorio `data`).
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

vi.mock("@/lib/api", () => ({
  api: {
    getAutoPaperEvidence: vi.fn(async () => ({
      schemaVersion: "paper_evidence_adapter_v1",
      readOnly: true,
      verdict: "NO_CONFIRMED",
      criteria: [],
      contradictions: [],
      notes: [],
      reconciliation: {
        fillsLoaded: false,
        settlementsLoaded: false,
        fillsTotal: 0,
        fillsWithCycle: 0,
        duplicateExecutions: 0,
        orphanExecutions: 0,
        closedCycles: 0,
        anonymousClosedCycles: 0,
        windowDays: null,
        windowEpisodes: null,
        settlementsTotal: 0,
        settlementsReconciled: 0,
        settlementsDivergent: 0,
        settlementsUnmatched: 0,
        cycles: [],
        contradictions: [],
        notes: [],
      },
    })),
    getAutoDiaDReplayDays: vi.fn(async () => ({
      readOnly: true,
      days: ["2026-09-30", "2026-09-29"],
      notes: [],
    })),
    listAutoOpsJobs: vi.fn(async () => ({ jobs: [], notes: [] })),
    getAutoDiaDReplay: vi.fn(async (day: string) => ({
      available: true,
      readOnly: true,
      day,
      artifactModifiedAt: "2026-10-18T20:00:00+00:00",
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
      meta: {
        account: "acc-1",
        versionA: "v283-window-a",
        watchSize: 12,
        watchSource: "pit",
        universeExcludedNoBars: 3,
        horizonDays: 20,
      },
      limits: ["Sandbox read-only: no escribe en la BD durable."],
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

vi.mock("@/features/auto-monitor/dia-d-auto-feedback-panel", () => ({
  DiaDAutoFeedbackPanel: () => <div data-testid="feedback-stub" />,
}));

import { api } from "@/lib/api";
import { DiaDAutoPanel } from "@/features/auto-monitor/dia-d-auto-panel";

function renderPanel(entry = "/auto-monitor?mode=dia-d") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <DiaDAutoPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DiaDAutoPanel", () => {
  it("pinta la cadena y rotula el hueco NO MEDIDO (nunca 0)", async () => {
    renderPanel();

    await waitFor(() =>
      expect(screen.getByTestId("dia-d-auto-steps")).toBeTruthy(),
    );

    const rows = screen.getAllByTestId("dia-d-auto-step");
    expect(rows.map((row) => row.getAttribute("data-step"))).toEqual([
      "SIGNAL",
      "FILL",
    ]);

    const fillRow = rows.find(
      (row) => row.getAttribute("data-step") === "FILL",
    );
    expect(fillRow?.textContent).toContain("NO MEDIDO");
    expect(fillRow?.getAttribute("data-verdict")).toBe("NOT_MEASURED");

    // El veredicto global y los límites también se muestran.
    expect(screen.getByTestId("dia-d-auto-summary").textContent).toContain(
      "n/d 1",
    );
    expect(screen.getByTestId("dia-d-auto-limits").textContent).toContain(
      "Sandbox read-only",
    );
    expect(api.getAutoDiaDReplay).toHaveBeenCalledWith("2026-09-30");
  });

  it("resume nivel 1 y no presenta como aprobación una muestra vacía", async () => {
    renderPanel();

    const summary = await screen.findByTestId("dia-d-auto-level1");
    // closedCount = 0 ⇒ muestra insuficiente, aunque el veredicto sea PARTIAL.
    expect(summary.getAttribute("data-insufficient")).toBe("true");
    const headline = screen.getByTestId("dia-d-auto-level1-headline");
    expect(headline.getAttribute("data-verdict")).toBe("INSUFFICIENT");
    expect(headline.textContent).toContain("Evidencia insuficiente");
    expect(summary.textContent).toContain("1/2 pasos medidos");
    expect(summary.textContent).toContain("12 valores");
    expect(summary.textContent).toContain("excluidos sin barras 3");
    expect(summary.textContent).toContain("0 cerrados");
  });

  it("separa la última ejecución del último artefacto válido", async () => {
    renderPanel();

    const lastRun = await screen.findByTestId("dia-d-auto-last-run");
    expect(lastRun.textContent).toContain("Sin job observado");

    const artifact = screen.getByTestId("dia-d-auto-last-artifact");
    await waitFor(() =>
      expect(artifact.textContent).toContain("2026-10-18T20:00:00+00:00"),
    );
    expect(artifact.textContent).toContain("acc-1");
    expect(artifact.textContent).toContain("v283-window-a");
    expect(artifact.textContent).toContain("20 d");
  });

  it("declara que el enlace con symbol es contexto, no validación individual", async () => {
    renderPanel("/auto-monitor?mode=dia-d&day=2026-09-30&symbol=AAA");

    const context = await screen.findByTestId("dia-d-auto-symbol-context");
    expect(context.textContent).toContain("AAA");
    expect(context.textContent).toContain("global del día");
    expect(context.textContent).toContain("no una validación individual");
  });

  it("lista los días disponibles y permite cambiar de fecha", async () => {
    renderPanel();

    await waitFor(() =>
      expect(screen.getByTestId("dia-d-auto-days")).toBeTruthy(),
    );
    expect(screen.getByTestId("dia-d-auto-days").textContent).toContain(
      "2026-09-29",
    );
    // El primer día disponible se selecciona solo y dispara la lectura del artefacto.
    await waitFor(() =>
      expect(api.getAutoDiaDReplay).toHaveBeenCalledWith("2026-09-30"),
    );

    // Cambiar de fecha vuelve a consultar el artefacto del día elegido.
    screen.getByRole("button", { name: "2026-09-29" }).click();
    await waitFor(() =>
      expect(api.getAutoDiaDReplay).toHaveBeenCalledWith("2026-09-29"),
    );
  });

  it("lee el día D de la URL", async () => {
    renderPanel("/auto-monitor?mode=dia-d&day=2026-09-29");
    await waitFor(() =>
      expect(api.getAutoDiaDReplay).toHaveBeenCalledWith("2026-09-29"),
    );
  });

  it("declara el error de DETALLE del día (no solo el de la lista)", async () => {
    // Rechazo PERSISTENTE (no `Once`): la query del día se remonta una vez tras el primer
    // fallo, así que un rechazo de un solo uso dejaría la vista en verde por error.
    const mock = vi.mocked(api.getAutoDiaDReplay);
    const original = mock.getMockImplementation();
    mock.mockRejectedValue(new Error("artefacto ilegible"));

    renderPanel();

    const err = await screen.findByTestId("dia-d-auto-detail-error");
    expect(err.getAttribute("role")).toBe("alert");
    expect(err.textContent).toContain("artefacto ilegible");

    if (original) mock.mockImplementation(original);
  });

  it("completa el patrón WAI-ARIA: tab ↔ tabpanel y roving tabIndex", () => {
    renderPanel();

    const tablist = screen.getByTestId("dia-d-auto-view-toolbar");
    expect(tablist.getAttribute("role")).toBe("tablist");

    const sandbox = screen.getByTestId("dia-d-auto-view-sandbox");
    expect(sandbox.getAttribute("role")).toBe("tab");
    expect(sandbox.getAttribute("aria-selected")).toBe("true");
    expect(sandbox.getAttribute("tabIndex")).toBe("0");
    expect(sandbox.getAttribute("aria-controls")).toBe(
      "dia-d-auto-view-panel-sandbox",
    );

    // La pestaña inactiva no participa del orden de tabulación (roving).
    expect(
      screen.getByTestId("dia-d-auto-view-feedback").getAttribute("tabIndex"),
    ).toBe("-1");

    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("id")).toBe("dia-d-auto-view-panel-sandbox");
    expect(panel.getAttribute("aria-labelledby")).toBe(
      "dia-d-auto-view-tab-sandbox",
    );
  });

  it("cambia de vista con flechas y Home/End", () => {
    renderPanel();

    // ArrowRight ⇒ feedback.
    fireEvent.keyDown(screen.getByTestId("dia-d-auto-view-sandbox"), {
      key: "ArrowRight",
    });
    expect(
      screen
        .getByTestId("dia-d-auto-view-feedback")
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(screen.getByRole("tabpanel").getAttribute("id")).toBe(
      "dia-d-auto-view-panel-feedback",
    );

    // Home ⇒ vuelve a sandbox.
    fireEvent.keyDown(screen.getByTestId("dia-d-auto-view-feedback"), {
      key: "Home",
    });
    expect(
      screen
        .getByTestId("dia-d-auto-view-sandbox")
        .getAttribute("aria-selected"),
    ).toBe("true");

    // End ⇒ última pestaña (feedback).
    fireEvent.keyDown(screen.getByTestId("dia-d-auto-view-sandbox"), {
      key: "End",
    });
    expect(
      screen
        .getByTestId("dia-d-auto-view-feedback")
        .getAttribute("aria-selected"),
    ).toBe("true");
  });
});
