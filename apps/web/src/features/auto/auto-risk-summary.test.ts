/**
 * AUTO UI REFACTOR 3.0 (S3) — cabecera plana de RIESGO: casos duros.
 *
 * Fija que RIESGO no inventa cifras: lo no materializado se declara «Sin dato todavía» y los
 * estados de integridad se traducen sin fundir «no medido» con un valor tranquilizador.
 */

import { describe, expect, it } from "vitest";
import {
  buildAutoRiskSummary,
  AUTO_RISK_TONE_CLASS,
} from "@/features/auto/auto-risk-summary";

describe("buildAutoRiskSummary", () => {
  it("traduce estado, integridad de cartera e incidencias de enlace", () => {
    const risk = buildAutoRiskSummary({
      operationalState: "OK",
      portfolioStatus: "clean",
      fillLinkIssuesCount: 0,
    });
    expect(risk.loaded).toBe(true);
    expect(risk.stateTone).toBe("ok");
    expect(risk.stateLabel).toBe("Normal");
    expect(risk.portfolioLabel).toBe("Cuadra");
    expect(risk.fillLinkIssuesLabel).toBe("Sin incidencias");
    // El riesgo por posición no se materializa en el read-model de AUTO.
    expect(risk.positionRiskAvailable).toBe(false);
    expect(risk.positionRiskLabel).toBe("Sin dato todavía");
  });

  it("un estado degradado/bloqueado no se disfraza de OK", () => {
    expect(
      buildAutoRiskSummary({ operationalState: "DEGRADED" }).stateTone,
    ).toBe("attention");
    expect(
      buildAutoRiskSummary({ operationalState: "BLOCKED" }).stateTone,
    ).toBe("blocked");
  });

  it("un hueco se declara, NUNCA se rellena con 0", () => {
    const risk = buildAutoRiskSummary({
      operationalState: null,
      portfolioStatus: null,
      fillLinkIssuesCount: null,
    });
    expect(risk.stateLabel).toBe("Sin dato todavía");
    expect(risk.portfolioLabel).toBe("Sin dato todavía");
    expect(risk.fillLinkIssuesLabel).toBe("Sin dato todavía");
    // Y jamás la cadena "0".
    expect(JSON.stringify(risk)).not.toContain('"0"');
  });

  it("cuenta incidencias reales sin colapsarlas a vacío", () => {
    expect(
      buildAutoRiskSummary({ operationalState: "OK", fillLinkIssuesCount: 1 })
        .fillLinkIssuesLabel,
    ).toBe("1 incidencia");
    expect(
      buildAutoRiskSummary({ operationalState: "OK", fillLinkIssuesCount: 3 })
        .fillLinkIssuesLabel,
    ).toBe("3 incidencias");
  });

  it("durante la carga y en error no se finge ningún dato", () => {
    const loading = buildAutoRiskSummary({
      operationalState: "OK",
      portfolioStatus: "clean",
      isLoading: true,
    });
    expect(loading.loaded).toBe(false);
    expect(loading.stateLabel).toBe("Sin dato todavía");

    const error = buildAutoRiskSummary({
      operationalState: "OK",
      isError: true,
    });
    expect(error.loaded).toBe(false);
    expect(error.stateLabel).toBe("Sin dato todavía");
  });

  it("cada tono tiene su clase de color", () => {
    for (const tone of ["ok", "attention", "blocked", "unknown"] as const) {
      expect(AUTO_RISK_TONE_CLASS[tone]).toBeTruthy();
    }
  });
});
