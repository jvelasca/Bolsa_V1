/**
 * Panel Coach (hub Probar → pestaña Coach).
 *
 * Operativa:
 * 1. Esperar a que termine «Probar + coach» (TOP ★ no se muestra a mitad).
 * 2. **Pasar las N al Lab** (CTA principal) = tablero 3 zonas + jobs; **Abrir Lab · #1** = prefill Lab.
 * 3. **Guardar TOP-3** = semifinal (sin Lab). Tras Lab: **Guardar Finalistas** (lab_validated).
 * 4. Batería / vs B&H = evidencia secundaria (colapsable).
 *
 * @see docs/engineering/research-lifecycle.md § P2
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  BacktestEquityPointDto,
  ChartTimeframe,
  ProfileHorizon,
  RiskTolerance,
} from "@bolsa/shared";
import {
  buildExploreCoachNote,
  type ExplorePresetRow,
  type ExploreSortKey,
} from "@/features/backtests/backtest-explore-value";
import { BacktestExploreBH } from "@/features/backtests/backtest-explore-bh";
import { BacktestExploreHeader } from "@/features/backtests/backtest-explore-header";
import { BacktestExploreBatteryTable } from "@/features/backtests/backtest-explore-battery-table";
import { BacktestExploreAtOutlook } from "@/features/backtests/backtest-explore-at-outlook";
import { BacktestExploreStarsGrid } from "@/features/backtests/backtest-explore-stars-grid";
import {
  buildDeepTechnicalCoachNote,
  buildCoachFacts,
  mergeLlmIntoDeepCoach,
  sanitizeLlmDeepCoachPayload,
  type DeepTechnicalCoachNote,
} from "@/features/backtests/backtest-deep-coach";
import {
  auditFindingsFromLlmPayload,
  buildAuditedDeepTechnicalCoachNote,
  readPriorCoachAuditHint,
  type CoachConfidence,
} from "@/features/backtests/coach-dual-audit";
import { CoachQuorumBar } from "@/features/backtests/coach-quorum-bar";
import { buildCoachTopSlots } from "@/features/backtests/coach-top-save";
import { sanitizeTopSlotsStrategyTypes } from "@/features/backtests/instrument-top-strategy-type";
import {
  buildCoachProfileBindingFacts,
  resolveCoachProfilePolicy,
} from "@/features/backtests/coach-profile-policy";
import {
  buildLabAdoptionFacts,
  readLabAdoption,
} from "@/features/backtests/lab-adoption-memory";
import { saveDiaDExperimentTop } from "@/features/backtests/dia-d-experiment-top";
import {
  resolveFullCycleSaveDecision,
  shouldWaitBeforeFinalistsAutoSave,
} from "@/features/backtests/backtest-assistant-full-cycle";
import {
  isCoach1AckSatisfied,
  resolveAssistantAckPolicy,
} from "@/features/backtests/assistant-cycle-orchestrator";
import {
  buildFinalistsFreshnessStamp,
  mergeFreshnessIntoCoachFacts,
  writeLocalFreshnessFingerprint,
} from "@/features/backtests/backtest-finalists-freshness";
import {
  mergeLabEvidenceIntoCoachFacts,
  resolveLabEvidenceForFinalistsSave,
} from "@/features/backtests/finalists-stability-summary";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { api } from "@/lib/api";

type Props = {
  rows: ExplorePresetRow[];
  instrumentId?: string | null;
  /** initial = Universo; post_lab = tras Reanalizar con Coach. */
  coachPass?: "initial" | "post_lab";
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
  /**
   * Si se pasa, manda sobre `savedTop` al decidir auto-save (p. ej. TOP huérfano → false).
   */
  hasExistingTopForSave?: boolean;
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
  /**
   * ADR-021: si hay fecha DÍA D en el pasado, el auto-save escribe F-D
   * (experimento) y **no** pisa Finalistas operativos (F-hoy).
   */
  experimentAsOf?: string | null;
};

function batteryText(rows: ExplorePresetRow[]): string {
  return rows
    .filter((r) => r.status === "ok")
    .map((r) => {
      const parts = [
        r.strategyType,
        r.label,
        `cat=${r.category}`,
        `ret=${r.totalReturnPct?.toFixed(2) ?? "n/a"}`,
        `excess=${r.excessReturnPct?.toFixed(2) ?? "n/a"}`,
        `dd=${r.maxDrawdownPct?.toFixed(2) ?? "n/a"}`,
        `sharpe=${r.sharpeRatio?.toFixed(2) ?? "n/a"}`,
        `trades=${r.tradeCount ?? "n/a"}`,
        `bars=${r.barCount ?? "n/a"}`,
      ];
      return parts.join(" | ");
    })
    .join("\n");
}

