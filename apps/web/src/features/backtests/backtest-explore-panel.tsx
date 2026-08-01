/**
 * Panel Coach (hub Probar → pestaña Coach).
 *
 * Operativa:
 * 1. Esperar a que termine «Probar + coach» (TOP ★ no se muestra a mitad).
 * 2. **Abrir Lab · #1** = prefill Lab; **Pasar las N al Lab** = tablero 3 zonas + jobs.
 * 3. **Guardar TOP-3** = semifinal (sin Lab). Tras Lab: **Guardar Finalistas** (lab_validated).
 * 4. Batería / vs B&H = evidencia secundaria (colapsable).
 *
 * @see docs/engineering/research-lifecycle.md § P2
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  BacktestEquityPointDto,
  ChartTimeframe,
  ProfileHorizon,
  RiskTolerance,
} from '@bolsa/shared';
import { formatPct } from '@/features/charts/chart-utils';
import { AiInfoButton } from '@/features/ai/ai-info-button';
import {
  buildExploreCoachNote,
  sortExploreRows,
  type ExplorePresetRow,
  type ExploreSortKey,
} from '@/features/backtests/backtest-explore-value';
import {
  buildDeepTechnicalCoachNote,
  buildCoachFacts,
  mergeLlmIntoDeepCoach,
  type DeepTechnicalCoachNote,
} from '@/features/backtests/backtest-deep-coach';
import {
  auditFindingsFromLlmPayload,
  buildAuditedDeepTechnicalCoachNote,
  confidenceLabel,
  readPriorCoachAuditHint,
  type CoachConfidence,
} from '@/features/backtests/coach-dual-audit';
import { CoachQuorumBar } from '@/features/backtests/coach-quorum-bar';
import { BacktestFutureStars } from '@/features/backtests/backtest-future-stars';
import {
  isOptimizableStrategy,
  optimizeFamilyProxyNote,
} from '@/features/backtests/backtest-optimize-seed';
import { buildCoachTopSlots } from '@/features/backtests/coach-top-save';
import {
  buildCoachProfileBindingFacts,
  resolveCoachProfilePolicy,
} from '@/features/backtests/coach-profile-policy';
import {
  buildLabAdoptionFacts,
  readLabAdoption,
} from '@/features/backtests/lab-adoption-memory';
import { resolveFullCycleSaveDecision, shouldWaitBeforeFinalistsAutoSave } from '@/features/backtests/backtest-assistant-full-cycle';
import {
  isCoach1AckSatisfied,
  resolveAssistantAckPolicy,
} from '@/features/backtests/assistant-cycle-orchestrator';
import {
  buildFinalistsFreshnessStamp,
  mergeFreshnessIntoCoachFacts,
  writeLocalFreshnessFingerprint,
} from '@/features/backtests/backtest-finalists-freshness';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const SORT_OPTIONS: { value: ExploreSortKey; label: string }[] = [
  { value: 'excess', label: 'Vs buy & hold' },
  { value: 'sharpe', label: 'Sharpe' },
  { value: 'return', label: 'Resultado %' },
  { value: 'drawdown', label: 'Peor caída' },
];

type Props = {
  rows: ExplorePresetRow[];
  instrumentId?: string | null;
  /** initial = Universo; post_lab = tras Reanalizar con Coach. */
  coachPass?: 'initial' | 'post_lab';
  symbol: string;
  timeframe: ChartTimeframe | string;
  periodLabel?: string;
  sort: ExploreSortKey;
  onSortChange: (sort: ExploreSortKey) => void;
  selectedRunId?: string | null;
  onSelectRun: (runId: string) => void;
  onOptimizeCandidate?: (row: ExplorePresetRow) => void;
  /** Pasa hasta 3 recomendaciones del coach al tablero Lab (proxy si no hay grid nativo). */
  onOptimizeSemifinal?: (
    candidates: Array<{
      row: ExplorePresetRow;
      stars?: number;
      starsCapped?: boolean;
      rank?: number;
    }>,
  ) => void;
  barLimit?: number | null;
  progress?: { done: number; total: number };
  running?: boolean;
  /** Equity curves keyed by runId (seeded detail cache). */
  equityByRunId?: Record<string, BacktestEquityPointDto[] | undefined>;
  /** Peso del tramo reciente en ★ (prefs asistente). */
  futureWeight?: number;
  /**
   * Ciclo completo: tras Coach² auto-guarda Finalistas si la política lo permite
   * (mejora Lab + canSaveTop). No guarda semifinal in-sample.
   */
  autoSaveFinalists?: boolean;
  onAutoSaveStatus?: (message: string) => void;
  /** Soft-ACK automático en ciclo (default true). */
  autoAckOnCycle?: boolean;
  /** Pausar ciclo si hace falta ACK humano (no soft-ACK). */
  pauseIfAckNeeded?: boolean;
  /** Notifica al hub: ciclo parado esperando ACK. */
  onAwaitingAckChange?: (awaiting: boolean) => void;
  /**
   * Ciclo en Coach¹: exigir ACK¹ (débil/discrepancia) antes de Lab / atajo.
   * Soft-ACK / pausa según autoAckOnCycle / pauseIfAckNeeded.
   */
  requireAckBeforeLab?: boolean;
  /**
   * Ciclo en Coach¹: tras ACK OK, guardar semifinal y cerrar (sin Lab).
   */
  autoSaveSemifinal?: boolean;
  /**
   * Hub: ciclo activo en pasada Coach¹ (para soft-ACK¹ / pausa sin confundir con idle).
   */
  cycleCoach1Active?: boolean;
  /**
   * Mejoras Lab reportadas por el hub al entrar en Coach² (fuente de verdad del ciclo).
   */
  labImprovedCountHint?: number;
  /** Estado del gate Coach para que el hub avance Lab / atajo. */
  onCoachGateChange?: (gate: {
    needsAck: boolean;
    ack: boolean;
    postLab: boolean;
    canSaveTop: boolean;
  }) => void;
  /**
   * Huella de entradas para stamp de frescura al guardar Finalistas
   * (`coachFacts.freshness`). Si falta, no se escribe stamp.
   */
  freshnessInputFingerprint?: string | null;
  /**
   * CORE A: narración / adversario LLM.
   * OFF → no auto-llama; ranking ★ + auditor heurístico locales.
   */
  llmNarrate?: boolean;
};

