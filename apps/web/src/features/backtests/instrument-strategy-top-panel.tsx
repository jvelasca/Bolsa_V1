/**
 * Panel / badge InstrumentStrategyTop (Finalistas por valor).
 *
 * CTAs por slot (2026-07-29 / 07-31):
 * - **Usar** — cargar estrategia en Probar
 * - **Checklist** — si hay `runId`: Detalle + checklist pre-demo (Camino A)
 * - **Proponer** — si TOP `lab_validated`: FA+perfil → cola F3 (Camino C)
 * - **Rastreador** — crea TrackerDefinition (Camino B) → Screeners
 *
 * Copy: `PAPER_PATH_LAB` / `PAPER_PATH_SUPERVISED` / `PAPER_PATH_RADAR`.
 * Premisa: deploy → cuenta activa DEMO.
 *
 * @see docs/engineering/backtesting-funnel-handoff-2026-07-29.md
 * @see docs/engineering/research-radar-unification-2026-07-31.md
 */

import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { InstrumentStrategyTopV1 } from '@bolsa/shared';
import { api } from '@/lib/api';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatPct } from '@/features/charts/chart-utils';
import {
  PAPER_PATH_LAB,
  PAPER_PATH_RADAR,
  PAPER_PATH_SUPERVISED,
} from '@/features/settings/paper-paths-copy';
import { activeTopProfileMismatch } from '@/features/backtests/coach-profile-policy';
import { libraryHrefForSavedStrategy } from '@/features/backtests/library-nav';
import { clearLocalFreshnessFingerprint } from '@/features/backtests/backtest-finalists-freshness';
import {
  buildTrackerFromFinalistSlot,
  screenersHrefAfterTrackerCreate,
} from '@/features/backtests/promote-finalist-to-tracker';
import { useAlertsStore } from '@/stores/alerts-store';
import {
  effectiveDiaD,
  isDiaDInPast,
  todayIsoDate,
} from '@/features/backtests/backtest-period';
import { loadBacktestRunContext } from '@/features/backtests/backtest-run-context';
import { useDiaDTradingSessionStore } from '@/stores/dia-d-trading-session-store';
import {
  diaDVerifyHref,
  VERIFY_DIA_D_CTA,
} from '@/features/platform/product-universe';
import { setAdoption } from '@/features/platform/strategy-adoption';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import {
  getDiaDExperimentTop,
  getDiaDExperimentTop1,
} from '@/features/backtests/dia-d-experiment-top';
import { sanitizeTopSlotsStrategyTypes } from '@/features/backtests/instrument-top-strategy-type';
import {
  finalistsStabilityWarnTitle,
  formatFinalistsStabilityBadge,
  readLabEvidenceFromCoachFacts,
} from '@/features/backtests/finalists-stability-summary';
/** Deep-link hub → foco Finalistas del valor. */
export function instrumentTopBacktestsHref(instrumentId: string, timeframe = '1d'): string {
  const params = new URLSearchParams({
    tab: 'run',
    instrumentId,
    focus: 'finalists',
    timeframe,
  });
  return `/backtests?${params.toString()}`;
}

/** Acción Usar / Checklist desde un slot Finalistas. */
export type FinalistSlotUse = {
  strategyDefinitionId: string;
  runId?: string | null;
  label: string;
  rank: number;
};

export function InstrumentStrategyTopBadge({
  instrumentId,
  timeframe = '1d',
  className,
}: {
  instrumentId: string;
  timeframe?: string;
  className?: string;
}) {
  const query = useQuery({
    queryKey: ['instrument-strategy-top', instrumentId, timeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId, timeframe),
    staleTime: 60_000,
    retry: false,
  });
  const top = query.data?.data;
  if (!top || top.slots.length === 0) return null;

  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-xs',
        top.status === 'active'
          ? 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-200'
          : 'bg-amber-500/15 text-amber-900 dark:text-amber-200',
        className,
      )}
      title={`${top.slots.length} estrategias · ${top.status} · v${top.version}`}
    >
      TOP {top.slots.length} · {top.status}
    </span>
  );
}

