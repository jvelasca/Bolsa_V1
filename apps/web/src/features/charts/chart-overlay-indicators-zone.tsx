import type { ChartIndicatorInstance } from "@bolsa/shared";
import {
  colorForInstance,
  findIndicatorDefinition,
  instanceLabel,
} from "@bolsa/shared";
import { Eye, EyeOff, Settings2, Trash2 } from "lucide-react";

import {
  CHART_BAR_ZONE_CHIP_CLASS,
  CHART_BAR_ZONE_LABEL_CLASS,
  CHART_BAR_ZONE_ROW_CLASS,
  CHART_BAR_ZONE_SCROLL_ROW_CLASS,
} from "@/features/charts/chart-bar-zone-styles";
import { useUiStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";

interface ChartOverlayIndicatorsZoneProps {
  instances: ChartIndicatorInstance[];
  onConfigure: (instanceId: string) => void;
  onToggleHidden: (instanceId: string) => void;
  onDelete: (instanceId: string) => void;
  wrapChips?: boolean;
  className?: string;
}

export function ChartOverlayIndicatorsZone({
  instances,
  onConfigure,
  onToggleHidden,
  onDelete,
  wrapChips = false,
  className,
}: ChartOverlayIndicatorsZoneProps) {
  const selectedId = useUiStore((s) => s.selectedIndicatorInstanceId);
  const setSelectedId = useUiStore((s) => s.setSelectedIndicatorInstanceId);

  if (instances.length === 0) return null;

  return (
    <div
      className={cn(CHART_BAR_ZONE_ROW_CLASS, "min-w-0 flex-1", className)}
      title="Indicadores dibujados sobre el precio de este gráfico. Clic para seleccionar; pulsar y arrastrar en la escala Y derecha ajusta el zoom vertical."
    >
      <span className={CHART_BAR_ZONE_LABEL_CLASS}>
        <span className="chart-overlay-zone-label-full">Sobre gráfico</span>
        <span className="chart-overlay-zone-label-short">S/gráf.</span>
      </span>
      <div
        className={cn(
          wrapChips
            ? "flex min-w-0 flex-1 flex-wrap items-center gap-0.5"
            : CHART_BAR_ZONE_SCROLL_ROW_CLASS,
        )}
      >
        {instances.map((instance, index) => {
          const def = findIndicatorDefinition(instance.definitionId);
          const isSelected = selectedId === instance.instanceId;
          const color = colorForInstance(instance, index);

          return (
            <div
              key={instance.instanceId}
              className={cn(
                "group flex shrink-0 items-center gap-0.5 rounded border px-1 py-0.5",
                isSelected
                  ? "border-primary/60 bg-primary/10"
                  : "border-transparent hover:border-border hover:bg-accent/40",
                !instance.visible && "opacity-50",
              )}
            >
              <button
                type="button"
                className={cn(
                  CHART_BAR_ZONE_CHIP_CLASS,
                  "max-w-[9rem] gap-1 border-0 px-1 py-0",
                )}
                title={`${instanceLabel(instance)} — ${def?.panel === "overlay" ? "Superpuesto al precio" : "Volumen"}. Doble clic para configurar.`}
                onClick={() => setSelectedId(instance.instanceId)}
                onDoubleClick={(event) => {
                  event.preventDefault();
                  onConfigure(instance.instanceId);
                }}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: color }}
                  aria-hidden
                />
                <span className="truncate">{instanceLabel(instance)}</span>
              </button>
              <button
                type="button"
                title="Configurar"
                onClick={() => onConfigure(instance.instanceId)}
                className="rounded p-0.5 text-muted-foreground opacity-0 hover:bg-accent hover:text-foreground group-hover:opacity-100"
              >
                <Settings2 className="h-3 w-3" />
              </button>
              <button
                type="button"
                title={instance.visible ? "Ocultar" : "Mostrar"}
                onClick={() => onToggleHidden(instance.instanceId)}
                className="rounded p-0.5 text-muted-foreground opacity-0 hover:bg-accent hover:text-foreground group-hover:opacity-100"
              >
                {instance.visible ? (
                  <EyeOff className="h-3 w-3" />
                ) : (
                  <Eye className="h-3 w-3" />
                )}
              </button>
              <button
                type="button"
                title="Eliminar del gráfico"
                onClick={() => onDelete(instance.instanceId)}
                className="rounded p-0.5 text-muted-foreground opacity-0 hover:bg-destructive/15 hover:text-destructive group-hover:opacity-100"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          );
        })}
        <button
          type="button"
          className={cn(
            CHART_BAR_ZONE_CHIP_CLASS,
            "shrink-0 border-dashed",
            selectedId == null && "border-primary/50 bg-primary/5",
          )}
          title="Seleccionar eje de precio (pulsar y arrastrar en escala derecha = zoom vertical)"
          onClick={() => setSelectedId(null)}
        >
          Precio
        </button>
      </div>
    </div>
  );
}
