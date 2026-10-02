/**
 * AUTO Operational Monitor (M1) — tests de UI: la cadena se pinta tal cual y los huecos se
 * rotulan `NO MEDIDO` (nunca un `0`).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildAutoOperationalMonitorView,
  type AutoOperationalMonitorV1,
} from "@bolsa/shared";
import { AutoCycleTimeline } from "@/features/auto-monitor/auto-cycle-timeline";
import { AutoConcurrencyPanel } from "@/features/auto-monitor/auto-concurrency-panel";
import { AutoReservationPanel } from "@/features/auto-monitor/auto-reservation-panel";

const view = buildAutoOperationalMonitorView(dtoFixture());

function dtoFixture(): AutoOperationalMonitorV1 {
  return {
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
            state: "unknown",
            at: null,
            measurement: "UNKNOWN",
            facts: [],
            note: "signal_not_durable",
          },
          {
            id: "RESERVATION",
            state: "reached",
            at: "2026-09-30T22:00:00Z",
            measurement: "COMPLETE",
            facts: [
              { key: "reservedRisk", value: 50, measurement: "COMPLETE" },
            ],
            note: null,
          },
        ],
        result: null,
        notes: ["signal_not_durable"],
      },
    ],
    reservations: [
      {
        reservationId: "res-1",
        instrumentId: "AAPL",
        side: "buy",
        quantity: 10,
        remainingQty: 10,
        ownerSession: null,
        ownerMeasurement: "UNKNOWN",
        created: "2026-09-30T22:00:00Z",
        expires: "2026-09-30T22:01:01Z",
        expiresMeasurement: "COMPLETE",
        state: "LIVE",
        releaseReason: null,
        releaseReasonMeasurement: "UNKNOWN",
        fillProgress: { filled: 0, requested: 10, measurement: "COMPLETE" },
        reconciliations: [],
      },
    ],
    concurrency: {
      activeSessions: null,
      activeSessionsMeasurement: "UNKNOWN",
      heartbeatsPersisted: 42,
      claimAttempts: null,
      claimAttemptsMeasurement: "UNKNOWN",
      successfulClaims: null,
      successfulClaimsMeasurement: "UNKNOWN",
      lostClaims: null,
      lostClaimsMeasurement: "UNKNOWN",
      raceConflicts: null,
      raceConflictsMeasurement: "UNKNOWN",
      reconciliations: null,
      reconciliationsMeasurement: "UNKNOWN",
      graceWindowKeeps: null,
      graceWindowKeepsMeasurement: "UNKNOWN",
      forcedReleases: 0,
      forcedReleasesMeasurement: "COMPLETE",
      lastConflict: null,
      lastConflictMeasurement: "UNKNOWN",
    },
    notes: ["decision_journal_not_durable"],
  };
}

afterEach(() => cleanup());

describe("AutoCycleTimeline", () => {
  it("pinta los pasos en orden y rotula el hueco como no medido", () => {
    render(<AutoCycleTimeline cycles={view.cycles} />);
    const steps = screen.getAllByTestId("auto-monitor-step");
    expect(steps.map((node) => node.getAttribute("data-step-id"))).toEqual([
      "SIGNAL",
      "RESERVATION",
    ]);
    expect(
      screen
        .getAllByTestId("auto-monitor-step")[0]!
        .getAttribute("data-step-state"),
    ).toBe("unknown");
    expect(screen.getByTestId("auto-monitor-step-note").textContent).toContain(
      "signal_not_durable",
    );
  });

  it("declara el hueco cuando no hay ciclos", () => {
    render(<AutoCycleTimeline cycles={[]} />);
    expect(screen.getByTestId("auto-monitor-empty")).toBeTruthy();
  });

  it("no afirma cerrado/abierto cuando la ventana de fills truncó el cierre", () => {
    const truncated = buildAutoOperationalMonitorView({
      ...dtoFixture(),
      cycles: [
        {
          ...dtoFixture().cycles[0]!,
          closed: null,
          closedMeasurement: "PARTIAL",
        },
      ],
    });
    render(<AutoCycleTimeline cycles={truncated.cycles} />);
    const card = screen.getByTestId("auto-monitor-cycle");
    expect(card.getAttribute("data-cycle-closed")).toBe("unknown");
    expect(card.textContent).toContain("NO MEDIDO");
  });
});

describe("AutoConcurrencyPanel", () => {
  it("muestra NO MEDIDO en los conteos sin productor durable", () => {
    render(<AutoConcurrencyPanel concurrency={view.concurrency} />);
    expect(screen.getByTestId("auto-monitor-race-conflicts").textContent).toBe(
      "NO MEDIDO",
    );
    expect(screen.getByTestId("auto-monitor-claim-attempts").textContent).toBe(
      "NO MEDIDO",
    );
    expect(screen.getByTestId("auto-monitor-forced-releases").textContent).toBe(
      "0",
    );
    expect(screen.getByTestId("auto-monitor-last-conflict").textContent).toBe(
      "NO MEDIDO",
    );
  });

  it("resume el último conflicto cuando el spine es durable", () => {
    render(
      <AutoConcurrencyPanel
        concurrency={{
          ...view.concurrency,
          lastConflict: {
            reservationId: "RES-dec-aaa",
            at: "2026-10-01T10:00:00Z",
          },
          lastConflictMeasurement: "COMPLETE",
        }}
      />,
    );
    expect(
      screen.getByTestId("auto-monitor-last-conflict").textContent,
    ).toContain("RES-dec-aaa");
  });

  it("distingue PARCIAL de COMPLETE en los conteos de concurrencia", () => {
    render(
      <AutoConcurrencyPanel
        concurrency={{
          ...view.concurrency,
          raceConflicts: 3,
          raceConflictsMeasurement: "PARTIAL",
        }}
      />,
    );
    const node = screen.getByTestId("auto-monitor-race-conflicts");
    expect(node.textContent).toContain("3");
    expect(node.textContent).toContain("PARCIAL");
    expect(node.getAttribute("data-measurement")).toBe("PARTIAL");
  });
});

describe("AutoReservationPanel", () => {
  it("declara la ownership no medida y el fill progreso", () => {
    render(<AutoReservationPanel reservations={view.reservations} />);
    expect(
      screen.getByTestId("auto-monitor-reservation-owner").textContent,
    ).toContain("NO MEDIDO");
    expect(screen.getByTestId("auto-monitor-reservation")).toBeTruthy();
  });

  it("muestra la sesión dueña cuando el claim ganado es durable", () => {
    render(
      <AutoReservationPanel
        reservations={[
          {
            ...view.reservations[0]!,
            ownerSession: "auto-abc123",
            ownerMeasurement: "COMPLETE",
          },
        ]}
      />,
    );
    expect(
      screen.getByTestId("auto-monitor-reservation-owner").textContent,
    ).toContain("auto-abc123");
  });
});

describe("AutoMonitorPage", () => {
  it("compone header, notas y timeline", async () => {
    vi.resetModules();
    vi.doMock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
      useAutoOperationalMonitor: () => ({
        view,
        isLoading: false,
        isError: false,
        isFetching: false,
        refetch: vi.fn(),
        accountId: "acc-1",
      }),
    }));
    const { AutoMonitorPage } =
      await import("@/features/auto-monitor/auto-monitor-page");
    render(<AutoMonitorPage />);
    expect(screen.getByTestId("auto-monitor-page")).toBeTruthy();
    expect(screen.getByTestId("auto-monitor-execution").textContent).toContain(
      "next_bar_open",
    );
    expect(screen.getByTestId("auto-monitor-real-price").textContent).toBe(
      "NO",
    );
    expect(
      screen.getByTestId("auto-monitor-last-heartbeat").textContent,
    ).toContain("2026-10-01T09:00:00Z");
    expect(
      screen.getByTestId("auto-monitor-last-decision").textContent,
    ).toContain("2026-09-30T23:00:00Z");
    expect(screen.getByTestId("auto-monitor-cycles")).toBeTruthy();
    vi.doUnmock("@/features/auto-monitor/use-auto-operational-monitor");
  });
});
