/**
 * Paper D — propose dry-run + execute opcional (PAPER_D_EXECUTE en API).
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import { Route } from 'lucide-react';
import { useState } from 'react';
import type { PaperDProposeResultV1 } from '@bolsa/shared';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

type Props = {
  listId: string;
  lists: Array<{ id: string; name: string; itemCount: number }>;
  onListIdChange: (listId: string) => void;
  className?: string;
};

export function PaperDProposePanel({ listId, lists, onListIdChange, className }: Props) {
  const [minScore, setMinScore] = useState('55');
  const [wantExecute, setWantExecute] = useState(false);
  const [policyId, setPolicyId] = useState('');
  const [result, setResult] = useState<PaperDProposeResultV1 | null>(null);

  const policiesQuery = useQuery({
    queryKey: ['execution-policies'],
    queryFn: () => api.getExecutionPolicies(true),
  });
  const paperPolicies = (policiesQuery.data?.data ?? []).filter(
    (p) => p.mode === 'paper_auto' && p.enabled,
  );

  const mutation = useMutation({
    mutationFn: () => {
      const min = Number(minScore);
      return api.proposePaperD({
        universe: { listId },
        horizon: 'swing',
        regime: 'neutral',
        minScoreDisplay100: Number.isFinite(min) ? min : 55,
        respectVetoNewLong: true,
        maxCandidates: 25,
        execute: wantExecute,
        executionPolicyId: wantExecute ? policyId || null : null,
      });
    },
    onSuccess: (res) => setResult(res.data),
  });

  const eligible = result?.candidates.filter((c) => c.status === 'eligible') ?? [];

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">Universo (p.ej. FA whitelist)</span>
          <select
            className="h-8 min-w-[10rem] rounded-md border border-border/60 bg-background px-2 text-xs"
            value={listId}
            onChange={(e) => onListIdChange(e.target.value)}
          >
            {lists.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name} ({l.itemCount})
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">Composite mín /100</span>
          <input
            className="h-8 w-20 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
          />
        </label>
        <label className="flex h-8 items-center gap-1.5 text-[11px] text-muted-foreground">
          <input
            type="checkbox"
            checked={wantExecute}
            onChange={(e) => setWantExecute(e.target.checked)}
          />
          Execute paper
        </label>
        {wantExecute ? (
          <label className="grid gap-1 text-[11px]">
            <span className="text-muted-foreground">Política paper_auto</span>
            <select
              className="h-8 min-w-[10rem] rounded-md border border-border/60 bg-background px-2 text-xs"
              value={policyId}
              onChange={(e) => setPolicyId(e.target.value)}
            >
              <option value="">— elegir —</option>
              {paperPolicies.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <Button
          type="button"
          size="sm"
          className="h-8 gap-1.5"
          disabled={
            !listId ||
            mutation.isPending ||
            (wantExecute && !policyId)
          }
          onClick={() => mutation.mutate()}
        >
          <Route className={cn('h-3.5 w-3.5', mutation.isPending && 'animate-pulse')} />
          {mutation.isPending
            ? '…'
            : wantExecute
              ? 'Proponer + execute'
              : 'Proponer plan D'}
        </Button>
      </div>

      <p className="text-[10px] text-muted-foreground">
        Dry-run por defecto. Execute exige env API <code>PAPER_D_EXECUTE=1</code>, política{' '}
        <code>paper_auto</code> con <code>entry_long</code>, y Gate cognitivo. ≠ radar (B).
      </p>

      {mutation.isError ? (
        <p className="text-[11px] text-destructive">
          {(mutation.error as Error)?.message || 'Error en Paper D'}
        </p>
      ) : null}

      {result ? (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            {result.weekKey} · escaneados {result.scannedCount} · elegibles{' '}
            {result.eligibleCount} · {result.executeStatus}
            {result.executeAllowedByEnv ? ' · env OK' : ' · env off'}
          </p>
          {eligible.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">Ningún elegible con el umbral actual.</p>
          ) : (
            <ul className="space-y-1 text-[11px]">
              {eligible.map((c) => (
                <li
                  key={c.instrumentId}
                  className="flex flex-wrap justify-between gap-2 rounded-md border border-border/50 px-2 py-1"
                >
                  <span className="font-medium">{c.ticker}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {c.scoreDisplay100 ?? '—'}/100 · {c.confidence ?? '—'}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {result.execution?.actions?.length ? (
            <div className="space-y-1">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Acciones Router
              </p>
              <ul className="space-y-0.5 text-[11px]">
                {result.execution.actions.map((a) => (
                  <li key={`${a.instrumentId}-${a.status}`}>
                    {a.instrumentId.slice(0, 8)}… · {a.status}
                    {a.reason ? ` · ${a.reason}` : ''}
                    {a.transactionId ? ` · tx ${a.transactionId.slice(0, 8)}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {result.notes[0] ? (
            <p className="text-[10px] italic text-muted-foreground">{result.notes[0]}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
