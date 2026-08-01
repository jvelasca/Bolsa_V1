import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Sparkles } from 'lucide-react';

import { useState } from 'react';

import {

  PROMPT_DRAFT_EXAMPLES,

  type DraftStrategyFromPromptResultDto,

  type StrategyDefinitionV1,

} from '@bolsa/shared';

import { api, ApiError } from '@/lib/api';

import { Button } from '@/components/ui/button';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

import { AiInfoButton } from '@/features/ai/ai-info-button';

import { scanConfigFromStrategyDefinition } from '@/features/screeners/scan-runner-form';

import { StrategyDraftFeedback } from '@/features/screeners/strategy-draft-feedback';



interface StrategyPromptAssistantPanelProps {

  compact?: boolean;

  /** Tras guardar estrategia, opcionalmente cargar config en el laboratorio de rastreo. */

  onApplyToScan?: (config: ReturnType<typeof scanConfigFromStrategyDefinition>) => void;

  description?: string;

}



export function StrategyPromptAssistantPanel({

  compact,

  onApplyToScan,

  description = 'Describe la estrategia en lenguaje natural — te explico qué interpreté antes de guardar.',

}: StrategyPromptAssistantPanelProps) {

  const queryClient = useQueryClient();

  const [prompt, setPrompt] = useState('');

  const [strategyName, setStrategyName] = useState('');

  const [draft, setDraft] = useState<DraftStrategyFromPromptResultDto | null>(null);



  const draftMutation = useMutation({

    mutationFn: api.draftStrategyFromPrompt,

    onSuccess: (result) => {

      setDraft(result.data);

      setStrategyName(result.data.suggestedName);

    },

  });



  const saveMutation = useMutation({

    mutationFn: api.createStrategy,

    onSuccess: (response) => {

      void queryClient.invalidateQueries({ queryKey: ['strategies'] });

      if (onApplyToScan) {

        onApplyToScan(scanConfigFromStrategyDefinition(response.data));

      }

      setDraft(null);

      setPrompt('');

      setStrategyName('');

    },

  });



  const fieldClass =

    'mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm';



  return (

    <Card className={compact ? 'border-0 shadow-none' : undefined}>

      <CardHeader className={compact ? 'px-0 pb-2' : 'pb-2'}>

        <CardTitle className="flex items-center gap-2 text-base">

          <Sparkles className="h-4 w-4 text-primary" />

          Asistente IA

          <AiInfoButton surface="strategy_draft" />

        </CardTitle>

        <CardDescription>{description}</CardDescription>

      </CardHeader>

      <CardContent className={compact ? 'space-y-3 px-0' : 'space-y-3'}>

        <label className="block text-sm">

          Describe la estrategia

          <textarea

            value={prompt}

            onChange={(e) => setPrompt(e.target.value)}

            rows={compact ? 2 : 3}

            placeholder="Ej: híbrido con SMA200 y rating ≥ 65"

            className={fieldClass}

          />

        </label>



        <div className="flex flex-wrap gap-1.5">

          {PROMPT_DRAFT_EXAMPLES.map((example) => (

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

            <div className="flex flex-wrap items-center gap-2">

              <span

                className={

                  draft.draftKind === 'hybrid'

                    ? 'rounded bg-violet-500/15 px-2 py-0.5 text-[10px] font-medium text-violet-700 dark:text-violet-300'

                    : 'rounded bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground'

                }

              >

                {draft.draftKind === 'hybrid' ? 'Híbrido IA' : 'Clásico'}

              </span>

            </div>



            <StrategyDraftFeedback draft={draft} compact={compact} />



            <label className="block text-xs">

              Nombre al guardar

              <input

                value={strategyName}

                onChange={(e) => setStrategyName(e.target.value)}

                className={fieldClass}

              />

            </label>

            <div className="flex flex-wrap gap-2">

              <Button

                size="sm"

                variant="outline"

                disabled={!strategyName.trim() || saveMutation.isPending}

                onClick={() =>

                  saveMutation.mutate({

                    name: strategyName.trim(),

                    definition: draft.definition as StrategyDefinitionV1,

                  })

                }

              >

                {saveMutation.isPending ? 'Guardando…' : 'Guardar estrategia'}

              </Button>

              {onApplyToScan && draft.validated && (

                <Button

                  size="sm"

                  variant="ghost"

                  disabled={saveMutation.isPending}

                  onClick={() => {

                    const definition = draft.definition as StrategyDefinitionV1;

                    onApplyToScan(

                      scanConfigFromStrategyDefinition({

                        id: 'draft',

                        name: strategyName.trim(),

                        kind: definition.kind ?? 'indicator_signals',

                        origin: 'assisted',

                        timeframe: draft.timeframe,

                        instrumentIds: definition.universe?.instrumentIds ?? [],

                        definition,

                        updatedAt: '',

                        createdAt: '',

                      }),

                    );

                  }}

                >

                  Usar en rastreo (sin guardar)

                </Button>

              )}

            </div>

            {saveMutation.isError && (

              <p className="text-xs text-destructive">

                {saveMutation.error instanceof ApiError

                  ? saveMutation.error.message

                  : 'Error al guardar'}

              </p>

            )}

          </div>

        )}

      </CardContent>

    </Card>

  );

}


