/**
 * Activa un preset S/R: herramienta hline + color + etiqueta pendiente.
 */
import type { ChartDrawTool } from "@bolsa/shared";
import {
  getSrPreset,
  type SrPresetId,
} from "@/features/charts/chart-sr-presets";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

export function applySrPreset(id: SrPresetId): void {
  const preset = getSrPreset(id);
  useUiStore.getState().setChartDrawTool(preset.tool);
  useUiStore.getState().setChartDrawPendingLabel(preset.label);
  useWorkspaceStore
    .getState()
    .rememberDrawStyleForTool(preset.tool as ChartDrawTool, {
      color: preset.color,
      lineWidth: 2,
      lineStyle: "solid",
    });
}
