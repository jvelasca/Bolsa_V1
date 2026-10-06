/**
 * AUTO UI REFACTOR 3.0 (S1) — resumen de la HOME: casos duros.
 *
 * Fija que un hueco nunca se convierte en un dato, que el contador cuenta ciclos en curso
 * y no los llama abiertos, y que la traducción de estado/riesgo es honesta.
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_HOME_NO_DATA_LABEL,
  buildAutoHomeSummary,
  decisionClockCopy,
  engineStateLabel,
  formatActivityTime,
  isOperationInCourse,
  isOperationOpen,
} from "@/features/auto/auto-home-summary";

describe("formatActivityTime", () => {
  it("extrae HH:mm del sello ISO de forma determinista", () => {
    expect(formatActivityTime("2026-10-03T09:42:00Z")).toBe("09:42");
    expect(formatActivityTime("2026-10-06T23:00:00+02:00")).toBe("23:00");
  });

  it("un valor ausente o ilegible se declara Sin dato todavía", () => {
    expect(formatActivityTime(null)).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(formatActivityTime("")).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(formatActivityTime("ayer")).toBe("ayer");
  });
});

const PRICE_STEP = { id: "FILL", state: "reached" } as const;
const ORDER_STEP = { id: "ORDER", state: "reached" } as const;
const FILL_PENDING = { id: "FILL", state: "pending" } as const;
const RESERVATION_STEP = { id: "RESERVATION", state: "reached" } as const;

describe("isOperationInCourse", () => {
  it("cuenta una orden sin fill y un precio aplicado", () => {
    expect(
      isOperationInCourse({
        cycleId: "order",
        closed: false,
        closedMeasurement: "COMPLETE",
        steps: [ORDER_STEP, FILL_PENDING],
      }),
    ).toBe(true);
    expect(
      isOperationInCourse({
        cycleId: "fill",
        closed: false,
        closedMeasurement: "COMPLETE",
        steps: [ORDER_STEP, PRICE_STEP],
      }),
    ).toBe(true);
  });

  it("una reserva, un cierre no medido o un ciclo cerrado no cuentan", () => {
    expect(
      isOperationInCourse({
        cycleId: "reserve",
        closed: false,
        closedMeasurement: "COMPLETE",
        steps: [RESERVATION_STEP],
      }),
    ).toBe(false);
    expect(isOperationInCourse({ cycleId: "bare", closed: false })).toBe(false);
    expect(isOperationInCourse({ cycleId: "c", closed: null })).toBe(false);
    expect(
      isOperationInCourse({
        cycleId: "partial-close",
        closed: false,
        closedMeasurement: "PARTIAL",
        steps: [PRICE_STEP],
      }),
    ).toBe(false);
    expect(
      isOperationInCourse({
        cycleId: "closed",
        closed: true,
        closedMeasurement: "COMPLETE",
        steps: [PRICE_STEP],
      }),
    ).toBe(false);
  });
});

describe("isOperationOpen", () => {
  it("sólo cuenta un fill alcanzado que no está cerrado", () => {
    expect(
      isOperationOpen({
        cycleId: "c",
        closed: false,
        closedMeasurement: "COMPLETE",
        steps: [PRICE_STEP],
      }),
    ).toBe(true);
  });

  it("una reserva, una orden o un cierre no medido no cuentan", () => {
    expect(isOperationOpen({ cycleId: "c", closed: false })).toBe(false);
    expect(
      isOperationOpen({
        cycleId: "c",
        closed: false,
        closedMeasurement: "COMPLETE",
        steps: [ORDER_STEP],
      }),
    ).toBe(false);
    expect(isOperationOpen({ cycleId: "c", closed: null })).toBe(false);
    expect(
      isOperationOpen({
        cycleId: "c",
        closed: false,
        closedMeasurement: "PARTIAL",
        steps: [PRICE_STEP],
      }),
    ).toBe(false);
    expect(
      isOperationOpen({
        cycleId: "c",
        closed: true,
        steps: [PRICE_STEP],
      }),
    ).toBe(false);
  });
});

describe("buildAutoHomeSummary", () => {
  it("traduce el estado del motor y cuenta las operaciones en curso", () => {
    const summary = buildAutoHomeSummary({
      header: {
        state: "RUNNING",
        lastDecisionAt: "2026-10-06T09:42:00Z",
        lastHeartbeatAt: "2026-10-06T11:11:00Z",
        nextDecisionAt: "2026-10-06T10:00:00Z",
      },
      cycles: [
        {
          cycleId: "a",
          closed: false,
          closedMeasurement: "COMPLETE",
          steps: [PRICE_STEP],
        },
        { cycleId: "b", closed: true, steps: [PRICE_STEP] },
        { cycleId: "c", closed: null },
        {
          cycleId: "d",
          closed: false,
          closedMeasurement: "COMPLETE",
          steps: [ORDER_STEP],
        },
      ],
      riskOperationalState: "OK",
    });
    expect(summary.loaded).toBe(true);
    expect(summary.autoLabel).toBe("Funcionando");
    expect(summary.statusLabel).toBe("Funcionando");
    expect(summary.lastActivityLabel).toBe("09:42");
    expect(summary.lastActivityLabel).not.toContain("11:11");
    expect(summary.nextStepLabel).toBe("Próxima decisión: 10:00");
    expect(summary.nextStepLabel).not.toContain("análisis");
    expect(
      decisionClockCopy(summary.lastActivityLabel, summary.nextStepLabel),
    ).toBe("Última decisión: 09:42 · Próxima decisión: 10:00");
    expect(summary.inCourseOperationsCount).toBe(2);
    expect(summary.inCourseOperationsLabel).toBe("2 en curso");
    expect(summary.inCourseOperationsLabel).not.toContain("abierta");
    expect(summary.hasOperationsInCourse).toBe(true);
    expect(summary.riskTone).toBe("ok");
    expect(summary.riskLabel).toBe("Normal");
  });

  it("una orden sin fill cuenta como en curso y no se llama abierta", () => {
    const orderOnly = {
      cycleId: "order",
      closed: false,
      closedMeasurement: "COMPLETE",
      steps: [ORDER_STEP, FILL_PENDING],
    };
    expect(isOperationOpen(orderOnly)).toBe(false);
    const summary = buildAutoHomeSummary({
      header: { state: "RUNNING" },
      cycles: [orderOnly],
    });
    expect(summary.inCourseOperationsLabel).toBe("1 en curso");
    expect(summary.inCourseOperationsLabel).not.toContain("abierta");
    expect(summary.nextStepLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(summary.nextStepLabel).not.toContain("Esperando nueva señal");
    expect(summary.nextStepLabel).not.toContain("Próximo análisis");
  });

  it("un estado desconocido y un riesgo no medido se declaran, no se asumen", () => {
    const summary = buildAutoHomeSummary({
      header: { state: "UNKNOWN" },
      cycles: [],
      riskOperationalState: null,
    });
    expect(summary.autoLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(summary.statusLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(summary.riskTone).toBe("unknown");
    expect(summary.riskLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(summary.inCourseOperationsLabel).toBe("Sin operaciones en curso");
    expect(summary.nextStepLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(summary.nextStepLabel).not.toContain("Esperando nueva señal");
    expect(summary.nextStepLabel).not.toContain("Próximo análisis");
    expect(summary.lastActivityLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
  });

  it("un latido no ocupa el hueco de la decisión", () => {
    const summary = buildAutoHomeSummary({
      header: {
        state: "RUNNING",
        lastHeartbeatAt: "2026-10-06T11:11:00Z",
      },
    });
    expect(summary.lastActivityLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(summary.lastActivityLabel).not.toContain("11:11");
    expect(summary.nextStepLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(summary.nextStepLabel).not.toContain("Esperando nueva señal");
    expect(summary.nextStepLabel).not.toContain("análisis");
    const phrase = decisionClockCopy(
      summary.lastActivityLabel,
      summary.nextStepLabel,
    );
    expect(phrase).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(phrase).not.toContain("11:11");
    expect(phrase).not.toContain("Última actividad");
  });

  it("traduce solo el conjunto cerrado del motor", () => {
    expect(engineStateLabel("RUNNING")).toBe("Funcionando");
    expect(engineStateLabel("PAUSED")).toBe("Detenido");
    expect(engineStateLabel("DEGRADED")).toBe("Funcionamiento limitado");
    expect(engineStateLabel("BLOCKED")).toBe("Bloqueado");
    expect(engineStateLabel("REQUIRES_ATTENTION")).toBe("Atención requerida");
    expect(engineStateLabel("WAITING")).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(engineStateLabel("STOPPED")).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(engineStateLabel("UNKNOWN")).toBe(AUTO_HOME_NO_DATA_LABEL);
    expect(engineStateLabel(null)).toBe(AUTO_HOME_NO_DATA_LABEL);

    for (const state of [
      "PAUSED",
      "DEGRADED",
      "BLOCKED",
      "REQUIRES_ATTENTION",
      "WAITING",
    ]) {
      const summary = buildAutoHomeSummary({ header: { state } });
      expect(summary.autoLabel).toBe(engineStateLabel(state));
      expect(summary.statusLabel).toBe(summary.autoLabel);
      expect(summary.statusLabel).not.toBe("Funcionando correctamente");
    }
  });

  it("mapea los estados de integridad operativa", () => {
    expect(
      buildAutoHomeSummary({ riskOperationalState: "DEGRADED" }).riskTone,
    ).toBe("attention");
    expect(
      buildAutoHomeSummary({ riskOperationalState: "BLOCKED" }).riskTone,
    ).toBe("blocked");
  });

  it("durante la carga y en error no se finge ningún dato", () => {
    const loading = buildAutoHomeSummary({
      header: { state: "RUNNING" },
      isLoading: true,
    });
    expect(loading.loaded).toBe(false);
    expect(loading.isLoading).toBe(true);
    expect(loading.autoLabel).toBe(AUTO_HOME_NO_DATA_LABEL);

    const error = buildAutoHomeSummary({
      header: { state: "RUNNING" },
      isError: true,
    });
    expect(error.loaded).toBe(false);
    expect(error.isError).toBe(true);
    expect(error.autoLabel).toBe(AUTO_HOME_NO_DATA_LABEL);
  });
});
