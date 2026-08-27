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
    expect(html).toContain("3");
    expect(html).toContain("180");
    expect(html).toContain("177 sin propose reciente");
    expect(html).not.toMatch(/view=cobertura/);
  });

  it("handles empty Estudio", () => {
    const html = renderToStaticMarkup(
      createElement(MesaCoberturaKpi, { frescos: 0, universeCount: 0 }),
    );
    expect(html).toContain("Añade valores a Estudio");
  });
});
