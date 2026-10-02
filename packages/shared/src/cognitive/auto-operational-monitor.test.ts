/**
 * AUTO Operational Monitor — view model puro: honestidad de la medición y labelling.
 */

import { describe, expect, it } from "vitest";
import {
  buildAutoOperationalMonitorView,
  executionModeLabel,
  formatLastConflict,
  formatMonitorFactValue,
  formatMonitorInstant,
  realPriceEnabledLabel,
  stepStateLabel,
  type AutoOperationalMonitorV1,
} from "./auto-operational-monitor.js";

function minimalDto(): AutoOperationalMonitorV1 {
  return {
    key: "auto_operational_monitor_v1",
    readOnly: true,
    asOf: "2026-10-01T00:00:00Z",
    header: {
      state: "RUNNING",
      venue: "paper",
      granularity: { execution: "signal_bar" },
      decisionClock: "CLOSED BAR",
      executionDeclared: "next_bar_open",
      executionEnabled: false,
      lastHeartbeatAt: "2026-10-01T09:00:00Z",
      lastHeartbeatMeasurement: "COMPLETE",
      lastDecisionMeasurement: "UNKNOWN",
      realPriceEnabled: false,
      heartbeatsPersisted: 1,
      asOf: "2026-10-01T00:00:00Z",
    },
    cycles: [
      {
        cycleId: "cyc-1",
        direction: "short",
        closed: true,
        steps: [
          {
            id: "RISK",
            state: "unknown",
            measurement: "UNKNOWN",
            facts: [
              { key: "reservedRisk", value: null, measurement: "UNKNOWN" },
            ],
          },
        ],
        result: { pnl: 0 },
      },
    ],
    reservations: [],
    concurrency: {
      activeSessionsMeasurement: "UNKNOWN",
      heartbeatsPersisted: 1,
      claimAttemptsMeasurement: "UNKNOWN",
      successfulClaimsMeasurement: "UNKNOWN",
      lostClaimsMeasurement: "UNKNOWN",
      raceConflictsMeasurement: "UNKNOWN",
      reconciliationsMeasurement: "UNKNOWN",
      graceWindowKeepsMeasurement: "UNKNOWN",
      forcedReleases: 0,
      forcedReleasesMeasurement: "COMPLETE",
      lastConflictMeasurement: "UNKNOWN",
    },
    notes: [],
  };
}

describe("formatMonitorFactValue", () => {
  it("rotula NO MEDIDO cuando el valor es null", () => {
    expect(formatMonitorFactValue(null, "UNKNOWN")).toBe("NO MEDIDO");
  });

  it("no convierte 0 en ausencia", () => {
    expect(formatMonitorFactValue(0, "COMPLETE")).toBe("0");
  });

  it("rotula PARCIAL", () => {
    expect(formatMonitorFactValue(null, "PARTIAL")).toBe("PARCIAL");
  });
});

describe("buildAutoOperationalMonitorView", () => {
  it("etiqueta estado, dirección y huecos sin reordenar pasos", () => {
    const view = buildAutoOperationalMonitorView(minimalDto());
    const cycle = view.cycles[0]!;
    expect(cycle.directionLabel).toBe("Corto");
    expect(cycle.statusLabel).toBe("Cerrado");
    expect(cycle.steps[0]!.label).toBe("Riesgo");
    expect(cycle.steps[0]!.stateLabel).toBe(stepStateLabel("unknown"));
    expect(cycle.unmeasuredStepIds).toEqual(["RISK"]);
  });
});

describe("executionModeLabel", () => {
  it("declara la diferencia entre declarado y habilitado", () => {
    const label = executionModeLabel(minimalDto().header);
    expect(label).toContain("next_bar_open");
    expect(label).toContain("NO habilitado");
  });
});

describe("formatLastConflict", () => {
  it("rotula NO MEDIDO sin productor durable", () => {
    expect(formatLastConflict(null, "UNKNOWN")).toBe("NO MEDIDO");
    expect(formatLastConflict(undefined, "UNKNOWN")).toBe("NO MEDIDO");
  });

  it("no confunde un cero medido con ausencia", () => {
    expect(formatLastConflict(null, "COMPLETE")).toBe("MEDIDO");
  });

  it("resume el conflicto medido por reserva y sello", () => {
    const label = formatLastConflict(
      {
        reservationId: "RES-dec-aaa",
        at: "2026-10-01T10:00:00Z",
        loserSession: "auto-1",
      },
      "COMPLETE",
    );
    expect(label).toContain("RES-dec-aaa");
    expect(label).toContain("2026-10-01T10:00:00Z");
  });
});

describe("realPriceEnabledLabel", () => {
  it("declara la configuración, no la fuente usada", () => {
    expect(realPriceEnabledLabel(true)).toBe("SÍ (habilitado)");
    expect(realPriceEnabledLabel(false)).toBe("NO");
  });
});

describe("formatMonitorInstant", () => {
  it("rotula NO MEDIDO cuando no hay instante durable", () => {
    expect(formatMonitorInstant(null, "UNKNOWN")).toBe("NO MEDIDO");
    expect(formatMonitorInstant(null, "COMPLETE")).toBe("MEDIDO");
    expect(formatMonitorInstant("2026-10-01T22:00:00Z", "COMPLETE")).toBe(
      "2026-10-01T22:00:00Z",
    );
  });
});
