/**
 * Preferencias de la barra de estado: defaults, persistencia y saneado.
 *
 * Regresión: la configuración vivía en `useState` y se perdía al recargar.
 */

import { beforeEach, describe, expect, it } from "vitest";

import {
  STATUS_BAR_PREFS_KEY,
  defaultStatusBarPrefs,
  getStatusBarPrefsSnapshot,
  loadStatusBarPrefs,
  normalizeStatusBarPrefs,
  saveStatusBarPrefs,
  setShowProviderHealth,
  toggleStatusItem,
} from "@/features/trading/status-bar-prefs";

describe("status-bar-prefs", () => {
  beforeEach(() => {
    localStorage.removeItem(STATUS_BAR_PREFS_KEY);
  });

  it("default: métricas de cartera y proveedores visibles", () => {
    const prefs = loadStatusBarPrefs();
    expect(prefs).toEqual(defaultStatusBarPrefs());
    expect(prefs.visibleItems).toEqual([
      "marketValue",
      "cash",
      "pnl",
      "equity",
    ]);
    expect(prefs.showProviderHealth).toBe(true);
  });

  it("persiste el apagado del icono de proveedores", () => {
    setShowProviderHealth(false);
    expect(
      JSON.parse(localStorage.getItem(STATUS_BAR_PREFS_KEY) ?? "{}"),
    ).toEqual({
      visibleItems: defaultStatusBarPrefs().visibleItems,
      showProviderHealth: false,
    });
    expect(getStatusBarPrefsSnapshot().showProviderHealth).toBe(false);
  });

  it("persiste el encendido/apagado de métricas respetando el orden elegido", () => {
    toggleStatusItem("positions", true);
    toggleStatusItem("cash", false);
    const stored = JSON.parse(
      localStorage.getItem(STATUS_BAR_PREFS_KEY) ?? "{}",
    );
    expect(stored.visibleItems).toEqual([
      "marketValue",
      "pnl",
      "equity",
      "positions",
    ]);
    expect(loadStatusBarPrefs().visibleItems).toEqual(stored.visibleItems);
  });

  it("sanea valores corruptos sin inventar métricas", () => {
    localStorage.setItem(
      STATUS_BAR_PREFS_KEY,
      JSON.stringify({
        visibleItems: ["pnl", "pnl", "inventada"],
        showProviderHealth: "sí",
      }),
    );
    expect(loadStatusBarPrefs()).toEqual({
      visibleItems: ["pnl"],
      showProviderHealth: true,
    });
    expect(normalizeStatusBarPrefs("no-es-objeto")).toEqual(
      defaultStatusBarPrefs(),
    );
  });

  it("permite dejar la barra sin métricas (elección explícita)", () => {
    saveStatusBarPrefs({ visibleItems: [], showProviderHealth: true });
    expect(loadStatusBarPrefs().visibleItems).toEqual([]);
  });
});
