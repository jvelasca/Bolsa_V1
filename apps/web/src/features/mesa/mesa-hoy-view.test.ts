import { describe, expect, it } from "vitest";
import { HOY_VIEW } from "@/features/confirm/daily-nav";
import {
  HOY_DETAIL_ITEMS,
  HOY_INBOX_BLOCKS,
  parseHoyView,
} from "@/features/mesa/mesa-hoy-view";

describe("parseHoyView", () => {
  it("defaults to resumen", () => {
    expect(parseHoyView(null, null)).toBe(HOY_VIEW.resumen);
  });

  it("honors view= query", () => {
    expect(parseHoyView("oportunidades", null)).toBe(HOY_VIEW.oportunidades);
    expect(parseHoyView("decisiones", null)).toBe(HOY_VIEW.decisiones);
    expect(parseHoyView("journal", null)).toBe(HOY_VIEW.journal);
    expect(parseHoyView("posiciones", null)).toBe(HOY_VIEW.posiciones);
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

  it("V1.23 — confirmar is not a Hoy view (firma = drawer + /confirm)", () => {
    expect(Object.values(HOY_VIEW)).not.toContain("confirmar");
    expect(parseHoyView("confirmar", null)).toBe(HOY_VIEW.resumen);
  });
});

describe("Hoy Daily Desk chrome (V1.55)", () => {
  it("lists five §B.7 inbox cubes", () => {
    expect(HOY_INBOX_BLOCKS.map((b) => b.id)).toEqual([
      "requiere_accion",
      "proteger",
      "posiciones",
      "oportunidades",
      "no_operar",
    ]);
    expect(HOY_INBOX_BLOCKS.map((b) => b.title)).toEqual([
      "Requiere acción",
      "Proteger",
      "Posiciones",
      "Oportunidades",
      "No operar",
    ]);
  });

  it("keeps Ranking / Libro / Decisiones / Consola behind Ver detalles (not a 5th cube)", () => {
    const byId = new Map(HOY_DETAIL_ITEMS.map((i) => [i.id, i.href]));
    expect(byId.get("oportunidades")).toBe("/mesa?view=oportunidades");
    expect(byId.get("decisiones")).toBe("/mesa?view=decisiones");
    expect(byId.get("journal")).toBe("/mesa?view=journal");
    expect(byId.get("posiciones")).toBe("/mesa?view=posiciones");
    expect(byId.get("consola")).toBe("/operational-console");
    expect(HOY_INBOX_BLOCKS).toHaveLength(5);
  });

  it("does not offer Confirmar as a detail entry", () => {
    const blob = HOY_DETAIL_ITEMS.map((i) => `${i.label} ${i.href}`).join(" ");
    expect(blob).not.toMatch(/confirmar/i);
    expect(blob).not.toMatch(/view=confirmar/);
  });
});
