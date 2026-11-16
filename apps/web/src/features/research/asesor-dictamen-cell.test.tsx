/**
 * A2 · La celda de Asesor reutiliza el bloque canónico de dictamen.
 *
 * Guardas de la celda: variante `cell`, chips propios, «Midiendo…» ≠ «Sin
 * dictamen», y un IO sin medir no fabrica ★ ni confianza.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { InstrumentDailyOpinionV1 } from "@bolsa/shared";
import { AsesorDictamenCell } from "@/features/research/asesor-dictamen-cell";

afterEach(() => cleanup());

function opinion(
  overrides: Partial<InstrumentDailyOpinionV1> = {},
): InstrumentDailyOpinionV1 {
  return {
    id: "op-1",
    instrumentId: "inst-1",
    asOfBarDate: "2026-11-12",
    stance: "buy",
    dictamenStars: 4,
    ioScore: 85,
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

describe("AsesorDictamenCell", () => {
  it("con dictamen usa la variante cell y pinta los chips del panel", () => {
    render(
      <AsesorDictamenCell
        opinion={opinion({
          stance: "buy",
          ioScore: 85,
          dictamenStars: 4,
          reasons: ["strong_buy_signal", "top_high"],
        })}
        emptyLabel="Sin dictamen"
      >
        <span data-testid="chip-propio">Fundamental en riesgo</span>
      </AsesorDictamenCell>,
    );

    const block = screen.getByTestId("operativa-dictamen");
    expect(block.getAttribute("data-variant")).toBe("cell");
    expect(block.textContent).toContain("Comprar");
    expect(block.textContent).toContain("Confianza 85 / 100");
    expect(block.textContent).toContain("★★★★☆");
    expect(block.textContent).toContain("Señal de compra fuerte");
    expect(block.getAttribute("title")).toContain("Motivos:");
    expect(screen.getByTestId("chip-propio")).toBeInTheDocument();
  });

  it("mientras carga sin opinión dice «Midiendo…», no «Sin dictamen»", () => {
    render(
      <AsesorDictamenCell opinion={null} loading emptyLabel="Sin dictamen" />,
    );
    const cell = screen.getByTestId("asesor-dictamen-cell");
    expect(cell).toHaveTextContent("Midiendo…");
    expect(cell).not.toHaveTextContent("Sin dictamen");
  });

  it("sin opinión ni carga declara el texto honesto", () => {
    render(<AsesorDictamenCell opinion={null} emptyLabel="Sin dictamen" />);
    expect(screen.getByTestId("asesor-dictamen-cell")).toHaveTextContent(
      "Sin dictamen",
    );
  });

  it("un IO sin medir no fabrica ★ ni confianza", () => {
    render(
      <AsesorDictamenCell
        opinion={opinion({
          stance: "hold_watch",
          ioScore: null,
          dictamenStars: 3,
        })}
        emptyLabel="Sin dictamen"
      />,
    );
    const block = screen.getByTestId("operativa-dictamen");
    expect(block.textContent).toContain("Sin medir");
    expect(block.textContent).not.toContain("★★★");
  });
});
