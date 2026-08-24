import { describe, expect, it } from "vitest";
import {
  SR_PRESETS,
  getSrPreset,
  isSrHorizontalTool,
} from "@/features/charts/chart-sr-presets";

describe("chart-sr-presets", () => {
  it("defines Soporte and Resistencia on hline with distinct colors", () => {
    expect(SR_PRESETS).toHaveLength(2);
    const support = getSrPreset("support");
    const resistance = getSrPreset("resistance");
    expect(support.tool).toBe("hline");
    expect(resistance.tool).toBe("hline");
    expect(support.label).toBe("Soporte");
    expect(resistance.label).toBe("Resistencia");
    expect(support.color).not.toBe(resistance.color);
  });

  it("recognizes horizontal tools for pending label", () => {
    expect(isSrHorizontalTool("hline")).toBe(true);
    expect(isSrHorizontalTool("hray")).toBe(true);
    expect(isSrHorizontalTool("line")).toBe(false);
  });
});
