/**
 * F5 — «Motivo de selección» del ranking AUTO: humanizador con degradado honesto.
 *
 * Invariantes: un código catalogado se traduce a su etiqueta de usuario; un código NO catalogado
 * NUNCA se pinta crudo (degrada a «Sin dato todavía»); sin componentes medibles el motivo es
 * `null` (⇒ la superficie declara `UNKNOWN`, nunca un relleno).
 */

import { describe, expect, it } from "vitest";

import {
  AUTO_RANKING_COMPONENT_LABELS,
  AUTO_RANKING_COMPONENT_ORDER,
  AUTO_RANKING_NO_DATA_LABEL,
  autoRankingComponentLabel,
  autoRankingMotiveLabel,
} from "./auto-ranking-motive.js";

describe("autoRankingComponentLabel", () => {
  it("traduce un componente catalogado a su etiqueta de usuario", () => {
    expect(autoRankingComponentLabel("edge")).toBe("Ventaja esperada");
    expect(autoRankingComponentLabel("regime_fit")).toBe(
      "Encaje con el régimen",
    );
    expect(autoRankingComponentLabel("execution_quality")).toBe(
      "Calidad de ejecución",
    );
  });

  it("un código desconocido o ausente degrada a «Sin dato todavía», nunca crudo", () => {
    expect(autoRankingComponentLabel("bogus_component")).toBe(
      AUTO_RANKING_NO_DATA_LABEL,
    );
    expect(autoRankingComponentLabel(null)).toBe(AUTO_RANKING_NO_DATA_LABEL);
    expect(autoRankingComponentLabel("")).toBe(AUTO_RANKING_NO_DATA_LABEL);
    // El código crudo NUNCA se devuelve tal cual.
    expect(autoRankingComponentLabel("bogus_component")).not.toContain("bogus");
  });

  it("cada componente canónico tiene etiqueta (sin huecos silenciosos)", () => {
    for (const code of AUTO_RANKING_COMPONENT_ORDER) {
      expect(AUTO_RANKING_COMPONENT_LABELS[code]).toBeTruthy();
    }
  });
});

describe("autoRankingMotiveLabel", () => {
  it("compone el motivo con los factores que CONTRIBUYERON, en orden canónico", () => {
    // `robustness` (peso 20%) va antes que `momentum` (10%); `edge` (30%) primero.
    const label = autoRankingMotiveLabel({
      momentum: 0.5,
      edge: 0.9,
      robustness: 0.6,
    });
    expect(label).toBe("Ventaja esperada · Robustez · Momento");
  });

  it("omite los factores que NO contribuyeron (valor 0)", () => {
    const label = autoRankingMotiveLabel({
      edge: 0.8,
      robustness: 0,
      momentum: 0,
    });
    expect(label).toBe("Ventaja esperada");
  });

  it("sin componentes medibles el motivo es null (⇒ UNKNOWN, nunca 0/relleno)", () => {
    expect(autoRankingMotiveLabel(null)).toBeNull();
    expect(autoRankingMotiveLabel(undefined)).toBeNull();
    expect(autoRankingMotiveLabel({})).toBeNull();
    expect(autoRankingMotiveLabel({ edge: 0, robustness: 0 })).toBeNull();
  });

  it("un componente NO catalogado degrada a «Sin dato todavía», nunca crudo", () => {
    const label = autoRankingMotiveLabel({ edge: 0.5, bogus_component: 0.4 });
    expect(label).toContain("Ventaja esperada");
    expect(label).toContain(AUTO_RANKING_NO_DATA_LABEL);
    expect(label).not.toContain("bogus");
  });

  it("un motivo hecho SÓLO de códigos no catalogados NO se declara medido", () => {
    expect(autoRankingMotiveLabel({ bogus_component: 0.4 })).toBeNull();
  });
});
