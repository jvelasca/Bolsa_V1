import { useEffect, useState } from "react";
import type { IndicatorTemplate } from "@bolsa/shared";
import { instanceLabel, presetLabel, templateItemLabel } from "@bolsa/shared";
import { findIndicatorPreset } from "@bolsa/shared";
import { Copy, LayoutTemplate, Plus, Save, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";
import { useActiveChartTab, useWorkspaceStore } from "@/stores/workspace-store";
import { requestChartReflow } from "@/features/charts/chart-utils";

export function IndicatorTemplatesDialog() {
  const open = useUiStore((s) => s.indicatorTemplatesOpen);
  const close = useUiStore((s) => s.closeIndicatorTemplates);
  const activeTab = useActiveChartTab();

  const templates = useWorkspaceStore(
    (s) => s.workspace.indicatorTemplates ?? [],
  );
  const presets = useWorkspaceStore((s) => s.workspace.indicatorPresets ?? []);
  const addTemplate = useWorkspaceStore((s) => s.addIndicatorTemplate);
  const updateTemplate = useWorkspaceStore((s) => s.updateIndicatorTemplate);
  const removeTemplate = useWorkspaceStore((s) => s.removeIndicatorTemplate);
  const duplicateTemplate = useWorkspaceStore(
    (s) => s.duplicateIndicatorTemplate,
  );
  const applyTemplate = useWorkspaceStore((s) => s.applyIndicatorTemplate);
  const createFromChart = useWorkspaceStore(
    (s) => s.createIndicatorTemplateFromChart,
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected =
    templates.find((t) => t.id === selectedId) ?? templates[0] ?? null;

  const chartInstances = activeTab?.indicatorInstances ?? [];
  const activeTemplateId = activeTab?.activeIndicatorTemplateId;

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [close, open]);

  if (!open) return null;

  function applyToChart(template: IndicatorTemplate) {
    if (!activeTab) return;
    applyTemplate(template.id, activeTab.id);
    requestChartReflow();
    close();
  }

  function saveFromChart() {
    if (!activeTab || chartInstances.length === 0) return;
    const label = activeTab.label || "Gráfico";
    const created = createFromChart(activeTab.id, `Plantilla ${label}`);
    setSelectedId(created.id);
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        aria-label="Cerrar"
        className="absolute inset-0 bg-black/80 backdrop-blur-[2px]"
        onClick={close}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative z-[101] flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-card text-foreground shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <LayoutTemplate className="h-4 w-4 text-primary" />
              Plantillas de indicadores
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Aplica un conjunto al gráfico de {activeTab?.label ?? "—"} o
              guarda el actual como plantilla
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

        {activeTab && chartInstances.length > 0 && (
          <div className="border-b border-border bg-muted/20 px-4 py-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              En este gráfico ahora
            </p>
            <div className="flex flex-wrap gap-1">
              {chartInstances.map((instance) => (
                <span
                  key={instance.instanceId}
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px]",
                    instance.visible
                      ? "bg-primary/15 text-primary"
                      : "bg-muted text-muted-foreground line-through",
                  )}
                >
                  {instanceLabel(instance)}
                </span>
              ))}
            </div>
            <button
              type="button"
              disabled={!activeTab}
              onClick={saveFromChart}
              className="mt-2 inline-flex items-center gap-1 rounded border border-dashed border-border px-2 py-1 text-xs hover:bg-accent disabled:opacity-40"
            >
              <Save className="h-3.5 w-3.5" />
              Guardar como nueva plantilla
            </button>
          </div>
        )}

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
                Nueva vacía
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
                      activeTemplateId === template.id &&
                        "ring-1 ring-primary/40",
                    )}
                  >
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
                    disabled={selected.locked ?? selected.builtin}
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
                  {!selected.locked && !selected.builtin && (
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

                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Indicadores incluidos (
                  {selected.presetIds?.length ?? selected.items?.length ?? 0})
                </p>
                <ul className="mb-4 max-h-48 space-y-1 overflow-auto text-xs">
                  {(selected.presetIds?.length ?? 0) === 0 &&
                    (selected.items?.length ?? 0) === 0 && (
                      <li className="text-muted-foreground">
                        Sin indicadores — edita o duplica otra.
                      </li>
                    )}
                  {selected.presetIds?.map((presetId) => {
                    const preset = findIndicatorPreset(presets, presetId);
                    return (
                      <li
                        key={presetId}
                        className="rounded border border-border bg-background px-2 py-1"
                      >
                        {preset ? presetLabel(preset) : presetId}
                      </li>
                    );
                  })}
                  {selected.items?.map((item, index) => (
                    <li
                      key={`${item.definitionId}-${index}`}
                      className="rounded border border-border bg-background px-2 py-1"
                    >
                      {templateItemLabel(item)}
                      {!item.visible && (
                        <span className="ml-1 text-muted-foreground">
                          (oculto)
                        </span>
                      )}
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  disabled={
                    !activeTab ||
                    (selected.presetIds?.length ??
                      selected.items?.length ??
                      0) === 0
                  }
                  className="w-full rounded bg-primary px-3 py-2 text-xs font-medium text-primary-foreground disabled:opacity-40"
                  onClick={() => applyToChart(selected)}
                >
                  Aplicar al gráfico{activeTab ? ` (${activeTab.label})` : ""}
                </button>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Selecciona una plantilla o guarda los indicadores actuales del
                gráfico.
              </p>
            )}

            {!activeTab && (
              <p className="mt-3 text-xs text-amber-500">
                Abre un instrumento en el gráfico para aplicar o guardar
                plantillas.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
