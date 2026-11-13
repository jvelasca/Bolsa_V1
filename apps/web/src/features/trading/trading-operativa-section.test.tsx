/**
 * Sección colapsable del panel DECISIÓN: el alto fijo y el asa de
 * redimensionar solo existen en el dock normal. Maximizada, el panel entero
 * desplaza y la sección crece con su contenido.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
      recomendacion: true,
      fundamental: true,
      tecnico: true,
      seguimientoDia: true,
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

describe("TradingOperativaSection — grupo del dock", () => {
  it("con autoHeight crece con su contenido y no ofrece asa", () => {
    const { container } = render(
      <TradingOperativaSection
        sectionId="recomendacion"
        title="Recomendación"
        autoHeight
        size="md"
      >
        <p>recomendación</p>
      </TradingOperativaSection>,
    );

    const section = screen.getByTestId("operativa-section-recomendacion");
    expect(section.dataset.variant).toBe("group");
    expect(section.querySelector('[role="separator"]')).toBeNull();

    const body = container.querySelector('[data-maximized="true"]');
    expect(body).toBeTruthy();
    expect((body as HTMLElement).style.height).toBe("auto");
  });

  it("la cabecera enlaza su cuerpo con aria-controls y alterna aria-expanded", () => {
    render(
      <TradingOperativaSection
        sectionId="fundamental"
        title="Fundamental"
        autoHeight
        size="md"
      >
        <p>fa</p>
      </TradingOperativaSection>,
    );

    const header = screen
      .getByTestId("operativa-section-fundamental")
      .querySelector("button") as HTMLButtonElement;
    expect(header.getAttribute("aria-expanded")).toBe("true");
    const bodyId = header.getAttribute("aria-controls");
    expect(bodyId).toBeTruthy();
    expect(document.getElementById(bodyId!)).toBeTruthy();

    fireEvent.click(header);
    expect(header.getAttribute("aria-expanded")).toBe("false");
    expect(document.getElementById(bodyId!)).toBeNull();
  });
});
