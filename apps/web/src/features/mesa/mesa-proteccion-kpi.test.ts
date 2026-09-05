import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { MesaProteccionKpi } from "@/features/mesa/mesa-proteccion-kpi";

describe("MesaProteccionKpi", () => {
  it("renders protegidas/N", () => {
    const html = renderToStaticMarkup(
      createElement(MesaProteccionKpi, {
        kpi: { protected: 2, open: 5, discrepancies: 0, pct: 40 },
      }),
    );
    expect(html).toContain('data-testid="mesa-proteccion-kpi"');
    expect(html).toContain('data-protected="2"');
    expect(html).toContain('data-open="5"');
    expect(html).toContain("protegidas");
    expect(html).toContain("40%");
    expect(html).not.toContain("disc.");
  });

  it("warns on discrepancies", () => {
    const html = renderToStaticMarkup(
      createElement(MesaProteccionKpi, {
        kpi: { protected: 1, open: 3, discrepancies: 2, pct: 33 },
      }),
    );
    expect(html).toContain('data-discrepancies="2"');
    expect(html).toContain("plan/sugerido");
  });

  it("compact chip", () => {
    const html = renderToStaticMarkup(
      createElement(MesaProteccionKpi, {
        compact: true,
        kpi: { protected: 1, open: 2, discrepancies: 1, pct: 50 },
      }),
    );
    expect(html).toContain("data-compact");
    expect(html).toContain("1 disc.");
  });
});
