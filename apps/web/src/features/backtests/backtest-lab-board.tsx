/**
 * Tablero Lab TOP-3: hasta 3 columnas responsive.
 * Lab no escribe Finalistas → CTA «Reanalizar con Coach».
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Beaker, FlaskConical, Loader2 } from 'lucide-react';
import { BacktestOptimizePanel } from '@/features/backtests/backtest-optimize-panel';
import type {
  LabBoardZone,
  LabReanalyzeRequest,
  LabZoneHandle,
} from '@/features/backtests/backtest-lab-board-types';
import { padLabZones } from '@/features/backtests/backtest-lab-board-types';
import type { OptimizeSeed } from '@/features/backtests/backtest-optimize-seed';
import type { OptimizeBeforeAfterSnapshot } from '@/features/backtests/backtest-optimize-delta';
import { buildOptimizeBeforeAfter } from '@/features/backtests/backtest-optimize-delta';
import { BacktestOptimizeCompareCard } from '@/features/backtests/backtest-optimize-compare-card';
import {
  LabBoardActivityBanner,
  type LabZoneActivitySnapshot,
} from '@/features/backtests/lab-board-activity-banner';
import { resolveLabReanalyzeGate } from '@/features/backtests/lab-coach-handoff';
import {
  isLabZoneTerminal,
  LAB_CYCLE_WATCHDOG_MS,
  labEmptyZonesStatus,
  labNoImproveStatus,
  labWatchdogStatus,
  shouldAutoHandoffLab,
} from '@/features/backtests/backtest-assistant-full-cycle';
import { Button } from '@/components/ui/button';
import type { OptimizeSmaGridResultDto, ProfileHorizon } from '@bolsa/shared';

type Props = {
  zones: LabBoardZone[];
  instruments: Array<{ id: string; symbol: string; name: string }>;
  defaultInstrumentId?: string;
  onClearZoneSeed?: (zoneId: string) => void;
  onReanalyzeWithCoach?: (payload: LabReanalyzeRequest) => void | Promise<void>;
  /** Ciclo completo: al terminar zonas con mejora, pasa solo a Coach². */
  autoHandoff?: boolean;
  onAutoHandoffStatus?: (message: string) => void;
  /** CORE-P: techo DD blando del perfil activo. */
  maxDrawdownSoftPct?: number | null;
  /** CORE-B / CORE-P: perfil para stamp de memoria Lab. */
  profileId?: string | null;
  /** CORE-P: horizonte → hint familias Lab preferidas. */
  profileHorizon?: ProfileHorizon | null;
  /** CORE-P: riesgo → soft-bias anchura espacio Lab. */
  profileRiskTolerance?: import('@bolsa/shared').RiskTolerance | null;
};

function EmptyLabZone({ rank }: { rank: 1 | 2 | 3 }) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border/70 bg-muted/20 px-4 py-8 text-center">
      <FlaskConical className="h-7 w-7 text-muted-foreground/50" aria-hidden />
      <p className="text-sm font-medium text-muted-foreground">Zona #{rank} vacía</p>
      <p className="max-w-[220px] text-[11px] text-muted-foreground">
        Sin candidata optimizable. Pasa desde Coach (TOP con 1–3) o abre Lab en otra tarjeta.
      </p>
    </div>
  );
}

