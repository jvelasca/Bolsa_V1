/**
 * Guarda de S1: las superficies de recomendación hablan lenguaje de mercado.
 *
 * Dos comprobaciones complementarias:
 * 1. Render: `OperativaDictamenBlock` nunca pinta la clave interna, snake_case,
 *    «Sobrecomprado» ni un ★3 fabricado cuando el IO no se midió.
 * 2. Fuente: los textos retirados (`MARKET_VOCABULARY_RETIRED_TERMS`) no vuelven
 *    a las superficies de dictamen, aunque alguien reescriba el componente.
 *
 * @see docs/engineering/glosario-mercado-asesor-2026-11-12.md
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  INSTRUMENT_DAILY_OPINION_STANCES,
  MARKET_VOCABULARY_RETIRED_TERMS,
  type InstrumentDailyOpinionStance,
  type InstrumentDailyOpinionV1,
} from "@bolsa/shared";
import { OperativaDictamenBlock } from "@/features/trading/operativa-dictamen";

afterEach(() => cleanup());

const INTERNAL_KEY = /[a-z]+_[a-z]+/;

function opinion(
  stance: InstrumentDailyOpinionStance,
  overrides: Partial<InstrumentDailyOpinionV1> = {},
): InstrumentDailyOpinionV1 {
  return {
    id: "op-1",
    instrumentId: "inst-1",
    asOfBarDate: "2026-11-12",
    stance,
    dictamenStars: 4,
    ioScore: 72,
    distress: false,
    reasons: [],
    source: "eod_batch",
    engineVersion: "opinion_v1",
    idempotencyKey: "k",
    computedAt: "2026-11-12T18:00:00.000Z",
    createdAt: "2026-11-12T18:00:00.000Z",
    updatedAt: "2026-11-12T18:00:00.000Z",
    ...overrides,
  } as InstrumentDailyOpinionV1;
}

function renderedText(): string {
  return screen.getByTestId("operativa-dictamen").textContent ?? "";
}

describe("OPERATIVA · recomendación sin jerga interna", () => {
  it("cada postura pinta su denominación y nunca su clave interna", () => {
    for (const stance of INSTRUMENT_DAILY_OPINION_STANCES) {
      render(<OperativaDictamenBlock opinion={opinion(stance)} />);
      const text = renderedText();
      expect(text).not.toContain(stance);
      expect(text).not.toMatch(INTERNAL_KEY);
      cleanup();
    }
  });

  it("overbought se lee «Sin respaldo», sin resbalar a sobrecompra", () => {
    render(
      <OperativaDictamenBlock
        opinion={opinion("overbought", {
          reasons: ["top_low", "overbought_or_exit"],
        })}
      />,
    );
    const text = renderedText();
    expect(text).toContain("Sin respaldo");
    expect(text).not.toContain("Sobrecomprado");
    expect(text.toLowerCase()).not.toContain("sobrecompra");
  });

  it("no_trade declara la causa: cartera sin medir no es «No operar»", () => {
    render(
      <OperativaDictamenBlock
        opinion={opinion("no_trade", {
          ioScore: null,
          reasons: ["position_unmeasured", "io_unmeasured", "io_medium"],
        })}
      />,
    );
    const text = renderedText();
    expect(text).toContain("No evaluable");
    expect(text).toContain("Cartera sin medir");
    expect(text).not.toContain("No operar");
    expect(text).not.toContain("sin posición");
    // IO sin medir: ni ★ fabricadas ni confianza fingida.
    expect(text).toContain("Sin medir");
    expect(text).not.toContain("★★★★");
  });

  it("un IO sin medir no se pinta como ★★★ medido", () => {
    render(
      <OperativaDictamenBlock
        opinion={opinion("hold_watch", { ioScore: null, dictamenStars: 3 })}
      />,
    );
    expect(renderedText()).not.toContain("★★★");
    expect(renderedText()).toContain("Sin medir");
  });

  it("los motivos se traducen y el tooltip conserva el detalle", () => {
    render(
      <OperativaDictamenBlock
        opinion={opinion("buy", {
          ioScore: 85,
          reasons: ["strong_buy_signal", "top_high", "io_high", "top_medium"],
        })}
      />,
    );
    const text = renderedText();
    expect(text).toContain("Señal de compra fuerte");
    expect(text).toContain("(+1)");
    expect(text).not.toMatch(INTERNAL_KEY);
    const motivos = screen.getByTestId("operativa-dictamen-motivos");
    expect(motivos.getAttribute("title")).toContain(
      "Estrategia del Lab con respaldo suficiente",
    );
  });

  it("hold_watch se lee «Mantener», no «Vigilar»", () => {
    render(<OperativaDictamenBlock opinion={opinion("hold_watch")} />);
    expect(renderedText()).toContain("Mantener");
    expect(renderedText()).not.toContain("Vigilar");
  });
});

describe("superficies de dictamen · textos retirados", () => {
  const SURFACES = [
    "operativa-dictamen.tsx",
    "operativa-analisis-diario.tsx",
    "../research/asesor-opiniones-panel.tsx",
    "../research/asesor-cartera-panel.tsx",
    "../auto-monitor/estudio-daily-ops-panel.tsx",
    "../instruments/instrument-dictamen-evolution.tsx",
    // S4 — recomendación principal de la ventana maximizada de DECISIÓN.
    "operativa-recomendacion-principal.tsx",
  ];

  it("no reaparecen los términos retirados en el primer nivel", () => {
    for (const file of SURFACES) {
      const source = readFileSync(resolve(__dirname, file), "utf8");
      for (const term of MARKET_VOCABULARY_RETIRED_TERMS) {
        expect(source, `${file} · ${term}`).not.toContain(term);
      }
    }
  });

  it("los motivos se traducen en las cuatro superficies de producto", () => {
    for (const file of [
      "operativa-dictamen.tsx",
      "../research/asesor-opiniones-panel.tsx",
      "../auto-monitor/estudio-daily-ops-panel.tsx",
      "../instruments/instrument-dictamen-evolution.tsx",
    ]) {
      const source = readFileSync(resolve(__dirname, file), "utf8");
      expect(source, file).toMatch(/marketStanceLabel|marketStanceLabelFromKey/);
    }
  });

  it("ninguna superficie vuelve a pintar el mapa interno de canales", () => {
    const source = readFileSync(
      resolve(__dirname, "../research/asesor-opiniones-panel.tsx"),
      "utf8",
    );
    expect(source).not.toContain("§5.2");
    expect(source).not.toContain("opinion-channel-map`");
    // Cabecera de tabla: «Stance» era jerga interna; ahora «Recomendación».
    expect(source).not.toMatch(/>\s*Stance\s*</);
  });
});
