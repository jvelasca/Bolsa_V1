/**
 * Bandeja Opiniones de hoy — Estudio → Asesor (no Operativa por valor).
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  INSTRUMENT_DAILY_OPINION_STANCE_LABELS,
  type InstrumentDailyOpinionHintV1,
} from '@bolsa/shared';
import { api } from '@/lib/api';
import {
  opinionByInstrumentId,
  useInstrumentDailyOpinions,
} from '@/features/trading/use-instrument-daily-opinions';
import { useInstrumentsHubScores } from '@/features/instruments/use-instruments-hub-scores';
import { computeIndiceOperativo } from '@/features/trading/operativa-index';
import { useVisualizationStore } from '@/stores/visualization-store';
import { cn } from '@/lib/utils';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function AsesorOpinionesPanel({ className }: { className?: string }) {
  const studyEntries = useVisualizationStore((s) => s.entries);
  const studyIds = useMemo(
    () => studyEntries.map((e) => e.instrumentId),
    [studyEntries],
  );
  const symbolById = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of studyEntries) m.set(e.instrumentId, e.symbol);
    return m;
  }, [studyEntries]);

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', 'asesor-opiniones'],
    queryFn: api.getPortfolio,
    staleTime: 30_000,
  });
  const openPositionIds = useMemo(() => {
    const set = new Set<string>();
    for (const p of portfolioQuery.data?.data.positions ?? []) {
      if (Math.abs(Number(p.quantity ?? 0)) > 0) set.add(p.instrumentId);
    }
    return set;
  }, [portfolioQuery.data]);

  const { faByInstrument, taByInstrument, scoresLoading } =
    useInstrumentsHubScores(studyIds);

  const hints: InstrumentDailyOpinionHintV1[] = useMemo(
    () =>
      studyIds.map((id) => {
        const fa = faByInstrument.get(id);
        const ta = taByInstrument.get(id);
        const io = computeIndiceOperativo({
          compositeDisplay100: ta?.compositeDisplay100,
          distress: fa?.distress,
        });
        return {
          instrumentId: id,
          ioScore: io,
          faScore: fa?.scoreDisplay100 ?? null,
          taScore: ta?.technicalDisplay100 ?? null,
          distress: Boolean(fa?.distress),
          positionOpen: openPositionIds.has(id),
          allowTrading: true,
          hasEodBar: true,
        };
      }),
    [studyIds, faByInstrument, taByInstrument, openPositionIds],
  );

  const opinionsQuery = useInstrumentDailyOpinions(studyIds, hints, {
    enabled: studyIds.length > 0 && !scoresLoading,
  });
  const byId = useMemo(
    () => opinionByInstrumentId(opinionsQuery.data),
    [opinionsQuery.data],
  );

  const rows = useMemo(() => {
    return studyIds
      .map((id) => {
        const op = byId.get(id);
        if (!op) return null;
        return { id, op, symbol: symbolById.get(id) ?? id.slice(0, 8) };
      })
      .filter(Boolean) as Array<{
      id: string;
      symbol: string;
      op: NonNullable<ReturnType<typeof byId.get>>;
    }>;
  }, [studyIds, byId, symbolById]);

  const sorted = useMemo(() => {
    const order = (stance: string) => {
      if (stance === 'buy') return 0;
      if (stance === 'sell_exit' || stance === 'reduce') return 1;
      if (stance === 'review_strategy' || stance === 'no_trade') return 2;
      return 3;
    };
    return [...rows].sort(
      (a, b) =>
        order(a.op.stance) - order(b.op.stance) ||
        b.op.dictamenStars - a.op.dictamenStars,
    );
  }, [rows]);

  return (
    <div className={cn('space-y-4', className)} data-testid="asesor-opiniones">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Opiniones de hoy</CardTitle>
          <CardDescription>
            Dictámenes del universo Estudio (on-demand). ★ dictamen ≠ ★ TOP. La acción sigue en
            Operativa → Confirm (SEMI).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {studyIds.length === 0 ? (
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>Estudio vacío. Añade valores desde Trading (Listas → Pasar a Estudio).</p>
              <Link
                to="/"
                className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
              >
                Ir a Trading
              </Link>
            </div>
          ) : opinionsQuery.isLoading || scoresLoading ? (
            <p className="text-sm text-muted-foreground">Calculando dictámenes…</p>
          ) : opinionsQuery.isError ? (
            <p className="text-sm text-destructive">No se pudieron cargar las opiniones.</p>
          ) : sorted.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sin dictámenes en caché aún.</p>
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border">
              {sorted.map(({ id, symbol, op }) => (
                <li
                  key={id}
                  className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                >
                  <div className="min-w-0">
                    <Link
                      to="/"
                      className="font-medium text-foreground hover:underline"
                      title="Abrir Trading"
                    >
                      {symbol}
                    </Link>
                    <p className="truncate text-xs text-muted-foreground" title={op.reasons.join(', ')}>
                      {op.reasons.slice(0, 3).join(' · ') || '—'}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 tabular-nums text-xs">
                    <span
                      className={cn(
                        'font-medium',
                        op.stance === 'buy' && 'text-emerald-700 dark:text-emerald-300',
                        (op.stance === 'sell_exit' || op.stance === 'reduce') &&
                          'text-rose-700 dark:text-rose-300',
                      )}
                    >
                      {INSTRUMENT_DAILY_OPINION_STANCE_LABELS[op.stance]}
                    </span>
                    <span>★{op.dictamenStars}</span>
                    {op.strategyStars != null ? (
                      <span className="text-muted-foreground">TOP {op.strategyStars}</span>
                    ) : null}
                    {op.ioScore != null ? (
                      <span className="text-muted-foreground">IO {Math.round(op.ioScore)}</span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted-foreground">
            {studyIds.length} en Estudio
            {sorted.length > 0 ? ` · ${sorted.length} con dictamen` : ''}
            {opinionsQuery.data?.[0]?.asOfBarDate
              ? ` · asOf ${opinionsQuery.data[0].asOfBarDate}`
              : ''}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
