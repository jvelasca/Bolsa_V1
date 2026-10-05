/**
 * AUTO · ANÁLISIS — contrato WAI-ARIA de las sub-pestañas (ADR-044).
 *
 * La pestaña activa vive en `?tab=` (compartible) y el patrón de tabs debe estar
 * completo: `tab` ↔ `tabpanel` enlazados, roving `tabIndex` y flechas/Home/End.
 * Los paneles pesados se mockean para aislar el contrato de navegación.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/features/auto-monitor/dia-d-auto-panel", () => ({
  DiaDAutoPanel: () => <div data-testid="dia-d-stub" />,
}));

vi.mock("@/features/operational-console/auto-evidence-section", () => ({
  OpsAutoEvidenceSection: () => <div data-testid="evidence-stub" />,
}));

import { AutoAnalisisPage } from "@/features/auto/auto-analisis-page";

afterEach(cleanup);

function renderPage(entry = "/auto/analisis") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AutoAnalisisPage />
    </MemoryRouter>,
  );
}

describe("AutoAnalisisPage — tabs ARIA", () => {
  it("enlaza cada tab con su tabpanel y sólo la activa es tabulable", () => {
    renderPage();

    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual([
      "DÍA-D",
      "Evidencia",
      "Estrategias",
      "Investigación",
    ]);

    const active = screen.getByTestId("auto-analisis-tab-dia-d");
    expect(active.getAttribute("aria-selected")).toBe("true");
    expect(active.getAttribute("tabIndex")).toBe("0");
    expect(active.getAttribute("aria-controls")).toBe(
      "auto-analisis-panel-dia-d",
    );

    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("id")).toBe("auto-analisis-panel-dia-d");
    expect(panel.getAttribute("aria-labelledby")).toBe(
      "auto-analisis-tab-dia-d",
    );

    // Las pestañas inactivas no participan del orden de tabulación (roving).
    expect(
      screen
        .getByTestId("auto-analisis-tab-evidencia")
        .getAttribute("tabIndex"),
    ).toBe("-1");
  });

  it("cambia de pestaña con flechas y Home/End", () => {
    renderPage();

    // Estado inicial: DÍA-D. ArrowRight ⇒ Evidencia.
    fireEvent.keyDown(screen.getByTestId("auto-analisis-tab-dia-d"), {
      key: "ArrowRight",
    });
    expect(
      screen
        .getByTestId("auto-analisis-tab-evidencia")
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(screen.getByRole("tabpanel").getAttribute("id")).toBe(
      "auto-analisis-panel-evidencia",
    );

    // End ⇒ última pestaña (Investigación).
    fireEvent.keyDown(screen.getByTestId("auto-analisis-tab-evidencia"), {
      key: "End",
    });
    expect(
      screen
        .getByTestId("auto-analisis-tab-investigacion")
        .getAttribute("aria-selected"),
    ).toBe("true");

    // Home ⇒ primera pestaña (DÍA-D).
    fireEvent.keyDown(screen.getByTestId("auto-analisis-tab-investigacion"), {
      key: "Home",
    });
    expect(
      screen
        .getByTestId("auto-analisis-tab-dia-d")
        .getAttribute("aria-selected"),
    ).toBe("true");
  });

  it("respeta el deep-link ?tab= de la operación canónica", () => {
    renderPage("/auto/analisis?tab=investigacion");
    expect(
      screen
        .getByTestId("auto-analisis-tab-investigacion")
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(screen.getByRole("tabpanel").getAttribute("id")).toBe(
      "auto-analisis-panel-investigacion",
    );
  });
});
