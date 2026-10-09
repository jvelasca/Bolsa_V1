/**
 * S4-agregador-evidencia — regresión de la superficie agregada.
 *
 * Invariantes:
 * 1. El veredicto global es `NO CONFIRMADO` aunque las tres capas medibles estén medidas.
 * 2. La capa de ejecución real se pinta como hueco («Sin dato todavía»).
 * 3. El primer nivel está humanizado: los enums crudos no se filtran fuera del detalle técnico.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { buildDiaDEvidenceAggregate } from "@/features/auto-monitor/dia-d-evidence-aggregate";
import { DiaDEvidenceAggregateView } from "@/features/auto-monitor/dia-d-evidence-aggregate-panel";

afterEach(() => {
  cleanup();
});

describe("DiaDEvidenceAggregateView", () => {
  it("muestra NO CONFIRMADO y la ejecución real como hueco, sin enums crudos", () => {
    const aggregate = buildDiaDEvidenceAggregate({
      window: {
        loaded: true,
        verdict: "READY",
        days: 4,
        episodes: 2,
        cycles: 32,
      },
      reconciliation: {
        loaded: true,
        verdict: "MATCH",
        match: 3,
        divergent: 0,
        notMeasured: 0,
      },
      oos: {
        loaded: true,
        oosSupported: 1,
        mixed: 0,
        refuted: 0,
        notMeasured: 0,
      },
    });

    render(<DiaDEvidenceAggregateView aggregate={aggregate} />);

    expect(
      screen.getByTestId("dia-d-evidence-aggregate-verdict").textContent,
    ).toContain("NO CONFIRMADO");

    const layers = screen.getAllByTestId("dia-d-evidence-aggregate-layer");
    const paper = layers.find(
      (layer) => layer.getAttribute("data-layer") === "paper",
    );
    expect(paper?.getAttribute("data-state")).toBe("gap");
    expect(paper?.textContent).toContain("Sin dato todavía");

    const stateText = screen
      .getAllByTestId("dia-d-evidence-aggregate-layer-state")
      .map((element) => element.textContent)
      .join(" ");
    expect(stateText).toContain("Soportado fuera de muestra");
    expect(stateText).not.toContain("OOS_SUPPORTED");
    expect(stateText).not.toContain("MATCH");
    expect(stateText).not.toContain("READY");
  });

  it("declara la evidencia OOS como hueco cuando falta un contador", () => {
    const aggregate = buildDiaDEvidenceAggregate({
      oos: {
        loaded: true,
        oosSupported: 2,
        mixed: null,
        refuted: null,
        notMeasured: null,
      },
    });

    render(<DiaDEvidenceAggregateView aggregate={aggregate} />);

    const oos = screen
      .getAllByTestId("dia-d-evidence-aggregate-layer")
      .find((layer) => layer.getAttribute("data-layer") === "oos");
    expect(oos?.getAttribute("data-state")).toBe("gap");
    expect(oos?.textContent).toContain("Sin dato todavía");
    expect(oos?.textContent).toContain("soportados 2");
    expect(oos?.textContent).not.toContain("Soportado fuera de muestra");
  });
});
