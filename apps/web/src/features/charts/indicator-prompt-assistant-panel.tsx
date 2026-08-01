import { useMutation } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { useState } from 'react';
import {
  INDICATOR_PROMPT_DRAFT_EXAMPLES,
  type DraftIndicatorFromPromptResultDto,
  type IndicatorPreset,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { IndicatorDraftFeedback } from '@/features/charts/indicator-draft-feedback';
import { useWorkspaceStore } from '@/stores/workspace-store';

interface IndicatorPromptAssistantPanelProps {
  compact?: boolean;
  chartId?: string;
  onPresetSaved?: (presetId: string) => void;
  onAddToChart?: (preset: IndicatorPreset) => void;
}

export function IndicatorPromptAssistantPanel({
  compact,
  chartId,
  onPresetSaved,
  onAddToChart,
}: IndicatorPromptAssistantPanelProps) {
  const addIndicatorPresetFromDraft = useWorkspaceStore((state) => state.addIndicatorPresetFromDraft);
  const save = useWorkspaceStore((state) => state.save);

  const [prompt, setPrompt] = useState('');
  const [presetName, setPresetName] = useState('');
  const [draft, setDraft] = useState<DraftIndicatorFromPromptResultDto | null>(null);

  const draftMutation = useMutation({
    mutationFn: api.draftIndicatorFromPrompt,
    onSuccess: (result) => {
      setDraft(result.data);
      setPresetName(result.data.suggestedPresetName);
    },
  });

  const fieldClass =
    'mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm';

  function saveDraftPreset(): string | null {
    if (!draft) return null;
    return addIndicatorPresetFromDraft(
      {
        ...draft.preset,
        name: presetName.trim() || draft.suggestedPresetName,
        locked: false,
      },
      presetName.trim() || draft.suggestedPresetName,
    );
  }

  function handleSaveToCatalog() {
    const presetId = saveDraftPreset();
    if (!presetId) return;
    save();
    onPresetSaved?.(presetId);
    setDraft(null);
    setPrompt('');
    setPresetName('');
  }

  function handleSaveAndAddToChart() {
    const presetId = saveDraftPreset();
    if (!presetId || !draft) return;
    save();
    onAddToChart?.({
      ...draft.preset,
      id: presetId,
      name: presetName.trim() || draft.suggestedPresetName,
      locked: false,
    });
    setDraft(null);
    setPrompt('');
    setPresetName('');
  }

  return (
    <div className={compact ? 'space-y-3' : 'space-y-3 rounded-md border border-border p-3'}>
      <div>
        <h4 className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="h-4 w-4 text-primary" />
          Generar con prompt
        </h4>
        <p className="mt-1 text-xs text-muted-foreground">
          Describe el indicador en lenguaje natural; validamos contra el catálogo antes de crear el
          preset.
        </p>
      </div>

      <label className="block text-sm">
        Describe el indicador
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={compact ? 2 : 3}
          placeholder="Ej: RSI 14 en panel inferior"
          className={fieldClass}
        />
      </label>

      <div className="flex flex-wrap gap-1.5">
        {INDICATOR_PROMPT_DRAFT_EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => setPrompt(example)}
            className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-accent"
          >
            {example}
          </button>
        ))}
      </div>

      <Button
        size="sm"
        disabled={prompt.trim().length < 4 || draftMutation.isPending}
        onClick={() => draftMutation.mutate({ prompt: prompt.trim() })}
      >
        {draftMutation.isPending ? 'Interpretando…' : 'Generar borrador'}
      </Button>

      {draftMutation.isError && (
        <p className="text-sm text-destructive">
          {draftMutation.error instanceof ApiError
            ? draftMutation.error.message
            : 'Error al generar borrador'}
        </p>
      )}

      {draft && (
        <div className="space-y-3 rounded-md border border-border p-3 text-sm">
          <IndicatorDraftFeedback draft={draft} compact={compact} />

          <label className="block text-xs">
            Nombre del preset
            <input
              value={presetName}
              onChange={(event) => setPresetName(event.target.value)}
              className={fieldClass}
            />
          </label>

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!presetName.trim()}
              onClick={handleSaveToCatalog}
            >
              Guardar en catálogo IA
            </Button>
            {onAddToChart && chartId && draft.validated && (
              <Button size="sm" variant="ghost" disabled={!presetName.trim()} onClick={handleSaveAndAddToChart}>
                Guardar y añadir al gráfico
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
