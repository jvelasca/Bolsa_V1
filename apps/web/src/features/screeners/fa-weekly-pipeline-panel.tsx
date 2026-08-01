/**
 * Pipeline semanal FA → whitelist → Paper D (manual; cron off-by-default).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock } from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  buildFundamentalGate,
  type FaWeeklyPipelineResultV1,
} from '@bolsa/shared';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

type Props = {
  listId: string;
  lists: Array<{ id: string; name: string; itemCount: number }>;
  onListIdChange: (listId: string) => void;
  className?: string;
};

export function FaWeeklyPipelinePanel({
  listId,
  lists,
  onListIdChange,
  className,
}: Props) {
  const queryClient = useQueryClient();
  const [maxPe, setMaxPe] = useState('25');
  const [minRoe, setMinRoe] = useState('10');
  const [minPiotroski, setMinPiotroski] = useState('6');
  const [minScore, setMinScore] = useState('55');
  const [wantExecute, setWantExecute] = useState(false);
  const [policyId, setPolicyId] = useState('');
  const [result, setResult] = useState<FaWeeklyPipelineResultV1 | null>(null);

  const gate = useMemo(() => {
    const pe = maxPe.trim() === '' ? null : Number(maxPe);
    const roePct = minRoe.trim() === '' ? null : Number(minRoe);
    const piot = minPiotroski.trim() === '' ? null : Number(minPiotroski);
    return buildFundamentalGate({
      maxTrailingPe: pe != null && Number.isFinite(pe) ? pe : null,
      minRoe: roePct != null && Number.isFinite(roePct) ? roePct / 100 : null,
      minPiotroski: piot != null && Number.isFinite(piot) ? piot : null,
      useSectorBands: true,
    });
  }, [maxPe, minRoe, minPiotroski]);

  const policiesQuery = useQuery({
    queryKey: ['execution-policies'],
    queryFn: () => api.getExecutionPolicies(true),
  });
  const paperPolicies = (policiesQuery.data?.data ?? []).filter(
    (p) => p.mode === 'paper_auto' && p.enabled,
  );

  const mutation = useMutation({
    mutationFn: () => {
      if (!gate) throw new Error('Define al menos un filtro FA');
      const min = Number(minScore);
      return api.runFaWeeklyPipeline({
        universe: { listId },
        fundamentalGate: gate,
        refreshStale: true,
        maxResults: 100,
        persist: {},
        horizon: 'swing',
        regime: 'neutral',
        minScoreDisplay100: Number.isFinite(min) ? min : 55,
        respectVetoNewLong: true,
        maxCandidates: 25,
        execute: wantExecute,
        executionPolicyId: wantExecute ? policyId || null : null,
      });
    },
    onSuccess: async (res) => {
      setResult(res.data);
      if (res.data.whitelistListId) {
        await queryClient.invalidateQueries({ queryKey: ['lists'] });
      }
    },
  });

  const eligible =
    result?.propose?.candidates.filter((c) => c.status === 'eligible') ?? [];

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">Universo fuente</span>
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
          <span className="text-muted-foreground">PE máx</span>
          <input
            className="h-8 w-16 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
            value={maxPe}
            onChange={(e) => setMaxPe(e.target.value)}
          />
        </label>
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">ROE % mín</span>
          <input
            className="h-8 w-16 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
            value={minRoe}
            onChange={(e) => setMinRoe(e.target.value)}
          />
        </label>
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">Piot. mín</span>
          <input
            className="h-8 w-14 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
            value={minPiotroski}
            onChange={(e) => setMinPiotroski(e.target.value)}
          />
        </label>
        <label className="grid gap-1 text-[11px]">
          <span className="text-muted-foreground">Composite mín</span>
          <input
            className="h-8 w-16 rounded-md border border-border/60 bg-background px-2 text-xs tabular-nums"
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
          Execute
        </label>
        {wantExecute ? (
          <label className="grid gap-1 text-[11px]">
            <span className="text-muted-foreground">Política</span>
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
          disabled={!listId || !gate || mutation.isPending || (wantExecute && !policyId)}
          onClick={() => mutation.mutate()}
        >
          <CalendarClock className={cn('h-3.5 w-3.5', mutation.isPending && 'animate-pulse')} />
          {mutation.isPending ? '…' : 'Correr FA→D'}
        </Button>
      </div>

      <p className="text-[10px] text-muted-foreground">
        Manual: Screener FA + whitelist + Paper D. Cron: <code>FA_WEEKLY_CRON_ENABLED=1</code>{' '}
        + <code>FA_WEEKLY_UNIVERSE_LIST_ID</code>. Execute: <code>PAPER_D_EXECUTE=1</code>.
      </p>

      {mutation.isError ? (
        <p className="text-[11px] text-destructive">
          {(mutation.error as Error)?.message || 'Error en pipeline FA→D'}
        </p>
      ) : null}

      {result ? (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            {result.weekKey} · {result.status} · hits {result.screener.hitCount}
            {result.whitelistListId
              ? ` · whitelist ${result.whitelistListId.slice(0, 8)}…`
              : ''}
            {result.propose
              ? ` · elegibles ${result.propose.eligibleCount} · ${result.propose.executeStatus}`
              : ''}
          </p>
          {eligible.length > 0 ? (
            <ul className="space-y-1 text-[11px]">
              {eligible.map((c) => (
                <li
                  key={c.instrumentId}
                  className="flex flex-wrap justify-between gap-2 rounded-md border border-border/50 px-2 py-1"
                >
                  <span className="font-medium">{c.ticker}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {c.scoreDisplay100 ?? '—'}/100
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          {result.notes[0] ? (
            <p className="text-[10px] italic text-muted-foreground">{result.notes[0]}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
