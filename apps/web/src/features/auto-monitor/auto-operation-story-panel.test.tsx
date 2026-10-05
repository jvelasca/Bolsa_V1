/**
 * AUTO UI REFACTOR 1.0 — piloto de la "operación única".
 *
 * Monta el panel real con la API mockeada y comprueba que las 13 etapas se pintan en orden,
 * que un paso sin traza se rotula NO MEDIDO y que la explicación OOS se pliega cuando existe.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  api: {
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
          instrumentId: "AAA",
          strategyVersion: "sv-1",
          direction: "long",
          closed: true,
          closedMeasurement: "COMPLETE",
          steps: [
            {
              id: "SIGNAL",
              state: "reached",
              at: "2026-09-29T20:00:00Z",
              measurement: "COMPLETE",
              facts: [{ key: "rank", value: 1, measurement: "COMPLETE" }],
              note: null,
            },
            {
              id: "TOP_N",
              state: "reached",
              at: "2026-09-29T20:00:01Z",
              measurement: "COMPLETE",
              facts: [],
              note: null,
            },
            {
              id: "FILL",
              state: "reached",
              at: "2026-09-30T09:00:00Z",
              measurement: "COMPLETE",
              facts: [],
              note: null,
            },
          ],
          result: { pnl: 250, closedAt: "2026-10-01T15:00:00Z" },
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
      notes: [],
    })),
    getAutoDiaDFeedbackList: vi.fn(async () => ({
      readOnly: true,
      windows: ["2026-09-29_2026-09-30"],
      latest: "2026-09-29_2026-09-30",
      artifact: {
        available: true,
        window: {
          from: "2026-09-29",
          to: "2026-09-30",
          days: ["2026-09-29", "2026-09-30"],
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
            errorTotal: 0,
          },
        ],
      },
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

import { AutoOperationStoryPanel } from "@/features/auto-monitor/auto-operation-story-panel";

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AutoOperationStoryPanel />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AutoOperationStoryPanel", () => {
  it("pinta las 13 etapas en orden, con NO MEDIDO donde no hay traza", async () => {
    renderPanel();

    // El selector de ciclos sólo aparece con el monitor cargado: esperar a él evita asertar
    // sobre la historia vacía del primer render.
    await waitFor(() =>
      expect(screen.getByTestId("auto-operation-story-cycles")).toBeTruthy(),
    );

    const stages = screen.getAllByTestId("auto-operation-story-stage");
    expect(stages.map((stage) => stage.getAttribute("data-stage"))).toEqual([
      "OPPORTUNITY",
      "SIGNAL",
      "DECISION",
      "RISK",
      "RESERVATION",
      "ORDER",
      "FILL",
      "POSITION",
      "PROTECTION",
      "EXIT",
      "SETTLEMENT",
      "RESULT",
      "EXPLANATION",
    ]);

    const byStage = new Map(
      stages.map((stage) => [stage.getAttribute("data-stage"), stage]),
    );
    expect(byStage.get("SIGNAL")?.getAttribute("data-state")).toBe("REACHED");
    // PROTECTION no está en el ciclo ⇒ NO MEDIDO (jamás `reached` ni `0`).
    expect(byStage.get("PROTECTION")?.getAttribute("data-state")).toBe(
      "NOT_MEASURED",
    );
    expect(byStage.get("OPPORTUNITY")?.getAttribute("data-state")).toBe(
      "NOT_MEASURED",
    );
  });

  it("pliega la explicación OOS del instrumento", async () => {
    renderPanel();

    await waitFor(() =>
      expect(screen.getByTestId("auto-operation-story-cycles")).toBeTruthy(),
    );
    await waitFor(() =>
      expect(
        screen
          .getAllByTestId("auto-operation-story-stage")
          .find((stage) => stage.getAttribute("data-stage") === "EXPLANATION")
          ?.getAttribute("data-state"),
      ).toBe("REACHED"),
    );

    const explanation = screen
      .getAllByTestId("auto-operation-story-stage")
      .find((stage) => stage.getAttribute("data-stage") === "EXPLANATION");
    expect(explanation?.getAttribute("data-state")).toBe("REACHED");
    expect(explanation?.textContent).toContain("OOS_SUPPORTED");
  });
});
