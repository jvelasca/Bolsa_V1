/**
 * Regresión del Monitor AUTO contra la forma REAL del endpoint.
 *
 * `GET /api/auto/operational-monitor` responde el `AutoOperationalMonitorDto` DIRECTO
 * (sin envoltorio `{ data }`). Un `query.data.data` en el hook dejaba `view = null`:
 * la página quedaba en blanco, sin "Cargando" y sin error. Este test muerde si vuelve.
 *
 * El resto de `auto-monitor.test.tsx` mockea el hook (por eso no lo detectó); aquí se
 * monta la página real con el hook real y sólo se mockean la API y la cuenta activa.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/lib/api", () => ({
  // El mock devuelve el DTO directo (como el endpoint), NO `{ data: dto }`.
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
    getAutoOperationalMonitor: vi.fn(async () => ({
      key: "auto_operational_monitor_v1",
      readOnly: true,
      accountId: "acc-1",
      asOf: "2026-10-01T00:00:00Z",
      header: {
        engineId: "auto-sim",
        state: "RUNNING",
        venue: "paper",
        granularity: { decision: "1d", execution: "signal_bar" },
        decisionClock: "CLOSED BAR",
        executionDeclared: "next_bar_open",
        executionEnabled: false,
        protectionModel: "bar_ohlc",
        heartbeatSeconds: 60,
        graceSeconds: 61,
        lastHeartbeatAt: "2026-10-01T09:00:00Z",
        lastHeartbeatMeasurement: "COMPLETE",
        lastDecisionAt: "2026-09-30T23:00:00Z",
        lastDecisionMeasurement: "COMPLETE",
        nextDecisionAt: "2026-10-01T00:01:00Z",
        realPriceEnabled: false,
        heartbeatsPersisted: 42,
        asOf: "2026-10-01T00:00:00Z",
      },
      cycles: [
        {
          cycleId: "cyc-1",
          instrumentId: "AAPL",
          strategyVersion: "sv-1",
          direction: "long",
          closed: false,
          steps: [
            {
              id: "SIGNAL",
              state: "reached",
              at: "2026-09-30T22:00:00Z",
              measurement: "COMPLETE",
              facts: [],
              note: null,
            },
          ],
          result: null,
          notes: [],
        },
      ],
      reservations: [],
      concurrency: {
        activeSessions: 0,
        activeSessionsMeasurement: "COMPLETE",
        heartbeatsPersisted: 42,
        claimAttempts: 0,
        claimAttemptsMeasurement: "COMPLETE",
        successfulClaims: 0,
        successfulClaimsMeasurement: "COMPLETE",
        lostClaims: 0,
        lostClaimsMeasurement: "COMPLETE",
        raceConflicts: 0,
        raceConflictsMeasurement: "COMPLETE",
        reconciliations: 0,
        reconciliationsMeasurement: "COMPLETE",
        graceWindowKeeps: 0,
        graceWindowKeepsMeasurement: "COMPLETE",
        forcedReleases: 0,
        forcedReleasesMeasurement: "COMPLETE",
        lastConflict: null,
        lastConflictMeasurement: "COMPLETE",
      },
      notes: ["decision_journal_not_durable"],
    })),
    getAutoDiaDFeedbackList: vi.fn(async () => ({
      readOnly: true,
      windows: ["2026-09-29_2026-09-30"],
      latest: "2026-09-29_2026-09-30",
      artifact: { available: false, notes: ["artifact_not_found"] },
      notes: [],
    })),
    getAutoDiaDFeedback: vi.fn(async () => ({
      available: false,
      readOnly: true,
      notes: ["artifact_not_found"],
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
import {
  AutoMonitorPage,
  readAutoMonitorMode,
} from "@/features/auto-monitor/auto-monitor-page";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";

function renderPage(entry = "/auto-monitor?mode=current") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <AutoMonitorPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AutoMonitorPage — consume el DTO directo del endpoint", () => {
  it("monta header, notas y timeline con la respuesta real (sin envoltorio `data`)", async () => {
    renderPage();

    // Si el hook volviera a leer `query.data.data`, esto nunca aparecería.
    await waitFor(() =>
      expect(screen.getByTestId("auto-monitor-header")).toBeTruthy(),
    );

    expect(screen.queryByTestId("auto-monitor-loading")).toBeNull();
    expect(screen.queryByTestId("auto-monitor-error")).toBeNull();
    expect(screen.getByTestId("auto-monitor-execution").textContent).toContain(
      "next_bar_open",
    );
    expect(screen.getByTestId("auto-monitor-real-price").textContent).toBe(
      "NO",
    );
    expect(screen.getByTestId("auto-monitor-cycles")).toBeTruthy();
    expect(screen.getByTestId("auto-monitor-notes").textContent).toContain(
      "decision_journal_not_durable",
    );

    expect(api.getAutoOperationalMonitor).toHaveBeenCalledTimes(1);
  });
});

describe("AutoMonitorPage — modo y selección en la URL", () => {
  it("por defecto abre Operación (no la ventana cruda)", () => {
    renderPage("/auto-monitor");
    expect(
      screen
        .getByTestId("auto-monitor-mode-operation")
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(screen.getByTestId("auto-operation-story-panel")).toBeTruthy();
  });

  it("lee el ciclo seleccionado de la URL", async () => {
    renderPage("/auto-monitor?mode=operation&cycle=cyc-1");
    await waitFor(() =>
      expect(screen.getByTestId("auto-operation-story-cycle")).toBeTruthy(),
    );
    expect(
      screen
        .getByTestId("auto-operation-story-cycle")
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("lee la ventana DÍA-D de la URL (mode=dia-d&view=feedback&window=…)", async () => {
    renderPage(
      "/auto-monitor?mode=dia-d&view=feedback&window=2026-09-29_2026-09-30",
    );
    await waitFor(() =>
      expect(api.getAutoDiaDFeedback).toHaveBeenCalledWith(
        "2026-09-29_2026-09-30",
      ),
    );
  });

  it("readAutoMonitorMode cae a `operation` con valores inválidos", () => {
    expect(readAutoMonitorMode(new URLSearchParams(""))).toBe("operation");
    expect(readAutoMonitorMode(new URLSearchParams("mode=dia-d"))).toBe(
      "dia-d",
    );
    expect(readAutoMonitorMode(new URLSearchParams("mode=basura"))).toBe(
      "operation",
    );
  });
});

function DisabledProbe() {
  useAutoOperationalMonitor({ enabled: false });
  return null;
}

describe("useAutoOperationalMonitor — enabled", () => {
  it("no dispara la query con enabled=false (la pestaña DÍA-D deja de sondear)", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <DisabledProbe />
      </QueryClientProvider>,
    );
    expect(api.getAutoOperationalMonitor).not.toHaveBeenCalled();
  });
});
