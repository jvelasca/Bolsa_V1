import type { ChartInspectorBarShortcutId } from "@bolsa/shared";
import type { ChartInspectorNavigateInput } from "@/features/charts/chart-inspector-nav";

export function inspectorBarShortcutNavigate(
  id: ChartInspectorBarShortcutId,
): ChartInspectorNavigateInput {
  switch (id) {
    case "layers":
      return {
        mode: "config",
        configSection: "layers",
        layerSection: "overlay",
      };
    case "series":
      return { mode: "config", configSection: "series" };
    case "objects":
      return { mode: "config", configSection: "objects" };
    case "styles":
      return { mode: "config", configSection: "styles" };
    case "context":
      return { mode: "config", configSection: "context" };
    default:
      return {
        mode: "config",
        configSection: "layers",
        layerSection: "overlay",
      };
  }
}
