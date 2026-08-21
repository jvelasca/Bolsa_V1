/**
 * Tests — labels y rutas de la mesa diaria vs laboratorio (R-12 C2).
 */

import { describe, expect, it } from "vitest";
import {
  ASESOR_LABEL,
  ASESOR_TESIS_HINT,
  CONFIRMAR_LABEL,
  DAILY_NAV_ORDER,
  HERRAMIENTAS_NAV_ORDER,
  LABORATORIO_LABEL,
  LAB_TESIS_NAV_ORDER,
  SEÑALES_LABEL,
  SEÑALES_PATH,
  TRADING_NAV_LABEL,
  UNIVERSO_EN_VIGILANCIA,
  formatFueraUniversoOperativaCopy,
} from "@/features/confirm/daily-nav";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";

describe("daily-nav", () => {
  it("names the daily signal hub Señales on /screeners", () => {
    expect(SEÑALES_LABEL).toBe("Señales");
    expect(SEÑALES_PATH).toBe("/screeners");
    expect(SEÑALES_PATH).not.toBe("/research");
  });

  it("relabels the backtesting menu Laboratorio", () => {
    expect(LABORATORIO_LABEL).toBe("Laboratorio");
    expect(LABORATORIO_LABEL).not.toBe("Backtesting");
  });

  it("keeps Confirm as a first-level daily door", () => {
    expect(CONFIRMAR_LABEL).toBe("Confirmar");
    expect(CONFIRM_PATH).toBe("/confirm");
  });

  it("orders daily, tools, and lab/tesis groups", () => {
    expect(DAILY_NAV_ORDER).toEqual([
      TRADING_NAV_LABEL,
      SEÑALES_LABEL,
      CONFIRMAR_LABEL,
    ]);
    expect(HERRAMIENTAS_NAV_ORDER).toEqual([
      "Overview",
      "Cuentas",
      "Alertas",
      "Instrumentos",
    ]);
    expect(LAB_TESIS_NAV_ORDER).toEqual([LABORATORIO_LABEL, ASESOR_LABEL]);
    expect(ASESOR_LABEL).toBe("Asesor");
    expect(ASESOR_TESIS_HINT.toLowerCase()).toMatch(/tesis/);
  });

  it("uses Universo en vigilancia copy for the Estudio gate", () => {
    expect(UNIVERSO_EN_VIGILANCIA).toBe("Universo en vigilancia");
    expect(formatFueraUniversoOperativaCopy("SEMI")).toBe(
      "Fuera del Universo en vigilancia — SEMI exige estar en Estudio",
    );
    expect(formatFueraUniversoOperativaCopy("SEMI")).not.toMatch(/membresía/);
  });
});