export function BacktestLabBoard({
  zones,
  instruments,
  defaultInstrumentId,
  onClearZoneSeed,
  onReanalyzeWithCoach,
  autoHandoff = false,
  onAutoHandoffStatus,
  maxDrawdownSoftPct = null,
  profileId = null,
  profileHorizon = null,
  profileRiskTolerance = null,
}: Props) {
  const padded = padLabZones(zones);
  const zoneIdsKey = zones.map((z) => z.id).join('|');
  const zoneRefs = useRef<Array<LabZoneHandle | null>>([null, null, null]);
  const [improvedCount, setImprovedCount] = useState(0);
  const [doneCount, setDoneCount] = useState(0);
  const [zoneOutcomes, setZoneOutcomes] = useState<
    Record<string, { improved: boolean; hasResult: boolean }>
  >({});
  const [zoneActivity, setZoneActivity] = useState<Record<string, LabZoneActivitySnapshot>>({});
  const [carryIds, setCarryIds] = useState<Set<string>>(() => new Set());
  const [pending, setPending] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [compares, setCompares] = useState<Record<string, OptimizeBeforeAfterSnapshot | null>>({});
  const autoHandoffFiredRef = useRef(false);

  const refreshZoneStats = useCallback(() => {
    let improved = 0;
    let done = 0;
    for (const h of zoneRefs.current) {
      const handoff = h?.getHandoff();
      if (!handoff) continue;
      if (handoff.hasResult) done += 1;
      if (handoff.improved) improved += 1;
    }
    setImprovedCount(improved);
    setDoneCount(done);
  }, []);

  const handleComplete = useCallback(
    (zoneId: string, seed: OptimizeSeed | null, result: OptimizeSmaGridResultDto) => {
      const snap = buildOptimizeBeforeAfter(seed, result);
      setCompares((prev) => ({ ...prev, [zoneId]: snap }));
      queueMicrotask(refreshZoneStats);
    },
    [refreshZoneStats],
  );

  function toggleCarry(zoneId: string) {
    setCarryIds((prev) => {
      const next = new Set(prev);
      if (next.has(zoneId)) next.delete(zoneId);
      else next.add(zoneId);
      return next;
    });
  }

  async function reanalyzeWithCoach() {
    if (!onReanalyzeWithCoach) return;
    setPending(true);
    setStatusMsg(null);
    try {
      const improved: LabReanalyzeRequest['improved'] = [];
      const carried: LabReanalyzeRequest['carried'] = [];
      const saveFailures: Array<{ rank: number; error: string }> = [];

      for (const h of zoneRefs.current) {
        const handoff = h?.getHandoff();
        if (!handoff || !handoff.hasResult) continue;

        if (handoff.improved) {
          const saved = await handoff.ensureBestStrategy();
          if (!saved) {
            saveFailures.push({
              rank: handoff.rank,
              error: 'Sin resultado de guardado',
            });
            continue;
          }
          if (!saved.ok) {
            saveFailures.push({ rank: handoff.rank, error: saved.error });
            continue;
          }
          improved.push({
            zoneId: handoff.zoneId,
            rank: handoff.rank,
            strategyId: saved.strategyId,
            label: saved.name,
            /** Preset ejecutable de la def (SMA…); strategyType sigue siendo identidad Coach/seed. */
            presetKey: saved.presetKey,
            strategyType: handoff.strategyType,
          });
        } else if (carryIds.has(handoff.zoneId)) {
          carried.push({
            zoneId: handoff.zoneId,
            rank: handoff.rank,
            label: handoff.seedLabel ?? handoff.label,
            strategyType: handoff.strategyType,
            seedLabel: handoff.seedLabel,
          });
        }
      }

      const gate = resolveLabReanalyzeGate({
        improvedSaved: improved.length,
        saveFailures,
        carriedCount: carried.length,
      });
      if (!gate.allow) {
        setStatusMsg(gate.message);
        return;
      }

      setStatusMsg(
        `Coach: reanalizando ${improved.length} mejora(s)` +
          (carried.length ? ` · ${carried.length} sin mejora (solo aviso)` : '') +
          '…',
      );
      await onReanalyzeWithCoach({ improved, carried });
    } catch (err) {
      setStatusMsg(err instanceof Error ? err.message : 'Error al pasar al Coach');
    } finally {
      setPending(false);
      refreshZoneStats();
    }
  }

  const filled = padded.filter((z) => z.seed).length;
  const activityList: LabZoneActivitySnapshot[] = padded
    .filter((z) => z.seed)
    .map((z) => {
      const snap = zoneActivity[z.id];
      return (
        snap ?? {
          zoneId: z.id,
          rank: z.rank,
          label: z.seed?.strategyLabel ?? z.coachLabel ?? `Zona #${z.rank}`,
          // Sin job → idle (no «pending» eterno). Con job y sin snap aún → pending.
          phase:
            z.jobId || (z.jobIds && z.jobIds.length > 0)
              ? ('pending' as const)
              : null,
        }
      );
    });
  const anyWorking = activityList.some(
    (z) => z.phase === 'pending' || z.phase === 'processing' || z.phase === 'running',
  );
  const terminalCount = padded.filter((z) => {
    if (!z.seed) return false;
    const hasJob = Boolean(z.jobId || (z.jobIds && z.jobIds.length > 0));
    const outcome = zoneOutcomes[z.id];
    const act = zoneActivity[z.id];
    return isLabZoneTerminal({
      hasSeed: true,
      hasJob,
      hasResult: Boolean(outcome?.hasResult),
      activityPhase: act?.phase ?? (!hasJob ? null : 'pending'),
    });
  }).length;
  // Terminal incluye fallos / sin job — no solo Mejores con resultado.
  const allDone = filled === 0 || Math.max(doneCount, terminalCount) >= filled;
  const canReanalyze = (improvedCount > 0 || carryIds.size > 0) && allDone;

  useEffect(() => {
    autoHandoffFiredRef.current = false;
  }, [zoneIdsKey]);

  useEffect(() => {
    if (pending || anyWorking) return;
    if (autoHandoff && filled === 0 && !autoHandoffFiredRef.current) {
      autoHandoffFiredRef.current = true;
      const msg = labEmptyZonesStatus();
      setStatusMsg(msg);
      onAutoHandoffStatus?.(msg);
      return;
    }
    if (
      shouldAutoHandoffLab({
        fullCycleActive: autoHandoff,
        allZonesDone: allDone && filled > 0,
        improvedCount,
        alreadyTriggered: autoHandoffFiredRef.current,
      })
    ) {
      autoHandoffFiredRef.current = true;
      onAutoHandoffStatus?.('Ciclo: Lab listo · pasando a Coach²…');
      void reanalyzeWithCoach();
      return;
    }
    if (autoHandoff && allDone && filled > 0 && improvedCount === 0 && !autoHandoffFiredRef.current) {
      autoHandoffFiredRef.current = true;
      const msg =
        labNoImproveStatus(improvedCount, Math.max(doneCount, terminalCount)) ??
        labEmptyZonesStatus();
      setStatusMsg(msg);
      onAutoHandoffStatus?.(msg);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    autoHandoff,
    allDone,
    filled,
    improvedCount,
    doneCount,
    terminalCount,
    pending,
    anyWorking,
  ]);

  // Watchdog: si Lab no termina (job colgado), cerrar ciclo y seguir Lista AUTO.
  useEffect(() => {
    if (!autoHandoff || filled === 0 || allDone) return;
    const t = window.setTimeout(() => {
      if (autoHandoffFiredRef.current) return;
      autoHandoffFiredRef.current = true;
      const msg = labWatchdogStatus();
      setStatusMsg(msg);
      onAutoHandoffStatus?.(msg);
    }, LAB_CYCLE_WATCHDOG_MS);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoHandoff, filled, allDone, zoneIdsKey]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-border/60 bg-background/80 px-3 py-2">
        <div className="min-w-0 space-y-0.5">
          <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <Beaker className="h-4 w-4 text-primary" aria-hidden />
            Lab TOP-{filled || 3}
            {anyWorking && (
              <span className="inline-flex items-center gap-1 rounded-md border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-medium text-sky-100">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                En curso
              </span>
            )}
          </p>
          <p className="text-[11px] text-muted-foreground">
            No hace falta pulsar Play: al «Pasar al Lab» ya se encolan las búsquedas (SMA→H0+Optuna
            unidos; RSI/MACD→grid H0; hold-out/WF según barras). Cada zona muestra el veredicto Mejoró /
            Sin mejora. Lab no escribe Finalistas.
          </p>
          <p className="text-[11px] text-muted-foreground">
            Estado: {doneCount}/{filled || 0} con resultado · {improvedCount} mejora(s)
            {!allDone ? ' · espera a que terminen todas antes de reanalizar' : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            type="button"
            size="sm"
            className="h-7 text-[11px]"
            disabled={pending || !canReanalyze || !onReanalyzeWithCoach}
            onClick={() => void reanalyzeWithCoach()}
            title={
              allDone
                ? 'Persiste los Mejores que mejoraron, los re-simula y abre Coach. Las no mejoradas marcadas van solo como aviso.'
                : 'Espera a que las 3 zonas terminen (o las que tengas en el tablero).'
            }
          >
            {pending ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                Pasando al Coach…
              </span>
            ) : !allDone ? (
              `Esperando zonas (${doneCount}/${filled})…`
            ) : (
              'Reanalizar con Coach'
            )}
          </Button>
        </div>
      </div>

      <LabBoardActivityBanner
        zones={activityList}
        coachPending={pending}
        coachStatus={pending ? statusMsg : null}
      />

      {statusMsg && !pending && (
        <p className="text-[11px] text-muted-foreground" role="status">
          {statusMsg}
        </p>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {padded.map((zone, index) => {
          if (!zone.seed) {
            return <EmptyLabZone key={zone.id} rank={zone.rank} />;
          }
          const snap = compares[zone.id];
          const outcome = zoneOutcomes[zone.id];
          const showCarry = Boolean(outcome?.hasResult && !outcome.improved);
          return (
            <div key={zone.id} className="flex min-w-0 flex-col gap-2">
              {snap && (
                <BacktestOptimizeCompareCard
                  snapshot={snap}
                  onDismiss={() =>
                    setCompares((prev) => {
                      const next = { ...prev };
                      delete next[zone.id];
                      return next;
                    })
                  }
                />
              )}
              {showCarry && (
                <label className="flex cursor-pointer items-start gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5 text-[11px] text-muted-foreground">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={carryIds.has(zone.id)}
                    onChange={() => toggleCarry(zone.id)}
                  />
                  <span>
                    <span className="font-medium text-foreground">Llevar al Coach</span>
                    {' · '}
                    no mejoró · no se reanaliza (solo aviso)
                  </span>
                </label>
              )}
              <BacktestOptimizePanel
                ref={(h) => {
                  zoneRefs.current[index] = h;
                }}
                instruments={instruments}
                defaultInstrumentId={defaultInstrumentId}
                seed={zone.seed}
                initialRunId={zone.jobId ?? null}
                initialRunIds={zone.jobIds ?? (zone.jobId ? [zone.jobId] : null)}
                compact
                zoneId={zone.id}
                zoneRank={zone.rank}
                zoneStars={zone.stars}
                zoneStarsCapped={zone.starsCapped}
                onClearSeed={
                  onClearZoneSeed ? () => onClearZoneSeed(zone.id) : undefined
                }
                onOptimizeComplete={({ seed: doneSeed, result }) =>
                  handleComplete(zone.id, doneSeed, result)
                }
                onAdoptReadyChange={(ready) => {
                  setZoneOutcomes((prev) => ({
                    ...prev,
                    [zone.id]: { improved: ready.improved, hasResult: true },
                  }));
                  refreshZoneStats();
                }}
                onActivityChange={(activity) => {
                  setZoneActivity((prev) => {
                    const prevSnap = prev[zone.id];
                    if (
                      prevSnap &&
                      prevSnap.phase === activity.phase &&
                      prevSnap.trialDone === activity.trialDone &&
                      prevSnap.trialTotal === activity.trialTotal &&
                      prevSnap.label === activity.label
                    ) {
                      return prev;
                    }
                    return {
                      ...prev,
                      [zone.id]: { ...activity, zoneId: zone.id },
                    };
                  });
                }}
                maxDrawdownSoftPct={maxDrawdownSoftPct}
                profileId={profileId}
                profileHorizon={profileHorizon}
                profileRiskTolerance={profileRiskTolerance}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
