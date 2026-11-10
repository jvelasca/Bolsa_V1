/**
 * Sección colapsable del panel DECISIÓN: el alto fijo y el asa de
 * redimensionar solo existen en el dock normal. Maximizada, el panel entero
 * desplaza y la sección crece con su contenido.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { TradingOperativaSection } from "@/features/trading/trading-operativa-section";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";

function renderSection() {
  return render(
    <TradingOperativaSection sectionId="recommendation" title="¿Por qué?">
      <p>evidencia</p>
    </TradingOperativaSection>,
  );
}

beforeEach(() => {
  useTradingLayoutStore.setState({
    operativaMaximized: false,
    operativaSections: { recommendation: true, info: true, config: true },
    operativaSectionHeights: {
      recommendation: 320,
      info: 200,
      config: 180,
    },
  });
});

afterEach(() => cleanup());

describe("TradingOperativaSection — dock normal", () => {
  it("mantiene el alto fijo y el asa de redimensionar", () => {
    const { container } = renderSection();

    const body = container.querySelector('[data-maximized="false"]');
    expect(body).toBeTruthy();
    expect((body as HTMLElement).style.height).toBe("320px");
    expect(
      screen
        .getByTestId("operativa-section-recommendation")
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
        .getByTestId("operativa-section-recommendation")
        .querySelector('[role="separator"]'),
    ).toBeNull();
  });
});
