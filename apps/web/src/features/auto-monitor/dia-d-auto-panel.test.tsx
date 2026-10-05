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
    getAutoDiaDReplayDays: vi.fn(async () => ({
      readOnly: true,
      days: ["2026-09-30", "2026-09-29"],
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
      meta: { account: "acc-1", versionA: "v283-window-a" },
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
