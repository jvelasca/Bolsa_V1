/**
 * Contrato de la sub-navegación AUTO (ADR-044).
 *
 * Fija el espacio AUTO como NO-L1: cinco secciones, rutas bajo `/auto`, y sin
 * colisión de labels con las puertas L1 de ADR-040 (`daily-nav`).
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_ANALISIS_PATH,
  AUTO_CARTERA_PATH,
  AUTO_LABEL,
  AUTO_MONITOR_PATH,
  AUTO_NAV,
  AUTO_OPERACION_BASE_PATH,
  AUTO_OPERAR_PATH,
  AUTO_RIESGO_PATH,
  AUTO_ROOT_PATH,
  AUTO_SISTEMA_PATH,
  autoDiaDHref,
  autoOperacionHref,
  autoSectionFromPathname,
  autoSectionLabel,
  autoTechnicalDetailHref,
} from "@/features/auto/auto-nav";
import { DAILY_NAV_ORDER, MESA_LABEL } from "@/features/confirm/daily-nav";

describe("auto-nav — contrato de secciones", () => {
  it("expone las seis secciones en orden de producto (HOME primero)", () => {
    expect(AUTO_NAV.label).toBe("AUTO");
    expect(AUTO_NAV.items.map((i) => i.id)).toEqual([
      "home",
      "operar",
      "cartera",
      "riesgo",
      "analisis",
      "sistema",
    ]);
    expect(AUTO_NAV.items.map((i) => i.label)).toEqual([
      "Resumen",
      "Operar",
      "Cartera",
      "Riesgo",
      "Análisis",
      "Sistema",
    ]);
  });

  it("vive bajo /auto y no colisiona con las puertas L1 (ADR-040)", () => {
    expect(AUTO_ROOT_PATH).toBe("/auto");
    for (const item of AUTO_NAV.items) {
      expect(item.path === "/auto" || item.path.startsWith("/auto/")).toBe(
        true,
      );
    }
    expect(AUTO_OPERAR_PATH).toBe("/auto/operar");
    expect(AUTO_CARTERA_PATH).toBe("/auto/cartera");
    expect(AUTO_RIESGO_PATH).toBe("/auto/riesgo");
    expect(AUTO_ANALISIS_PATH).toBe("/auto/analisis");
    expect(AUTO_SISTEMA_PATH).toBe("/auto/sistema");
    expect(DAILY_NAV_ORDER).not.toContain(AUTO_LABEL);
    expect(AUTO_LABEL).not.toBe(MESA_LABEL);
  });

  it("construye el deep-link de la operación (con codificación)", () => {
    expect(autoOperacionHref()).toBe(AUTO_OPERAR_PATH);
    expect(autoOperacionHref("")).toBe(AUTO_OPERAR_PATH);
    expect(autoOperacionHref("cyc-1")).toBe(
      `${AUTO_OPERACION_BASE_PATH}/cyc-1`,
    );
    expect(autoOperacionHref("a/b c")).toBe(
      `${AUTO_OPERACION_BASE_PATH}/a%2Fb%20c`,
    );
  });

  it("construye el detalle técnico apuntando al monitor experto", () => {
    expect(AUTO_MONITOR_PATH).toBe("/auto-monitor");
    expect(autoTechnicalDetailHref()).toBe("/auto-monitor?mode=current");
    expect(autoTechnicalDetailHref("")).toBe("/auto-monitor?mode=current");
    expect(autoTechnicalDetailHref("cyc-1")).toBe(
      "/auto-monitor?mode=current&cycle=cyc-1",
    );
    // El ciclo vive en la query ⇒ se codifica (no rompe la URL).
    const href = autoTechnicalDetailHref("a/b c");
    const params = new URLSearchParams(href.split("?")[1]);
    expect(params.get("mode")).toBe("current");
    expect(params.get("cycle")).toBe("a/b c");
  });

  it("construye el deep-link DÍA-D hacia el workspace AUTO", () => {
    const base = autoDiaDHref();
    expect(base.startsWith(`${AUTO_ANALISIS_PATH}?`)).toBe(true);
    const baseParams = new URLSearchParams(base.split("?")[1]);
    expect(baseParams.get("tab")).toBe("dia-d");
    expect(baseParams.get("view")).toBe("feedback");
    expect(baseParams.get("symbol")).toBeNull();

    const full = new URLSearchParams(
      autoDiaDHref({ window: "2026-09-29_2026-09-30", symbol: "a/b c" }).split(
        "?",
      )[1],
    );
    expect(full.get("window")).toBe("2026-09-29_2026-09-30");
    expect(full.get("symbol")).toBe("a/b c");
  });

  it("resuelve la sección activa desde el pathname", () => {
    expect(autoSectionFromPathname("/auto")?.id).toBe("home");
    expect(autoSectionFromPathname("/auto/operar")?.id).toBe("operar");
    expect(autoSectionFromPathname("/auto/operar/operacion/cyc-1")?.id).toBe(
      "operar",
    );
    expect(autoSectionFromPathname("/auto/sistema")?.id).toBe("sistema");
    expect(autoSectionFromPathname("/mesa")).toBeNull();
    expect(autoSectionFromPathname("/auto-monitor")).toBeNull();
  });

  it("etiqueta secciones por id", () => {
    expect(autoSectionLabel("home")).toBe("Resumen");
    expect(autoSectionLabel("operar")).toBe("Operar");
    expect(autoSectionLabel("analisis")).toBe("Análisis");
  });
});
