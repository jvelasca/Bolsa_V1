/**
 * Presets de mesa: Soporte / Resistencia (hline + etiqueta + color).
 * No añade ids a ChartDrawTool en shared — reutiliza hline/hray.
 */
import type { ChartDrawTool } from "@bolsa/shared";

export type SrPresetId = "support" | "resistance";

export type SrPreset = {
  id: SrPresetId;
  tool: ChartDrawTool;
  label: string;
  /** Color de línea al dibujar. */
  color: string;
  /** Título corto del botón en el rail. */
  shortLabel: string;
  title: string;
};

export const SR_PRESETS: readonly SrPreset[] = [
  {
    id: "support",
    tool: "hline",
    label: "Soporte",
    color: "#10b981",
    shortLabel: "S",
    title: "Soporte — línea horizontal verde",
  },
  {
    id: "resistance",
    tool: "hline",
    label: "Resistencia",
    color: "#f43f5e",
    shortLabel: "R",
    title: "Resistencia — línea horizontal roja",
  },
] as const;

export function getSrPreset(id: SrPresetId): SrPreset {
  const found = SR_PRESETS.find((p) => p.id === id);
  if (!found) throw new Error(`Unknown SR preset: ${id}`);
  return found;
}

export function isSrHorizontalTool(tool: ChartDrawTool): boolean {
  return tool === "hline" || tool === "hray";
}
