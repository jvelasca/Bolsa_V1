/**
 * Tests — labels y rutas de la mesa diaria vs laboratorio (R-12 C2 + C4).
 */

import { describe, expect, it } from "vitest";
import {
  ASESOR_LABEL,
  ASESOR_PATH,
  ASESOR_TESIS_HINT,
  CONFIRMAR_LABEL,
  DAILY_NAV_ORDER,
  HERRAMIENTAS_NAV_ORDER,
  LABORATORIO_LABEL,
  LAB_TESIS_NAV_ORDER,
  LEDGER_ASESOR_LINK_LABEL,
  LIBRO_HISTORIAL_HINT,
  LIBRO_HISTORIAL_LABEL,
  LIBRO_HISTORIAL_PATH,
  LIBRO_LABEL,
  LIBRO_NAV,
  OPERATIONAL_CONSOLE_HINT,
  OPERATIONAL_CONSOLE_LABEL,
  OPERATIONAL_CONSOLE_PATH,
  LIBRO_OPERACIONES_HINT,
  LIBRO_OPERACIONES_LABEL,
  LIBRO_OPERACIONES_PATH,
  LIST_HUB_EXPAND_ACCESOS_TITLE,
  SEÑALES_LABEL,
  SEÑALES_PATH,
  TRADING_NAV_LABEL,
  UNIVERSO_EN_VIGILANCIA,
  VER_EN_ASESOR_LABEL,
  asesorHistoryHref,
  formatFueraUniversoOperativaCopy,
} from "@/features/confirm/daily-nav";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";

describe("daily-nav", () => {
  it("names the daily signal hub Señales on /screeners", () => {
    expect(SEÑALES_LABEL).toBe("Señales");
    expect(SEÑALES_PATH).toBe("/screeners");
    expect(SEÑALES_PATH).not.toBe("/research");
    expect(ASESOR_PATH).toBe("/research");
    expect(ASESOR_PATH).not.toBe(SEÑALES_PATH);
  });

  it("builds Asesor history deep-links for ledger CTAs", () => {
    expect(asesorHistoryHref()).toBe("/research?tab=history");
    expect(asesorHistoryHref("trial-abc")).toBe(
      "/research?tab=history&trialId=trial-abc",
    );
    expect(asesorHistoryHref(" id & x ")).toBe(
      "/research?tab=history&trialId=id+%26+x",
    );
    expect(VER_EN_ASESOR_LABEL).toBe("Ver en Asesor");
    expect(LEDGER_ASESOR_LINK_LABEL).toBe("Ledger Asesor →");
    expect(VER_EN_ASESOR_LABEL).not.toMatch(/Research/i);
  });

  it("relabels the backtesting menu Laboratorio", () => {
    expect(LABORATORIO_LABEL).toBe("Laboratorio");
    expect(LABORATORIO_LABEL).not.toBe("Backtesting");
  });

  it("keeps Confirm as a first-level daily door", () => {
    expect(CONFIRMAR_LABEL).toBe("Confirmar");
    expect(CONFIRM_PATH).toBe("/confirm");
  });

  it("exposes Libro dropdown to Operaciones and Historial without merging routes", () => {
    expect(LIBRO_LABEL).toBe("Libro");
    expect(LIBRO_OPERACIONES_LABEL).toBe("Operaciones");
    expect(LIBRO_HISTORIAL_LABEL).toBe("Historial");
    expect(LIBRO_OPERACIONES_PATH).toBe("/operations");
    expect(LIBRO_HISTORIAL_PATH).toBe("/history");
    expect(LIBRO_OPERACIONES_PATH).not.toBe(LIBRO_HISTORIAL_PATH);
    expect(LIBRO_OPERACIONES_HINT.toLowerCase()).toMatch(/posicion/);
    expect(LIBRO_HISTORIAL_HINT.toLowerCase()).toMatch(/ledger|fill/);
    expect(LIBRO_NAV.label).toBe(LIBRO_LABEL);
    expect(LIBRO_NAV.items).toEqual([
      {
        label: LIBRO_OPERACIONES_LABEL,
        href: LIBRO_OPERACIONES_PATH,
        hint: LIBRO_OPERACIONES_HINT,
      },
      {
        label: OPERATIONAL_CONSOLE_LABEL,
        href: OPERATIONAL_CONSOLE_PATH,
        hint: OPERATIONAL_CONSOLE_HINT,
      },
      {
        label: LIBRO_HISTORIAL_LABEL,
        href: LIBRO_HISTORIAL_PATH,
        hint: LIBRO_HISTORIAL_HINT,
      },
    ]);
  });

  it("orders daily, tools, and lab/tesis groups", () => {
    expect(DAILY_NAV_ORDER).toEqual([
      TRADING_NAV_LABEL,
      SEÑALES_LABEL,
      CONFIRMAR_LABEL,
      LIBRO_LABEL,
    ]);
    expect(DAILY_NAV_ORDER.indexOf(LIBRO_LABEL)).toBeGreaterThan(
      DAILY_NAV_ORDER.indexOf(CONFIRMAR_LABEL),
    );
    expect(HERRAMIENTAS_NAV_ORDER).toEqual([
      "Overview",
      "Cuentas",
      "Alertas",
      "Instrumentos",
      "Decision Board",
    ]);
    expect(LAB_TESIS_NAV_ORDER).toEqual([LABORATORIO_LABEL, ASESOR_LABEL]);
    expect(ASESOR_LABEL).toBe("Asesor");
    expect(ASESOR_TESIS_HINT.toLowerCase()).toMatch(/tesis/);
  });

  it("names list-hub expand atajos Señales and Laboratorio", () => {
    expect(LIST_HUB_EXPAND_ACCESOS_TITLE).toBe(
      `Accesos: ${SEÑALES_LABEL}, Alertas, ${LABORATORIO_LABEL}`,
    );
    expect(LIST_HUB_EXPAND_ACCESOS_TITLE).not.toMatch(
      /Rastreadores|Backtesting/,
    );
  });

  it("uses Universo en vigilancia copy for the Estudio gate", () => {
    expect(UNIVERSO_EN_VIGILANCIA).toBe("Universo en vigilancia");
    expect(formatFueraUniversoOperativaCopy("SEMI")).toBe(
      "Fuera del Universo en vigilancia — SEMI exige estar en Estudio",
    );
    expect(formatFueraUniversoOperativaCopy("SEMI")).not.toMatch(/membresía/);
  });
});
