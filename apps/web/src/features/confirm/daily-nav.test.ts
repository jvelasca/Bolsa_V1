/**
 * Tests — arquitectura de usuario V1.20 (ADR-040).
 */

import { describe, expect, it } from "vitest";
import {
  ASESOR_LABEL,
  ASESOR_PATH,
  ASESOR_TESIS_HINT,
  CARTERA_LABEL,
  CARTERA_NAV,
  CARTERA_POSICIONES_PATH,
  CONFIRMAR_LABEL,
  DAILY_NAV_ORDER,
  DECISIONES_LABEL,
  DECISIONES_PATH,
  DECISION_SPINE_PATH,
  HERRAMIENTAS_NAV_ORDER,
  HOY_VIEW,
  LABORATORIO_LABEL,
  LAB_TESIS_NAV_ORDER,
  LEDGER_ASESOR_LINK_LABEL,
  LIBRO_HISTORIAL_HINT,
  LIBRO_HISTORIAL_LABEL,
  LIBRO_HISTORIAL_PATH,
  LIBRO_LABEL,
  LIBRO_NAV,
  LIBRO_OPERACIONES_HINT,
  LIBRO_OPERACIONES_LABEL,
  LIBRO_OPERACIONES_PATH,
  LIST_HUB_EXPAND_ACCESOS_TITLE,
  MERCADO_LABEL,
  MERCADO_NAV,
  MERCADO_PATH,
  MESA_LABEL,
  MESA_PATH,
  OPERATIONAL_CONSOLE_LABEL,
  OPERATIONAL_CONSOLE_PATH,
  SEÑALES_LABEL,
  SEÑALES_PATH,
  TRADING_NAV_LABEL,
  UNIVERSO_EN_VIGILANCIA,
  UX_DOOR,
  VER_EN_ASESOR_LABEL,
  asesorHistoryHref,
  formatFueraUniversoOperativaCopy,
  hoyViewHref,
} from "@/features/confirm/daily-nav";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";

describe("daily-nav", () => {
  it("names the daily signal hub Señales on /screeners (under Mercado)", () => {
    expect(SEÑALES_LABEL).toBe("Señales");
    expect(SEÑALES_PATH).toBe("/screeners");
    expect(SEÑALES_PATH).not.toBe("/research");
    expect(ASESOR_PATH).toBe("/research");
    expect(ASESOR_PATH).not.toBe(SEÑALES_PATH);
    expect(MERCADO_NAV.items.some((i) => i.href === SEÑALES_PATH)).toBe(true);
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

  it("keeps Confirm as a route but not a L1 door", () => {
    expect(CONFIRMAR_LABEL).toBe("Confirmar");
    expect(CONFIRM_PATH).toBe("/confirm");
    expect(DAILY_NAV_ORDER).not.toContain(CONFIRMAR_LABEL);
  });

  it("exposes Cartera dropdown (Posiciones / Órdenes / Historial / Riesgo)", () => {
    expect(CARTERA_LABEL).toBe("Cartera");
    expect(LIBRO_LABEL).toBe(CARTERA_LABEL);
    expect(LIBRO_OPERACIONES_LABEL).toBe("Posiciones");
    expect(LIBRO_HISTORIAL_LABEL).toBe("Historial");
    expect(CARTERA_POSICIONES_PATH).toBe("/mesa?view=posiciones");
    expect(LIBRO_OPERACIONES_PATH).toBe(CARTERA_POSICIONES_PATH);
    expect(LIBRO_HISTORIAL_PATH).toBe("/history");
    expect(LIBRO_OPERACIONES_PATH).not.toBe(LIBRO_HISTORIAL_PATH);
    expect(LIBRO_OPERACIONES_HINT.toLowerCase()).toMatch(/posicion/);
    expect(LIBRO_HISTORIAL_HINT.toLowerCase()).toMatch(/ledger|fill/);
    expect(CARTERA_NAV.label).toBe(CARTERA_LABEL);
    expect(CARTERA_NAV.items).toHaveLength(4);
    expect(LIBRO_NAV.label).toBe(CARTERA_LABEL);
  });

  it("promotes Hoy as first daily nav item (ADR-040)", () => {
    expect(MESA_LABEL).toBe("Hoy");
    expect(MESA_PATH).toBe("/mesa");
    expect(DAILY_NAV_ORDER[0]).toBe(MESA_LABEL);
    expect(DAILY_NAV_ORDER).toEqual([
      MESA_LABEL,
      MERCADO_LABEL,
      CARTERA_LABEL,
      ASESOR_LABEL,
      LABORATORIO_LABEL,
    ]);
    expect(TRADING_NAV_LABEL).toBe(MERCADO_LABEL);
    expect(MERCADO_PATH).toBe("/trading");
  });

  it("does not expose Consola ops / Decision Spine as L1 tools", () => {
    expect(HERRAMIENTAS_NAV_ORDER).not.toContain(OPERATIONAL_CONSOLE_LABEL);
    expect(HERRAMIENTAS_NAV_ORDER).not.toContain("Consola ops");
    expect(HERRAMIENTAS_NAV_ORDER).not.toContain("Decision Spine");
    expect(HERRAMIENTAS_NAV_ORDER).not.toContain("Decision Board");
    expect(
      CARTERA_NAV.items.some((i) => i.href === OPERATIONAL_CONSOLE_PATH),
    ).toBe(false);
    expect(DECISIONES_PATH).toBe("/mesa?view=decisiones");
    expect(DECISION_SPINE_PATH).toBe(DECISIONES_PATH);
    expect(DECISIONES_LABEL).toBe("Decisiones");
  });

  it("orders the five user doors and lab/asesor", () => {
    expect(DAILY_NAV_ORDER.indexOf(CARTERA_LABEL)).toBeGreaterThan(
      DAILY_NAV_ORDER.indexOf(MERCADO_LABEL),
    );
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

  it("answers UX-01…05 without internal module names", () => {
    expect(UX_DOOR.whatToDoToday).toBe("Hoy");
    expect(UX_DOOR.bestToBuy).toBe("Hoy → Oportunidades");
    expect(UX_DOOR.studySymbol).toMatch(/Mercado/);
    expect(UX_DOOR.modifyOrder).toBe("Cartera → Órdenes");
    expect(UX_DOOR.opsFailed).toMatch(/estado operativo/);
    const blob = Object.values(UX_DOOR).join(" ");
    expect(blob).not.toMatch(
      /Decision Spine|Consola ops|Libro|Decision Journal/i,
    );
  });

  it("builds Hoy view hrefs", () => {
    expect(hoyViewHref(HOY_VIEW.resumen)).toBe("/mesa");
    expect(hoyViewHref(HOY_VIEW.oportunidades)).toBe(
      "/mesa?view=oportunidades",
    );
    expect(hoyViewHref(HOY_VIEW.decisiones)).toBe("/mesa?view=decisiones");
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
