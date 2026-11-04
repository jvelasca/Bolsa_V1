import { describe, expect, it } from "vitest";

import {
  blocksChartPointerPan,
  resolveEscapeDrawTool,
  shouldCaptureDrawingPointer,
  shouldExitDrawModeOnEscape,
} from "./chart-draw-tool-utils";

describe("chart-draw-tool-utils", () => {
  it("permite pan en modo select y cross", () => {
    expect(blocksChartPointerPan("select", null)).toBe(false);
    expect(blocksChartPointerPan("cross", null)).toBe(false);
  });

  it("bloquea pan en herramientas de dibujo y regla", () => {
    expect(blocksChartPointerPan("crosshair", null)).toBe(true);
    expect(blocksChartPointerPan("trend-line", null)).toBe(true);
  });

  it("captura puntero solo sobre dibujo en select/cross", () => {
    expect(shouldCaptureDrawingPointer("select", false, false)).toBe(false);
    expect(shouldCaptureDrawingPointer("select", true, false)).toBe(true);
    expect(shouldCaptureDrawingPointer("cross", true, false)).toBe(true);
    expect(shouldCaptureDrawingPointer("trend-line", false, false)).toBe(true);
  });

  it("Escape sale de las herramientas de dibujo, no de los cursores puros", () => {
    expect(shouldExitDrawModeOnEscape("select")).toBe(false);
    expect(shouldExitDrawModeOnEscape("cross")).toBe(false);
    expect(shouldExitDrawModeOnEscape("dot")).toBe(false);
    expect(shouldExitDrawModeOnEscape("dot-halo")).toBe(false);
    // `arrow` crea flechas fijas: es modo de dibujo, no cursor puro.
    expect(shouldExitDrawModeOnEscape("arrow")).toBe(true);
    expect(shouldExitDrawModeOnEscape("hline")).toBe(true);
    expect(shouldExitDrawModeOnEscape("line")).toBe(true);
    expect(shouldExitDrawModeOnEscape("rectangle")).toBe(true);
    expect(shouldExitDrawModeOnEscape("brush")).toBe(true);
    expect(shouldExitDrawModeOnEscape("text")).toBe(true);
    expect(shouldExitDrawModeOnEscape("crosshair")).toBe(true);
  });

  it("Escape vuelve al cursor que se estaba usando (no al puntero)", () => {
    expect(
      resolveEscapeDrawTool({
        currentTool: "hline",
        lastDrawToolByGroup: { cursor: "cross" },
      }),
    ).toBe("cross");
    expect(
      resolveEscapeDrawTool({
        currentTool: "crosshair",
        lastDrawToolByGroup: { cursor: "dot" },
      }),
    ).toBe("dot");
  });

  it("Escape cae al puntero si no hay cursor recordado válido", () => {
    expect(
      resolveEscapeDrawTool({ currentTool: "line", lastDrawToolByGroup: {} }),
    ).toBe("select");
    expect(
      resolveEscapeDrawTool({
        currentTool: "line",
        lastDrawToolByGroup: { cursor: "hline" },
      }),
    ).toBe("select");
    // `arrow` no es destino válido: dejaría al usuario en un modo que dibuja.
    expect(
      resolveEscapeDrawTool({
        currentTool: "line",
        lastDrawToolByGroup: { cursor: "arrow" },
      }),
    ).toBe("select");
  });

  it("Escape no cambia el cursor actual", () => {
    expect(
      resolveEscapeDrawTool({
        currentTool: "cross",
        lastDrawToolByGroup: { cursor: "select" },
      }),
    ).toBe("cross");
  });
});
