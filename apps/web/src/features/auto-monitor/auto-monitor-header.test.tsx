/**
 * AUTO Operacional Monitor — cabecera: un dato AUSENTE no se pinta como un valor plausible.
 *
 * O-3: el venue del encabezado viaja `None` cuando el snapshot del motor no lo declara (antes
 * el API rellenaba «paper» en la firma del DTO). La cabecera declara el hueco con la misma
 * etiqueta que usa para el resto de mediciones ausentes.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { AutoMonitorHeaderV1 } from "@bolsa/shared";

import { AutoMonitorHeader } from "@/features/auto-monitor/auto-monitor-header";

function header(
  overrides: Partial<AutoMonitorHeaderV1> = {},
): AutoMonitorHeaderV1 {
  return {
    engineId: "auto-window-test",
    state: "RUNNING",
    venue: "paper",
    granularity: { decision: "1d", execution: "1d" },
    decisionClock: "CLOSED BAR",
    executionDeclared: "SIMULATED",
    executionEnabled: true,
    protectionModel: "ACTIVE",
    heartbeatSeconds: 60,
    graceSeconds: 180,
    lastHeartbeatAt: "2026-10-27T09:00:00Z",
    lastHeartbeatMeasurement: "COMPLETE",
    lastDecisionAt: "2026-10-27T08:59:00Z",
    lastDecisionMeasurement: "COMPLETE",
    nextDecisionAt: "2026-10-27T09:59:00Z",
    currentActivity: "ANALYZING",
    currentActivityMeasurement: "COMPLETE",
    currentActivityAt: "2026-10-27T09:00:00Z",
    currentActivityAtMeasurement: "COMPLETE",
    realPriceEnabled: false,
    heartbeatsPersisted: 10,
    asOf: "2026-10-27T09:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("AutoMonitorHeader · venue medido", () => {
  it("pinta el venue que el motor declaró", () => {
    render(<AutoMonitorHeader header={header({ venue: "paper" })} />);
    expect(screen.getByTestId("auto-monitor-venue").textContent).toBe("paper");
  });

  it("no inventa «paper» cuando el motor no declaró venue", () => {
    render(<AutoMonitorHeader header={header({ venue: null })} />);
    const venue = screen.getByTestId("auto-monitor-venue");
    expect(venue.textContent).toBe("NO MEDIDO");
    expect(venue.textContent).not.toContain("paper");
  });
});
