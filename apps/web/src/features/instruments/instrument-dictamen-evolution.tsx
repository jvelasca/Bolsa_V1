/**
 * Evolución del dictamen: micrográfica ★ + resumen por días.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  INSTRUMENT_DAILY_OPINION_STANCE_LABELS,
  type InstrumentDailyOpinionStance,
  type InstrumentDailyOpinionV1,
} from '@bolsa/shared';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

function stanceFill(stance: InstrumentDailyOpinionStance): string {
  switch (stance) {
    case 'buy':
      return 'fill-emerald-600';
    case 'sell_exit':
    case 'reduce':
      return 'fill-rose-600';
    case 'no_trade':
    case 'review_strategy':
      return 'fill-amber-600';
    case 'overbought':
      return 'fill-orange-500';
    default:
      return 'fill-sky-700';
  }
}

function formatDay(isoDate: string): string {
  const d = isoDate.slice(0, 10);
  const [, m, day] = d.split('-');
  return `${day}/${m}`;
}

function reasonHint(reasons: string[]): string {
  if (!reasons.length) return '';
  return reasons.slice(0, 2).join(', ');
}

/** Construye puntos SVG para sparkline de ★ dictamen (1–5). */
export function buildDictamenSparklinePath(
  rows: InstrumentDailyOpinionV1[],
  width: number,
  height: number,
  pad = 4,
): { line: string; dots: Array<{ x: number; y: number; stance: InstrumentDailyOpinionStance }> } {
  if (!rows.length) return { line: '', dots: [] };
  const w = Math.max(1, width - pad * 2);
  const h = Math.max(1, height - pad * 2);
  const n = rows.length;
  const dots = rows.map((row, i) => {
    const x = pad + (n === 1 ? w / 2 : (i / (n - 1)) * w);
    const stars = Math.min(5, Math.max(1, row.dictamenStars));
    const y = pad + h - ((stars - 1) / 4) * h;
    return { x, y, stance: row.stance };
  });
  const line = dots.map((d, i) => `${i === 0 ? 'M' : 'L'}${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' ');
  return { line, dots };
}

function DictamenSparkline({
  rows,
  className,
}: {
  rows: InstrumentDailyOpinionV1[];
  className?: string;
}) {
  const width = 220;
  const height = 44;
  const { line, dots } = useMemo(
    () => buildDictamenSparklinePath(rows, width, height),
    [rows],
  );

  if (!rows.length) {
    return (
      <p className={cn('text-[10px] text-muted-foreground', className)}>
        Sin serie aún — pulsa «Rellenar 14d».
      </p>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={cn('h-11 w-full max-w-[240px]', className)}
      role="img"
      aria-label="Evolución ★ dictamen"
      data-testid="dictamen-sparkline"
    >
      {/* bandas ★2 / ★4 */}
      <line
        x1="0"
        x2={width}
        y1={4 + ((44 - 8) * 3) / 4}
        y2={4 + ((44 - 8) * 3) / 4}
        className="stroke-border/60"
        strokeWidth="1"
        strokeDasharray="2 3"
      />
      <line
        x1="0"
        x2={width}
        y1={4 + ((44 - 8) * 1) / 4}
        y2={4 + ((44 - 8) * 1) / 4}
        className="stroke-border/40"
        strokeWidth="1"
        strokeDasharray="2 3"
      />
      {line ? (
        <path d={line} fill="none" className="stroke-foreground/70" strokeWidth="1.5" />
      ) : null}
      {dots.map((d, i) => (
        <circle
          key={`${rows[i]!.asOfBarDate}-${i}`}
          cx={d.x}
          cy={d.y}
          r={2.4}
          className={stanceFill(d.stance)}
        />
      ))}
    </svg>
  );
}

export function InstrumentDictamenEvolution({
  instrumentId,
  className,
}: {
  instrumentId: string;
  className?: string;
}) {
  const [request, setRequest] = useState({ ensureDays: 14, nonce: 0 });

  const query = useQuery({
    queryKey: [
      'instrument-daily-opinions-history',
      instrumentId,
      request.ensureDays,
      request.nonce,
    ],
    queryFn: () =>
      api.listInstrumentDailyOpinions(instrumentId, {
        days: 30,
        ensureDays: request.ensureDays,
      }),
    staleTime: 60_000,
  });

  const rows = useMemo(() => query.data?.data ?? [], [query.data?.data]);
  const newestFirst = useMemo(() => [...rows].reverse(), [rows]);
  const latest = newestFirst[0];

  return (
    <div className={cn('space-y-2', className)} data-testid="instrument-dictamen-evolution">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Dictamen · 30d
          </p>
          {latest ? (
            <p className="text-[11px] text-foreground">
              Último {formatDay(latest.asOfBarDate)} ·{' '}
              {INSTRUMENT_DAILY_OPINION_STANCE_LABELS[latest.stance]} · ★
              {latest.dictamenStars}
            </p>
          ) : query.isLoading ? (
            <p className="text-[11px] text-muted-foreground">Calculando serie…</p>
          ) : (
            <p className="text-[11px] text-muted-foreground">Sin puntos en caché</p>
          )}
        </div>
        <DictamenSparkline rows={rows} />
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[10px]"
          disabled={query.isFetching}
          onClick={() =>
            setRequest((prev) => ({ ensureDays: 14, nonce: prev.nonce + 1 }))
          }
        >
          {query.isFetching && request.ensureDays > 0 ? 'Rellenando…' : 'Rellenar 14d'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 text-[10px]"
          disabled={query.isFetching}
          onClick={() =>
            setRequest((prev) => ({ ensureDays: 0, nonce: prev.nonce + 1 }))
          }
        >
          Solo caché
        </Button>
      </div>

      {query.isError ? (
        <p className="text-[10px] text-destructive">No se pudo cargar el historial</p>
      ) : null}

      {newestFirst.length > 0 ? (
        <ul
          className="max-h-36 space-y-0.5 overflow-y-auto rounded-md border border-border/60 bg-muted/15 px-1.5 py-1"
          aria-label="Resumen por días"
        >
          {newestFirst.map((row) => (
            <li
              key={row.id}
              className="flex items-baseline gap-2 border-b border-border/30 py-0.5 text-[10px] last:border-0"
            >
              <span className="w-10 shrink-0 tabular-nums text-muted-foreground">
                {formatDay(row.asOfBarDate)}
              </span>
              <span
                className={cn(
                  'min-w-[4.5rem] font-medium',
                  row.stance === 'buy' && 'text-emerald-700 dark:text-emerald-300',
                  (row.stance === 'sell_exit' || row.stance === 'reduce') &&
                    'text-rose-700 dark:text-rose-300',
                )}
              >
                {INSTRUMENT_DAILY_OPINION_STANCE_LABELS[row.stance]}
              </span>
              <span className="shrink-0 tabular-nums">★{row.dictamenStars}</span>
              <span className="truncate text-muted-foreground" title={row.reasons.join(', ')}>
                {reasonHint(row.reasons)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <p className="text-[9px] text-muted-foreground">
        ★ dictamen ≠ ★ TOP · la serie crece al abrir Estudio / Operativa o al rellenar.
      </p>
    </div>
  );
}
