/**
 * B-5 / O-6 — panel único de declaraciones de HOLD.
 *
 * Certifica lo que el usuario ve sin abrir el monitor: símbolo, causa, motivo y día legible; la
 * procedencia declarada con su medición; y los datos crudos bajo UN disclosure canónico.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  AutoHoldDeclarationsPanel,
  AutoHoldSummaryLine,
} from "@/features/auto/auto-hold-declarations-panel";

afterEach(cleanup);

const HOLD = {
  instrumentId: "AAA",
  barTimestamp: "2026-09-30T00:00:00Z",
  at: "2026-09-30T00:00:01Z",
  reason: "warmup_unmeasurable",
  measurement: "COMPLETE",
  facts: [
    {
      key: "holdReason",
      value: "warmup_unmeasurable",
      measurement: "COMPLETE",
    },
    {
      key: "featureSource",
      value: "real",
      measurement: "COMPLETE",
    },
    { key: "signalWindowBars", value: 201, measurement: "COMPLETE" },
    { key: "warmupBars", value: 201, measurement: "COMPLETE" },
    {
      key: "gatedState",
      value: { holdsLong: null, source: "unavailable" },
      measurement: "COMPLETE",
    },
    { key: "mysteryKey", value: "crudo", measurement: "COMPLETE" },
  ],
};

describe("AutoHoldDeclarationsPanel", () => {
  it("pinta símbolo, causa, motivo, día legible y procedencia", () => {
    render(<AutoHoldDeclarationsPanel holds={[HOLD]} />);

    const item = screen.getByTestId("auto-decision-silence-item");
    expect(
      within(item).getByTestId("auto-decision-silence-item-symbol").textContent,
    ).toBe("AAA");
    expect(
      within(item).getByTestId("auto-decision-silence-item-cause").textContent,
    ).toBe("no evaluable");
    expect(
      within(item).getByTestId("auto-decision-silence-item-reason").textContent,
    ).toBe("warmup no medible");
    // El día de la barra se pinta legible y sin hora: el sello ISO completo no sube.
    const bar = within(item).getByTestId("auto-decision-silence-item-bar");
    expect(bar.textContent).toContain("barra");
    expect(bar.textContent).toContain("2026");
    expect(bar.textContent).not.toContain("T00:00:00Z");
    expect(bar.textContent).not.toContain(":");

    const provenance = screen.getAllByTestId(
      "auto-decision-silence-provenance-item",
    );
    expect(
      provenance.map((node) => node.getAttribute("data-fact-key")),
    ).toEqual([
      "featureSource",
      "signalWindowBars",
      "warmupBars",
      "gatedState",
    ]);
    const values = screen.getAllByTestId(
      "auto-decision-silence-provenance-value",
    );
    expect(values[0]?.textContent).toBe("datos reales");
    expect(values[1]?.textContent).toBe("201 barras");
    expect(values[3]?.textContent).toContain("libro no legible");
  });

  it("lo crudo vive en UN único detalle técnico canónico, fuera del primer nivel", () => {
    render(<AutoHoldDeclarationsPanel holds={[HOLD]} />);

    // RT-04: un solo disclosure por bloque y rotulado canónicamente.
    const details = document.querySelectorAll('[data-technical-detail="true"]');
    expect(details).toHaveLength(1);
    expect(screen.getAllByText("Detalle técnico")).toHaveLength(1);
    const technical = screen.getByTestId("auto-decision-silence-technical");
    expect(technical.getAttribute("data-technical-detail")).toBe("true");

    // Ni la clave desconocida ni el sello de auditoría aparecen en el primer nivel.
    const firstLevel = screen.getByTestId("auto-decision-silence-list");
    expect(firstLevel.textContent).not.toContain("mysteryKey");
    expect(firstLevel.textContent).not.toContain("2026-09-30T00:00:01Z");
    expect(firstLevel.textContent).not.toContain("warmup_unmeasurable");

    // Y siguen disponibles dentro del disclosure.
    const group = screen.getByTestId("auto-decision-silence-item-technical");
    expect(
      within(group).getByTestId("auto-decision-silence-technical-instrument")
        .textContent,
    ).toContain("AAA");
    expect(
      within(group).getByTestId("auto-decision-silence-technical-at")
        .textContent,
    ).toContain("2026-09-30T00:00:01Z");
    expect(
      within(group).getByTestId("auto-decision-silence-technical-reason")
        .textContent,
    ).toContain("warmup_unmeasurable");
    const facts = within(group).getAllByTestId(
      "auto-decision-silence-technical-fact",
    );
    expect(facts.map((node) => node.getAttribute("data-fact-key"))).toEqual([
      "holdReason",
      "featureSource",
      "signalWindowBars",
      "warmupBars",
      "gatedState",
      "mysteryKey",
    ]);
  });

  it("declara la procedencia ausente en vez de inventarla", () => {
    render(
      <AutoHoldDeclarationsPanel
        holds={[{ instrumentId: "BBB", reason: "no_signal", facts: [] }]}
      />,
    );

    expect(
      screen.getByTestId("auto-decision-silence-provenance-absent").textContent,
    ).toBe("Procedencia no declarada");
    expect(
      screen.queryAllByTestId("auto-decision-silence-provenance-item"),
    ).toHaveLength(0);
  });

  it("sin declaraciones no afirma «sin señal»", () => {
    render(<AutoHoldDeclarationsPanel holds={[]} />);

    expect(
      screen.getByTestId("auto-decision-silence-empty").textContent,
    ).toContain("consta el motivo");
    expect(
      screen.getByTestId("auto-decision-silence-headline").textContent,
    ).toBe("Sin HOLD declarados en la ventana");
    expect(screen.queryAllByTestId("auto-decision-silence-item")).toHaveLength(
      0,
    );
    // Sin filas no se monta un disclosure vacío.
    expect(screen.queryByTestId("auto-decision-silence-technical")).toBeNull();
  });

  it("un motivo ausente se declara y no se rellena con una causa", () => {
    render(
      <AutoHoldDeclarationsPanel
        holds={[{ instrumentId: "AAA", reason: null, facts: [] }]}
      />,
    );

    const item = screen.getByTestId("auto-decision-silence-item");
    expect(
      within(item).getByTestId("auto-decision-silence-item-reason").textContent,
    ).toBe("Motivo no declarado");
    expect(item.getAttribute("data-cause")).toBe("unmeasured");
  });

  it("el aviso ámbar sólo lista los no evaluables", () => {
    render(
      <AutoHoldDeclarationsPanel
        holds={[
          { instrumentId: "AAA", reason: "warmup_unmeasurable", facts: [] },
          { instrumentId: "BBB", reason: "no_signal", facts: [] },
        ]}
      />,
    );

    const attention = screen.getByTestId("auto-decision-silence-attention");
    expect(attention.textContent).toContain("1 de 2");
    expect(attention.textContent).toContain("AAA");
    expect(attention.textContent).not.toContain("BBB");
  });

  it("la carga no se presenta como vacío", () => {
    render(<AutoHoldDeclarationsPanel holds={[]} loading />);

    expect(screen.getByTestId("auto-decision-silence-loading")).toBeTruthy();
    expect(screen.queryByTestId("auto-decision-silence-empty")).toBeNull();
    expect(screen.queryByTestId("auto-decision-silence-headline")).toBeNull();
  });

  it("el error de lectura se declara distinto del vacío", () => {
    render(<AutoHoldDeclarationsPanel holds={[]} error />);

    expect(screen.getByTestId("auto-decision-silence-error")).toBeTruthy();
    expect(screen.queryByTestId("auto-decision-silence-empty")).toBeNull();
  });

  it("con día declarado filtra y declara las declaraciones que quedan fuera", () => {
    render(
      <AutoHoldDeclarationsPanel
        day="2026-09-30"
        holds={[
          HOLD,
          {
            instrumentId: "BBB",
            barTimestamp: "2026-09-29T00:00:00Z",
            at: "2026-09-29T00:00:01Z",
            reason: "no_signal",
            measurement: "COMPLETE",
            facts: [],
          },
        ]}
      />,
    );

    expect(screen.getAllByTestId("auto-decision-silence-item")).toHaveLength(1);
    expect(
      screen.getByTestId("auto-decision-silence-scope").textContent,
    ).toContain("1 declaración queda fuera");
  });

  it("acepta un prefijo de testids y un encabezado de nivel 3 para vivir dentro de una capa", () => {
    render(
      <AutoHoldDeclarationsPanel
        holds={[HOLD]}
        headingLevel="h3"
        testIdPrefix="auto-no-trade-hold"
        title="Por qué hubo HOLD en la señal (hoy)"
      />,
    );

    expect(screen.getByTestId("auto-no-trade-hold")).toBeTruthy();
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Por qué hubo HOLD en la señal (hoy)",
      }),
    ).toBeTruthy();
    expect(screen.getByTestId("auto-no-trade-hold-item")).toBeTruthy();
  });
});

describe("AutoHoldSummaryLine", () => {
  it("publica el titular honesto sin duplicar el copy en cada página", () => {
    render(
      <AutoHoldSummaryLine
        testId="sum"
        holds={[
          { instrumentId: "AAA", reason: "warmup_unmeasurable", facts: [] },
          { instrumentId: "BBB", reason: "no_signal", facts: [] },
        ]}
      />,
    );

    const line = screen.getByTestId("sum");
    expect(line.textContent).toContain("1 sin señal");
    expect(line.textContent).toContain("1 HOLD no evaluable");
  });

  it("sin declaraciones declara el hueco, no «sin señal»", () => {
    render(<AutoHoldSummaryLine testId="sum" holds={[]} />);

    expect(screen.getByTestId("sum").textContent).toBe(
      "Sin HOLD declarados en la ventana",
    );
  });
});