function SlotRow({
  slot,
  onUse,
  onOpenChecklist,
  onProposeSupervised,
  proposePending,
  onCreateTracker,
  trackerPending,
  onSimulateDiaD,
  diaDActive,
}: {
  slot: InstrumentStrategyTopV1['slots'][number];
  onUse?: (use: FinalistSlotUse) => void;
  onOpenChecklist?: (use: FinalistSlotUse) => void;
  onProposeSupervised?: (use: FinalistSlotUse) => void;
  proposePending?: boolean;
  onCreateTracker?: (use: FinalistSlotUse) => void;
  trackerPending?: boolean;
  onSimulateDiaD?: (use: FinalistSlotUse) => void;
  diaDActive?: boolean;
}) {
  const strategyId = slot.strategyDefinitionId;
  if (!strategyId) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/70 bg-background/70 px-2.5 py-2 text-sm">
        <div className="min-w-0">
          <p className="font-medium text-foreground">
            #{slot.rank} {slot.label}
          </p>
          <p className="text-[11px] text-muted-foreground">sin estrategia guardada</p>
        </div>
      </div>
    );
  }

  const usePayload: FinalistSlotUse = {
    strategyDefinitionId: strategyId,
    runId: slot.runId,
    label: slot.label,
    rank: slot.rank,
  };
  const canChecklist = Boolean(slot.runId && onOpenChecklist);
  const canPropose = Boolean(onProposeSupervised);
  const canTracker = Boolean(onCreateTracker);
  const canDiaD =
    Boolean(onSimulateDiaD && diaDActive && strategyId) && slot.rank === 1;

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/70 bg-background/70 px-2.5 py-2 text-sm">
      <div className="min-w-0">
        <p className="font-medium text-foreground">
          #{slot.rank} {slot.label}
          {slot.stars > 0 ? (
            <span className="ml-1.5 text-[11px] text-amber-700 dark:text-amber-300">
              {'★'.repeat(Math.min(5, slot.stars))}
            </span>
          ) : null}
        </p>
        <p className="text-[11px] text-muted-foreground">
          {slot.source}
          {slot.totalReturnPct != null ? ` · ret ${formatPct(slot.totalReturnPct)}` : ''}
          {slot.maxDrawdownPct != null ? ` · DD ${formatPct(slot.maxDrawdownPct)}` : ''}
          {slot.runId ? ' · con resultado' : ''}
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {canDiaD ? (
          <Button
            type="button"
            size="sm"
            variant="default"
            className="h-7 text-[11px]"
            title="Verificar D→hoy en LAB (Análisis técnico · Cartera LAB · Manual/Semi/Auto)"
            onClick={() => onSimulateDiaD!(usePayload)}
          >
            {VERIFY_DIA_D_CTA}
          </Button>
        ) : null}
        {canPropose ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="h-7 text-[11px]"
            disabled={proposePending}
            title={PAPER_PATH_SUPERVISED.blurb}
            onClick={() => onProposeSupervised!(usePayload)}
          >
            {proposePending ? '…' : PAPER_PATH_SUPERVISED.cta}
          </Button>
        ) : null}
        {canChecklist ? (
          <Button
            type="button"
            size="sm"
            variant="default"
            className="h-7 text-[11px]"
            title={`${PAPER_PATH_LAB.checklistTitle}: abrir run y checklist (camino Lab → demo)`}
            onClick={() => onOpenChecklist!(usePayload)}
          >
            Checklist
          </Button>
        ) : null}
        {canTracker ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 text-[11px]"
            disabled={trackerPending}
            title={PAPER_PATH_RADAR.finalistsHint}
            onClick={() => onCreateTracker!(usePayload)}
          >
            {trackerPending ? '…' : PAPER_PATH_RADAR.cta}
          </Button>
        ) : null}
        {onUse ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 text-[11px]"
            title={
              slot.runId
                ? 'Seleccionar estrategia (y abrir resultado si hay run)'
                : 'Seleccionar estrategia en el wizard'
            }
            onClick={() => onUse(usePayload)}
          >
            Usar
          </Button>
        ) : null}
        <Link
          to={libraryHrefForSavedStrategy(strategyId)}
          className={cn(
            buttonVariants({ variant: 'ghost', size: 'sm' }),
            'h-7 text-[11px]',
          )}
          title="Abrir en Biblioteca (ver, renombrar, eliminar…)"
        >
          Biblio
        </Link>
      </div>
    </div>
  );
}

