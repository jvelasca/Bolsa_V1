import { useMemo, useState } from 'react';
import {
  AI_INDICATOR_DEFINITIONS,
  defaultParameters,
  type IndicatorPreset,
} from '@bolsa/shared';
import { Brain, Copy, Plus, Star, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { IndicatorPromptAssistantPanel } from '@/features/charts/indicator-prompt-assistant-panel';

interface AiIndicatorsPanelProps {
  presets: IndicatorPreset[];
  chartId?: string;
  onPresetCreated: (presetId: string) => void;
  onMessage: (message: string | null) => void;
  onAddToChart: (preset: IndicatorPreset) => void;
}

export function AiIndicatorsPanel({
  presets,
  chartId,
  onPresetCreated,
  onMessage,
  onAddToChart,
}: AiIndicatorsPanelProps) {
  const createAiVariant = useWorkspaceStore((state) => state.createAiIndicatorVariant);
  const forkPresetToPersonal = useWorkspaceStore((state) => state.forkPresetToPersonal);
  const removePreset = useWorkspaceStore((state) => state.removeIndicatorPreset);
  const save = useWorkspaceStore((state) => state.save);

  const [selectedMotorId, setSelectedMotorId] = useState(AI_INDICATOR_DEFINITIONS[0]?.id ?? '');
  const [variantName, setVariantName] = useState('');

  const systemAiPresets = useMemo(
    () => presets.filter((preset) => preset.source === 'ai' && preset.locked),
    [presets],
  );
  const userAiVariants = useMemo(
    () => presets.filter((preset) => preset.source === 'ai' && !preset.locked),
    [presets],
  );

  function handleCreateVariant() {
    onMessage(null);
    const definition = AI_INDICATOR_DEFINITIONS.find((item) => item.id === selectedMotorId);
    if (!definition) return;
    const name =
      variantName.trim() ||
      `${definition.shortLabel} · ${new Date().toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })}`;
    const presetId = createAiVariant({
      definitionId: selectedMotorId,
      name,
      parameters: defaultParameters(definition),
    });
    if (!presetId) {
      onMessage('No se pudo crear la variante IA.');
      return;
    }
    save();
    setVariantName('');
    onPresetCreated(presetId);
    onMessage(`Variante «${name}» creada.`);
  }

  function handlePublishAsPersonal(preset: IndicatorPreset) {
    const name = window.prompt('Nombre del indicador personal:', `${preset.name} personal`);
    if (!name?.trim()) return;
    const newId = forkPresetToPersonal(preset.id, name.trim());
    if (!newId) {
      onMessage('No se pudo publicar como personal.');
      return;
    }
    save();
    onMessage(`«${name.trim()}» guardado en Personal.`);
  }

  return (
    <section className="mb-4 space-y-4 rounded-lg border border-primary/20 bg-primary/5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Brain className="h-4 w-4 text-primary" />
            Indicadores IA
          </h3>
          <p className="mt-1 max-w-2xl text-xs text-muted-foreground">
            Scores compuestos deterministas (0–100) alineados con rastreadores híbridos. Crea variantes
            con pesos o parámetros distintos, añádelas al gráfico con ★ y publícalas como personal
            cuando quieras editarlas libremente.
          </p>
        </div>
        <div className="flex-1" />
      </div>

      <IndicatorPromptAssistantPanel
        compact
        chartId={chartId}
        onPresetSaved={onPresetCreated}
        onAddToChart={onAddToChart}
      />

      <div className="grid gap-3 lg:grid-cols-3">
        {AI_INDICATOR_DEFINITIONS.map((definition) => {
          const preset = systemAiPresets.find((item) => item.definitionId === definition.id);
          return (
            <article
              key={definition.id}
              className="rounded-md border border-border bg-background/80 p-3 text-sm"
            >
              <p className="font-medium">{definition.name}</p>
              <p className="mt-1 text-xs text-muted-foreground">{definition.description}</p>
              {preset && (
                <div className="mt-3 flex flex-wrap gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={!chartId}
                    onClick={() => onAddToChart(preset)}
                    className="h-7 text-xs"
                  >
                    <Star className="mr-1 h-3 w-3" />
                    Añadir al gráfico
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => handlePublishAsPersonal(preset)}
                    className="h-7 text-xs"
                  >
                    <Copy className="mr-1 h-3 w-3" />
                    Como personal
                  </Button>
                </div>
              )}
            </article>
          );
        })}
      </div>

      <div className="rounded-md border border-border bg-background/80 p-3">
        <p className="text-xs font-medium">Crear variante IA</p>
        <div className="mt-2 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <label className="block text-xs">
            Motor
            <select
              value={selectedMotorId}
              onChange={(event) => setSelectedMotorId(event.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
            >
              {AI_INDICATOR_DEFINITIONS.map((definition) => (
                <option key={definition.id} value={definition.id}>
                  {definition.shortLabel}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs">
            Nombre
            <input
              value={variantName}
              onChange={(event) => setVariantName(event.target.value)}
              placeholder="Ej. Rating IA conservador"
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
            />
          </label>
          <div className="flex items-end">
            <Button type="button" size="sm" onClick={handleCreateVariant} className="w-full md:w-auto">
              <Plus className="mr-1 h-3.5 w-3.5" />
              Crear
            </Button>
          </div>
        </div>
      </div>

      {userAiVariants.length > 0 && (
        <div className="rounded-md border border-border bg-background/80 p-3">
          <p className="text-xs font-medium">Tus variantes IA ({userAiVariants.length})</p>
          <ul className="mt-2 space-y-1">
            {userAiVariants.map((preset) => (
              <li
                key={preset.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-border/60 px-2 py-1.5 text-xs"
              >
                <span className="font-medium">{preset.name}</span>
                <div className="flex gap-1">
                  <button
                    type="button"
                    disabled={!chartId}
                    title="Añadir al gráfico"
                    onClick={() => onAddToChart(preset)}
                    className={cn(
                      'rounded p-1 hover:bg-accent disabled:opacity-40',
                      !chartId && 'cursor-not-allowed',
                    )}
                  >
                    <Star className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    title="Publicar como personal"
                    onClick={() => handlePublishAsPersonal(preset)}
                    className="rounded p-1 hover:bg-accent"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    title="Eliminar variante"
                    onClick={() => {
                      if (!window.confirm(`¿Eliminar «${preset.name}»?`)) return;
                      removePreset(preset.id);
                      save();
                    }}
                    className="rounded p-1 text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
