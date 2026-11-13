import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { computeMarketStructure, type OhlcvBarDto } from "@bolsa/shared";
import {
  MarketStructureReadoutView,
  describeStudyStrength,
} from "@/features/market-structure/market-structure-readout";

const START = Date.UTC(2026, 0, 1);
const DAY = 86_400_000;

function zigzag(points: readonly number[], legBars = 10): OhlcvBarDto[] {
  const bars: OhlcvBarDto[] = [];
  let index = 0;
  const push = (price: number) => {
    bars.push({
      timestamp: new Date(START + index * DAY).toISOString(),
      open: price,
      high: price + 0.15,
      low: price - 0.15,
      close: price,
      volume: 1_000,
      adjClose: null,
      source: "yahoo",
    });
    index += 1;
  };
  for (let p = 0; p < points.length - 1; p += 1) {
    const from = points[p]!;
    const to = points[p + 1]!;
    for (let k = 0; k < legBars; k += 1) {
      push(from + ((to - from) * k) / legBars);
    }
  }
  push(points[points.length - 1]!);
  return bars;
}

const ascendingBars = zigzag([
  11.5, 10.0, 11.8, 10.2, 12.1, 10.4, 12.4, 10.6, 12.6,
]);

afterEach(() => {
  cleanup();
});

describe("describeStudyStrength", () => {
  it("declara la fuerza del estudio en su escala", () => {
    expect(
      describeStudyStrength({ value: 6.2, max: 10, band: "Fuerte" }),
    ).toEqual({
      measured: true,
      text: "Fuerza del estudio: 6,2 / 10 · Fuerte",
    });
  });

  it("usa ADX/DI cuando son el único dato disponible", () => {
    expect(
      describeStudyStrength({ adx: 27.4, diPlus: 18, diMinus: 22.2 }),
    ).toEqual({
      measured: true,
      text: "Fuerza del estudio: ADX 27,4 · +DI 18 · −DI 22,2",
    });
  });

  it("sin dato declara el hueco, nunca un cero", () => {
    expect(describeStudyStrength(null)).toEqual({
      measured: false,
      text: "Sin dato de fuerza",
    });
    expect(describeStudyStrength({ value: null, adx: null })).toEqual({
      measured: false,
      text: "Sin dato de fuerza",
    });
  });
});

describe("MarketStructureReadoutView", () => {
  it("emite el título como h2, sin saltar a h3 bajo el h1 de la ruta", () => {
    const { container } = render(
      <MarketStructureReadoutView bars={ascendingBars} timeframe="1d" />,
    );
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /Estructura y niveles calculados/i,
      }),
    ).toBeTruthy();
    expect(screen.queryAllByRole("heading", { level: 3 })).toHaveLength(0);
    expect(container.querySelector("h3")).toBeNull();
  });

  it("con showHeading=false deja el título en texto solo para lectores", () => {
    const { container } = render(
      <MarketStructureReadoutView
        bars={ascendingBars}
        timeframe="1d"
        showHeading={false}
      />,
    );
    expect(screen.queryAllByRole("heading")).toHaveLength(0);
    expect(
      container.querySelector('[data-testid="market-structure-readout"]')
        ?.getAttribute("aria-label"),
    ).toBe("Estructura y niveles calculados");
  });

  it("declara histórico insuficiente sin inventar niveles", () => {
    const { container } = render(
      <MarketStructureReadoutView
        bars={ascendingBars.slice(0, 20)}
        timeframe="1d"
      />,
    );
    expect(screen.getByTestId("market-structure-gap").textContent).toBe(
      "Histórico insuficiente: 20 velas (mínimo 80)",
    );
    expect(screen.queryAllByTestId("market-structure-level")).toHaveLength(0);
    expect(
      container
        .querySelector('[data-testid="market-structure-readout"]')
        ?.getAttribute("data-status"),
    ).toBe("insufficient_history");
  });

  it("declara los no fiables con su motivo, sin dibujarlos", () => {
    render(<MarketStructureReadoutView bars={ascendingBars} timeframe="1d" />);
    const rows = screen.getAllByTestId("market-structure-level");
    const failing = rows.filter((row) => row.dataset.state !== "detectado");
    expect(failing.length).toBeGreaterThan(0);
    expect(failing[0]!.textContent).toContain("No fiable");
    expect(failing[0]!.textContent).toMatch(
      /Un solo toque|Dos toques sin toque reciente|Absorbido por un nivel más fuerte/,
    );
    const drawable = rows.filter((row) => row.dataset.state === "detectado");
    expect(drawable.length).toBeGreaterThan(0);
  });

  it("la estructura de pivotes y la fuerza del estudio van en líneas separadas", () => {
    const { container } = render(
      <MarketStructureReadoutView
        bars={ascendingBars}
        timeframe="1d"
        studyStrength={{ adx: 27.4, diPlus: 18, diMinus: 22.2 }}
      />,
    );
    expect(
      container
        .querySelector('[data-testid="market-structure-readout"]')
        ?.getAttribute("data-structure"),
    ).toBe("ascendente");
    expect(screen.getByTestId("market-structure-strength").textContent).toBe(
      "Fuerza del estudio: ADX 27,4 · +DI 18 · −DI 22,2",
    );
    expect(container.textContent).toContain("Estructura ascendente");
    expect(container.textContent?.toLowerCase()).not.toContain("lateral");
  });

  it("sin dato de fuerza lo declara y no lo confunde con la estructura", () => {
    render(<MarketStructureReadoutView bars={ascendingBars} timeframe="1d" />);
    const strength = screen.getByTestId("market-structure-strength");
    expect(strength.textContent).toBe("Sin dato de fuerza");
    expect(strength.getAttribute("data-measured")).toBe("false");
  });

  it("la procedencia declara ventana, método, firma y pivotes", () => {
    const { container } = render(
      <MarketStructureReadoutView bars={ascendingBars} timeframe="1d" />,
    );
    expect(screen.getByTestId("market-structure-provenance-toggle").textContent).toBe(
      "Ver procedencia",
    );
    const text = container.textContent ?? "";
    expect(text).toContain("swing-atr-v1 v1");
    expect(text).toContain("Ventana ");
    expect(text).toContain("último toque");
  });

  it("declara la coincidencia con el plan sin cederle la autoridad", () => {
    const result = computeMarketStructure({ bars: ascendingBars, timeframe: "1d" });
    const detectado = result.supports.find((level) => level.state === "detectado");
    expect(detectado).toBeTruthy();
    render(
      <MarketStructureReadoutView
        bars={ascendingBars}
        timeframe="1d"
        planLevels={[{ price: detectado!.price, title: "Entrada" }]}
      />,
    );
    expect(screen.getAllByTestId("market-structure-level")[0]!.textContent).toContain(
      "manda el nivel operativo",
    );
  });

  it("no pinta ninguna clave interna en crudo", () => {
    const { container } = render(
      <MarketStructureReadoutView bars={ascendingBars} timeframe="1d" />,
    );
    const text = container.textContent ?? "";
    expect(text).not.toContain("no_fiable");
    expect(text).not.toContain("un_solo_toque");
    expect(text).not.toContain("sin_toque_reciente");
  });
});
