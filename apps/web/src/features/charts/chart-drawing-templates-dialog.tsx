import { useMemo, useState } from "react";
import type { ChartDrawingTemplate } from "@bolsa/shared";
import {
  CHART_DRAWING_TYPE_LABELS,
  TEMPLATE_ASSIGNABLE_TOOLS,
  drawingTypeForTool,
  templateMatchesDrawingType,
} from "@bolsa/shared";
import { Copy, Plus, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { ChartDrawingPropertiesPanel } from "@/features/charts/chart-drawing-properties-panel";
import { DRAWING_TOOL_CATALOG } from "@/features/charts/chart-drawing-tools";

export function ChartDrawingTemplatesDialog() {
  const open = useUiStore((s) => s.drawingTemplatesOpen);
  const close = useUiStore((s) => s.closeDrawingTemplates);
  const tool = useUiStore((s) => s.chartDrawTool);

  const templates = useWorkspaceStore(
    (s) => s.workspace.drawingTemplates ?? [],
  );
  const activeByTool = useWorkspaceStore(
    (s) => s.workspace.activeDrawingTemplateByTool ?? {},
  );
  const addTemplate = useWorkspaceStore((s) => s.addDrawingTemplate);
  const updateTemplate = useWorkspaceStore((s) => s.updateDrawingTemplate);
  const removeTemplate = useWorkspaceStore((s) => s.removeDrawingTemplate);
  const duplicateTemplate = useWorkspaceStore(
    (s) => s.duplicateDrawingTemplate,
  );
  const setActiveTemplateForTool = useWorkspaceStore(
    (s) => s.setActiveDrawingTemplateForTool,
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected =
    templates.find((t) => t.id === selectedId) ?? templates[0] ?? null;

  const toolLabel = useMemo(() => {
    const def = DRAWING_TOOL_CATALOG.find((item) => item.id === tool);
    return def?.label ?? tool;
  }, [tool]);

  const activeTemplateId = TEMPLATE_ASSIGNABLE_TOOLS.includes(tool)
    ? activeByTool[tool]
    : undefined;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-card shadow-xl"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold">Plantillas gráficas</h2>
            <p className="text-xs text-muted-foreground">
              Estilo XTB: define estilo, texto, coordenadas y visibilidad por
              plantilla
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            className="rounded p-1 hover:bg-accent"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex min-h-0 flex-1">
          <aside className="flex w-44 shrink-0 flex-col border-r border-border">
            <div className="border-b border-border p-2">
              <button
                type="button"
                className="flex w-full items-center justify-center gap-1 rounded border border-dashed border-border px-2 py-1.5 text-xs hover:bg-accent"
                onClick={() => {
                  const created = addTemplate();
                  setSelectedId(created.id);
                }}
              >
                <Plus className="h-3.5 w-3.5" />
                Nueva
              </button>
            </div>
            <ul className="min-h-0 flex-1 overflow-auto p-1">
              {templates.map((template) => (
                <li key={template.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(template.id)}
                    className={cn(
                      "w-full rounded px-2 py-1.5 text-left text-xs hover:bg-accent",
                      selected?.id === template.id && "bg-accent text-primary",
                    )}
                  >
                    <span
                      className="mr-1.5 inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: template.style.color }}
                    />
                    {template.name}
                    {template.builtin && (
                      <span className="ml-1 text-[9px] text-muted-foreground">
                        · sistema
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <div className="flex min-h-0 min-w-0 flex-1 flex-col p-4">
            {selected ? (
              <>
                <div className="mb-3 flex items-center gap-2">
                  <input
                    className="flex-1 rounded border border-border bg-background px-2 py-1 text-sm font-medium"
                    value={selected.name}
                    disabled={selected.builtin}
                    onChange={(e) =>
                      updateTemplate(selected.id, {
                        name: e.target.value.trim() || selected.name,
                      })
                    }
                  />
                  <button
                    type="button"
                    title="Duplicar"
                    className="rounded p-1.5 hover:bg-accent"
                    onClick={() => {
                      const copy = duplicateTemplate(selected.id);
                      if (copy) setSelectedId(copy.id);
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  {!selected.builtin && (
                    <button
                      type="button"
                      title="Eliminar"
                      className="rounded p-1.5 text-destructive hover:bg-destructive/10"
                      onClick={() => {
                        if (
                          !window.confirm(
                            `¿Eliminar plantilla "${selected.name}"?`,
                          )
                        )
                          return;
                        removeTemplate(selected.id);
                        setSelectedId(null);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <label className="mb-3 flex flex-col gap-1 text-xs">
                  <span className="text-muted-foreground">Tipos de objeto</span>
                  <select
                    multiple
                    className="h-20 rounded border border-border bg-background px-2 py-1"
                    value={selected.drawingTypes}
                    disabled={selected.builtin}
                    onChange={(e) => {
                      const drawingTypes = Array.from(
                        e.target.selectedOptions,
                      ).map(
                        (opt) => opt.value,
                      ) as ChartDrawingTemplate["drawingTypes"];
                      updateTemplate(selected.id, { drawingTypes });
                    }}
                  >
                    {Object.entries(CHART_DRAWING_TYPE_LABELS).map(
                      ([type, label]) => (
                        <option key={type} value={type}>
                          {label}
                        </option>
                      ),
                    )}
                  </select>
                  <span className="text-[10px] text-muted-foreground">
                    Vacío = todos los tipos. Ctrl+clic para varios.
                  </span>
                </label>

                <ChartDrawingPropertiesPanel
                  mode="template"
                  template={selected}
                  onUpdateTemplate={(id, patch) => updateTemplate(id, patch)}
                />
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Selecciona o crea una plantilla.
              </p>
            )}
          </div>
        </div>

        {TEMPLATE_ASSIGNABLE_TOOLS.includes(tool) && (
          <footer className="border-t border-border px-4 py-3">
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">
                Plantilla activa para «{toolLabel}»
              </span>
              <select
                className="rounded border border-border bg-background px-2 py-1.5"
                value={activeTemplateId ?? ""}
                onChange={(e) =>
                  setActiveTemplateForTool(tool, e.target.value || null)
                }
              >
                <option value="">Por defecto (sin plantilla)</option>
                {templates
                  .filter((t) => {
                    const dt = drawingTypeForTool(tool);
                    return dt ? templateMatchesDrawingType(t, dt) : true;
                  })
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
              </select>
            </label>
          </footer>
        )}
      </div>
    </div>
  );
}
