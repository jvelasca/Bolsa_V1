import type { ChartDrawing } from "@bolsa/shared";
import {
  CHART_DRAWING_TYPE_LABELS,
  DEFAULT_DRAWING_TEMPLATES,
  drawingHasLinkedOrder,
} from "@bolsa/shared";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { ChartDrawingPropertiesPanel } from "@/features/charts/chart-drawing-properties-panel";

interface ChartDrawingEditPopoverProps {
  chartId: string;
  drawing: ChartDrawing;
  className?: string;
  onClose: () => void;
}

export function ChartDrawingEditPopover({
  chartId,
  drawing,
  className,
  onClose,
}: ChartDrawingEditPopoverProps) {
  const templates = useWorkspaceStore(
    (s) => s.workspace.drawingTemplates ?? DEFAULT_DRAWING_TEMPLATES,
  );
  const updateDrawing = useWorkspaceStore((s) => s.updateChartDrawing);
  const removeDrawing = useWorkspaceStore((s) => s.removeChartDrawing);
  const setDrawingEditorOpen = useWorkspaceStore((s) => s.setDrawingEditorOpen);
  const applyDrawingTemplate = useWorkspaceStore((s) => s.applyDrawingTemplate);

  const close = () => {
    setDrawingEditorOpen(null);
    onClose();
  };

  return (
    <div
      className={cn(
        "absolute left-3 top-14 z-20 w-64 rounded-md border border-border bg-card p-3 text-sm shadow-lg",
        className,
      )}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p className="font-medium leading-tight">
            {CHART_DRAWING_TYPE_LABELS[drawing.type] ?? drawing.type}
          </p>
          <p className="text-[10px] text-muted-foreground">
            Doble clic · 4 pestañas
          </p>
        </div>
        <button
          type="button"
          className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          onClick={close}
          aria-label="Cerrar editor"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <ChartDrawingPropertiesPanel
        mode="instance"
        drawing={drawing}
        templates={templates}
        compact
        initialTab={drawing.type === "text-label" ? "text" : "style"}
        onUpdateDrawing={(patch) => updateDrawing(drawing.id, patch, chartId)}
        onApplyTemplate={(templateId) =>
          applyDrawingTemplate(drawing.id, templateId, chartId)
        }
      />

      <button
        type="button"
        className="mt-3 w-full rounded border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
        onClick={() => {
          if (
            drawingHasLinkedOrder(drawing) &&
            !window.confirm(
              "Este dibujo tiene una orden asociada. ¿Eliminar el dibujo de todos modos?",
            )
          ) {
            return;
          }
          removeDrawing(drawing.id, chartId);
          close();
        }}
      >
        Eliminar
      </button>
    </div>
  );
}
