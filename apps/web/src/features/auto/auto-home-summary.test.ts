/**
 * AUTO UI REFACTOR 3.0 (S1) — resumen de la HOME: casos duros.
 *
 * Fija que un hueco nunca se convierte en un dato, que el contador sólo incluye ciclos con
 * precio aplicado, y que la traducción de estado/riesgo es honesta.
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_HOME_NO_DATA_LABEL,
  buildAutoHomeSummary,
  formatActivityTime,
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
  it("traduce el estado del motor y cuenta las operaciones abiertas", () => {
    const summary = buildAutoHomeSummary({
      header: {
        state: "RUNNING",
        lastDecisionAt: "2026-10-06T09:42:00Z",
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
    expect(summary.autoLabel).toBe("Activo");
    expect(summary.statusLabel).toBe("Funcionando correctamente");
    expect(summary.lastActivityLabel).toBe("09:42");
    expect(summary.nextStepLabel).toBe("Próximo análisis: 10:00");
    expect(summary.openOperationsCount).toBe(1);
    expect(summary.openOperationsLabel).toBe("1 abierta");
    expect(summary.hasOpenOperations).toBe(true);
    expect(summary.riskTone).toBe("ok");
    expect(summary.riskLabel).toBe("Normal");
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
    expect(summary.openOperationsLabel).toBe("Sin operaciones abiertas");
    // Cargado (el header existe) pero sin próxima decisión ⇒ esperando señal.
    expect(summary.nextStepLabel).toBe("Esperando nueva señal");
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
