/**
 * UI Contract 5.0 (`UI5-10`) — derivación del modo de operación por evidencia.
 *
 * El modo nunca se deduce: se afirma con evidencia (`HUMAN_MANUAL`) o se declara
 * «Sin dato todavía». Dentro del espacio AUTO, el modo es AUTO por definición de la superficie.
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import {
  AUTO_OPERATION_MODE,
  OPERATION_MODE_LABEL,
  OPERATION_MODE_NO_DATA_LABEL,
  SEMI_OPERATION_MODE,
  operationModeForPosition,
  operationModeLabel,
} from "@/features/operations/operation-mode";

function position(tradePlanId?: string): PositionDto {
  return {
    symbol: "AAPL",
    quantity: 1,
    operational: tradePlanId ? { tradePlanId } : undefined,
  } as unknown as PositionDto;
}

describe("operationModeLabel", () => {
  it("declara modo y canal de dinero juntos", () => {
    expect(operationModeLabel(AUTO_OPERATION_MODE)).toBe("AUTO · SIMULADO");
    expect(operationModeLabel(SEMI_OPERATION_MODE)).toBe("SEMI · SIMULADO");
  });

  it("sin modo, declara «Sin dato todavía» (UNKNOWN ≠ 0)", () => {
    expect(operationModeLabel({ mode: null, channel: "SIMULADO" })).toBe(
      OPERATION_MODE_NO_DATA_LABEL,
    );
  });
});

describe("OPERATION_MODE_LABEL", () => {
  it("fija el casing canónico de primer nivel", () => {
    expect(OPERATION_MODE_LABEL).toEqual({
      AUTO: "AUTO",
      SEMI: "SEMI",
      MANUAL: "MANUAL",
    });
  });
});

describe("operationModeForPosition", () => {
  it("una posición nacida del canal manual es MANUAL", () => {
    expect(
      operationModeForPosition(position("manual-2026-10-08-abc"), "market")
        .mode,
    ).toBe("MANUAL");
  });

  it("dentro del espacio AUTO, el modo es AUTO", () => {
    expect(operationModeForPosition(position(), "auto")).toEqual(
      AUTO_OPERATION_MODE,
    );
  });

  it("fuera de AUTO y sin evidencia, el modo no se inventa", () => {
    const badge = operationModeForPosition(position(), "market");
    expect(badge.mode).toBeNull();
    expect(operationModeLabel(badge)).toBe(OPERATION_MODE_NO_DATA_LABEL);
  });
});
