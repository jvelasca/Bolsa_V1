import { useEffect, useMemo, useState } from 'react';
import type { IndicatorPreset, IndicatorSource, IndicatorTemplate } from '@bolsa/shared';
import {
  BUILTIN_PERSONAL_TEMPLATE_ID,
  findIndicatorDefinition,
  formatParameterSummary,
  isIndicatorApiSupported,
  presetDerivedHint,
  presetLabel,
  templateHasIndicators,
  templateIncludesPreset,
} from '@bolsa/shared';
import {
  Copy,
  Eye,
  EyeOff,
  LayoutTemplate,
  Pencil,
  Pin,
  Play,
  Plus,
  Settings2,
  Star,
  Trash2,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { requestChartReflow } from '@/features/charts/chart-utils';
import { IndicatorPresetEditorPanel } from '@/features/charts/indicator-preset-editor-panel';
import { AiIndicatorsPanel } from '@/features/charts/ai-indicators-panel';
import { useChartIndicatorTemplateFavorites } from '@/features/charts/use-chart-indicator-template-favorites';
import { useUiStore } from '@/stores/ui-store';
import { useActiveChartTab, useWorkspaceStore } from '@/stores/workspace-store';

type CatalogFilter = 'all' | IndicatorSource;

const SOURCE_LABELS: Record<IndicatorSource, string> = {
  builtin: 'Sistema',
  custom: 'Personal',
  ai: 'IA',
};

const SOURCE_FILTERS: { id: CatalogFilter; label: string }[] = [
  { id: 'all', label: 'Todos' },
  { id: 'builtin', label: 'Sistema' },
  { id: 'custom', label: 'Personal' },
  { id: 'ai', label: 'IA' },
];

function ChartStarButton({
  active,
  disabled,
  title,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={title}
      onClick={onClick}
      className="rounded p-1 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40"
    >
      <Star
        className={cn(
          'h-4 w-4',
          active ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground',
        )}
      />
    </button>
  );
}

export function IndicatorsCatalogDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const activeTab = useActiveChartTab();
  const chartId = activeTab?.id;
  const instances = activeTab?.indicatorInstances ?? [];

  const presets = useWorkspaceStore((s) => s.workspace.indicatorPresets ?? []);
  const templates = useWorkspaceStore((s) => s.workspace.indicatorTemplates ?? []);
  const defaultTemplateId = useWorkspaceStore((s) => s.workspace.defaultIndicatorTemplateId ?? null);

  const togglePresetOnChart = useWorkspaceStore((s) => s.togglePresetOnChart);
  const togglePresetVisibility = useWorkspaceStore((s) => s.togglePresetVisibilityOnChart);
  const togglePresetInTemplate = useWorkspaceStore((s) => s.togglePresetInTemplate);
  const applyTemplate = useWorkspaceStore((s) => s.applyIndicatorTemplate);
  const setDefaultTemplate = useWorkspaceStore((s) => s.setDefaultIndicatorTemplate);
  const duplicatePreset = useWorkspaceStore((s) => s.duplicateUserIndicatorPreset);
  const forkPresetToPersonal = useWorkspaceStore((s) => s.forkPresetToPersonal);
  const removePreset = useWorkspaceStore((s) => s.removeIndicatorPreset);
  const addTemplate = useWorkspaceStore((s) => s.addIndicatorTemplate);
  const updateTemplate = useWorkspaceStore((s) => s.updateIndicatorTemplate);
  const removeTemplate = useWorkspaceStore((s) => s.removeIndicatorTemplate);
  const createTemplateFromChart = useWorkspaceStore((s) => s.createIndicatorTemplateFromChart);
  const save = useWorkspaceStore((s) => s.save);
  const openIndicatorConfig = useUiStore((s) => s.openIndicatorConfig);
  const { toggleFavorite: toggleToolbarFavorite, isFavorite: isToolbarFavorite } =
    useChartIndicatorTemplateFavorites();

  const [catalogFilter, setCatalogFilter] = useState<CatalogFilter>('all');
  const [onlyOnChart, setOnlyOnChart] = useState(false);
  const [editingPresetId, setEditingPresetId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const editingPreset = editingPresetId
    ? presets.find((item) => item.id === editingPresetId) ?? null
    : null;

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose, open]);

  useEffect(() => {
    if (!open) {
      setMessage(null);
      setEditingPresetId(null);
    }
  }, [open]);

  const personalPresetIds = useMemo(() => {
    const personal = templates.find((template) => template.id === BUILTIN_PERSONAL_TEMPLATE_ID);
    return new Set(personal?.presetIds ?? []);
  }, [templates]);

  const filteredPresets = useMemo(() => {
    let rows = [...presets];
    if (catalogFilter === 'custom') {
      rows = rows.filter((preset) => personalPresetIds.has(preset.id));
    } else if (catalogFilter !== 'all') {
      rows = rows.filter((preset) => preset.source === catalogFilter);
    }
    if (onlyOnChart) {
      rows = rows.filter((preset) =>
        instances.some((instance) => instance.presetId === preset.id),
      );
    }
    return rows.sort((a, b) => {
      const sourceOrder = { builtin: 0, custom: 1, ai: 2 };
      const sa = sourceOrder[a.source] - sourceOrder[b.source];
      if (sa !== 0) return sa;
      return presetLabel(a).localeCompare(presetLabel(b));
    });
  }, [catalogFilter, instances, onlyOnChart, personalPresetIds, presets]);

  function reflow() {
    requestChartReflow();
  }

  function instanceForPreset(presetId: string) {
    return instances.find((item) => item.presetId === presetId);
  }

  function handleStar(preset: IndicatorPreset) {
    if (!chartId) return;
    setMessage(null);
    const result = togglePresetOnChart(preset.id, chartId);
    if (result === 'failed') setMessage('No se pudo cambiar el indicador.');
    else {
      save();
      reflow();
    }
  }

  function handleVisibility(preset: IndicatorPreset) {
    if (!chartId) return;
    const instance = instanceForPreset(preset.id);
    if (!instance) return;
    if (togglePresetVisibility(preset.id, chartId)) {
      save();
      reflow();
    }
  }

  function handleGroupCell(template: IndicatorTemplate, preset: IndicatorPreset) {
    togglePresetInTemplate(template.id, preset.id);
    save();
  }

  function handleApplyTemplate(template: IndicatorTemplate) {
    if (!chartId) return;
    if (!templateHasIndicators(template)) {
      setMessage(`"${template.name}" no tiene indicadores. Añádelos en la matriz.`);
      return;
    }
    applyTemplate(template.id, chartId);
    save();
    reflow();
  }

  function handleSetDefaultTemplate(template: IndicatorTemplate) {
    setDefaultTemplate(template.id);
    save();
  }

  function openPresetConfig(preset: IndicatorPreset) {
    const instance = instanceForPreset(preset.id);
    if (instance && chartId) {
      openIndicatorConfig(chartId, instance.instanceId);
    }
  }

  function handleForkPreset(preset: IndicatorPreset) {
    const name = window.prompt('Nombre del indicador personal:', `${preset.name} personal`);
    if (!name?.trim()) return;
    const newId = forkPresetToPersonal(preset.id, name.trim());
    if (!newId) {
      setMessage('No se pudo crear el preset personal.');
      return;
    }
    save();
    setCatalogFilter('custom');
    setEditingPresetId(newId);
  }

  function handleNewGroup() {
    const created = addTemplate();
    const name = window.prompt('Nombre del nuevo grupo:', created.name);
    if (name?.trim()) updateTemplate(created.id, { name: name.trim() });
    save();
  }

  function handleRenameGroup(template: IndicatorTemplate) {
    if (template.locked) return;
    const name = window.prompt('Renombrar grupo:', template.name);
    if (!name?.trim() || name.trim() === template.name) return;
    updateTemplate(template.id, { name: name.trim() });
    save();
  }

  function handleDeleteGroup(template: IndicatorTemplate) {
    if (template.locked) return;
    if (!window.confirm(`¿Eliminar el grupo "${template.name}"?`)) return;
    removeTemplate(template.id);
    if (defaultTemplateId === template.id) setDefaultTemplate(null);
    save();
  }

  function handleSaveChartAsGroup() {
    if (!chartId || instances.length === 0) return;
    const name = window.prompt('Nombre del grupo:', `Grupo ${activeTab?.label ?? ''}`.trim());
    if (!name?.trim()) return;
    createTemplateFromChart(chartId, name.trim());
    save();
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        aria-label="Cerrar"
        className="absolute inset-0 bg-black/80 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative z-[101] flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-lg border border-border bg-card text-foreground shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <LayoutTemplate className="h-5 w-5 text-primary" />
              Indicadores y grupos
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              ★ añade o quita en{' '}
              <span className="font-medium text-foreground">{activeTab?.label ?? 'el gráfico'}</span>
              . El ojo oculta sin borrar. Las columnas de grupo muestran pertenencia y permiten
              editarla con un clic.
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded p-1 hover:bg-accent">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 overflow-auto px-5 py-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-1">
              {SOURCE_FILTERS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setCatalogFilter(id)}
                  className={cn(
                    'rounded px-2 py-1 text-xs font-medium',
                    catalogFilter === id
                      ? 'bg-primary/20 text-primary'
                      : 'bg-muted/40 text-muted-foreground hover:bg-accent',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setOnlyOnChart((v) => !v)}
              className={cn(
                'rounded-md border border-border px-2.5 py-1 text-xs font-medium',
                onlyOnChart
                  ? 'bg-primary/20 text-primary'
                  : 'text-muted-foreground hover:bg-accent',
              )}
            >
              Solo en gráfico ({instances.length})
            </button>
            <div className="ml-auto flex flex-wrap gap-1">
              <button
                type="button"
                onClick={handleNewGroup}
                className="inline-flex items-center gap-1 rounded border border-dashed border-border px-2 py-1 text-xs hover:bg-accent"
              >
                <Plus className="h-3.5 w-3.5" />
                Nuevo grupo
              </button>
              {chartId && instances.length > 0 && (
                <button
                  type="button"
                  onClick={handleSaveChartAsGroup}
                  className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-accent"
                >
                  Guardar gráfico como grupo
                </button>
              )}
            </div>
          </div>

          {!activeTab && (
            <p className="mb-3 text-sm text-amber-400">Abre un instrumento para gestionar indicadores.</p>
          )}

          {catalogFilter === 'ai' && (
            <AiIndicatorsPanel
              presets={presets}
              chartId={chartId}
              onPresetCreated={(presetId) => setEditingPresetId(presetId)}
              onMessage={setMessage}
              onAddToChart={(preset) => {
                if (!chartId) return;
                const result = togglePresetOnChart(preset.id, chartId);
                if (result === 'failed') setMessage('No se pudo añadir al gráfico.');
                else {
                  save();
                  reflow();
                  setMessage(`«${preset.name}» añadido al gráfico.`);
                }
              }}
            />
          )}

          <div className="overflow-x-auto rounded-md border border-border bg-background">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-muted text-xs uppercase tracking-wide">
                <tr>
                  <th className="sticky left-0 z-20 w-10 bg-muted px-2 py-2" title="En gráfico">
                    ★
                  </th>
                  <th className="sticky left-10 z-20 w-10 bg-muted px-2 py-2" title="Visible">
                    👁
                  </th>
                  <th className="sticky left-20 z-20 min-w-[220px] bg-muted px-3 py-2">
                    Indicador
                  </th>
                  <th className="px-3 py-2">Panel</th>
                  <th className="px-3 py-2">Origen</th>
                  <th className="px-3 py-2">Datos</th>
                  {templates.map((template) => (
                    <th
                      key={template.id}
                      className="min-w-[108px] border-l border-border/60 px-2 py-2 text-center normal-case"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span className="truncate font-semibold" title={template.name}>
                          {template.name}
                        </span>
                        <div className="flex items-center gap-0.5">
                          <button
                            type="button"
                            title={`Aplicar ${template.name} al gráfico`}
                            disabled={!chartId}
                            onClick={() => handleApplyTemplate(template)}
                            className="rounded p-0.5 hover:bg-accent disabled:opacity-40"
                          >
                            <Play className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            title={
                              isToolbarFavorite(template.id)
                                ? 'Quitar acceso directo en la barra del gráfico'
                                : 'Añadir acceso directo en la barra del gráfico'
                            }
                            onClick={() => toggleToolbarFavorite(template.id)}
                            className="rounded p-0.5 hover:bg-accent"
                          >
                            <Star
                              className={cn(
                                'h-3.5 w-3.5',
                                isToolbarFavorite(template.id)
                                  ? 'fill-amber-400 text-amber-400'
                                  : 'text-muted-foreground',
                              )}
                            />
                          </button>
                          <button
                            type="button"
                            title={
                              defaultTemplateId === template.id
                                ? 'Grupo por defecto en gráficos nuevos'
                                : 'Marcar como grupo por defecto'
                            }
                            onClick={() => handleSetDefaultTemplate(template)}
                            className={cn(
                              'rounded p-0.5 hover:bg-accent',
                              defaultTemplateId === template.id && 'text-primary',
                            )}
                          >
                            <Pin
                              className={cn(
                                'h-3.5 w-3.5',
                                defaultTemplateId === template.id && 'fill-current',
                              )}
                            />
                          </button>
                          {!template.locked && (
                            <>
                              <button
                                type="button"
                                title="Renombrar grupo"
                                onClick={() => handleRenameGroup(template)}
                                className="rounded p-0.5 hover:bg-accent"
                              >
                                <Pencil className="h-3 w-3" />
                              </button>
                              <button
                                type="button"
                                title="Eliminar grupo"
                                onClick={() => handleDeleteGroup(template)}
                                className="rounded p-0.5 text-destructive hover:bg-destructive/10"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </th>
                  ))}
                  <th className="w-12 px-2 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredPresets.map((preset) => {
                  const definition = findIndicatorDefinition(preset.definitionId);
                  const onChart = Boolean(instanceForPreset(preset.id));
                  const instance = instanceForPreset(preset.id);
                  const derived = presetDerivedHint(preset, presets);
                  const apiOk = isIndicatorApiSupported(preset.definitionId, preset.parameters);
                  return (
                    <tr
                      key={preset.id}
                      className={cn('hover:bg-accent/30', !instance?.visible && onChart && 'opacity-60')}
                    >
                      <td className="sticky left-0 z-10 bg-background px-2 py-2">
                        <ChartStarButton
                          active={onChart}
                          disabled={!chartId}
                          title={onChart ? 'Quitar del gráfico' : 'Añadir al gráfico'}
                          onClick={() => handleStar(preset)}
                        />
                      </td>
                      <td className="sticky left-10 z-10 bg-background px-2 py-2">
                        {onChart ? (
                          <button
                            type="button"
                            title={instance?.visible ? 'Ocultar en gráfico' : 'Mostrar en gráfico'}
                            onClick={() => handleVisibility(preset)}
                            className="rounded p-1 hover:bg-accent"
                          >
                            {instance?.visible ? (
                              <Eye className="h-4 w-4" />
                            ) : (
                              <EyeOff className="h-4 w-4 text-muted-foreground" />
                            )}
                          </button>
                        ) : (
                          <span className="inline-block w-6 text-center text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="sticky left-20 z-10 bg-background px-3 py-2">
                        <div className="font-medium">{presetLabel(preset)}</div>
                        {derived && (
                          <div className="text-[10px] text-primary/80">{derived}</div>
                        )}
                        {definition && (
                          <div className="text-xs text-muted-foreground">
                            {formatParameterSummary(definition, preset.parameters)}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {definition?.panel === 'sub' ? 'Inferior' : 'Precio'}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {SOURCE_LABELS[preset.source]}
                        {preset.locked && (
                          <span className="ml-1 text-[9px] uppercase text-muted-foreground/80">
                            fijo
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            'rounded px-1.5 py-0.5 text-[10px] font-medium',
                            preset.source === 'ai' && 'bg-violet-500/20 text-violet-300',
                            preset.source !== 'ai' && apiOk && 'bg-emerald-500/20 text-emerald-400',
                            preset.source !== 'ai' && !apiOk && 'bg-sky-500/20 text-sky-300',
                          )}
                        >
                          {preset.source === 'ai' ? 'IA' : apiOk ? 'API' : 'UI'}
                        </span>
                      </td>
                      {templates.map((template) => {
                        const included = templateIncludesPreset(template, preset.id);
                        return (
                          <td
                            key={template.id}
                            className="border-l border-border/40 px-2 py-2 text-center"
                          >
                            <button
                              type="button"
                              title={
                                included
                                  ? `Quitar de ${template.name}`
                                  : `Añadir a ${template.name}`
                              }
                              onClick={() => handleGroupCell(template, preset)}
                              className={cn(
                                'mx-auto flex h-6 w-6 items-center justify-center rounded border text-xs',
                                included
                                  ? 'border-primary/40 bg-primary/15 text-primary'
                                  : 'border-border text-muted-foreground hover:bg-accent',
                              )}
                            >
                              {included ? '✓' : ''}
                            </button>
                          </td>
                        );
                      })}
                      <td className="px-2 py-2">
                        <div className="flex justify-end gap-0.5">
                          {preset.locked ? (
                            <button
                              type="button"
                              title="Guardar como personal"
                              onClick={() => handleForkPreset(preset)}
                              className="rounded p-1 hover:bg-accent"
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </button>
                          ) : (
                            <button
                              type="button"
                              title="Editar preset"
                              onClick={() => setEditingPresetId(preset.id)}
                              className="rounded p-1 hover:bg-accent"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                          )}
                          {onChart && (
                            <button
                              type="button"
                              title="Configurar instancia en gráfico"
                              onClick={() => openPresetConfig(preset)}
                              className="rounded p-1 hover:bg-accent"
                            >
                              <Settings2 className="h-3.5 w-3.5" />
                            </button>
                          )}
                          {!preset.locked && (
                            <>
                              <button
                                type="button"
                                title="Duplicar preset"
                                onClick={() => {
                                  duplicatePreset(preset.id);
                                  save();
                                }}
                                className="rounded p-1 text-[10px] hover:bg-accent"
                              >
                                ⧉
                              </button>
                              <button
                                type="button"
                                title="Eliminar preset"
                                onClick={() => {
                                  if (!window.confirm(`¿Eliminar "${preset.name}"?`)) return;
                                  removePreset(preset.id);
                                  if (editingPresetId === preset.id) setEditingPresetId(null);
                                  save();
                                }}
                                className="rounded p-1 text-destructive hover:bg-destructive/10"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filteredPresets.length === 0 && (
                  <tr>
                    <td
                      colSpan={6 + templates.length}
                      className="px-3 py-8 text-center text-muted-foreground"
                    >
                      {catalogFilter === 'ai'
                        ? 'Usa el panel superior para crear variantes IA o añade los motores del sistema con ★.'
                        : 'Sin indicadores en este filtro.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {message && <p className="mt-3 text-xs text-amber-400">{message}</p>}

          {editingPreset && !editingPreset.locked && (
            <IndicatorPresetEditorPanel
              preset={editingPreset}
              presets={presets}
              onClose={() => setEditingPresetId(null)}
              onSaved={() => {
                reflow();
                setMessage(null);
              }}
            />
          )}

          <p className="mt-4 text-xs text-muted-foreground">
            {presets.length} presets · {templates.length} grupos · Los de sistema no se eliminan;
            usa el icono copiar para crear una variante personal editable.
          </p>
        </div>

        <div className="flex justify-end border-t border-border px-5 py-3">
          <Button type="button" variant="outline" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      </div>
    </div>
  );
}
