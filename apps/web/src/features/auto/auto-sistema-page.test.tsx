/**
 * AUTO · SISTEMA — sólo diagnóstico; el estado en frases ya no re-espeja la HOME (UI5-19).
 *
 * Verifica que el estado de AUTO (antes duplicado del primer nivel de la HOME) vive ahora dentro
 * del bloque «Detalle técnico» plegado por defecto, junto al monitor crudo.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

const monitorState = vi.hoisted(() => ({
  view: null as Record<string, unknown> | null,
  isLoading: false,
  isError: false,
}));

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => ({
    view: monitorState.view,
    isLoading: monitorState.isLoading,
    isError: monitorState.isError,
    isFetching: false,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
    accounts: [],
  }),
}));

const reconState = vi.hoisted(() => ({
  selfEval: undefined as
    | { portfolioReconciliation?: { status?: string } }
    | undefined,
  lifecycle: undefined as
    | {
        status: string;
        driftCount: number;
        lagCount: number;
        blockedCount: number;
      }
    | undefined,
}));

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({
    data: reconState.selfEval,
    isLoading: false,
    isError: false,
  }),
  portfolioReconStatusFromReport: (
    report: { portfolioReconciliation?: { status?: string } } | undefined,
  ) => report?.portfolioReconciliation?.status ?? null,
}));
vi.mock("@/features/operational-console/use-lifecycle-reconciliation", () => ({
  useLifecycleReconciliation: () => ({
    data: reconState.lifecycle,
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock("@/features/auto-monitor/auto-monitor-header", () => ({
  AutoMonitorHeader: () => <div data-testid="monitor-header-stub" />,
}));
vi.mock("@/features/auto-monitor/auto-cycle-timeline", () => ({
  AutoCycleTimeline: () => <div data-testid="monitor-timeline-stub" />,
}));
vi.mock("@/features/auto-monitor/auto-reservation-panel", () => ({
  AutoReservationPanel: () => <div data-testid="monitor-reservations-stub" />,
}));
vi.mock("@/features/auto-monitor/auto-concurrency-panel", () => ({
  AutoConcurrencyPanel: () => <div data-testid="monitor-concurrency-stub" />,
}));
vi.mock("@/features/operational-console/operational-console-sections", () => ({
  OpsReconSection: () => <div data-testid="ops-recon-stub" />,
  OpsLifecycleReconSection: () => <div data-testid="ops-lifecycle-stub" />,
}));

import { AutoSistemaPage } from "@/features/auto/auto-sistema-page";

beforeEach(() => {
  monitorState.view = {
    header: {
      state: "RUNNING",
      lastDecisionAt: "2026-10-06T09:42:00Z",
      nextDecisionAt: "2026-10-06T10:00:00Z",
    },
    cycles: [],
    reservations: [],
    concurrency: {},
  };
  monitorState.isLoading = false;
  monitorState.isError = false;
  reconState.selfEval = undefined;
  reconState.lifecycle = undefined;
});

afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/auto/sistema"]}>
      <AutoSistemaPage />
    </MemoryRouter>,
  );
}

describe("AutoSistemaPage", () => {
  it("expone un h1 y el estado en lenguaje de usuario dentro del detalle técnico", () => {
    renderPage();
    expect(screen.queryAllByRole("heading", { level: 1 })).toHaveLength(1);
    const detail = screen.getByTestId("auto-sistema-technical");
    expect(detail.contains(screen.getByTestId("auto-sistema-auto"))).toBe(true);
    expect(
      detail.contains(screen.getByTestId("auto-sistema-human-state")),
    ).toBe(true);
    expect(screen.getByTestId("auto-sistema-auto").textContent).toContain(
      "Funcionando",
    );
    expect(screen.getByTestId("auto-sistema-doing").textContent).toBe(
      "Sin dato todavía",
    );
    expect(screen.getByTestId("auto-sistema-last-activity").textContent).toBe(
      "Última decisión: 09:42 · Próxima decisión: 10:00",
    );
    expect(
      screen.getByTestId("auto-sistema-last-activity").textContent,
    ).not.toContain("Esperando nueva señal");
    expect(
      screen.getByTestId("auto-sistema-last-activity").textContent,
    ).not.toContain("análisis");
  });

  it("la fase operacional del tick se pinta sin inventar desde RUNNING", () => {
    monitorState.view = {
      ...monitorState.view,
      header: {
        state: "RUNNING",
        currentActivity: "ANALYZING",
        currentActivityMeasurement: "COMPLETE",
        currentActivityAt: "2026-10-06T09:42:00Z",
        currentActivityAtMeasurement: "COMPLETE",
        asOf: "2026-10-06T09:43:00Z",
      },
    };
    renderPage();
    expect(screen.getByTestId("auto-sistema-doing").textContent).toBe(
      "Analizando",
    );
    expect(screen.getByTestId("auto-sistema-doing").textContent).not.toBe(
      "Funcionando",
    );
  });

  it("el monitor crudo vive en un detalle técnico plegado", () => {
    renderPage();
    const detail = screen.getByTestId("auto-sistema-technical");
    expect(detail.tagName).toBe("DETAILS");
    expect((detail as HTMLDetailsElement).open).toBe(false);
    expect(screen.getByTestId("monitor-header-stub")).toBeTruthy();
    expect(screen.getByTestId("monitor-timeline-stub")).toBeTruthy();
  });

  it("el error se declara distinto del estado vacío", () => {
    monitorState.isError = true;
    monitorState.view = null;
    renderPage();
    expect(screen.getByTestId("auto-sistema-error")).toBeTruthy();
    expect(screen.queryByTestId("auto-sistema-doing")).toBeNull();
  });

  it("la carga se declara", () => {
    monitorState.isLoading = true;
    monitorState.view = null;
    renderPage();
    expect(screen.getByTestId("auto-sistema-loading")).toBeTruthy();
  });

  it("la conciliación se lee en llano en el primer nivel (Frente C)", () => {
    reconState.selfEval = { portfolioReconciliation: { status: "ok" } };
    reconState.lifecycle = {
      status: "ok",
      driftCount: 0,
      lagCount: 0,
      blockedCount: 0,
    };
    renderPage();
    expect(
      screen.getByTestId("auto-sistema-recon-plain-label").textContent,
    ).toBe("Cuadra");
    // No vive dentro del detalle técnico plegado.
    const detail = screen.getByTestId("auto-sistema-technical");
    expect(
      detail.contains(screen.getByTestId("auto-sistema-recon-plain")),
    ).toBe(false);
  });

  it("sin lectura de conciliación declara el hueco, no «Cuadra»", () => {
    renderPage();
    expect(
      screen.getByTestId("auto-sistema-recon-plain-label").textContent,
    ).toBe("Sin dato todavía");
  });

  it("un desajuste de cartera se traduce a «Revisar»", () => {
    reconState.selfEval = { portfolioReconciliation: { status: "drift" } };
    renderPage();
    expect(
      screen.getByTestId("auto-sistema-recon-plain-label").textContent,
    ).toBe("Revisar");
  });
});