function localSummaryText(note: DeepTechnicalCoachNote): string {
  return [
    note.headline,
    ...note.analysis,
    ...note.recommendations.map(
      (r) =>
        `#${r.rank} ${r.row.label} (${r.row.strategyType}) score=${r.score}: ${r.reasons.join("; ")}`,
    ),
    note.regime?.narrative,
    ...note.outlook,
  ]
    .filter(Boolean)
    .join("\n");
}

/**
 * P2.8: serialización tipada del blob-abierto de hechos Coach → Record de wire.
 * El pipeline de coachFacts (policy/labEvidence/freshness/dualAudit...) es un
 * blob abierto intencional que el BE guarda opaco; por ello convertimos a la
 * representación de wire (Record<string, unknown>) en este único punto de
 * serialización, confinando el cast a la frontera TS↔wire.
 */
function toCoachFactsRecord(facts: import("@bolsa/shared").CoachFactsV1Dto) {
  return facts as unknown as Record<string, unknown>;
}

export function BacktestExploreRanking({
  rows,
  instrumentId,
  coachPass = "initial",
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
  autoSaveSemifinal = false,
  labImprovedCountHint = 0,
  hasExistingTopForSave,
  onCoachGateChange,
  freshnessInputFingerprint = null,
  llmNarrate = true,
  experimentAsOf = null,
}: Props) {
  const queryClient = useQueryClient();
  const postLab = coachPass === "post_lab";
  const savingExperiment = Boolean(experimentAsOf);
  const autoSaveFiredRef = useRef(false);
  const softAckLatchedRef = useRef(false);
  const loteKey = rows
    .map((r) => r.strategyDefinitionId ?? r.runId ?? r.strategyType)
    .join("|");
  const carryRows = useMemo(
    () => rows.filter((r) => r.labPass === "lab_carry"),
    [rows],
  );
  const coach = useMemo(
    () => buildExploreCoachNote(rows, symbol, { barLimit }),
    [rows, symbol, barLimit],
  );
  const okCount = rows.filter(
    (row) => row.status === "ok" && row.labPass !== "lab_carry",
  ).length;

  const { effectiveAccountId } = useActiveAccount();
  const profileQuery = useQuery({
    queryKey: ["account-active-profile", effectiveAccountId],
    queryFn: () => api.getAccountActiveProfile(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 60_000,
    retry: false,
  });
  const profile = profileQuery.data?.data;
  const horizon = (profile?.declared?.horizon ?? null) as ProfileHorizon | null;
  const riskTolerance = (profile?.declared?.riskTolerance ??
    null) as RiskTolerance | null;

  const coachCtx = useMemo(() => {
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
      evidenceLevel: (postLab ? "lab_validated" : "in_sample_only") as
        | "lab_validated"
        | "in_sample_only",
      futureWeight,
    };
  }, [
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
  ]);

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
          "El TOP ★ a futuro se calcula al terminar todas las genéricas.",
          "Motor A (ranking) + Motor B (auditor) + gate de consenso.",
          "La IA puede vetar tipado; no inventa estrategias fuera del lote.",
        ],
        recommendations: [],
        outlook: ["Espera al final del lote o cancela si no quieres seguir."],
        disclaimer:
          "Mientras corre la batería no mostramos un TOP provisional: evita elecciones inestables.",
      } satisfies DeepTechnicalCoachNote;
    }
    return buildAuditedDeepTechnicalCoachNote(rows, coachCtx, undefined, {
      coachPass: postLab ? "post_lab" : "initial",
    });
  }, [
    rows,
    coachCtx,
    running,
    progress?.done,
    progress?.total,
    okCount,
    symbol,
    timeframe,
    postLab,
  ]);

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
  const [engineLabel, setEngineLabel] = useState("local-AT+B");
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [discrepancyAck, setDiscrepancyAck] = useState(false);
  const lastLlmFingerprintRef = useRef<string>("");

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
    setEngineLabel("local-AT+B");
    if (softAckLatchedRef.current) {
      setDiscrepancyAck(true);
    }
  }, [localDeep]);

  const confidence: CoachConfidence =
    deepNote.audit?.confidence ?? "no_auditor";
  const softWeak = Boolean(deepNote.audit?.softWeak);
  const needsAck = confidence === "discrepancy" || confidence === "weak";
  /** Misma política que el check de ⋯ (no un segundo ACK distinto). */
  const ackPolicy = resolveAssistantAckPolicy({
    autoAckOnCycle,
    pauseIfAckNeeded,
  });
  const prefsAutoAck = ackPolicy.mode === "auto";
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
      (r) => r.labPass === "lab_improved" && r.status === "ok",
    ).length;
    return Math.max(fromRows, labImprovedCountHint);
  }, [rows, labImprovedCountHint]);

  const savedTopQuery = useQuery({
    queryKey: ["instrument-strategy-top", instrumentId, timeframe],
    queryFn: () =>
      api.getInstrumentStrategyTop(instrumentId!, String(timeframe)),
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
      if (!instrumentId) throw new Error("Sin instrumento");
      const note = opts?.note ?? deepNote;
      const conf = note.audit?.confidence ?? "no_auditor";
      const noteNeedsAck = conf === "discrepancy" || conf === "weak";
      const ackOk =
        !noteNeedsAck ||
        discrepancyAck ||
        Boolean(opts?.forceCycleAck) ||
        prefsAutoAck;
      const recs = note.recommendations.slice(0, 3);
      if (recs.length === 0) {
        throw new Error("Sin candidatas TOP para guardar");
      }
      if (noteNeedsAck && !ackOk) {
        throw new Error(
          "Marca el ack (TOP débil o discrepancia) para guardar con reserva",
        );
      }

      const strategiesRes = await api.getStrategies();
      const existing = strategiesRes.data ?? [];
      const tf = String(timeframe);

      const slots = await buildCoachTopSlots({
        recommendations: recs,
        symbol,
        timeframe: tf,
        slotSource: postLab ? "optimized" : "coach",
        requireRunId: postLab,
        lookup: {
          existing,
          createFromPreset: async (input) => {
            const created = await api.createStrategyFromPreset({
              name: input.name,
              presetKey:
                input.presetKey as import("@bolsa/shared").BacktestStrategyType,
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
      if (slots.length === 0)
        throw new Error("Sin recomendaciones para guardar");

      const strategiesFresh = await api.getStrategies();
      const presetById = new Map(
        (strategiesFresh.data ?? []).map((s) => [s.id, s.presetKey ?? null]),
      );
      for (const slot of slots) {
        const id = slot.strategyDefinitionId?.trim();
        if (!id || presetById.has(id)) continue;
        try {
          const one = await api.getStrategy(id);
          if (one?.data?.presetKey) presetById.set(id, one.data.presetKey);
        } catch {
          /* ignore */
        }
      }
      const slotsSanitized = sanitizeTopSlotsStrategyTypes(slots, presetById);

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
        ...toCoachFactsRecord(noteFacts),
        ...buildCoachProfileBindingFacts(policy),
        ...(adoptionFacts ?? {}),
        dualAudit: note.audit ?? null,
        discrepancyAck:
          conf === "discrepancy" || conf === "weak" ? true : false,
        coachPass: postLab ? "post_lab" : "initial",
        cycleAutoAck: Boolean(opts?.forceCycleAck) || prefsAutoAck,
      };
      const withFreshness =
        freshnessInputFingerprint && postLab
          ? mergeFreshnessIntoCoachFacts(
              baseFacts,
              buildFinalistsFreshnessStamp({
                inputFingerprint: freshnessInputFingerprint,
                lab: true,
              }),
            )
          : baseFacts;
      const slot1ForEvidence = [...slotsSanitized].sort(
        (a, b) => a.rank - b.rank,
      )[0];
      const labEvidenceSnap = postLab
        ? resolveLabEvidenceForFinalistsSave({
            strategyDefinitionId: slot1ForEvidence?.strategyDefinitionId,
            runId: slot1ForEvidence?.runId,
          })
        : null;
      const stampedFacts = mergeLabEvidenceIntoCoachFacts(
        withFreshness,
        labEvidenceSnap,
      );

      // ADR-021: experimento DÍA D → F-D local; no pisa F-hoy en BD.
      if (experimentAsOf) {
        const prodSlot1 = [...(savedTop?.slots ?? [])].sort(
          (a, b) => a.rank - b.rank,
        )[0];
        saveDiaDExperimentTop({
          instrumentId,
          timeframe: tf,
          asOfDiaD: experimentAsOf,
          slots: slotsSanitized,
          coachHeadline: note.headline,
          productionTop1AtSave: prodSlot1
            ? {
                strategyDefinitionId: prodSlot1.strategyDefinitionId ?? null,
                label: prodSlot1.label ?? null,
                strategyType: prodSlot1.strategyType ?? null,
              }
            : null,
        });
        return {
          experiment: true as const,
          asOfDiaD: experimentAsOf,
          slotCount: slotsSanitized.length,
        };
      }

      return api.upsertInstrumentStrategyTop(instrumentId, {
        instrumentId,
        symbol,
        timeframe: tf,
        periodLabel: periodLabel ?? null,
        status: postLab ? "active" : "semifinal",
        evidenceLevel: postLab ? "lab_validated" : noteFacts.evidenceLevel,
        slots: slotsSanitized,
        coachHeadline: note.headline,
        coachFacts: stampedFacts,
      });
    },
    onSuccess: async (data) => {
      if (
        data &&
        typeof data === "object" &&
        "experiment" in data &&
        data.experiment
      ) {
        setSaveMsg(
          `Experimento DÍA D ${data.asOfDiaD}: TOP F-D guardado (${data.slotCount}) · Finalistas operativos intactos`,
        );
        onAutoSaveStatus?.(
          `Ciclo: F-D guardado (DÍA D ${data.asOfDiaD}) · F-hoy no se pisó.`,
        );
        return;
      }
      setSaveMsg(
        postLab
          ? "Finalistas actualizados (lab_validated) · en Mis estrategias"
          : "TOP-3 semifinal guardado (sustituye previos) · en Mis estrategias",
      );
      if (postLab && freshnessInputFingerprint && instrumentId) {
        writeLocalFreshnessFingerprint({
          instrumentId,
          timeframe: String(timeframe),
          fingerprint: freshnessInputFingerprint,
        });
      }
      await savedTopQuery.refetch();
      await queryClient.invalidateQueries({ queryKey: ["strategies"] });
      await queryClient.invalidateQueries({
        queryKey: ["instrument-strategy-top"],
      });
    },
    onError: (err: Error) => {
      setSaveMsg(err.message || "Error al guardar TOP-3");
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
    if (!autoSaveSemifinal || postLab || running || autoSaveFiredRef.current)
      return;
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
        "Ciclo: atajo semifinal sin TOP guardable · Finalistas intactos.",
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
            "Ciclo: TOP semifinal guardado · Lab omitido (atajo).",
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
    if (!autoSaveFinalists || !postLab || running || autoSaveFiredRef.current)
      return;
    if (saveTopMutation.isPending) return;

    // Nota viva (localDeep): evita skip en el frame en que running=false pero
    // deepNote aún está vacío (carrera ACS / Coach²).
    const note = localDeep;
    const recsWithRun = note.recommendations.filter((r) =>
      Boolean(r.row.runId),
    );
    if (
      shouldWaitBeforeFinalistsAutoSave({
        running: Boolean(running),
        okCount,
        recommendationCount: note.recommendations.length,
        postLabRecsWithRunId: recsWithRun.length,
        postLab: true,
      })
    ) {
      return;
    }

    const conf = note.audit?.confidence ?? "no_auditor";
    const noteNeedsAck = conf === "weak" || conf === "discrepancy";
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

    const canSave =
      note.recommendations.length > 0 && noteAckOk && recsWithRun.length > 0;

    const decision = resolveFullCycleSaveDecision({
      postLab: true,
      labImprovedCount,
      canSaveTop: canSave,
      existingTopStatus: savingExperiment ? null : (savedTop?.status ?? null),
      // Experimento DÍA D: F-hoy no bloquea primera escritura de F-D.
      hasExistingTop: savingExperiment
        ? false
        : hasExistingTopForSave !== undefined
          ? hasExistingTopForSave
          : Boolean(savedTop),
    });

    if (decision.action === "save_active") {
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
      decision.action === "skip_no_candidates" &&
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
    hasExistingTopForSave,
    savingExperiment,
    experimentAsOf,
    discrepancyAck,
    prefsAutoAck,
    autoAckOnCycle,
    pauseIfAckNeeded,
  ]);

  const llmAbortRef = useRef<AbortController | null>(null);

  const llmMutation = useMutation({
    mutationFn: async () => {
      llmAbortRef.current?.abort();
      const ac = new AbortController();
      llmAbortRef.current = ac;
      const base = {
        context: localDeep.contextLabel,
        battery: batteryText(rows),
        localSummary: localSummaryText(localDeep),
        facts: coachFacts,
      };
      try {
        const [narrate, adversary] = await Promise.all([
          api.analyzeBacktestCoach(
            { ...base, mode: "narrate" },
            { signal: ac.signal },
          ),
          api.analyzeBacktestCoach(
            { ...base, mode: "adversary" },
            { signal: ac.signal },
          ),
        ]);
        return { narrate, adversary, aborted: ac.signal.aborted };
      } catch (error) {
        if (
          ac.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          return { narrate: null, adversary: null, aborted: true };
        }
        throw error;
      }
    },
    onSuccess: (result) => {
      if (!result || result.aborted || !result.narrate || !result.adversary)
        return;
      const { narrate, adversary } = result;
      const rawPayload = narrate.data.payload;
      const payload = sanitizeLlmDeepCoachPayload(rawPayload);
      const llmFindings = auditFindingsFromLlmPayload(payload, "llm");
      const adversaryFindings = auditFindingsFromLlmPayload(
        sanitizeLlmDeepCoachPayload(adversary.data.payload),
        "llm_c",
      );
      const audited = buildAuditedDeepTechnicalCoachNote(
        rows,
        coachCtx,
        llmFindings,
        {
          adversaryFindings,
          coachPass: postLab ? "post_lab" : "initial",
        },
      );
      if (!payload) {
        setEngineLabel(
          adversary.data.provider
            ? `${narrate.data.engine || "heuristic"} · C`
            : narrate.data.engine || "heuristic",
        );
        setDeepNote(audited);
        return;
      }
      setDeepNote(mergeLlmIntoDeepCoach(audited, payload));
      const provider = narrate.data.provider ?? adversary.data.provider;
      const model = narrate.data.model ?? adversary.data.model;
      setEngineLabel(
        provider
          ? `${provider}${model ? ` · ${model}` : ""} · A/B/C`
          : `${narrate.data.engine} · A/B/C`,
      );
    },
  });

  useEffect(() => {
    if (!running) return;
    llmAbortRef.current?.abort();
  }, [running]);

  useEffect(() => {
    return () => {
      llmAbortRef.current?.abort();
    };
  }, []);

  const loteFingerprint = rows
    .filter((r) => r.status === "ok")
    .map((r) => r.runId ?? r.strategyType)
    .join(",");

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
    setEngineLabel("local-AT+B · sin LLM");
  }, [llmNarrate, running, loteFingerprint]);

  const savedTopFooter = savedTop
    ? `Finalistas BD: v${savedTop.version} · ${savedTop.status} · ${savedTop.slots
        .map((s) => `#${s.rank} ${s.label}`)
        .join(" · ")}`
    : instrumentId
      ? "Sin TOP guardado aún para este valor/TF."
      : "";

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-y-auto overscroll-contain pb-2">
      {/* Núcleo: TOP-3 ★ + acciones Lab */}
      <div className="space-y-2.5 rounded-lg border border-border bg-muted/20 px-3 py-2.5">
        <BacktestExploreHeader
          contextLabel={deepNote.contextLabel}
          running={running}
          okCount={okCount}
          audit={deepNote.audit}
          confidence={confidence}
          engineLabel={engineLabel}
          llmNarrate={llmNarrate}
          llmBusy={llmMutation.isPending}
          saveEnabled={
            !running &&
            okCount > 0 &&
            Boolean(instrumentId) &&
            canSaveTop &&
            !saveTopMutation.isPending
          }
          reanalyzeEnabled={
            !running && okCount > 0 && !llmMutation.isPending && llmNarrate
          }
          postLab={postLab}
          saveMsg={saveMsg}
          savedTopFooter={savedTopFooter}
          priorAuditHint={priorAuditHint}
          onSaveTop={() => {
            setSaveMsg(null);
            saveTopMutation.mutate({});
          }}
          onReanalyze={() => {
            lastLlmFingerprintRef.current = "";
            llmMutation.mutate();
          }}
        />

        <p className="text-sm font-medium leading-snug text-foreground">
          {deepNote.headline}
        </p>
        {postLab && !running && (
          <p className="rounded-md border border-emerald-500/25 bg-emerald-500/5 px-2 py-1.5 text-[10px] text-emerald-100/90">
            <span className="font-medium">4 · Revalidar (Coach²)</span>
            {" · "}
            pasada tras Lab · evidencia lab · techo ★{coachFacts.starCeiling}.
            Las que no mejoraron (si las llevaste) no entran en el ranking ★.
            Soft-fail del red-team no bloquea Guardar si #1 está limpia.
          </p>
        )}
        {!postLab && !running && okCount > 0 && (
          <p className="rounded-md border border-border/50 bg-muted/20 px-2 py-1 text-[10px] text-muted-foreground">
            <span className="font-medium text-foreground">
              2 · Coach · ACK¹
            </span>
            {" · "}
            analiza el lote. Con ACK¹ (si hace falta) → Lab; sin mejora Lab no
            se revalida ni se pisa Finalistas; con mejora → Revalidar (ACK
            final).
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
              {postLab ? "ACK final" : "ACK¹"} = config Asistente
            </span>
            {" · "}
            automático (⋯).{" "}
            {postLab
              ? "Se graban Finalistas en BD si hubo mejora Lab."
              : "El ciclo sigue al Lab sin checkbox extra."}
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
                ? confidence === "weak"
                  ? "ACK final (paso 4→5): confirma para grabar Finalistas (⋯ tiene «Pausar ACK» o Auto-ACK OFF)."
                  : "ACK final: confirma para grabar Finalistas con reserva."
                : confidence === "weak"
                  ? "ACK¹: confirma para pasar al Lab."
                  : "ACK¹: confirma para pasar al Lab con reserva."}
              {!discrepancyAck ? " · Ciclo en pausa." : ""}
            </span>
          </label>
        )}

        {softWeak && confidence !== "weak" && !running && deepNote.audit && (
          <p className="rounded-md border border-border/70 bg-muted/25 px-2 py-1.5 text-[10px] text-muted-foreground">
            Aviso red-team (soft, no bloquea):{" "}
            {deepNote.audit.challenge.checks
              .filter((c) => !c.passed && c.severity === "soft")
              .map((c) => c.detail)
              .join(" · ")}
          </p>
        )}

        {confidence === "weak" && !running && deepNote.audit && (
          <p className="rounded-md border border-amber-500/25 bg-amber-500/5 px-2 py-1.5 text-[10px] text-amber-100/80">
            Avisos red-team:{" "}
            {deepNote.audit.challenge.checks
              .filter((c) => !c.passed)
              .map((c) => c.detail)
              .join(" · ") || "candidatas con veto suavizado"}
            . El TOP-3 se muestra igual; las ★ bajas indican poca confianza.
          </p>
        )}

        {deepNote.audit &&
          !running &&
          deepNote.audit.findings.some((f) => f.action === "veto") && (
            <p className="text-[10px] text-muted-foreground">
              Vetos B/C:{" "}
              {deepNote.audit.findings
                .filter((f) => f.action === "veto")
                .map((f) => `${f.strategyType} (${f.code}/${f.source})`)
                .join(" · ")}
            </p>
          )}

        <BacktestExploreStarsGrid
          recommendations={deepNote.recommendations}
          starCeiling={coachFacts.starCeiling}
          postLab={postLab}
          running={running}
          onSelectRun={onSelectRun}
          onOptimizeCandidate={onOptimizeCandidate}
          onOptimizeSemifinal={onOptimizeSemifinal}
        />

        <BacktestExploreAtOutlook
          regime={deepNote.regime}
          analysis={deepNote.analysis}
          outlook={deepNote.outlook}
          disclaimer={deepNote.disclaimer}
        />
      </div>

      {/* Evidencia B&H: secundaria, no decide el TOP ★ */}
      <BacktestExploreBH coach={coach} />

      {/* Batería: evidencia completa, colapsada */}
      <BacktestExploreBatteryTable
        rows={rows}
        symbol={symbol}
        okCount={okCount}
        progress={progress}
        running={running}
        sort={sort}
        onSortChange={onSortChange}
        selectedRunId={selectedRunId}
        onSelectRun={onSelectRun}
        onOptimizeCandidate={onOptimizeCandidate}
      />
    </div>
  );
}
