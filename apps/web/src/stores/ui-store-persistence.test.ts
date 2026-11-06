/**
 * Persistencia de tema y densidad (WS-D11).
 *
 * Compartían clave con la sesión de herramienta de dibujo y
 * `writeDrawToolSessionLocal` la reescribía sin ellos: cambiar de herramienta
 * borraba el tema y al recargar volvía el oscuro.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { UI_PREFS_STORAGE_KEY, useUiStore } from "@/stores/ui-store";
import { writeDrawToolSessionLocal } from "@/lib/draw-tool-session-storage";

const LEGACY_KEY = "bolsa-chart-draw-tool-session";

function readPersisted(): Record<string, unknown> {
  const raw = localStorage.getItem(UI_PREFS_STORAGE_KEY);
  expect(raw).toBeTruthy();
  return (JSON.parse(raw!) as { state?: Record<string, unknown> }).state ?? {};
}

beforeEach(() => {
  localStorage.clear();
  useUiStore.setState({ uiTheme: "dark", uiDensity: "comfortable" });
});

describe("ui-store — clave propia de preferencias", () => {
  it("persiste tema y densidad bajo bolsa-ui-prefs-v1", () => {
    useUiStore.getState().setUiTheme("light");
    useUiStore.getState().setUiDensity("compact");

    const persisted = readPersisted();
    expect(persisted.uiTheme).toBe("light");
    expect(persisted.uiDensity).toBe("compact");
  });

  it("no guarda la herramienta de dibujo en la clave de preferencias", () => {
    useUiStore.getState().setUiTheme("light");
    useUiStore.getState().setChartDrawTool("hline");

    const persisted = readPersisted();
    expect(persisted).not.toHaveProperty("chartDrawTool");
    expect(persisted).not.toHaveProperty("lastDrawToolByGroup");
  });

  it("cambiar de herramienta de dibujo no borra el tema persistido", () => {
    useUiStore.getState().setUiTheme("light");
    useUiStore.getState().setUiDensity("compact");

    // Antes esta escritura machacaba la clave compartida y perdía el tema.
    writeDrawToolSessionLocal({
      chartDrawTool: "hline",
      lastDrawToolByGroup: {},
    });

    const persisted = readPersisted();
    expect(persisted.uiTheme).toBe("light");
    expect(persisted.uiDensity).toBe("compact");

    const legacy = JSON.parse(localStorage.getItem(LEGACY_KEY)!);
    expect(legacy.state).not.toHaveProperty("uiTheme");
  });
});

describe("ui-store — migración desde la clave antigua", () => {
  it("recupera tema y densidad del blob legacy una sola vez", async () => {
    localStorage.clear();
    localStorage.setItem(
      LEGACY_KEY,
      JSON.stringify({
        state: {
          chartDrawTool: "hline",
          lastDrawToolByGroup: { cursor: "hline" },
          uiTheme: "light",
          uiDensity: "compact",
        },
        version: 0,
      }),
    );

    vi.resetModules();
    const fresh = await import("@/stores/ui-store");

    expect(fresh.useUiStore.getState().uiTheme).toBe("light");
    expect(fresh.useUiStore.getState().uiDensity).toBe("compact");
  });

  it("la clave nueva gana sobre el blob legacy", async () => {
    localStorage.clear();
    localStorage.setItem(
      UI_PREFS_STORAGE_KEY,
      JSON.stringify({
        state: { uiTheme: "system", uiDensity: "compact" },
        version: 0,
      }),
    );
    localStorage.setItem(
      LEGACY_KEY,
      JSON.stringify({ state: { uiTheme: "light", uiDensity: "comfortable" } }),
    );

    vi.resetModules();
    const fresh = await import("@/stores/ui-store");

    expect(fresh.useUiStore.getState().uiTheme).toBe("system");
    expect(fresh.useUiStore.getState().uiDensity).toBe("compact");
  });
});
