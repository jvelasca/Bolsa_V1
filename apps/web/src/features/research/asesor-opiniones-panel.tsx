/**
 * Bandeja Opiniones de hoy — Estudio → Asesor.
 * Canales AVISO | ALARMA (§5.2) derivados del dictamen; SEMI propone desde Alarma.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  INSTRUMENT_DAILY_OPINION_STANCE_LABELS,
  OPINION_CHANNEL_LEVEL_LABELS,
  OPINION_CHANNEL_MAP_LEGEND,
  buildOpinionChannelItems,
  mapOpinionToChannel,
  type InstrumentDailyOpinionHintV1,
  type OpinionChannelItemV1,
} from '@bolsa/shared';
import { api } from '@/lib/api';
import {
  opinionByInstrumentId,
  useInstrumentDailyOpinions,
} from '@/features/trading/use-instrument-daily-opinions';
import { useInstrumentsHubScores } from '@/features/instruments/use-instruments-hub-scores';
import { computeIndiceOperativo } from '@/features/trading/operativa-index';
import { proposeInstrumentSupervised } from '@/features/trading/propose-instrument-supervised';
import {
  demoBookAllowsEnqueueConfirm,
} from '@/features/trading/demo-book-prefs';
import { useDemoBookPrefs } from '@/features/trading/use-demo-book-prefs';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { useVisualizationStore } from '@/stores/visualization-store';
import { useAlertsStore } from '@/stores/alerts-store';
import { useNotificationPrefsStore } from '@/stores/notification-prefs-store';
import {
  openHelpAiPlatform,
  useSupervisedF3QueueStore,
} from '@/stores/supervised-f3-queue-store';
import { cn } from '@/lib/utils';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

function pctLabel(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(0)}%`;
}

type ChannelFilter = 'todas' | 'alarma' | 'aviso';

export function AsesorOpinionesPanel({ className }: { className?: string }) {
  const [filter, setFilter] = useState<ChannelFilter>('todas');
  const [showMap, setShowMap] = useState(false);
  const bookPrefs = useDemoBookPrefs();
  const canEnqueue = demoBookAllowsEnqueueConfirm(bookPrefs.mode);
  const { effectiveAccountId } = useActiveAccount();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const notifyEmail = useNotificationPrefsStore((s) => s.alarmaEmail);
  const notifyEmailEnabled = useNotificationPrefsStore((s) => s.alarmaEmailEnabled);
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);

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
  const telemetryQuery = useQuery({
    queryKey: ['instrument-daily-opinions-telemetry', studyIds],
    queryFn: () =>
      api.getInstrumentDailyOpinionTelemetry({
        lookbackDays: 90,
        instrumentIds: studyIds.length > 0 ? studyIds : undefined,
      }),
    staleTime: 60_000,
  });
  const byId = useMemo(
    () => opinionByInstrumentId(opinionsQuery.data),
    [opinionsQuery.data],
  );

  const channelItems = useMemo(() => {
    const rows = studyIds
      .map((id) => {
        const opinion = byId.get(id);
        if (!opinion) return null;
        return { opinion, symbol: symbolById.get(id) ?? id.slice(0, 8) };
      })
      .filter(Boolean) as Array<{
      opinion: NonNullable<ReturnType<typeof byId.get>>;
      symbol: string;
    }>;
    return buildOpinionChannelItems(rows);
  }, [studyIds, byId, symbolById]);

  const silentCount = useMemo(() => {
    let n = 0;
    for (const id of studyIds) {
      const op = byId.get(id);
      if (!op) continue;
      if (mapOpinionToChannel(op) === 'silent') n += 1;
    }
    return n;
  }, [studyIds, byId]);

  const filtered = useMemo(() => {
    if (filter === 'todas') return channelItems;
    return channelItems.filter((i) => i.level === filter);
  }, [channelItems, filter]);

  const alarmaCount = channelItems.filter((i) => i.level === 'alarma').length;
  const avisoCount = channelItems.filter((i) => i.level === 'aviso').length;

  const proposeMutation = useMutation({
    mutationFn: async (item: OpinionChannelItemV1) => {
      if (!effectiveAccountId) throw new Error('Sin cuenta DEMO activa');
      return proposeInstrumentSupervised({
        instrumentId: item.instrumentId,
        symbol: item.symbol,
        accountId: effectiveAccountId,
        source: 'asesor_alarma',
      });
    },
    onSuccess: (payload, item) => {
      const id = enqueue(payload, {
        symbol: payload.symbol ?? item.symbol,
        origin: 'asesor',
      });
      setActive(id);
      pushToast(`Alarma · ${item.symbol}: ${payload.action} → Confirm`);
      openHelpAiPlatform({ panel: 'supervised-f3' });
    },
    onError: (e: Error) => {
      pushToast(`Alarma · ${e.message}`);
    },
  });

  return (
    <div className={cn('space-y-4', className)} data-testid="asesor-opiniones">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Opiniones de hoy</CardTitle>
          <CardDescription>
            Dictamen Estudio → canal AVISO (info) / ALARMA (accionable en SEMI). ★ dictamen ≠ ★ TOP.
            Toast alarma en app · email tras EOD solo si flag SMTP.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {telemetryQuery.data?.data ? (
            <div
              className="rounded-md border border-border/80 bg-muted/15 px-3 py-2 text-xs"
              data-testid="asesor-opinion-telemetry"
              title={telemetryQuery.data.data.caveats.join(' · ')}
            >
              <p className="font-medium text-foreground">Telemetría A0 (90d · Estudio)</p>
              <p className="mt-1 tabular-nums text-muted-foreground">
                {telemetryQuery.data.data.daysWithOpinions} días ·{' '}
                {telemetryQuery.data.data.alarmaBuyCount} BUY-alarma · prec.5d{' '}
                {pctLabel(telemetryQuery.data.data.buyPrecision5d)} · recall≈{' '}
                {pctLabel(telemetryQuery.data.data.buyRecall5d)} · n=
                {telemetryQuery.data.data.matureBuySample}
              </p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">
                Thaw P3≥70% / P4≥55% — sin flip AUTO. Proxy Outcomes {telemetryQuery.data.data.criteriaVersion}.
              </p>
            </div>
          ) : telemetryQuery.isError ? (
            <p className="text-xs text-muted-foreground">Telemetría A0 no disponible.</p>
          ) : null}

          <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Canal">
            {(
              [
                ['todas', `Todas (${channelItems.length})`],
                ['alarma', `Alarmas (${alarmaCount})`],
                ['aviso', `Avisos (${avisoCount})`],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={filter === id}
                className={cn(
                  'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                  filter === id
                    ? 'border-primary/50 bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-accent',
                )}
                onClick={() => setFilter(id)}
              >
                {label}
              </button>
            ))}
            <button
              type="button"
              className={cn(
                'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                showMap
                  ? 'border-primary/50 bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:bg-accent',
              )}
              aria-expanded={showMap}
              onClick={() => setShowMap((v) => !v)}
            >
              Mapa canales
            </button>
          </div>

          {showMap ? (
            <div
              className="overflow-x-auto rounded-md border border-border text-xs"
              data-testid="asesor-channel-map-legend"
            >
              <table className="w-full min-w-[28rem] text-left">
                <thead className="bg-muted/40 text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1.5 font-medium">Stance</th>
                    <th className="px-2 py-1.5 font-medium">★</th>
                    <th className="px-2 py-1.5 font-medium">Canal</th>
                    <th className="px-2 py-1.5 font-medium">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {OPINION_CHANNEL_MAP_LEGEND.map((row) => (
                    <tr
                      key={`${row.stance}-${row.stars}-${row.level}`}
                      className="border-t border-border/70"
                    >
                      <td className="px-2 py-1">
                        {INSTRUMENT_DAILY_OPINION_STANCE_LABELS[row.stance]}
                      </td>
                      <td className="px-2 py-1 tabular-nums">{row.stars}</td>
                      <td className="px-2 py-1">{OPINION_CHANNEL_LEVEL_LABELS[row.level]}</td>
                      <td className="px-2 py-1 text-muted-foreground">{row.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="border-t border-border px-2 py-1.5 text-[10px] text-muted-foreground">
                Mapa fijo §5.2 (`opinion-channel-map`). Correo de Alarmas: menú usuario → Notificaciones.
                SMS aparcado.
              </p>
            </div>
          ) : null}

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
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {channelItems.length === 0
                ? `Sin avisos ni alarmas (${silentCount} en silencio · hold/no_trade).`
                : 'Nada en este filtro.'}
            </p>
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border">
              {filtered.map((item) => (
                <li
                  key={item.opinionId}
                  className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                  data-testid={`asesor-channel-${item.level}`}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to="/"
                        className="font-medium text-foreground hover:underline"
                        title="Abrir Trading"
                      >
                        {item.symbol}
                      </Link>
                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                          item.level === 'alarma'
                            ? 'bg-rose-500/15 text-rose-800 dark:text-rose-200'
                            : 'bg-amber-500/15 text-amber-900 dark:text-amber-100',
                        )}
                      >
                        {OPINION_CHANNEL_LEVEL_LABELS[item.level]}
                      </span>
                    </div>
                    <p
                      className="truncate text-xs text-muted-foreground"
                      title={item.reasons.join(', ')}
                    >
                      {INSTRUMENT_DAILY_OPINION_STANCE_LABELS[item.stance]}
                      {item.reasons.length
                        ? ` · ${item.reasons.slice(0, 2).join(' · ')}`
                        : ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 tabular-nums text-xs">
                    <span>★{item.dictamenStars}</span>
                    {item.strategyStars != null ? (
                      <span className="text-muted-foreground">TOP {item.strategyStars}</span>
                    ) : null}
                    {item.ioScore != null ? (
                      <span className="text-muted-foreground">IO {Math.round(item.ioScore)}</span>
                    ) : null}
                    {item.actionable ? (
                      <button
                        type="button"
                        className={cn(
                          buttonVariants({ variant: 'outline', size: 'sm' }),
                          'h-7 text-[10px]',
                        )}
                        disabled={
                          proposeMutation.isPending || !canEnqueue || !effectiveAccountId
                        }
                        title={
                          !canEnqueue
                            ? 'Pasa a SEMI en Operativa → Configuración'
                            : 'Proponer F3 → Confirm'
                        }
                        onClick={() => proposeMutation.mutate(item)}
                      >
                        {!canEnqueue ? 'SEMI para actuar' : 'Proponer F3'}
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted-foreground">
            {studyIds.length} Estudio · {alarmaCount} alarmas · {avisoCount} avisos
            {silentCount > 0 ? ` · ${silentCount} silencio` : ''}
            {opinionsQuery.data?.[0]?.asOfBarDate
              ? ` · asOf ${opinionsQuery.data[0].asOfBarDate}`
              : ''}
          </p>
          {studyIds.length > 0 ? (
            <button
              type="button"
              className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'h-7 text-[10px]')}
              disabled={opinionsQuery.isFetching}
              title="POST eod-batch con force=true (flag ESTUDIO_EOD_OPINION_ENABLED sigue off)"
              onClick={() => {
                void api
                  .runInstrumentDailyOpinionEodBatch({
                    instrumentIds: studyIds,
                    force: true,
                    notifyEmail: notifyEmail.trim() || null,
                    notifyEmailEnabled,
                  })
                  .then((res) => {
                    void opinionsQuery.refetch();
                    const n = res.count ?? 0;
                    const email = res.emailNotify;
                    let msg = `EOD batch · ${n} dictamen${n === 1 ? '' : 'es'}`;
                    if (email) {
                      if (email.sent) {
                        msg += ` · email ${email.alarmaCount} alarma(s)`;
                      } else if (email.skippedReason) {
                        msg += ` · email skip (${email.skippedReason})`;
                      }
                    }
                    pushToast(msg);
                  })
                  .catch((e: Error) => pushToast(`EOD batch · ${e.message}`));
              }}
            >
              Recalcular EOD (manual / force)
            </button>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
