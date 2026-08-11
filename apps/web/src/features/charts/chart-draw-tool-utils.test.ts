import { describe, expect, it } from "vitest";

import {
  blocksChartPointerPan,
  shouldCaptureDrawingPointer,
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
});
