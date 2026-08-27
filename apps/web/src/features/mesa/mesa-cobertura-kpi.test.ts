import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { MesaCoberturaKpi } from "@/features/mesa/mesa-cobertura-kpi";

describe("MesaCoberturaKpi", () => {
  it("renders frescos/N without inventing a cobertura tab", () => {
    const html = renderToStaticMarkup(
      createElement(MesaCoberturaKpi, { frescos: 3, universeCount: 180 }),
    );
    expect(html).toContain('data-testid="mesa-cobertura-kpi"');
    expect(html).toContain('data-frescos="3"');
    expect(html).toContain('data-universe="180"');
    expect(html).toContain('data-estudio-status="ok"');
    expect(html).toContain("3");
    expect(html).toContain("180");
    expect(html).toContain("177 sin propose reciente");
    expect(html).not.toMatch(/view=cobertura/);
  });

  it("handles empty Estudio (≠ unavailable)", () => {
    const html = renderToStaticMarkup(
      createElement(MesaCoberturaKpi, {
        frescos: 0,
        universeCount: 0,
        estudioStatus: "empty",
      }),
    );
    expect(html).toContain('data-estudio-status="empty"');
    expect(html).toContain("Universo vacío");
    expect(html).toMatch(/añade valores/i);
    expect(html).not.toContain("No disponible");
  });

  it("unavailable does not look like empty 0 candidates", () => {
    const html = renderToStaticMarkup(
      createElement(MesaCoberturaKpi, {
        frescos: 0,
        universeCount: 0,
        estudioStatus: "unavailable",
      }),
    );
    expect(html).toContain('data-estudio-status="unavailable"');
    expect(html).toContain("No disponible");
    expect(html).not.toContain("Universo vacío");
    expect(html).not.toContain("Añade valores");
  });
});
