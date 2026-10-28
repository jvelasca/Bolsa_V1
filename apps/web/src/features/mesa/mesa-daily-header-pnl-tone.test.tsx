/**
 * P2-01 / I-03 — la cabecera de Mesa no colorea un P&L que no se ha medido.
 *
 * Falsable: con `(unrealizedPnl ?? 0) >= 0` el caso `null` sale verde y esta
 * prueba falla.
 */
import { cleanup, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { MesaDailyHeader } from "@/features/mesa/mesa-daily-header";

afterEach(() => cleanup());

function renderHeader(unrealizedPnl: number | null) {
  return render(
    <MemoryRouter>
      <MesaDailyHeader
        cash={1000}
        equity={5000}
        unrealizedPnl={unrealizedPnl}
        positionsCount={2}
        alertCount={0}
      />
    </MemoryRouter>,
  );
}

describe("MesaDailyHeader · tono del P&L (P2-01)", () => {
  it("sin medición declara el hueco y no se pinta como ganancia", () => {
    const { container } = renderHeader(null);
    const node = container.querySelector('[data-tone="neutral"]');
    expect(node).not.toBeNull();
    expect(node?.textContent).toBe("Sin dato todavía");
    expect(container.querySelector('[data-tone="positive"]')).toBeNull();
    expect(container.innerHTML).not.toContain("text-emerald");
  });

  it("un cero medido es plano, no ganancia", () => {
    const { container } = renderHeader(0);
    expect(container.querySelector('[data-tone="neutral"]')).not.toBeNull();
    expect(container.querySelector('[data-tone="positive"]')).toBeNull();
  });

  it("un valor medido positivo sí se afirma", () => {
    const { container } = renderHeader(120);
    const node = container.querySelector('[data-tone="positive"]');
    expect(node).not.toBeNull();
    expect(node?.textContent).toBe("120.00");
  });
});