function batteryText(rows: ExplorePresetRow[]): string {
  return rows
    .filter((r) => r.status === 'ok')
    .map((r) => {
      const parts = [
        r.strategyType,
        r.label,
        `cat=${r.category}`,
        `ret=${r.totalReturnPct?.toFixed(2) ?? 'n/a'}`,
        `excess=${r.excessReturnPct?.toFixed(2) ?? 'n/a'}`,
        `dd=${r.maxDrawdownPct?.toFixed(2) ?? 'n/a'}`,
        `sharpe=${r.sharpeRatio?.toFixed(2) ?? 'n/a'}`,
        `trades=${r.tradeCount ?? 'n/a'}`,
        `bars=${r.barCount ?? 'n/a'}`,
      ];
      return parts.join(' | ');
    })
    .join('\n');
}

function localSummaryText(note: DeepTechnicalCoachNote): string {
  return [
    note.headline,
    ...note.analysis,
    ...note.recommendations.map(
      (r) =>
        `#${r.rank} ${r.row.label} (${r.row.strategyType}) score=${r.score}: ${r.reasons.join('; ')}`,
    ),
    note.regime?.narrative,
    ...note.outlook,
  ]
    .filter(Boolean)
    .join('\n');
}

export function BacktestExploreRanking({
  rows,
  instrumentId,
  coachPass = 'initial',
  symbol,
  timeframe,
  periodLabel,
  sort,
  onSortChange,
  selectedRunId,
  onSelectRun,
  onOptimizeCandidate,
  onOptimizeSemifinal,
  barLimit,
  progress,
  running,
  equityByRunId,
  futureWeight,
  autoSaveFinalists = false,
  onAutoSaveStatus,
  autoAckOnCycle = true,
  pauseIfAckNeeded = false,
  onAwaitingAckChange,
  requireAckBeforeLab = true,
  autoSaveSemifinal = false,
  cycleCoach1Active = false,
  labImprovedCountHint = 0,
  onCoachGateChange,
  freshnessInputFingerprint = null,
  llmNarrate = true,
}: Props) {
  const queryClient = useQueryClient();
  const postLab = coachPass === 'post_lab';
  const autoSaveFiredRef = useRef(false);
  const softAckLatchedRef = useRef(false);
  const loteKey = rows.map((r) => r.strategyDefinitionId ?? r.runId ?? r.strategyType).join('|');
  const ranked = useMemo(() => sortExploreRows(rows, sort), [rows, sort]);
  const carryRows = useMemo(
    () => rows.filter((r) => r.labPass === 'lab_carry'),
    [rows],
  );
  const coach = useMemo(
    () => buildExploreCoachNote(rows, symbol, { barLimit }),
    [rows, symbol, barLimit],
  );
  const okCount = rows.filter((row) => row.status === 'ok' && row.labPass !== 'lab_carry').length;

  const { effectiveAccountId } = useActiveAccount();
  const profileQuery = useQuery({
    queryKey: ['account-active-profile', effectiveAccountId],
    queryFn: () => api.getAccountActiveProfile(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 60_000,
    retry: false,
  });
  const profile = profileQuery.data?.data;
  const horizon = (profile?.declared?.horizon ?? null) as ProfileHorizon | null;
  const riskTolerance = (profile?.declared?.riskTolerance ?? null) as RiskTolerance | null;

  const coachCtx = useMemo(
    () => {
      const policy = resolveCoachProfilePolicy({
        profileId: profile?.profileId,
        profileName: profile?.name,
        horizon,
        riskTolerance,
      });
      return {
        symbol,
        timeframe,
        periodLabel,
        horizon,
        riskTolerance,
        profileName: profile?.name,
        profileId: profile?.profileId,
        maxDrawdownSoftPct: policy.maxDrawdownSoftPct,
        equityByRunId,
        evidenceLevel: (postLab ? 'lab_validated' : 'in_sample_only') as
          | 'lab_validated'
          | 'in_sample_only',
        futureWeight,
      };
    },
    [
      symbol,
      timeframe,
      periodLabel,
      horizon,
      riskTolerance,
      profile?.name,
      profile?.profileId,
      equityByRunId,
      postLab,
      futureWeight,
    ],
  );

  /**
   * El TOP ★ solo se fija cuando la batería termina (ranking A + auditor B + gate).
   */
  const localDeep = useMemo(() => {
    if (running) {
      const empty = buildDeepTechnicalCoachNote([], coachCtx);
      return {
        ...empty,
        headline: `Batería en curso (${progress?.done ?? okCount}/${progress?.total ?? rows.length})…`,
        contextLabel: coachCtx.periodLabel
          ? `${symbol} · ${coachCtx.periodLabel} · ${timeframe}`
          : `${symbol} · ${timeframe}`,
        analysis: [
          'El TOP ★ a futuro se calcula al terminar todas las genéricas.',
          'Motor A (ranking) + Motor B (auditor) + gate de consenso.',
          'La IA puede vetar tipado; no inventa estrategias fuera del lote.',
        ],
        recommendations: [],
        outlook: ['Espera al final del lote o cancela si no quieres seguir.'],
        disclaimer:
          'Mientras corre la batería no mostramos un TOP provisional: evita elecciones inestables.',
      } satisfies DeepTechnicalCoachNote;
    }
    return buildAuditedDeepTechnicalCoachNote(rows, coachCtx, undefined, {
      coachPass: postLab ? 'post_lab' : 'initial',
    });
  }, [rows, coachCtx, running, progress?.done, progress?.total, okCount, symbol, timeframe, postLab]);

  const coachFacts = useMemo(
    () =>
      buildCoachFacts(
        rows,
        coachCtx,
        running ? buildDeepTechnicalCoachNote(rows, coachCtx) : localDeep,
      ),
    [rows, coachCtx, localDeep, running],
  );

  const [deepNote, setDeepNote] = useState<DeepTechnicalCoachNote>(localDeep);
  const [engineLabel, setEngineLabel] = useState('local-AT+B');
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [discrepancyAck, setDiscrepancyAck] = useState(false);
  const lastLlmFingerprintRef = useRef<string>('');

  // Reset ACK solo al cambiar valor / pasada / lote — no en cada recompute de localDeep
  // (eso rompía soft-ACK y el auto-guardado de Finalistas).
  useEffect(() => {
    softAckLatchedRef.current = false;
    setDiscrepancyAck(false);
    onAwaitingAckChange?.(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al cambiar contexto de lote
  }, [instrumentId, coachPass, loteKey]);

  useEffect(() => {
    setDeepNote(localDeep);
    setEngineLabel('local-AT+B');
    if (softAckLatchedRef.current) {
      setDiscrepancyAck(true);
    }
  }, [localDeep]);

  const confidence: CoachConfidence = deepNote.audit?.confidence ?? 'no_auditor';
  const softWeak = Boolean(deepNote.audit?.softWeak);
  const needsAck = confidence === 'discrepancy' || confidence === 'weak';
  /** Misma política que el check de ⋯ (no un segundo ACK distinto). */
  const ackPolicy = resolveAssistantAckPolicy({
    autoAckOnCycle,
    pauseIfAckNeeded,
  });
  const prefsAutoAck = ackPolicy.mode === 'auto';
  const ackSatisfied = isCoach1AckSatisfied({
    needsAck,
    ackReady: discrepancyAck,
    autoAckOnCycle,
    pauseIfAckNeeded,
  });
  const canSaveTop =
    deepNote.recommendations.length > 0 &&
    (!needsAck || discrepancyAck || ackSatisfied);
  /** Estado visual = prefs Auto-ACK O checkbox humano (una sola verdad). */
  const ackApplied = !needsAck || ackSatisfied || discrepancyAck;

  useEffect(() => {
    onCoachGateChange?.({
      needsAck,
      ack: ackApplied,
      postLab,
      canSaveTop,
    });
  }, [needsAck, ackApplied, postLab, canSaveTop, onCoachGateChange]);

  const labImprovedCount = useMemo(() => {
    const fromRows = rows.filter(
      (r) => r.labPass === 'lab_improved' && r.status === 'ok',
    ).length;
    return Math.max(fromRows, labImprovedCountHint);
  }, [rows, labImprovedCountHint]);

  const savedTopQuery = useQuery({
    queryKey: ['instrument-strategy-top', instrumentId, timeframe],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId!, String(timeframe)),
    enabled: Boolean(instrumentId),
    staleTime: 30_000,
    retry: false,
  });
  const savedTop = savedTopQuery.data?.data ?? null;
  const priorAuditHint = useMemo(
    () =>
      readPriorCoachAuditHint(
        savedTop?.coachFacts as Record<string, unknown> | null | undefined,
      ),
    [savedTop?.coachFacts],
  );

  const saveTopMutation = useMutation({
    mutationFn: async (opts?: {
      forceCycleAck?: boolean;
      /** Evita carrera: usar el note vivo (localDeep), no deepNote atrasado. */
      note?: DeepTechnicalCoachNote;
    }) => {
      if (!instrumentId) throw new Error('Sin instrumento');
      const note = opts?.note ?? deepNote;
      const conf = note.audit?.confidence ?? 'no_auditor';
      const noteNeedsAck = conf === 'discrepancy' || conf === 'weak';
      const ackOk =
        !noteNeedsAck ||
        discrepancyAck ||
        Boolean(opts?.forceCycleAck) ||
        prefsAutoAck;
      const recs = note.recommendations.slice(0, 3);
      if (recs.length === 0) {
        throw new Error('Sin candidatas TOP para guardar');
      }
      if (noteNeedsAck && !ackOk) {
        throw new Error(
          'Marca el ack (TOP débil o discrepancia) para guardar con reserva',
        );
      }

      const strategiesRes = await api.getStrategies();
      const existing = strategiesRes.data ?? [];
      const tf = String(timeframe);

      const slots = await buildCoachTopSlots({
        recommendations: recs,
        symbol,
        timeframe: tf,
        slotSource: postLab ? 'optimized' : 'coach',
        requireRunId: postLab,
        lookup: {
          existing,
          createFromPreset: async (input) => {
            const created = await api.createStrategyFromPreset({
              name: input.name,
              presetKey: input.presetKey as import('@bolsa/shared').BacktestStrategyType,
              timeframe: input.timeframe,
            });
            return {
              id: created.data.id,
              name: created.data.name,
              presetKey: created.data.presetKey,
              origin: created.data.origin,
              timeframe: created.data.timeframe,
              kind: created.data.kind,
              instrumentIds: created.data.instrumentIds ?? [],
              updatedAt: created.data.updatedAt,
              createdAt: created.data.createdAt,
            };
          },
        },
      });
      if (slots.length === 0) throw new Error('Sin recomendaciones para guardar');

      const policy = resolveCoachProfilePolicy({
        profileId: profile?.profileId,
        profileName: profile?.name,
        horizon,
        riskTolerance,
      });
      const adoptionFacts =
        postLab && instrumentId
          ? buildLabAdoptionFacts(readLabAdoption(instrumentId, tf))
          : null;
      const noteFacts = buildCoachFacts(rows, coachCtx, note);
      const baseFacts: Record<string, unknown> = {
        ...(noteFacts as unknown as Record<string, unknown>),
        ...buildCoachProfileBindingFacts(policy),
        ...(adoptionFacts ?? {}),
        dualAudit: note.audit ?? null,
        discrepancyAck:
          conf === 'discrepancy' || conf === 'weak' ? true : false,
        coachPass: postLab ? 'post_lab' : 'initial',
        cycleAutoAck: Boolean(opts?.forceCycleAck) || prefsAutoAck,
      };
      const stampedFacts =
        freshnessInputFingerprint && postLab
          ? mergeFreshnessIntoCoachFacts(
              baseFacts,
              buildFinalistsFreshnessStamp({
                inputFingerprint: freshnessInputFingerprint,
                lab: true,
              }),
            )
          : baseFacts;

      return api.upsertInstrumentStrategyTop(instrumentId, {
        instrumentId,
        symbol,
        timeframe: tf,
        periodLabel: periodLabel ?? null,
        status: postLab ? 'active' : 'semifinal',
        evidenceLevel: postLab ? 'lab_validated' : noteFacts.evidenceLevel,
        slots,
        coachHeadline: note.headline,
        coachFacts: stampedFacts,
      });
    },
    onSuccess: async () => {
      setSaveMsg(
        postLab
          ? 'Finalistas actualizados (lab_validated) · en Mis estrategias'
          : 'TOP-3 semifinal guardado (sustituye previos) · en Mis estrategias',
      );
      if (postLab && freshnessInputFingerprint && instrumentId) {
        writeLocalFreshnessFingerprint({
          instrumentId,
          timeframe: String(timeframe),
          fingerprint: freshnessInputFingerprint,
        });
      }
      await savedTopQuery.refetch();
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
      await queryClient.invalidateQueries({ queryKey: ['instrument-strategy-top'] });
    },
    onError: (err: Error) => {
      setSaveMsg(err.message || 'Error al guardar TOP-3');
    },
  });

  useEffect(() => {
    autoSaveFiredRef.current = false;
  }, [instrumentId, coachPass, loteKey]);

  // Soft-ACK: refleja prefs Auto-ACK en el estado del panel (una sola verdad).
  useEffect(() => {
    if (running || !needsAck) {
      if (!needsAck) onAwaitingAckChange?.(false);
      return;
    }
    if (prefsAutoAck) {
      softAckLatchedRef.current = true;
      if (!discrepancyAck) setDiscrepancyAck(true);
      onAwaitingAckChange?.(false);
      return;
    }
    if (!discrepancyAck) onAwaitingAckChange?.(true);
    else onAwaitingAckChange?.(false);
  }, [running, needsAck, prefsAutoAck, discrepancyAck, onAwaitingAckChange]);

  // Atajo: guardar semifinal sin Lab (pref saveSemifinalSkipLab).
  useEffect(() => {
    if (!autoSaveSemifinal || postLab || running || autoSaveFiredRef.current) return;
    if (saveTopMutation.isPending) return;
    if (!ackSatisfied) {
      onAwaitingAckChange?.(true);
      return;
    }
    if (needsAck && !discrepancyAck && prefsAutoAck) {
      softAckLatchedRef.current = true;
      setDiscrepancyAck(true);
    }
    if (deepNote.recommendations.length === 0) {
      autoSaveFiredRef.current = true;
      onAwaitingAckChange?.(false);
      onAutoSaveStatus?.(
        'Ciclo: atajo semifinal sin TOP guardable · Finalistas intactos.',
      );
      return;
    }
    autoSaveFiredRef.current = true;
    onAwaitingAckChange?.(false);
    saveTopMutation.mutate(
      { forceCycleAck: prefsAutoAck },
      {
        onSuccess: () => {
          onAutoSaveStatus?.(
            'Ciclo: TOP semifinal guardado · Lab omitido (atajo).',
          );
        },
        onError: (err: Error) => {
          autoSaveFiredRef.current = false;
          onAutoSaveStatus?.(
            `Ciclo: error atajo semifinal (${err.message}). Finalistas intactos.`,
          );
        },
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    autoSaveSemifinal,
    postLab,
    running,
    needsAck,
    discrepancyAck,
    ackSatisfied,
    prefsAutoAck,
    deepNote.recommendations.length,
  ]);

  useEffect(() => {
    if (!autoSaveFinalists || !postLab || running || autoSaveFiredRef.current) return;
    if (saveTopMutation.isPending) return;

    // Nota viva (localDeep): evita skip en el frame en que running=false pero
    // deepNote aún está vacío (carrera ACS / Coach²).
    const note = localDeep;
    const recsWithRun = note.recommendations.filter((r) => Boolean(r.row.runId));
    if (
      shouldWaitBeforeFinalistsAutoSave({
        running,
        okCount,
        recommendationCount: note.recommendations.length,
        postLabRecsWithRunId: recsWithRun.length,
        postLab: true,
      })
    ) {
      return;
    }

    const conf = note.audit?.confidence ?? 'no_auditor';
    const noteNeedsAck = conf === 'weak' || conf === 'discrepancy';
    const noteAckOk = isCoach1AckSatisfied({
      needsAck: noteNeedsAck,
      ackReady: discrepancyAck,
      autoAckOnCycle,
      pauseIfAckNeeded,
    });
    if (!noteAckOk) {
      onAwaitingAckChange?.(true);
      return;
    }

    if (noteNeedsAck && !discrepancyAck && prefsAutoAck) {
      softAckLatchedRef.current = true;
      setDiscrepancyAck(true);
    }

    const canSave = note.recommendations.length > 0 && noteAckOk && recsWithRun.length > 0;

    const decision = resolveFullCycleSaveDecision({
      postLab: true,
      labImprovedCount,
      canSaveTop: canSave,
      existingTopStatus: savedTop?.status ?? null,
      hasExistingTop: Boolean(savedTop),
    });

    if (decision.action === 'save_active') {
      autoSaveFiredRef.current = true;
      onAwaitingAckChange?.(false);
      saveTopMutation.mutate(
        { forceCycleAck: true, note },
        {
          onSuccess: () => {
            onAutoSaveStatus?.(`Ciclo: ${decision.reason}`);
          },
          onError: (err: Error) => {
            autoSaveFiredRef.current = false;
            onAutoSaveStatus?.(
              `Ciclo: error al guardar Finalistas (${err.message}). Revisa Revalidar (Coach²).`,
            );
          },
        },
      );
      return;
    }

    // Candidatas aún no listas: no quemar el ciclo.
    if (
      decision.action === 'skip_no_candidates' &&
      (okCount > 0 || labImprovedCountHint > 0)
    ) {
      return;
    }

    autoSaveFiredRef.current = true;
    onAwaitingAckChange?.(false);
    onAutoSaveStatus?.(`Ciclo: ${decision.reason}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    autoSaveFinalists,
    postLab,
    running,
    localDeep,
    okCount,
    labImprovedCount,
    labImprovedCountHint,
    savedTop,
    savedTop?.status,
    discrepancyAck,
    prefsAutoAck,
    autoAckOnCycle,
    pauseIfAckNeeded,
  ]);

  const llmMutation = useMutation({
    mutationFn: async () => {
      const base = {
        context: localDeep.contextLabel,
        battery: batteryText(rows),
        localSummary: localSummaryText(localDeep),
        facts: coachFacts as unknown as Record<string, unknown>,
      };
      const [narrate, adversary] = await Promise.all([
        api.analyzeBacktestCoach({ ...base, mode: 'narrate' }),
        api.analyzeBacktestCoach({ ...base, mode: 'adversary' }),
      ]);
      return { narrate, adversary };
    },
    onSuccess: ({ narrate, adversary }) => {
      const payload = narrate.data.payload;
      const llmFindings = auditFindingsFromLlmPayload(payload, 'llm');
      const adversaryFindings = auditFindingsFromLlmPayload(adversary.data.payload, 'llm_c');
      const audited = buildAuditedDeepTechnicalCoachNote(rows, coachCtx, llmFindings, {
        adversaryFindings,
        coachPass: postLab ? 'post_lab' : 'initial',
      });
      if (!payload) {
        setEngineLabel(
          adversary.data.provider
            ? `${narrate.data.engine || 'heuristic'} · C`
            : narrate.data.engine || 'heuristic',
        );
        setDeepNote(audited);
        return;
      }
      setDeepNote(mergeLlmIntoDeepCoach(audited, payload));
      const provider = narrate.data.provider ?? adversary.data.provider;
      const model = narrate.data.model ?? adversary.data.model;
      setEngineLabel(
        provider
          ? `${provider}${model ? ` · ${model}` : ''} · A/B/C`
          : `${narrate.data.engine} · A/B/C`,
      );
    },
  });

  const loteFingerprint = rows
    .filter((r) => r.status === 'ok')
    .map((r) => r.runId ?? r.strategyType)
    .join(',');

  // Auto-disparar IA una vez por lote terminado (CORE A: respeta llmNarrate).
  useEffect(() => {
    if (!llmNarrate) return;
    if (running) return;
    if (okCount === 0) return;
    if (!loteFingerprint) return;
    if (lastLlmFingerprintRef.current === loteFingerprint) return;
    lastLlmFingerprintRef.current = loteFingerprint;
    llmMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, okCount, loteFingerprint, llmNarrate]);

  useEffect(() => {
    if (llmNarrate) return;
    if (running) return;
    setEngineLabel('local-AT+B · sin LLM');
  }, [llmNarrate, running, loteFingerprint]);

  const firstLabRec = deepNote.recommendations.find((r) =>
    isOptimizableStrategy(r.row.strategyType),
  );
  const labRecCount = deepNote.recommendations.filter((r) =>
    isOptimizableStrategy(r.row.strategyType),
  ).length;

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-y-auto overscroll-contain pb-2">
      {/* Núcleo: TOP-3 ★ + acciones Lab */}
      <div className="space-y-2.5 rounded-lg border border-border bg-muted/20 px-3 py-2.5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <p
                className="text-[11px] font-semibold text-foreground"
                title="Ranking local (A) + auditor (B) + gate. La IA puede vetar tipado; no inventa el TOP."
              >
                Coach · TOP a futuro
              </p>
              <AiInfoButton surface="backtest_coach" />
            </div>
            <p className="text-[10px] text-muted-foreground">{deepNote.contextLabel}</p>
            <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
              Quorum: <strong className="font-medium text-foreground/80">A</strong> ranking ·{' '}
              <strong className="font-medium text-foreground/80">A2</strong> shadow ·{' '}
              <strong className="font-medium text-foreground/80">B</strong> auditor ·{' '}
              <strong className="font-medium text-foreground/80">C</strong> adversario · red-team
              pre-guardar.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {!running && okCount > 0 && deepNote.audit && (
              <span
                className={cn(
                  'rounded-md border px-1.5 py-0.5 text-[10px] font-medium',
                  confidence === 'consensus' &&
                    'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
                  confidence === 'discrepancy' &&
                    'border-amber-500/40 bg-amber-500/10 text-amber-200',
                  confidence === 'weak' && 'border-amber-500/40 bg-amber-500/10 text-amber-200',
                  confidence === 'no_auditor' && 'border-border text-muted-foreground',
                )}
                title={
                  deepNote.audit.challenge.passed
                    ? deepNote.audit.shadowDisagreement || deepNote.audit.auditorCDisagreement
                      ? `Discrepancia A/A2/C · ack para guardar`
                      : 'Quorum B + red-team OK'
                    : deepNote.audit.challenge.checks
                        .filter((c) => !c.passed && c.severity === 'hard')
                        .map((c) => c.detail)
                        .join(' · ') || 'TOP débil — ack para guardar'
                }
              >
                {confidenceLabel(confidence)}
              </span>
            )}
            <span className="text-[10px] text-muted-foreground">
              {llmMutation.isPending ? 'IA A+C…' : engineLabel}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 text-[11px]"
              disabled={
                running ||
                okCount === 0 ||
                !instrumentId ||
                !canSaveTop ||
                saveTopMutation.isPending
              }
              onClick={() => {
                setSaveMsg(null);
                saveTopMutation.mutate();
              }}
              title={
                postLab
                  ? 'Guarda Finalistas (active + lab_validated) tras el Lab. Sustituye el TOP del valor.'
                  : 'Guarda TOP-3 semifinal (sin Lab). No escribe lab_validated.'
              }
            >
              {postLab ? 'Guardar Finalistas' : 'Guardar TOP-3'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 text-[11px]"
              disabled={running || okCount === 0 || llmMutation.isPending || !llmNarrate}
              onClick={() => {
                lastLlmFingerprintRef.current = '';
                llmMutation.mutate();
              }}
              title={
                llmNarrate
                  ? 'Vuelve a pedir narrativa IA (el ranking ★ es local-AT)'
                  : 'Activa «Narración LLM Coach» en (…) del Asistente'
              }
            >
              Reanalizar
            </Button>
          </div>
        </div>

        {(saveMsg || savedTop) && (
          <p className="text-[10px] text-muted-foreground">
            {saveMsg ? `${saveMsg}. ` : ''}
            {savedTop
              ? `Finalistas BD: v${savedTop.version} · ${savedTop.status} · ${savedTop.slots
                  .map((s) => `#${s.rank} ${s.label}`)
                  .join(' · ')}`
              : instrumentId
                ? 'Sin TOP guardado aún para este valor/TF.'
                : ''}
          </p>
        )}

        {priorAuditHint && !running && (
          <p
            className={cn(
              'rounded-md border px-2 py-1.5 text-[10px]',
              priorAuditHint.confidence === 'weak' || priorAuditHint.softWeak
                ? 'border-amber-500/30 bg-amber-500/5 text-amber-100/90'
                : priorAuditHint.confidence === 'discrepancy'
                  ? 'border-amber-500/25 bg-amber-500/5 text-muted-foreground'
                  : 'border-border/70 bg-muted/20 text-muted-foreground',
            )}
            title="Contexto de la pasada guardada (CORE A). No cambia el ranking ★ actual."
          >
            Pasada anterior · {confidenceLabel(priorAuditHint.confidence)}
            {priorAuditHint.softWeak ? ' · soft-débil' : ''}
            {priorAuditHint.coachPass === 'post_lab' ? ' · post-Lab' : ''}
            {' · '}
            no modula el TOP actual (solo contexto).
          </p>
        )}

        <p className="text-sm font-medium leading-snug text-foreground">{deepNote.headline}</p>
        {postLab && !running && (
          <p className="rounded-md border border-emerald-500/25 bg-emerald-500/5 px-2 py-1.5 text-[10px] text-emerald-100/90">
            <span className="font-medium">4 · Revalidar (Coach²)</span>
            {' · '}
            pasada tras Lab · evidencia lab · techo ★{coachFacts.starCeiling}. Las que no mejoraron
            (si las llevaste) no entran en el ranking ★. Soft-fail del red-team no bloquea Guardar
            si #1 está limpia.
          </p>
        )}
        {!postLab && !running && okCount > 0 && (
          <p className="rounded-md border border-border/50 bg-muted/20 px-2 py-1 text-[10px] text-muted-foreground">
            <span className="font-medium text-foreground">2 · Coach · ACK¹</span>
            {' · '}
            analiza el lote. Con ACK¹ (si hace falta) → Lab; sin mejora Lab no se
            revalida ni se pisa Finalistas; con mejora → Revalidar (ACK final).
          </p>
        )}

        {!running && deepNote.audit?.quorum && okCount > 0 && (
          <CoachQuorumBar quorum={deepNote.audit.quorum} />
        )}

        {carryRows.length > 0 && !running && (
          <div className="space-y-1 rounded-md border border-border/60 bg-muted/20 px-2.5 py-2">
            <p className="text-[10px] font-medium text-muted-foreground">
              Sin mejora en Lab · no reanalizadas
            </p>
            <ul className="space-y-0.5 text-[11px] text-muted-foreground">
              {carryRows.map((r) => (
                <li key={`carry-${r.strategyType}-${r.label}`}>· {r.label}</li>
              ))}
            </ul>
          </div>
        )}

        {needsAck && !running && prefsAutoAck && (
          <p
            className="rounded-md border border-emerald-500/35 bg-emerald-500/10 px-2 py-1.5 text-[10px] text-emerald-100/90"
            title="Misma preferencia que ⋯ Asistente → «ACK final automático → grabar en BD»"
          >
            <span className="font-medium">
              {postLab ? 'ACK final' : 'ACK¹'} = config Asistente
            </span>
            {' · '}
            automático (⋯).{' '}
            {postLab
              ? 'Se graban Finalistas en BD si hubo mejora Lab.'
              : 'El ciclo sigue al Lab sin checkbox extra.'}
          </p>
        )}

        {needsAck && !running && ackPolicy.showHumanCheckbox && (
          <label className="flex cursor-pointer items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-[10px] text-amber-100/90">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={discrepancyAck}
              onChange={(e) => {
                const v = e.target.checked;
                setDiscrepancyAck(v);
                if (v) {
                  softAckLatchedRef.current = true;
                  onAwaitingAckChange?.(false);
                } else {
                  onAwaitingAckChange?.(true);
                }
              }}
            />
            <span>
              {postLab
                ? confidence === 'weak'
                  ? 'ACK final (paso 4→5): confirma para grabar Finalistas (⋯ tiene «Pausar ACK» o Auto-ACK OFF).'
                  : 'ACK final: confirma para grabar Finalistas con reserva.'
                : confidence === 'weak'
                  ? 'ACK¹: confirma para pasar al Lab.'
                  : 'ACK¹: confirma para pasar al Lab con reserva.'}
              {!discrepancyAck ? ' · Ciclo en pausa.' : ''}
            </span>
          </label>
        )}

        {softWeak && confidence !== 'weak' && !running && deepNote.audit && (
          <p className="rounded-md border border-border/70 bg-muted/25 px-2 py-1.5 text-[10px] text-muted-foreground">
            Aviso red-team (soft, no bloquea):{' '}
            {deepNote.audit.challenge.checks
              .filter((c) => !c.passed && c.severity === 'soft')
              .map((c) => c.detail)
              .join(' · ')}
          </p>
        )}

        {confidence === 'weak' && !running && deepNote.audit && (
          <p className="rounded-md border border-amber-500/25 bg-amber-500/5 px-2 py-1.5 text-[10px] text-amber-100/80">
            Avisos red-team:{' '}
            {deepNote.audit.challenge.checks
              .filter((c) => !c.passed)
              .map((c) => c.detail)
              .join(' · ') || 'candidatas con veto suavizado'}
            . El TOP-3 se muestra igual; las ★ bajas indican poca confianza.
          </p>
        )}

        {deepNote.audit && !running && deepNote.audit.findings.some((f) => f.action === 'veto') && (
          <p className="text-[10px] text-muted-foreground">
            Vetos B/C:{' '}
            {deepNote.audit.findings
              .filter((f) => f.action === 'veto')
              .map((f) => `${f.strategyType} (${f.code}/${f.source})`)
              .join(' · ')}
          </p>
        )}

        {deepNote.recommendations.length > 0 ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <p className="text-[11px] font-medium text-foreground">Candidatas ★ (1–5)</p>
                <p className="text-[10px] text-muted-foreground">
                  Orden por tramo reciente · techo ★{coachFacts.starCeiling}
                  {coachFacts.starCeiling <= 3 ? ' (solo in-sample)' : ' (lab)'}.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {onOptimizeCandidate && firstLabRec && !postLab && (
                  <Button
                    type="button"
                    size="sm"
                    className="h-7 text-[11px]"
                    disabled={running}
                    onClick={() => onOptimizeCandidate(firstLabRec.row)}
                    title="Abre Lab con la #1 ★ precargada. Tú lanzas la búsqueda allí."
                  >
                    Abrir Lab · #1
                  </Button>
                )}
                {onOptimizeSemifinal && labRecCount > 0 && !postLab && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 text-[11px]"
                    disabled={running}
                    onClick={() =>
                      onOptimizeSemifinal(
                        deepNote.recommendations.map((r) => ({
                          row: r.row,
                          stars: r.stars,
                          starsCapped: r.starsCapped,
                          rank: r.rank,
                        })),
                      )
                    }
                    title={`Pasa hasta ${labRecCount} candidatas al Lab (3 columnas). Encola jobs hold-out/WF y deja config editable por zona.`}
                  >
                    {labRecCount === 1 ? 'Pasar al Lab' : `Pasar las ${labRecCount} al Lab`}
                  </Button>
                )}
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-3">
              {deepNote.recommendations.map((rec) => {
                const proxy = optimizeFamilyProxyNote(rec.row.strategyType);
                const canLab = isOptimizableStrategy(rec.row.strategyType);
                return (
                  <div
                    key={rec.row.strategyDefinitionId ?? `${rec.row.strategyType}-${rec.rank}`}
                    className={cn(
                      'flex flex-col gap-1.5 rounded-lg border bg-background/80 px-2.5 py-2',
                      rec.rank === 1
                        ? 'border-amber-400/50 ring-1 ring-amber-400/30'
                        : 'border-border/60',
                    )}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <div className="min-w-0">
                        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                          #{rec.rank}
                        </p>
                        <p className="text-xs font-semibold leading-snug text-foreground">
                          {rec.row.label}
                        </p>
                      </div>
                      <BacktestFutureStars stars={rec.stars} capped={rec.starsCapped} size="sm" />
                    </div>
                    <p className="text-[10px] tabular-nums text-muted-foreground">
                      {rec.row.totalReturnPct != null ? `Total ${formatPct(rec.row.totalReturnPct)}` : '—'}
                      {rec.lateReturnPct != null
                        ? ` · reciente ${rec.lateReturnPct >= 0 ? '+' : ''}${rec.lateReturnPct.toFixed(1)}%`
                        : ''}
                      {rec.row.excessReturnPct != null
                        ? ` · vs B&H ${formatPct(rec.row.excessReturnPct)}`
                        : ''}
                      {rec.row.maxDrawdownPct != null
                        ? ` · DD ${formatPct(rec.row.maxDrawdownPct)}`
                        : ''}
                    </p>
                    {(rec.earlyReturnPct != null ||
                      rec.midReturnPct != null ||
                      rec.usedSoftFallback ||
                      rec.qualityFlagged) && (
                      <p className="text-[10px] tabular-nums text-muted-foreground/90">
                        {rec.earlyReturnPct != null && rec.midReturnPct != null
                          ? `Tercios ${rec.earlyReturnPct.toFixed(0)}/${rec.midReturnPct.toFixed(0)}/${(rec.lateReturnPct ?? 0).toFixed(0)}%`
                          : null}
                        {rec.usedSoftFallback ? ' · sin tercios (fallback)' : ''}
                        {rec.qualityFlagged ? ' · suelo calidad' : ''}
                      </p>
                    )}
                    <p className="line-clamp-2 text-[10px] leading-snug text-muted-foreground">
                      {rec.reasons[1] ?? rec.reasons[0]}
                    </p>
                    <div className="mt-auto flex flex-wrap gap-1 pt-0.5">
                      {rec.row.runId && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-7 flex-1 text-[11px]"
                          onClick={() => onSelectRun(rec.row.runId!)}
                          title="Ver detalle / gráfico de esta prueba"
                        >
                          Ver
                        </Button>
                      )}
                      {onOptimizeCandidate && canLab && !postLab && (
                        <Button
                          type="button"
                          size="sm"
                          variant={rec.rank === 1 ? 'default' : 'outline'}
                          className="h-7 flex-1 text-[11px]"
                          title={
                            proxy
                              ? `${proxy} Abre Lab (tú lanzas).`
                              : 'Abre Lab con esta candidata (tú lanzas).'
                          }
                          onClick={() => onOptimizeCandidate(rec.row)}
                        >
                          {proxy ? 'Lab (aprox.)' : 'Lab'}
                        </Button>
                      )}
                      {onOptimizeCandidate && !canLab && (
                        <span className="px-1 text-[10px] text-muted-foreground" title="Sin familia de lab">
                          Sin lab
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="text-[10px] leading-snug text-muted-foreground">
              <strong className="font-medium text-foreground/80">Lab</strong> = abre el laboratorio
              con la candidata. <strong className="font-medium text-foreground/80">Encolar</strong> =
              lanza búsquedas en segundo plano. Guardar TOP-3 ≠ optimizar.
            </p>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Aún no hay candidatas ★. Espera a que termine la batería o lanza «Probar + coach».
          </p>
        )}

        {deepNote.regime && (
          <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5">
            <p className="text-[11px] font-medium text-foreground">{deepNote.regime.label}</p>
            <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
              {deepNote.regime.narrative}
            </p>
          </div>
        )}

        <details className="rounded-md border border-border/50 bg-background/40">
          <summary className="cursor-pointer list-none px-2 py-1.5 text-[11px] text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden">
            Análisis AT y outlook
          </summary>
          <div className="space-y-2 border-t border-border/40 px-2 py-2">
            <ul className="list-inside list-disc space-y-0.5 text-[11px] leading-snug text-muted-foreground">
              {deepNote.analysis.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <ul className="list-inside list-disc space-y-0.5 text-[11px] text-muted-foreground">
              {deepNote.outlook.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="text-[10px] leading-snug text-muted-foreground">{deepNote.disclaimer}</p>
          </div>
        </details>
      </div>

      {/* Evidencia B&H: secundaria, no decide el TOP ★ */}
      <details className="rounded-lg border border-dashed border-border/70 px-3 py-1.5">
        <summary
          className="cursor-pointer list-none text-[11px] text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden"
          title="Heurística vs buy & hold del lote. No manda sobre las estrellas del TOP-3."
        >
          Comparativa vs buy & hold
          <span className="ml-1 opacity-70">· no decide el TOP ★</span>
        </summary>
        <div className="mt-1.5 space-y-1 border-t border-border/40 pt-1.5">
          <p className="text-xs text-foreground">{coach.headline}</p>
          <ul className="list-inside list-disc space-y-0.5 text-[11px] text-muted-foreground">
            {coach.bullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
        </div>
      </details>

      {/* Batería: evidencia completa, colapsada */}
      <details className="rounded-lg border border-border/70" open={running || okCount === 0}>
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-3 py-2 text-[11px] marker:content-none [&::-webkit-details-marker]:hidden">
          <span className="font-medium text-foreground">
            Resultados de la batería
            <span className="ml-1.5 font-normal text-muted-foreground">
              {symbol} · {okCount} ok
              {progress && progress.total > 0 ? ` · ${progress.done}/${progress.total}` : ''}
              {running ? ' · ejecutando…' : ''}
            </span>
          </span>
          <span className="text-muted-foreground">Ver tabla</span>
        </summary>
        <div className="space-y-2 border-t border-border/50 px-3 pb-2.5 pt-2">
          <p className="text-[10px] text-muted-foreground">
            Ranking por % / B&H (histórico). Distinto del TOP ★ a futuro. Clic = Detalle · Lab =
            abre laboratorio.
          </p>
          <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
            Ordenar
            <select
              value={sort}
              onChange={(event) => onSortChange(event.target.value as ExploreSortKey)}
              className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <div className="max-h-[min(420px,50vh)] overflow-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card text-left text-muted-foreground">
                <tr>
                  <th className="w-8 p-1.5">#</th>
                  <th className="p-1.5">Preset</th>
                  <th className="p-1.5">Estrategia</th>
                  <th className="p-1.5">Vs B&H</th>
                  <th className="p-1.5">DD</th>
                  <th className="p-1.5">Estado</th>
                  <th className="p-1.5 text-right">Acción</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((row, index) => {
                  const rank = row.status === 'ok' ? index + 1 : '—';
                  const selected = Boolean(row.runId && row.runId === selectedRunId);
                  const clickable = row.status === 'ok' && Boolean(row.runId);
                  const canLab =
                    row.status === 'ok' && isOptimizableStrategy(row.strategyType);
                  const proxy = optimizeFamilyProxyNote(row.strategyType);
                  return (
                    <tr
                      key={row.strategyType}
                      className={cn(
                        'border-t border-border/50',
                        clickable && 'cursor-pointer hover:bg-muted/40',
                        selected && 'bg-amber-500/10 ring-1 ring-inset ring-amber-400/40',
                      )}
                      onClick={() => {
                        if (row.runId) onSelectRun(row.runId);
                      }}
                      title={row.error}
                    >
                      <td className="p-1.5 tabular-nums text-muted-foreground">{rank}</td>
                      <td className="p-1.5 font-medium text-foreground">
                        {row.label}
                        <span className="mt-0.5 block text-[10px] font-normal text-muted-foreground">
                          {row.categoryLabel}
                        </span>
                      </td>
                      <td
                        className={cn(
                          'p-1.5 tabular-nums',
                          (row.totalReturnPct ?? 0) >= 0 ? 'text-success' : 'text-destructive',
                        )}
                      >
                        {row.totalReturnPct != null ? formatPct(row.totalReturnPct) : '—'}
                      </td>
                      <td
                        className={cn(
                          'p-1.5 tabular-nums',
                          (row.excessReturnPct ?? 0) > 0 && 'text-success',
                          (row.excessReturnPct ?? 0) < 0 && 'text-destructive',
                        )}
                      >
                        {row.excessReturnPct != null ? formatPct(row.excessReturnPct) : '—'}
                      </td>
                      <td className="p-1.5 tabular-nums text-destructive">
                        {row.maxDrawdownPct != null ? formatPct(row.maxDrawdownPct) : '—'}
                      </td>
                      <td className="p-1.5 text-muted-foreground">
                        {row.status === 'ok'
                          ? 'OK'
                          : row.status === 'running'
                            ? '…'
                            : row.status === 'error'
                              ? 'Error'
                              : row.status === 'skipped'
                                ? 'Skip'
                                : '—'}
                      </td>
                      <td className="p-1.5 text-right">
                        {onOptimizeCandidate && canLab ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="h-6 px-1.5 text-[10px]"
                            title={proxy ?? 'Abrir Lab con este preset'}
                            onClick={(event) => {
                              event.stopPropagation();
                              onOptimizeCandidate(row);
                            }}
                          >
                            {proxy ? 'Lab≈' : 'Lab'}
                          </Button>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </div>
  );
}
