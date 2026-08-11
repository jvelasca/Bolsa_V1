import { describe, expect, it } from "vitest";
import {
  brushStrokeDrawTool,
  drawToolForDrawing,
  resolveDrawToolStyle,
} from "@bolsa/shared";

describe("chart-draw-style-memory", () => {
  it("distingue resaltador y pincel en trazos brush-stroke", () => {
    expect(
      brushStrokeDrawTool({
        type: "brush-stroke",
        lineWidth: 12,
        strokeOpacity: 0.35,
      }),
    ).toBe("highlighter");
    expect(
      brushStrokeDrawTool({
        type: "brush-stroke",
        lineWidth: 2,
        strokeOpacity: 1,
      }),
    ).toBe("brush");
  });

  it("mapea brush-stroke al tool correcto al recordar estilo", () => {
    expect(
      drawToolForDrawing({
        id: "x",
        type: "brush-stroke",
        points: [],
        color: "#ff0000",
        lineWidth: 12,
        strokeOpacity: 0.2,
      }),
    ).toBe("highlighter");
  });

  it("prioriza memoria manual sobre defaults al resolver estilo", () => {
    const style = resolveDrawToolStyle("highlighter", {
      memory: { color: "#ff00ff", strokeOpacity: 0.5, lineWidth: 16 },
    });
    expect(style.color).toBe("#ff00ff");
    expect(style.strokeOpacity).toBe(0.5);
    expect(style.lineWidth).toBe(16);
  });

  it("usa defaults distintos para brush y highlighter", () => {
    const brush = resolveDrawToolStyle("brush");
    const highlighter = resolveDrawToolStyle("highlighter");
    expect(brush.lineWidth).toBeLessThan(highlighter.lineWidth!);
    expect(brush.strokeOpacity).toBeGreaterThan(highlighter.strokeOpacity!);
  });
});
