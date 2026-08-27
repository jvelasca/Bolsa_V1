import { describe, expect, it } from "vitest";
import { HOY_VIEW } from "@/features/confirm/daily-nav";
import { parseHoyView } from "@/features/mesa/mesa-hoy-view";

describe("parseHoyView", () => {
  it("defaults to resumen", () => {
    expect(parseHoyView(null, null)).toBe(HOY_VIEW.resumen);
  });

  it("honors view= query", () => {
    expect(parseHoyView("oportunidades", null)).toBe(HOY_VIEW.oportunidades);
    expect(parseHoyView("decisiones", null)).toBe(HOY_VIEW.decisiones);
    expect(parseHoyView("journal", null)).toBe(HOY_VIEW.journal);
  });

  it("maps legacy focus=spine|libro", () => {
    expect(parseHoyView(null, "spine")).toBe(HOY_VIEW.decisiones);
    expect(parseHoyView(null, "libro")).toBe(HOY_VIEW.posiciones);
  });

  it("prefers view over focus", () => {
    expect(parseHoyView("oportunidades", "spine")).toBe(HOY_VIEW.oportunidades);
  });

  it("does not open a cobertura door (epic posterior)", () => {
    expect(parseHoyView("cobertura", null)).toBe(HOY_VIEW.resumen);
    expect(Object.values(HOY_VIEW)).not.toContain("cobertura");
  });
});
