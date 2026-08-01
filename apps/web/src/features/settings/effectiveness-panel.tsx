/**
 * RFC-008 D7 — Panel Efectividad (skill vs luck + memoria + observed).
 * Vive en Ayuda → Plataforma IA (no en Configuración editable).
 */

import { useQuery } from '@tanstack/react-query';
import type { EffectivenessSummaryV1 } from '@bolsa/shared';
import { BAND_LABEL } from '@bolsa/shared';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

function BandBadge({ band }: { band: EffectivenessSummaryV1['band'] }) {
  if (!band) {
    return (
      <span className="rounded border border-border px-2 py-0.5 text-[10px] uppercase text-muted-foreground">
        Sin edge
      </span>
    );
  }
  const cls =
    band === 'skill'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
      : band === 'luck'
        ? 'border-red-500/40 bg-red-500/10 text-red-400'
        : 'border-amber-500/40 bg-amber-500/10 text-amber-400';
  return (
    <span className={cn('rounded border px-2 py-0.5 text-[10px] font-semibold uppercase', cls)}>
      {BAND_LABEL[band]}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border/70 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

export function EffectivenessPanel({ compact }: { compact?: boolean }) {
  const pgQuery = useQuery({
    queryKey: ['ai-effectiveness', 'pg'],
    queryFn: async () => (await api.getAiEffectiveness(false)).data,
    retry: 1,
  });
  const useDemo =
    pgQuery.isSuccess &&
    (pgQuery.data.status === 'insufficient_data' ||
      pgQuery.data.source === 'postgres_unavailable');
  const demoQuery = useQuery({
    queryKey: ['ai-effectiveness', 'demo'],
    queryFn: async () => (await api.getAiEffectiveness(true)).data,
    enabled: useDemo,
    retry: 1,
  });

  const data = useDemo ? demoQuery.data : pgQuery.data;
  const loading = pgQuery.isLoading || (useDemo && demoQuery.isLoading);
  const errored = pgQuery.isError && !useDemo;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Efectividad (D7)</CardTitle>
        <CardDescription>
          Skill vs luck · Decision Memory · Observed Profile. No reescribe Declared ni Policy.
          {data?.source === 'postgres' ? ' · Fuente: PostgreSQL.' : null}
          {data?.status === 'demo' || data?.source === 'demo'
            ? ' · Vista ilustrativa (sin filas PG aún).'
            : null}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <p className="text-xs text-muted-foreground">Cargando resumen…</p>
        ) : null}
        {errored ? (
          <p className="text-xs text-destructive">
            No se pudo cargar `/api/ai/effectiveness`. ¿API en marcha?
          </p>
        ) : null}
        {data ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className={cn('text-sm text-foreground', compact && 'text-xs')}>{data.headline}</p>
              <BandBadge band={data.band} />
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metric
                label="Credibility"
                value={data.credibility != null ? data.credibility.toFixed(1) : '—'}
              />
              <Metric label="Trials N" value={data.trialsN} />
              <Metric
                label="Memoria A/R/D"
                value={`${data.memory.accepted}/${data.memory.rejected}/${data.memory.deferred}`}
              />
              <Metric label="Reevaluar" value={data.memory.reevaluatePending} />
            </div>
            {data.persistence ? (
              <p className="text-[10px] text-muted-foreground">
                PG · memory {data.persistence.decisionMemoryCount} · trials{' '}
                {data.persistence.trialCount} · edge {data.persistence.edgeReportCount} · open CFS{' '}
                {data.persistence.openConfidenceStates}
              </p>
            ) : null}
            {data.observed ? (
              <div className="rounded-md border border-dashed border-border px-3 py-2 text-xs">
                <p className="font-medium text-foreground">Observed (solo lectura)</p>
                <p className="mt-1 text-muted-foreground">
                  Trades muestra: {data.observed.sampleTradeCount}
                  {data.observed.disciplineScore != null
                    ? ` · disciplina ${data.observed.disciplineScore.toFixed(2)}`
                    : ''}
                  {data.observed.impulsivityScore != null
                    ? ` · impulsividad ${data.observed.impulsivityScore.toFixed(2)}`
                    : ''}
                </p>
                <p className="mt-1 text-muted-foreground">
                  Divergencia Declared:{' '}
                  {data.observed.divergesFromDeclared ? 'sí' : 'no'} · Policy:{' '}
                  {data.observed.divergesFromPolicy ? 'sí' : 'no'}
                </p>
                {(data.observed.notes ?? []).slice(0, 2).map((n) => (
                  <p key={n} className="mt-0.5 text-muted-foreground">
                    · {n}
                  </p>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Sin Observed aún — se calculará desde operaciones (nunca escribe el cuestionario).
              </p>
            )}
            {data.notes.length > 0 ? (
              <ul className="list-inside list-disc text-[10px] text-muted-foreground">
                {data.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
