/**
 * Sección colapsable del panel DECISIÓN: el alto fijo y el asa de
 * redimensionar solo existen en el dock normal. Maximizada, el panel entero
 * desplaza y la sección crece con su contenido.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { TradingOperativaSection } from "@/features/trading/trading-operativa-section";
import {
  DEFAULT_OPERATIVA_SECTION_HEIGHTS,
  useTradingLayoutStore,
} from "@/stores/trading-layout-store";

function renderSection() {
  return render(
    <TradingOperativaSection sectionId="evidencia" title="Evidencia">
      <p>evidencia</p>
    </TradingOperativaSection>,
  );
}

beforeEach(() => {
  useTradingLayoutStore.setState({
    operativaMaximized: false,
    operativaSections: {
      lab: true,
      mandato: true,
      evidencia: true,
      resultados: true,
      auto: true,
    },
    operativaSectionHeights: { ...DEFAULT_OPERATIVA_SECTION_HEIGHTS },
  });
});

afterEach(() => cleanup());

describe("TradingOperativaSection — dock normal", () => {
  it("mantiene el alto fijo y el asa de redimensionar", () => {
    const { container } = renderSection();

    const body = container.querySelector('[data-maximized="false"]');
    expect(body).toBeTruthy();
    expect((body as HTMLElement).style.height).toBe(
      `${DEFAULT_OPERATIVA_SECTION_HEIGHTS.evidencia}px`,
    );
    expect(
      screen
        .getByTestId("operativa-section-evidencia")
        .querySelector('[role="separator"]'),
    ).toBeTruthy();
  });
});

describe("TradingOperativaSection — DECISIÓN maximizada", () => {
  it("crece con el contenido y oculta el asa", () => {
    useTradingLayoutStore.setState({ operativaMaximized: true });
    const { container } = renderSection();

    const body = container.querySelector('[data-maximized="true"]');
    expect(body).toBeTruthy();
    expect((body as HTMLElement).style.height).toBe("auto");
    expect(
      screen
        .getByTestId("operativa-section-evidencia")
        .querySelector('[role="separator"]'),
    ).toBeNull();
  });
});
