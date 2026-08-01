/**
 * Decision Replay — lista sesiones, timeline caja negra, cerrar Outcome.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { DecisionReplayStepV1 } from '@bolsa/shared';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

const STEP_ACCENT: Record<string, string> = {
  context: 'border-sky-500/40',
  assessments: 'border-emerald-500/40',
  evidence: 'border-violet-500/40',
  predictions: 'border-violet-500/30',
  weights: 'border-amber-500/40',
  runtime: 'border-orange-500/40',
  recommendation: 'border-primary/50',
  gate: 'border-rose-500/40',
  execution: 'border-border',
  outcome: 'border-muted-foreground/40',
};

function StepCard({ step }: { step: DecisionReplayStepV1 }) {
  const [open, setOpen] = useState(false);
  return (
    <li
      className={cn(
        'rounded-md border-l-2 border border-border bg-muted/15 px-3 py-2',
        STEP_ACCENT[step.stepId] ?? 'border-l-border',
      )}
    >
      <button
        type="button"
        className="flex w-full items-start justify-between gap-2 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="min-w-0 space-y-0.5">
          <p className="text-xs font-medium text-foreground">{step.title}</p>
          <p className="text-[11px] text-muted-foreground">{step.detail}</p>
        </div>
        {step.payload ? (
          <span className="shrink-0 text-[10px] text-muted-foreground">{open ? '▼' : '▶'}</span>
        ) : null}
      </button>
      {open && step.payload ? (
        <pre className="mt-2 max-h-40 overflow-auto rounded bg-background/80 p-2 text-[10px] text-muted-foreground">
          {JSON.stringify(step.payload, null, 2)}
        </pre>
      ) : null}
    </li>
  );
}

export function DecisionReplayPanel({
  initialSessionId,
}: {
  initialSessionId?: string | null;
} = {}) {
  const { effectiveAccountId } = useActiveAccount();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(initialSessionId ?? null);
  const [outcomeLog, setOutcomeLog] = useState<string | null>(null);

  useEffect(() => {
    if (initialSessionId) {
      setSelectedId(initialSessionId);
      setOutcomeLog(null);
    }
  }, [initialSessionId]);

  const listQuery = useQuery({
    queryKey: ['decision-sessions', effectiveAccountId],
    queryFn: async () =>
      (
        await api.listDecisionSessions({
          accountId: effectiveAccountId ?? undefined,
          limit: 20,
        })
      ).data,
    enabled: true,
    staleTime: 15_000,
  });

  const replayQuery = useQuery({
    queryKey: ['decision-replay', selectedId],
    queryFn: async () => {
      if (!selectedId) throw new Error('sin session');
      return (await api.getDecisionSessionReplay(selectedId)).data;
    },
    enabled: Boolean(selectedId),
  });

  const learningQuery = useQuery({
    queryKey: ['decision-learning', effectiveAccountId],
    queryFn: async () =>
      (
        await api.getDecisionSessionLearningSummary({
          accountId: effectiveAccountId ?? undefined,
          limit: 200,
        })
      ).data,
    staleTime: 30_000,
  });

  const closeOutcome = useMutation({
    mutationFn: async () => {
      if (!selectedId) throw new Error('sin session');
      return (await api.closeDecisionSessionOutcome(selectedId, { mode: 'auto' })).data;
    },
    onSuccess: (data) => {
      const v = data.outcome as { verdict?: string; returnPct?: number } | null | undefined;
      setOutcomeLog(
        v
          ? `Outcome ${v.verdict}${v.returnPct != null ? ` · ${v.returnPct}%` : ''} · session closed`
          : 'Outcome registrado',
      );
      void queryClient.invalidateQueries({ queryKey: ['decision-sessions'] });
      void queryClient.invalidateQueries({ queryKey: ['decision-replay', selectedId] });
      void queryClient.invalidateQueries({ queryKey: ['decision-learning'] });
    },
    onError: (err: Error) => setOutcomeLog(err.message),
  });

  const items = listQuery.data ?? [];
  const selectedMeta = items.find((i) => i.sessionId === selectedId);
  const canClose =
    Boolean(selectedId) &&
    selectedMeta?.status !== 'closed' &&
    !replayQuery.data?.steps.some(
      (s) => s.stepId === 'outcome' && s.payload && (s.payload as { verdict?: string }).verdict,
    );

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Reproduce la fotografía de un propose (no re-ejecuta motores).
        </p>
        <button
          type="button"
          className="text-[10px] text-muted-foreground hover:underline"
          onClick={() => {
            void listQuery.refetch();
            void learningQuery.refetch();
          }}
        >
          Actualizar lista
        </button>
      </div>

      {learningQuery.data && learningQuery.data.sampleClosed > 0 ? (
        <p className="rounded-md border border-border/60 bg-muted/20 px-2 py-1.5 text-[11px] text-muted-foreground">
          Learning · maduro {learningQuery.data.matureScored ?? 0}
          {learningQuery.data.matureHitRate != null
            ? ` · matureHitRate ${(learningQuery.data.matureHitRate * 100).toFixed(0)}%`
            : ''}
          {learningQuery.data.prematureScored
            ? ` · prematuros ${learningQuery.data.prematureScored}`
            : ''}
          {' · '}
          total {learningQuery.data.hits}H / {learningQuery.data.misses}M
        </p>
      ) : null}

      {listQuery.isLoading ? (
        <p className="text-xs text-muted-foreground">Cargando sesiones…</p>
      ) : listQuery.isError ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          No se pudieron cargar sesiones (¿API / migración?).
        </p>
      ) : items.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Aún no hay DecisionSessions. Genera una en Ayuda → Plataforma IA → Supervisado F3.
        </p>
      ) : (
        <ul className="max-h-36 space-y-1 overflow-y-auto text-[11px]">
          {items.map((item) => (
            <li key={item.sessionId}>
              <button
                type="button"
                className={cn(
                  'w-full rounded px-2 py-1.5 text-left hover:bg-accent',
                  selectedId === item.sessionId && 'bg-accent',
                )}
                onClick={() => {
                  setSelectedId(item.sessionId);
                  setOutcomeLog(null);
                }}
              >
                <span className="font-medium text-foreground">
                  {item.symbol ?? item.instrumentId}
                </span>
                <span className="text-muted-foreground">
                  {' · '}
                  {item.kind}/{item.status}
                  {' · '}
                  <code className="text-[10px]">{item.sessionId}</code>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedId ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="rounded border border-border px-2 py-1 text-[11px] text-foreground hover:bg-accent disabled:opacity-50"
              disabled={!canClose || closeOutcome.isPending}
              onClick={() => closeOutcome.mutate()}
            >
              {closeOutcome.isPending ? 'Evaluando…' : 'Cerrar Outcome (auto)'}
            </button>
            <span className="text-[10px] text-muted-foreground">
              Criterio v1.1: close en barra D1 +N del horizonte (si faltan días → premature_mtm)
            </span>
          </div>
          {outcomeLog ? <p className="text-[11px] text-foreground/80">{outcomeLog}</p> : null}
          {replayQuery.isLoading ? (
            <p className="text-xs text-muted-foreground">Cargando replay…</p>
          ) : replayQuery.isError ? (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              {(replayQuery.error as Error).message}
            </p>
          ) : replayQuery.data ? (
            <>
              <p className="text-xs text-foreground">
                Replay · {replayQuery.data.symbol ?? replayQuery.data.instrumentId}
                {replayQuery.data.createdAt
                  ? ` · ${new Date(replayQuery.data.createdAt).toLocaleString()}`
                  : ''}
              </p>
              <ol className="space-y-2">
                {replayQuery.data.steps.map((step) => (
                  <StepCard key={step.stepId} step={step} />
                ))}
              </ol>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
