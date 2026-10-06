/**
 * AUTO · SISTEMA — primero «qué está haciendo AUTO», detalle técnico plegado (spec 3.0 §5).
 *
 * Verifica la inversión de jerarquía: el estado en frases arriba (reutilizando el helper de la
 * HOME) y el monitor crudo dentro de un bloque «Detalle técnico» cerrado por defecto.
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

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({ data: undefined, isLoading: false, isError: false }),
}));
vi.mock("@/features/operational-console/use-lifecycle-reconciliation", () => ({
  useLifecycleReconciliation: () => ({
    data: undefined,
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
  it("expone un h1 y el estado en lenguaje de usuario arriba", () => {
    renderPage();
    expect(screen.queryAllByRole("heading", { level: 1 })).toHaveLength(1);
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
});