type PanelProps = {
  instrumentId: string;
  symbol?: string | null;
  timeframe?: string;
  /** Preloaded top (skips fetch when provided). */
  top?: InstrumentStrategyTopV1 | null;
  compact?: boolean;
  /**
   * Usar estrategia. Segundo arg (slot) incluye runId cuando existe.
   * Firma amplia: acepta callbacks legacy `(id: string) => void`.
   */
  onUseStrategy?: (strategyDefinitionId: string, slot?: FinalistSlotUse) => void;
  /** Abrir run del slot + checklist pre-demo (Camino A). */
  onOpenChecklist?: (slot: FinalistSlotUse) => void;
  /** Camino C: propose FA+perfil → cola Supervisado F3. */
  onProposeSupervised?: (slot: FinalistSlotUse) => void;
  proposePendingStrategyId?: string | null;
  /** Cuando ya estás en Finalistas del hub: ir al Coach (evita link no-op). */
  onGoToCoach?: () => void;
  /** CORE-P: perfil activo — aviso si Finalistas se guardaron con otro. */
  activeProfileId?: string | null;
  /** Hoy simulado (DÍA D). Si no se pasa, se lee del run context. */
  asOfDiaD?: string | null;
  className?: string;
};

export function InstrumentStrategyTopPanel({
  instrumentId,
  symbol,
  timeframe = '1d',
  top: topProp,
  compact,
  onUseStrategy,
  onOpenChecklist,
  onProposeSupervised,
  proposePendingStrategyId = null,
  onGoToCoach,
  activeProfileId = null,
  asOfDiaD = null,
  /** Lista opcional: el rastreador vigila toda la lista en vez del solo ticker. */
  trackerListId = null,
  className,
}: PanelProps & { trackerListId?: string | null }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enterDiaDSession = useDiaDTradingSessionStore((s) => s.enterSession);
  const { effectiveAccountId } = useActiveAccount();
  const diaD = asOfDiaD ?? loadBacktestRunContext().diaD;
  const diaDActive = isDiaDInPast(diaD);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [trackerPendingRank, setTrackerPendingRank] = useState<number | null>(null);
  const query = useQuery({
    queryKey: ['instrument-strategy-top', instrumentId, timeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId, timeframe),
    enabled: topProp !== undefined ? false : Boolean(instrumentId),
    staleTime: 30_000,
    retry: false,
  });
  const top = topProp !== undefined ? topProp : (query.data?.data ?? null);
  const experimentAsOf = diaDActive ? effectiveDiaD(diaD) : null;
  const experimentTop = experimentAsOf
    ? getDiaDExperimentTop(instrumentId, timeframe, experimentAsOf)
    : null;
  const experimentTop1 = experimentAsOf
    ? getDiaDExperimentTop1(instrumentId, timeframe, experimentAsOf)
    : null;

  const strategiesQuery = useQuery({
    queryKey: ['strategies'],
    queryFn: () => api.getStrategies(),
    staleTime: 60_000,
  });

  const repairedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!top?.slots?.length || topProp !== undefined) return;
    if (!strategiesQuery.data?.data) return;
    const key = `${instrumentId}:${timeframe}:${top.version ?? 0}`;
    if (repairedRef.current === key) return;
    const presetById = new Map(
      strategiesQuery.data.data.map((s) => [s.id, s.presetKey ?? null]),
    );
    const sanitized = sanitizeTopSlotsStrategyTypes(top.slots, presetById);
    const changed = sanitized.some(
      (s, i) => s.strategyType !== top.slots[i]?.strategyType,
    );
    if (!changed) {
      repairedRef.current = key;
      return;
    }
    repairedRef.current = key;
    void api
      .upsertInstrumentStrategyTop(instrumentId, {
        instrumentId,
        symbol: top.symbol ?? undefined,
        timeframe: top.timeframe || timeframe,
        periodLabel: top.periodLabel ?? null,
        status: top.status,
        evidenceLevel: top.evidenceLevel,
        slots: sanitized,
        coachHeadline: top.coachHeadline ?? null,
        coachFacts: (top.coachFacts as Record<string, unknown> | null) ?? null,
      })
      .then(() => {
        void queryClient.invalidateQueries({
          queryKey: ['instrument-strategy-top', instrumentId, timeframe],
        });
        void queryClient.invalidateQueries({
          queryKey: ['instrument-strategy-tops-batch'],
        });
        pushToast('Finalistas: tipos de estrategia alineados con la definición');
      })
      .catch(() => {
        repairedRef.current = null;
      });
  }, [
    top,
    topProp,
    strategiesQuery.data?.data,
    instrumentId,
    timeframe,
    queryClient,
    pushToast,
  ]);

  const createTrackerMutation = useMutation({
    mutationFn: async (slotUse: FinalistSlotUse) => {
      const slot = top?.slots.find(
        (s) => s.rank === slotUse.rank && s.strategyDefinitionId === slotUse.strategyDefinitionId,
      );
      if (!slot) throw new Error('Slot no encontrado en Finalistas');
      const policiesRes = await api.getExecutionPolicies(true);
      const built = buildTrackerFromFinalistSlot({
        instrumentId,
        symbol,
        timeframe: top?.timeframe ?? timeframe,
        slot,
        topVersion: top?.version,
        scheduleKind: 'manual',
        listId: trackerListId,
        alarmPolicies: (policiesRes.data ?? []).map((p) => ({
          id: p.id,
          mode: p.mode,
          enabled: p.enabled,
        })),
      });
      if (!built.ok) throw new Error(built.error);
      const res = await api.createTracker(built.dto);
      return res.data;
    },
    onMutate: (slotUse) => {
      setTrackerPendingRank(slotUse.rank);
    },
    onSuccess: (detail) => {
      void queryClient.invalidateQueries({ queryKey: ['trackers'] });
      pushToast(
        `${PAPER_PATH_RADAR.cta} creado: ${detail.name}. Abre Screeners para escanear / programar.`,
      );
      navigate(screenersHrefAfterTrackerCreate(detail.id));
    },
    onError: (err: Error) => {
      pushToast(`Rastreador: ${err.message}`);
    },
    onSettled: () => {
      setTrackerPendingRank(null);
    },
  });

  async function handleDeleteFinalists() {
    if (!instrumentId || deleting) return;
    const ok = window.confirm(
      `¿Eliminar Finalistas (TOP) de ${symbol ?? 'este valor'}?\n\nEl próximo Play / Lista AUTO volverá a analizarlo.`,
    );
    if (!ok) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteInstrumentStrategyTop(instrumentId, timeframe);
      clearLocalFreshnessFingerprint(instrumentId, timeframe);
      queryClient.setQueryData(
        ['instrument-strategy-top', instrumentId, timeframe],
        { data: null },
      );
      await queryClient.invalidateQueries({
        queryKey: ['instrument-strategy-top', instrumentId, timeframe],
      });
      await queryClient.invalidateQueries({
        queryKey: ['instrument-strategy-tops-batch'],
      });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'No se pudo eliminar el TOP');
    } finally {
      setDeleting(false);
    }
  }
  const href = instrumentTopBacktestsHref(instrumentId, timeframe);
  const stampedProfileId = (() => {
    const facts = top?.coachFacts as Record<string, unknown> | null | undefined;
    return typeof facts?.profileId === 'string' ? facts.profileId : null;
  })();
  const profileWarn = activeTopProfileMismatch({
    topStatus: top?.status,
    stampedProfileId,
    activeProfileId,
  });

  if (query.isLoading && topProp === undefined) {
    return (
      <p className={cn('text-sm text-muted-foreground', className)}>Cargando TOP del valor…</p>
    );
  }

  if (!top || top.slots.length === 0) {
    return (
      <div className={cn('rounded-lg border border-dashed border-border px-3 py-3 text-sm', className)}>
        <p className="font-medium text-foreground">
          {symbol ? `Sin Finalistas · ${symbol}` : 'Sin Finalistas'}
        </p>
        <p className="mt-1 text-muted-foreground">
          Aún no hay TOP guardado. Ruta corta: Play (ciclo ON) → Coach → Lab → Coach² → Finalistas
          (solo con mejora Lab). Alternativa: Coach → Guardar TOP-3 (semifinal) o Lab → Reanalizar →
          Guardar Finalistas.
        </p>
        {onGoToCoach ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-2"
            onClick={onGoToCoach}
          >
            Ir al Coach
          </Button>
        ) : (
          <Link to={href} className="mt-2 inline-block text-xs font-medium text-primary hover:underline">
            Abrir Finalistas en Backtests
          </Link>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'space-y-2 rounded-lg border border-border bg-muted/15 px-3 py-3',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">
            {symbol
              ? `${top.slots.length} estrategias de ${symbol}`
              : `TOP · ${top.slots.length} estrategias`}
          </p>
          <p
            className="text-[11px] text-muted-foreground"
            title={
              finalistsStabilityWarnTitle(
                readLabEvidenceFromCoachFacts(
                  top.coachFacts as Record<string, unknown> | null | undefined,
                ),
              ) ?? undefined
            }
          >
            {top.status} · v{top.version} · TF {top.timeframe}
            {(() => {
              const snap = readLabEvidenceFromCoachFacts(
                top.coachFacts as Record<string, unknown> | null | undefined,
              );
              const badge = formatFinalistsStabilityBadge(snap);
              if (badge) return ` · ${badge}`;
              return top.evidenceLevel === 'lab_validated' ? ' · lab OOS' : ' · in-sample';
            })()}
            {diaDActive ? ` · DÍA D ${effectiveDiaD(diaD)} (F-hoy intacto)` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 text-[11px] text-destructive hover:text-destructive"
            disabled={deleting}
            title="Borra el TOP del valor (no las estrategias de Biblioteca). Invalida Omitido en Lista AUTO."
            onClick={() => void handleDeleteFinalists()}
          >
            {deleting ? 'Eliminando…' : 'Eliminar Finalistas'}
          </Button>
          <Link
            to={href}
            className="text-[11px] font-medium text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            Ver en Backtests
          </Link>
        </div>
      </div>
      {deleteError ? (
        <p className="text-[11px] text-destructive" role="alert">
          {deleteError}
        </p>
      ) : null}
      {diaDActive && experimentTop ? (
        <p
          className="rounded-md border border-sky-600/30 bg-sky-500/10 px-2 py-1.5 text-[11px] text-sky-950 dark:text-sky-50"
          role="status"
        >
          Experimento F-D ({experimentAsOf}): {experimentTop.slots.length} slot(s)
          {experimentTop1 ? ` · #1 ${experimentTop1.label}` : ''}. Verificar usa F-D; Finalistas
          operativos (arriba) no se pisan.
        </p>
      ) : diaDActive ? (
        <p
          className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-950 dark:text-amber-50"
          role="status"
        >
          DÍA D activo: Play guardará un TOP experimento (F-D) sin pisar Finalistas operativos.
          Luego Verificar D→hoy.
        </p>
      ) : null}
      {profileWarn.mismatch && profileWarn.message ? (
        <p
          className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-[11px] leading-snug text-amber-950 dark:text-amber-50"
          role="status"
        >
          {profileWarn.message}
        </p>
      ) : null}
      {diaDActive ? (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-[11px] leading-snug text-amber-950 dark:text-amber-50">
          Embudo as-of · DÍA D {effectiveDiaD(diaD)}. La #1 puede abrir{' '}
          <strong>Verificar D→hoy</strong> en LAB (Cartera LAB · Manual / Semi / Auto).
        </p>
      ) : null}
      {onOpenChecklist && top.evidenceLevel === 'lab_validated' ? (
        <p className="text-[11px] leading-snug text-muted-foreground">
          {PAPER_PATH_LAB.finalistsHint}
        </p>
      ) : null}
      {onProposeSupervised && top.evidenceLevel === 'lab_validated' ? (
        <p className="text-[11px] leading-snug text-muted-foreground">
          {PAPER_PATH_SUPERVISED.finalistsHint}
        </p>
      ) : null}
      <p className="text-[11px] leading-snug text-muted-foreground">
        {PAPER_PATH_RADAR.finalistsHint}
      </p>
      <div className={cn('space-y-1.5', compact && 'max-h-48 overflow-auto')}>
        {top.slots
          .slice()
          .sort((a, b) => a.rank - b.rank)
          .map((slot) => (
            <SlotRow
              key={`${slot.rank}-${slot.label}`}
              slot={slot}
              onUse={
                onUseStrategy
                  ? (use) => onUseStrategy(use.strategyDefinitionId, use)
                  : undefined
              }
              onOpenChecklist={onOpenChecklist}
              onProposeSupervised={
                onProposeSupervised && top.evidenceLevel === 'lab_validated'
                  ? onProposeSupervised
                  : undefined
              }
              proposePending={
                Boolean(
                  proposePendingStrategyId &&
                    slot.strategyDefinitionId === proposePendingStrategyId,
                )
              }
              onCreateTracker={(use) => createTrackerMutation.mutate(use)}
              trackerPending={trackerPendingRank === slot.rank}
              diaDActive={diaDActive}
              onSimulateDiaD={(use) => {
                const sym = symbol?.trim() || instrumentId.slice(0, 8);
                const fromExp =
                  experimentTop1?.strategyDefinitionId
                    ? {
                        strategyDefinitionId: experimentTop1.strategyDefinitionId,
                        strategyLabel: experimentTop1.label,
                        rank: experimentTop1.rank,
                      }
                    : null;
                enterDiaDSession({
                  instrumentId,
                  symbol: sym,
                  strategyDefinitionId:
                    fromExp?.strategyDefinitionId ?? use.strategyDefinitionId,
                  strategyLabel: fromExp?.strategyLabel ?? use.label,
                  rank: fromExp?.rank ?? use.rank,
                  diaD: effectiveDiaD(diaD),
                  endDate: todayIsoDate(),
                  mode: 'auto',
                });
                if (effectiveAccountId) {
                  setAdoption({
                    instrumentId,
                    accountId: effectiveAccountId,
                    state: 'candidata',
                    strategyDefinitionId:
                      fromExp?.strategyDefinitionId ?? use.strategyDefinitionId,
                    strategyLabel: fromExp?.strategyLabel ?? use.label,
                    timeframe,
                  });
                }
                navigate(diaDVerifyHref(instrumentId));
                pushToast(
                  fromExp
                    ? `LAB · Verificar ${effectiveDiaD(diaD)} → hoy · F-D #1 (experimento)`
                    : `LAB · Verificar ${effectiveDiaD(diaD)} → hoy · Auto (Cartera LAB)`,
                );
              }}
            />
          ))}
      </div>
    </div>
  );
}
