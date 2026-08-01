import { useMemo } from 'react';
import type { ChartDrawTool, ChartLineStyle } from '@bolsa/shared';
import {
  DEFAULT_RECT_FILL_OPACITY,
  drawToolStyleFields,
  resolveDrawToolStyle,
  stylePatchFromTemplate,
  templateMatchesDrawingType,
  drawingTypeForTool,
  DEFAULT_DRAWING_TEMPLATES,
} from '@bolsa/shared';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace-store';

export function ChartDrawToolStyleBar({
  tool,
  className,
}: {
  tool: ChartDrawTool;
  className?: string;
}) {
  const rememberDrawStyleForTool = useWorkspaceStore((s) => s.rememberDrawStyleForTool);
  const lastStyleMemory = useWorkspaceStore(
    (s) => s.workspace.chartToolbarGlobal?.lastDrawStyleByTool?.[tool],
  );
  const activeTemplateId = useWorkspaceStore(
    (s) => s.workspace.activeDrawingTemplateByTool?.[tool] ?? null,
  );
  const drawingTemplates = useWorkspaceStore((s) => s.workspace.drawingTemplates);

  const activeTemplatePatch = useMemo(() => {
    if (!activeTemplateId) return null;
    const pool = drawingTemplates?.length ? drawingTemplates : DEFAULT_DRAWING_TEMPLATES;
    const template = pool.find((item) => item.id === activeTemplateId);
    if (!template) return null;
    const drawingType = drawingTypeForTool(tool);
    if (drawingType && !templateMatchesDrawingType(template, drawingType)) return null;
    return stylePatchFromTemplate(template);
  }, [activeTemplateId, drawingTemplates, tool]);

  const style = useMemo(
    () => resolveDrawToolStyle(tool, { memory: lastStyleMemory, templatePatch: activeTemplatePatch }),
    [activeTemplatePatch, lastStyleMemory, tool],
  );

  const fields = drawToolStyleFields(tool);

  const patchStyle = (patch: Parameters<typeof rememberDrawStyleForTool>[1]) => {
    rememberDrawStyleForTool(tool, patch);
  };

  return (
    <div
      className={cn(
        'flex w-44 shrink-0 flex-col gap-2 rounded-lg border border-border bg-card p-2 text-xs shadow-lg',
        className,
      )}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Estilo herramienta
      </p>

      {fields.includes('color') && (
        <label className="flex items-center gap-2">
          <span className="w-12 text-muted-foreground">Color</span>
          <input
            type="color"
            className="h-7 flex-1 cursor-pointer rounded border border-border bg-background"
            value={style.color ?? '#14b8a6'}
            onChange={(e) => patchStyle({ color: e.target.value })}
          />
        </label>
      )}

      {fields.includes('lineWidth') && (
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Grosor</span>
          <input
            type="range"
            min={tool === 'highlighter' ? 4 : 1}
            max={tool === 'highlighter' ? 24 : 4}
            step={tool === 'highlighter' ? 1 : 0.5}
            value={style.lineWidth ?? 1.5}
            onChange={(e) => patchStyle({ lineWidth: Number(e.target.value) })}
          />
        </label>
      )}

      {fields.includes('lineStyle') && (
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Línea</span>
          <select
            className="rounded border border-border bg-background px-2 py-1"
            value={style.lineStyle ?? 'solid'}
            onChange={(e) => patchStyle({ lineStyle: e.target.value as ChartLineStyle })}
          >
            <option value="solid">Sólida</option>
            <option value="dashed">Discontinua</option>
            <option value="dotted">Punteada</option>
          </select>
        </label>
      )}

      {fields.includes('fillOpacity') && (
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Relleno</span>
          <input
            type="range"
            min={0.05}
            max={0.5}
            step={0.01}
            value={style.fillOpacity ?? DEFAULT_RECT_FILL_OPACITY}
            onChange={(e) => patchStyle({ fillOpacity: Number(e.target.value) })}
          />
        </label>
      )}

      {fields.includes('strokeOpacity') && (
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Opacidad</span>
          <input
            type="range"
            min={0.05}
            max={1}
            step={0.01}
            value={style.strokeOpacity ?? 0.35}
            onChange={(e) => patchStyle({ strokeOpacity: Number(e.target.value) })}
          />
        </label>
      )}

      {fields.includes('fontSize') && (
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Texto</span>
          <input
            type="range"
            min={8}
            max={72}
            value={style.fontSize ?? 13}
            onChange={(e) => patchStyle({ fontSize: Number(e.target.value) })}
          />
        </label>
      )}
    </div>
  );
}
