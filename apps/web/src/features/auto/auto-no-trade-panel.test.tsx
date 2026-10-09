/**
 * P4 — render del panel «Por qué AUTO no operó».
 *
 * El componente presentacional pinta el read-model tal cual: dos capas rotuladas, seis causas
 * con su estado tri-valente y la evidencia enlazada al registro que la demuestra. No se
 * recalcula nada, así que los tests usan el constructor puro para preparar el modelo.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AutoNoTradeExplanationView } from "@/features/auto/auto-no-trade-panel";
import { buildAutoNoTradeExplanation } from "@/features/auto/auto-no-trade-explanation";

afterEach(cleanup);

function renderView(
  explanation: ReturnType<typeof buildAutoNoTradeExplanation>,
) {
  return render(
    <MemoryRouter>
      <AutoNoTradeExplanationView explanation={explanation} />
    </MemoryRouter>,
  );
}

describe("AutoNoTradeExplanationView", () => {
  it("sin datos pinta las seis causas y ninguna se afirma", () => {
    renderView(
      buildAutoNoTradeExplanation({ day: null, discovery: null, engine: null }),
    );
    const rows = screen.getAllByTestId("auto-no-trade-row");
    expect(rows).toHaveLength(6);
    expect(rows.every((row) => row.dataset.status === "unknown")).toBe(true);
    expect(screen.getAllByTestId("auto-no-trade-row-status")).toHaveLength(6);
    expect(
      screen.getAllByText("Sin dato todavía").length,
    ).toBeGreaterThanOrEqual(6);
  });

  it("declara dos capas rotuladas", () => {
    renderView(
      buildAutoNoTradeExplanation({ day: null, discovery: null, engine: null }),
    );
    const layers = screen.getAllByTestId("auto-no-trade-layer");
    expect(layers).toHaveLength(2);
    expect(layers[0]?.dataset.layer).toBe("discovery");
    expect(layers[1]?.dataset.layer).toBe("engine");
    expect(screen.getByText("Cadena del motor AUTO")).toBeTruthy();
  });

  it("una causa declarada enlaza con la operación que la demuestra", () => {
    renderView(
      buildAutoNoTradeExplanation({
        day: "2026-10-09",
        discovery: null,
        engine: {
          loaded: true,
          cycles: [
            {
              id: "cyc-9",
              closed: null,
              closedMeasurement: "COMPLETE",
              resultClosedAt: null,
              steps: [
                { id: "ORDER", state: "reached", at: "2026-10-09T10:00:00Z" },
                { id: "FILL", state: "pending", at: "2026-10-09T10:05:00Z" },
              ],
            },
          ],
        },
      }),
    );
    const row = screen
      .getAllByTestId("auto-no-trade-row")
      .find((item) => item.dataset.cause === "order_without_fill");
    expect(row?.dataset.status).toBe("occurred");
    const link = within(row!).getByTestId("auto-no-trade-evidence-link");
    expect(link.getAttribute("href")).toBe("/auto/operar/operacion/cyc-9");
  });

  it("traduce los motivos y no filtra enums crudos", () => {
    renderView(
      buildAutoNoTradeExplanation({
        day: null,
        discovery: {
          loaded: true,
          estudioStatus: "ok",
          autoDesk: {
            entry: {
              status: "skipped",
              proposed: 1,
              executed: 0,
              skipped: [{ symbol: "AAA", reasonCode: "ENTRY_RISK_LIMIT" }],
            },
          },
        },
        engine: null,
      }),
    );
    expect(screen.getByText(/Límite de riesgo alcanzado/)).toBeTruthy();
    expect(screen.queryByText(/ENTRY_RISK_LIMIT/)).toBeNull();
  });
});
