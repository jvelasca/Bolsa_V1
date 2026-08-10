import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDown,
  ChevronUp,
  Loader2,
  Play,
} from 'lucide-react';
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { OptimizeCardHeader } from '@/features/backtests/optimize-card-header';
import { OptimizeEmptyTip } from '@/features/backtests/optimize-empty-tip';
import { OptimizeSummaryStrip } from '@/features/backtests/optimize-summary-strip';
import { OptimizeWalkForwardReport } from '@/features/backtests/optimize-walk-forward-report';
import { OptimizeEdgeReport } from '@/features/backtests/optimize-edge-report';
import { OptimizeCpcvReport } from '@/features/backtests/optimize-cpcv-report';
import { OptimizeSeedBanner } from '@/features/backtests/optimize-seed-banner';
import type { LabZoneHandle } from '@/features/backtests/backtest-lab-board-types';
import type {
  ChartTimeframe,
  OptimizeEngine,
  OptimizeSmaGridRequestDto,
  OptimizeSmaGridResultDto,
  OptimizeStrategyFamily,
  SmaGridTrialDto,
  StrategyDefinitionV1,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { formatPct } from '@/features/charts/chart-utils';
import {
  BacktestOptimizeCompareTable,
  buildCompareRows,
  oosRankScore,
  type OptimizeCompareRow,
  type OptimizeRankBy,
} from '@/features/backtests/backtest-optimize-compare';
import {
  strategyDefinitionFromOptimizedMacd,
  strategyDefinitionFromOptimizedRsi,
  strategyDefinitionFromOptimizedSma,
  suggestOptimizedMacdName,
  suggestOptimizedRsiName,
  suggestOptimizedSmaName,
} from '@/features/backtests/backtest-optimized-strategy';
import { BacktestOptimizeProgress } from '@/features/backtests/backtest-optimize-progress';
import type { OptimizeProgressPhase } from '@/features/backtests/backtest-optimize-progress';
import {
  buildSmaPeriodLists,
  isOptimizableStrategy,
  optimizeFamilyForStrategy,
  optimizeFamilyProxyNote,
  smaAnchorPeriods,
  suggestBarLimit,
  suggestOptimizeValidation,
  type OptimizeSeed,
} from '@/features/backtests/backtest-optimize-seed';
import {
  buildOosEvidenceForAdopt,
  extractOosEvidenceFromOptimizeResult,
  oosEvidenceToPaperLabSnapshot,
  stashOosEvidenceForStrategy,
} from '@/features/backtests/backtest-oos-evidence';
import { credibilityHintFromLabWfe } from '@bolsa/shared';
import {
  OPTIMIZE_CPCV_HELP,
  OPTIMIZE_OOS_HELP,
  OPTIMIZE_WF_HELP,
  cpcvPathCount,
  clampRange,
  countValidCombinations,
  defaultMacdSpace,
  defaultRsiSpace,
  defaultSpaceForFamily,
  expandRange,
  formatTrialParams,
  scaleSearchSpace,
  spaceFromAnchor,
  spaceFromPeriodLists,
  type OptimizeSearchSpace,
  type RsiSearchSpace,
  type SmaSearchSpace,
} from '@/features/backtests/backtest-optimize-space';
import { BacktestOptimizeHeatmapPanel } from '@/features/backtests/backtest-optimize-heatmap-panel';
import { plateauAdoptionMetaFromTrials } from '@/features/backtests/backtest-optimize-heatmap';
import { LabZoneVerdictHero } from '@/features/backtests/lab-zone-verdict';
import {
  formatLabRiskSpaceHint,
  formatPreferredLabFamiliesHint,
  labImprovedRespectingProfileDd,
  labSpaceWidthFactorForRisk,
  preferredLabFamiliesForHorizon,
  resolveDefaultLabFamily,
} from '@/features/backtests/coach-profile-policy';
import {
  formatLabAdoptionHint,
  guidedSpaceFromAdoption,
  readLabAdoption,
  rememberLabAdoption,
  shouldApplyGuidedSpace,
  type LabAdoptionPlateauMeta,
} from '@/features/backtests/lab-adoption-memory';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface BacktestOptimizePanelProps {
  instruments: Array<{ id: string; symbol: string; name: string }>;
  defaultInstrumentId?: string;
  seed?: OptimizeSeed | null;
  onClearSeed?: () => void;
  /** Job ya encolado (p. ej. desde «Pasar al Lab»). */
  initialRunId?: string | null;
  /** Varios jobs (H0+Optuna): se enganchan en serie y se unen. */
  initialRunIds?: string[] | null;
  /** Columna del tablero TOP-3: cabecera compacta + estrella Coach. */
  compact?: boolean;
  zoneId?: string;
  zoneRank?: 1 | 2 | 3;
  zoneStars?: number;
  zoneStarsCapped?: boolean;
  /** Fired when a lab result is available (sync or async job). */
  onOptimizeComplete?: (payload: {
    seed: OptimizeSeed | null;
    result: OptimizeSmaGridResultDto;
  }) => void;
  /** After saving Mejor for Probar (no escribe Finalistas). */
  onAdoptedStrategy?: (payload: {
    strategyId: string;
    instrumentId: string;
    initialCash: number;
    timeframe: ChartTimeframe;
    barLimit?: number;
    labEvidence?: import('@bolsa/shared').PaperLabEvidenceSnapshot | null;
    skipAutoRun?: boolean;
  }) => void;
  /** Notifica estado de la zona para el CTA «Reanalizar con Coach». */
  onAdoptReadyChange?: (ready: {
    canAdopt: boolean;
    improved: boolean;
    label: string;
    score: number;
  }) => void;
  /** Actividad en vivo (cola / analizando) para el banner del tablero Lab. */
  onActivityChange?: (activity: {
    zoneId: string;
    rank: 1 | 2 | 3;
    label: string;
    phase: OptimizeProgressPhase | null;
    trialDone?: number | null;
    trialTotal?: number | null;
  }) => void;
  /** CORE-P: techo DD blando del perfil — no adoptar Mejor que lo rompa. */
  maxDrawdownSoftPct?: number | null;
  /** CORE-B / CORE-P: id perfil para stamp de memoria. */
  profileId?: string | null;
  /** CORE-P: horizonte → hint familias preferidas en espacio Lab. */
  profileHorizon?: import('@bolsa/shared').ProfileHorizon | null;
  /** CORE-P: riesgo → soft-bias anchura espacio Lab. */
  profileRiskTolerance?: import('@bolsa/shared').RiskTolerance | null;
}

function trialMergeKey(trial: SmaGridTrialDto, family: string): string {
  if (family === 'rsi_mean_reversion') {
    return `rsi-${trial.period}-${trial.oversold}-${trial.overbought}`;
  }
  if (family === 'macd_signal_cross') {
    return `macd-${trial.fastPeriod}-${trial.slowPeriod}-${trial.signalPeriod}`;
  }
  return `sma-${trial.fastPeriod}-${trial.slowPeriod}`;
}

function trialOos(trial: SmaGridTrialDto): number | null {
  const score = trial.oosMetrics?.score;
  return typeof score === 'number' && Number.isFinite(score) ? score : null;
}

/** Prefer OOS (with sparse-trade penalty) when both trials have it; otherwise IS. */
function isBetterTrial(candidate: SmaGridTrialDto, existing: SmaGridTrialDto): boolean {
  const candOos = trialOos(candidate);
  const existOos = trialOos(existing);
  if (candOos != null && existOos != null) {
    const diff = oosRankScore(candidate) - oosRankScore(existing);
    if (diff !== 0) return diff > 0;
  }
  return candidate.score > existing.score;
}

/** Union trials from several engines; keep the best OOS (else IS) per parameter set. */
function mergeOptimizeResults(parts: OptimizeSmaGridResultDto[]): OptimizeSmaGridResultDto {
  const first = parts[0]!;
  const family = String(first.strategyFamily ?? 'sma_crossover');
  const byKey = new Map<string, SmaGridTrialDto>();
  for (const part of parts) {
    for (const trial of part.trials) {
      const key = trialMergeKey(trial, family);
      const existing = byKey.get(key);
      if (!existing || isBetterTrial(trial, existing)) byKey.set(key, trial);
    }
  }
  const trials = [...byKey.values()].sort((a, b) => {
    const aOos = trialOos(a);
    const bOos = trialOos(b);
    if (aOos != null && bOos != null) {
      const diff = oosRankScore(b) - oosRankScore(a);
      if (diff !== 0) return diff;
    }
    return b.score - a.score;
  });
  return {
    ...first,
    engine: parts.map((part) => part.engine).join('+'),
    trialsTotal: Math.max(...parts.map((part) => part.trialsTotal ?? part.trials.length)),
    trials,
  };
}

function seedKey(seed: OptimizeSeed | null | undefined): string {
  if (!seed) return '';
  return [
    seed.source,
    seed.sourceRunId ?? '',
    seed.instrumentId,
    seed.strategyType,
    seed.barLimit ?? '',
    seed.initialCash,
    seed.timeframe,
  ].join('|');
}

const METHOD_OPTIONS: Array<{ id: OptimizeEngine; label: string; title: string }> = [
  {
    id: 'h0',
    label: 'Grid clásico',
    title: 'Prueba todas las combinaciones válidas del espacio (rápida < lenta). Base fiable.',
  },
  {
    id: 'vectorbt',
    label: 'Grid VectorBT',
    title: 'Mismo tipo de grid, motor más rápido si está instalado. Suele coincidir con el clásico.',
  },
  {
    id: 'optuna',
    label: 'IA Optuna',
    title: 'Búsqueda inteligente dentro del rango (no solo la malla). Complementa al grid; tarda más.',
  },
];

type AnchorOverride = {
  fast?: number;
  slow?: number;
  signal?: number;
  period?: number;
  oversold?: number;
  overbought?: number;
  returnPct: number;
  ddPct: number;
  tradeCount: number;
  score: number;
  label: string;
};

export const BacktestOptimizePanel = forwardRef<LabZoneHandle, BacktestOptimizePanelProps>(
  function BacktestOptimizePanel(
    {
      instruments,
      defaultInstrumentId = '',
      seed = null,
      onClearSeed,
      initialRunId = null,
      initialRunIds = null,
      compact = false,
      zoneId,
      zoneRank,
      zoneStars,
      zoneStarsCapped,
      onOptimizeComplete,
      onAdoptedStrategy,
      onAdoptReadyChange,
      onActivityChange,
      maxDrawdownSoftPct = null,
      profileId = null,
      profileHorizon = null,
      profileRiskTolerance = null,
    },
    ref,
  ) {
  const queryClient = useQueryClient();
  const onActivityChangeRef = useRef(onActivityChange);
  const [instrumentId, setInstrumentId] = useState(defaultInstrumentId);
  const preferredLabFamilies = preferredLabFamiliesForHorizon(profileHorizon);
  const labFamiliesHint = formatPreferredLabFamiliesHint(profileHorizon);
  const labRiskHint = formatLabRiskSpaceHint(profileRiskTolerance);
  const riskSpaceFactor = labSpaceWidthFactorForRisk(profileRiskTolerance);
  const [family, setFamily] = useState<OptimizeStrategyFamily>(() =>
    resolveDefaultLabFamily({ horizon: profileHorizon }),
  );
  /** Usuario eligió familia a mano — no pisar con horizonte/adopción. */
  const [familyUserPicked, setFamilyUserPicked] = useState(false);
  const [space, setSpace] = useState<OptimizeSearchSpace>(() =>
    defaultSpaceForFamily(resolveDefaultLabFamily({ horizon: profileHorizon })),
  );
  const [initialCash, setInitialCash] = useState('10000');
  const [barLimit, setBarLimit] = useState('500');
  const [timeframe, setTimeframe] = useState<ChartTimeframe>('1d');
  /** SMA: can combine grid + Optuna. RSI/MACD always H0. */
  const [methods, setMethods] = useState<OptimizeEngine[]>(['h0']);
  /** Off by default — short windows from a prior backtest often cannot split cleanly. */
  const [oosEnabled, setOosEnabled] = useState(false);
  const [oosPct, setOosPct] = useState('0.2');
  /** Expanding walk-forward (mutually exclusive with hold-out / CPCV). */
  const [wfEnabled, setWfEnabled] = useState(false);
  const [wfFolds, setWfFolds] = useState('3');
  /** CPCV ligero (mutually exclusive with hold-out / WF). */
  const [cpcvEnabled, setCpcvEnabled] = useState(false);
  const [cpcvGroups, setCpcvGroups] = useState('5');
  const [cpcvPurge, setCpcvPurge] = useState('5');
  const [cpcvEmbargo, setCpcvEmbargo] = useState('5');
  /** Prefer OOS for «Mejor» when hold-out/WF/CPCV produced oosMetrics. */
  const [rankBy, setRankBy] = useState<OptimizeRankBy>('oos');
  const [expanded, setExpanded] = useState(true);
  /** Sync by default so the results table always appears without depending on a worker. */
  const [runInBackground, setRunInBackground] = useState(Boolean(initialRunId));
  const [activeRunId, setActiveRunId] = useState<string | null>(initialRunId ?? null);
  const [multiRunning, setMultiRunning] = useState(false);
  const [multiProgress, setMultiProgress] = useState<string | null>(null);
  const [appliedSeedKey, setAppliedSeedKey] = useState('');
  const [savedRowId, setSavedRowId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [promoteMsg, setPromoteMsg] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [lastAsyncResult, setLastAsyncResult] = useState<OptimizeSmaGridResultDto | null>(null);
  const [anchorOverride, setAnchorOverride] = useState<AnchorOverride | null>(null);
  const optimizeNotifyRef = useRef('');
  const skipAutoRunRef = useRef(false);
  const attachedRunRef = useRef<string | null>(null);
  /** Coach→Lab multi-job (H0+Optuna): ids en orden + parts acumuladas. */
  const coachJobQueueRef = useRef<string[]>([]);
  const coachJobPartsRef = useRef<OptimizeSmaGridResultDto[]>([]);

  const resolvedInitialRunIds = useMemo(() => {
    if (initialRunIds && initialRunIds.length > 0) {
      return initialRunIds.filter(Boolean);
    }
    return initialRunId ? [initialRunId] : [];
  }, [initialRunId, initialRunIds]);

  const optimizeMutation = useMutation({
    mutationFn: api.optimizeBacktest,
    onSuccess: (response) => {
      setLastAsyncResult(response.data);
      setJobError(null);
      void queryClient.invalidateQueries({ queryKey: ['optimize-runs'] });
      void queryClient.invalidateQueries({ queryKey: ['research'] });
    },
    onError: (error) => {
      setJobError(
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'Error al optimizar',
      );
    },
  });

  const enqueueMutation = useMutation({
    mutationFn: api.enqueueOptimizeJob,
    onSuccess: (response) => {
      setActiveRunId(response.data.id);
      setJobError(null);
      // If the API already finished the job inline, show the table immediately.
      if (response.data.status === 'completed' && response.data.result) {
        setLastAsyncResult(response.data.result);
        setActiveRunId(null);
      } else if (response.data.status === 'failed') {
        setJobError(response.data.error ?? 'Optimización fallida');
        setActiveRunId(null);
      }
      void queryClient.invalidateQueries({ queryKey: ['optimize-runs'] });
    },
    onError: (error) => {
      setJobError(
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'No se pudo encolar la optimización',
      );
    },
  });

  const saveStrategyMutation = useMutation({
    mutationFn: (payload: {
      rowId: string;
      name: string;
      definition: StrategyDefinitionV1;
      /** Legacy flag: after save, optional Probar jump (never Finalistas). */
      adopt?: boolean;
      skipAutoRun?: boolean;
      oosEvidence?: ReturnType<typeof extractOosEvidenceFromOptimizeResult>;
      rowScore?: number;
      rowReturnPct?: number | null;
      rowMaxDrawdownPct?: number | null;
      paramsLabel?: string;
      params?: {
        fastPeriod?: number | null;
        slowPeriod?: number | null;
        signalPeriod?: number | null;
        period?: number | null;
        oversold?: number | null;
        overbought?: number | null;
      };
      /** CORE-B v0.1: meseta heatmap al adoptar. */
      plateau?: LabAdoptionPlateauMeta | null;
    }) => api.createStrategy({ name: payload.name, definition: payload.definition }),
    onSuccess: async (response, variables) => {
      setSavedRowId(variables.rowId);
      setSaveError(null);
      setPromoteMsg(null);
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
      if (variables.oosEvidence) {
        stashOosEvidenceForStrategy(response.data.id, variables.oosEvidence);
      }

      if (instrumentId && variables.paramsLabel) {
        rememberLabAdoption({
          instrumentId,
          timeframe,
          family,
          params: variables.params ?? {},
          paramsLabel: variables.paramsLabel,
          strategyId: response.data.id,
          oosKind: variables.oosEvidence?.kind ?? null,
          oosScore:
            variables.oosEvidence?.oosScore ??
            variables.oosEvidence?.meanOosScore ??
            null,
          score: variables.rowScore ?? null,
          maxDrawdownPct: variables.rowMaxDrawdownPct ?? null,
          profileId,
          plateau: variables.plateau ?? null,
        });
      }

      if (variables.adopt && onAdoptedStrategy && instrumentId) {
        const limit = Number.parseInt(barLimit, 10);
        onAdoptedStrategy({
          strategyId: response.data.id,
          instrumentId,
          initialCash: Number.parseFloat(initialCash) || 10_000,
          timeframe,
          barLimit: Number.isFinite(limit) && limit > 0 ? limit : undefined,
          labEvidence: variables.oosEvidence
            ? oosEvidenceToPaperLabSnapshot(variables.oosEvidence)
            : null,
          skipAutoRun: skipAutoRunRef.current || Boolean(variables.skipAutoRun),
        });
        skipAutoRunRef.current = false;
      }
    },
    onError: (error) => {
      setSaveError(
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'No se pudo guardar la estrategia',
      );
    },
  });

  const activeRunQuery = useQuery({
    queryKey: ['optimize-run', activeRunId],
    queryFn: () => api.getOptimizeRun(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: 1500,
  });

  useEffect(() => {
    const run = activeRunQuery.data?.data;
    if (!run || run.id !== activeRunId) return;
    if (run.status === 'completed') {
      if (run.result) {
        const queue = coachJobQueueRef.current;
        const isCoachBatch = queue.length > 1 && queue.includes(run.id);
        if (isCoachBatch) {
          coachJobPartsRef.current = [...coachJobPartsRef.current, run.result];
          const done = coachJobPartsRef.current.length;
          if (done < queue.length) {
            const nextId = queue[done]!;
            setMultiProgress(`Método ${done + 1}/${queue.length} (H0+Optuna)…`);
            setActiveRunId(nextId);
            attachedRunRef.current = nextId;
            setJobError(null);
            return;
          }
          setLastAsyncResult(mergeOptimizeResults(coachJobPartsRef.current));
          setJobError(null);
          setMultiProgress(null);
          coachJobQueueRef.current = [];
          coachJobPartsRef.current = [];
          setActiveRunId(null);
          attachedRunRef.current = null;
        } else {
          setLastAsyncResult(run.result);
          setJobError(null);
          setActiveRunId(null);
        }
      } else {
        setJobError(
          'La optimización terminó, pero no se pudieron leer los resultados. Prueba sin segundo plano.',
        );
        setActiveRunId(null);
        setMultiProgress(null);
        coachJobQueueRef.current = [];
        coachJobPartsRef.current = [];
      }
      void queryClient.invalidateQueries({ queryKey: ['optimize-runs'] });
      void queryClient.invalidateQueries({ queryKey: ['research'] });
    } else if (run.status === 'failed') {
      const queue = coachJobQueueRef.current;
      const isCoachBatch = queue.length > 1;
      if (isCoachBatch && coachJobPartsRef.current.length > 0) {
        setLastAsyncResult(mergeOptimizeResults(coachJobPartsRef.current));
        setJobError(
          `Un método falló (${run.error ?? 'error'}); se muestran los que sí terminaron.`,
        );
        setMultiProgress(null);
        coachJobQueueRef.current = [];
        coachJobPartsRef.current = [];
        setActiveRunId(null);
        attachedRunRef.current = null;
      } else {
        setJobError(run.error ?? 'Optimización fallida');
        setActiveRunId(null);
        setMultiProgress(null);
        coachJobQueueRef.current = [];
        coachJobPartsRef.current = [];
      }
    }
  }, [activeRunQuery.data, activeRunId, queryClient]);

  useEffect(() => {
    if (!seed) return;
    const key = seedKey(seed);
    if (key === appliedSeedKey) return;

    setInstrumentId(seed.instrumentId);
    setInitialCash(String(seed.initialCash));
    setTimeframe(seed.timeframe);
    const bars = suggestBarLimit(seed.barLimit);
    setBarLimit(String(bars));
    const hint = seed.validationHint ?? suggestOptimizeValidation(bars);
    setCpcvEnabled(false);
    if (hint.mode === 'walkforward') {
      setOosEnabled(false);
      setWfEnabled(true);
      setWfFolds(String(hint.walkForwardFolds ?? 3));
    } else {
      // Preset pro: hold-out ON para evidencia OOS del Lab (puerta a Coach² / Finalistas).
      setOosEnabled(true);
      setOosPct(String(hint.oosPct ?? 0.2));
      setWfEnabled(false);
    }
    setRankBy('oos');
    setExpanded(true);
    setLastAsyncResult(null);
    setJobError(null);
    setSavedRowId(null);
    setMultiProgress(null);
    coachJobPartsRef.current = [];

    // Reattach queued job(s) for this zone (Coach → Lab) after seed reset.
    const ids = resolvedInitialRunIds;
    coachJobQueueRef.current = ids;
    if (ids.length > 0) {
      setRunInBackground(true);
      setActiveRunId(ids[0]!);
      attachedRunRef.current = ids[0]!;
      if (ids.length > 1) {
        setMultiProgress(`Método 1/${ids.length} (H0+Optuna)…`);
      }
    } else {
      setActiveRunId(null);
      attachedRunRef.current = null;
    }

    const resolvedFamily = optimizeFamilyForStrategy(seed.strategyType) ?? 'sma_crossover';
    setFamily(resolvedFamily);
    setMethods(resolvedFamily === 'sma_crossover' ? ['h0', 'optuna'] : ['h0']);
    setSpace(defaultSpaceForFamily(resolvedFamily));

    if (resolvedFamily === 'sma_crossover') {
      const lists = buildSmaPeriodLists(
        isOptimizableStrategy(seed.strategyType) ? seed.strategyType : 'sma_crossover',
      );
      setSpace(spaceFromPeriodLists(lists.fastPeriods, lists.slowPeriods));
    }

    const catalog = smaAnchorPeriods(seed.strategyType);
    const ret = seed.anchorReturnPct;
    const dd = seed.anchorMaxDrawdownPct;
    setAnchorOverride({
      fast: seed.anchorFast ?? catalog?.fast,
      slow: seed.anchorSlow ?? catalog?.slow,
      signal: seed.anchorSignal,
      period: seed.anchorPeriod,
      oversold: seed.anchorOversold,
      overbought: seed.anchorOverbought,
      returnPct: ret ?? 0,
      ddPct: dd ?? 0,
      tradeCount: seed.anchorTradeCount ?? 0,
      score: seed.anchorScore ?? (ret != null && dd != null ? ret - dd * 0.25 : 0),
      label: `Original · ${seed.strategyLabel}`,
    });

    if (resolvedFamily === 'sma_crossover' && seed.anchorFast != null && seed.anchorSlow != null) {
      if (ret == null || dd == null) {
        setSpace(spaceFromAnchor(seed.anchorFast, seed.anchorSlow));
      }
    }

    // CORE B: espacio guiado desde última adopción (misma familia).
    const priorAdoption = readLabAdoption(seed.instrumentId, seed.timeframe);
    if (shouldApplyGuidedSpace(priorAdoption, resolvedFamily) && priorAdoption) {
      const guided = guidedSpaceFromAdoption(priorAdoption);
      if (guided) {
        setSpace(scaleSearchSpace(guided, labSpaceWidthFactorForRisk(profileRiskTolerance)));
      }
    }

    setAppliedSeedKey(key);
  }, [seed, appliedSeedKey, resolvedInitialRunIds, profileRiskTolerance]);

  useEffect(() => {
    if (resolvedInitialRunIds.length === 0) return;
    const first = resolvedInitialRunIds[0]!;
    if (attachedRunRef.current === first && activeRunId === first) return;
    if (lastAsyncResult) return;
    if (coachJobPartsRef.current.length > 0) return;
    setRunInBackground(true);
    coachJobQueueRef.current = resolvedInitialRunIds;
    setActiveRunId(first);
    attachedRunRef.current = first;
    if (resolvedInitialRunIds.length > 1) {
      setMultiProgress(`Método 1/${resolvedInitialRunIds.length} (H0+Optuna)…`);
    }
  }, [resolvedInitialRunIds, activeRunId, lastAsyncResult]);

  useEffect(() => {
    if (seed) return;
    if (familyUserPicked) return;
    const prior = instrumentId
      ? readLabAdoption(instrumentId, timeframe)
      : null;
    const nextFamily = resolveDefaultLabFamily({
      adoptionFamily: prior?.family ?? null,
      horizon: profileHorizon,
    });
    setFamily(nextFamily);
    let nextSpace: OptimizeSearchSpace;
    if (prior && shouldApplyGuidedSpace(prior, nextFamily)) {
      const guided = guidedSpaceFromAdoption(prior);
      nextSpace = guided ?? defaultSpaceForFamily(nextFamily);
    } else {
      nextSpace = defaultSpaceForFamily(nextFamily);
    }
    setSpace(scaleSearchSpace(nextSpace, riskSpaceFactor));
  }, [
    seed,
    familyUserPicked,
    instrumentId,
    timeframe,
    profileHorizon,
    riskSpaceFactor,
  ]);

  useEffect(() => {
    if (seed) return;
    if (defaultInstrumentId && !instrumentId) setInstrumentId(defaultInstrumentId);
  }, [defaultInstrumentId, instrumentId, seed]);

  useEffect(() => {
    if (family !== 'sma_crossover') setMethods(['h0']);
  }, [family]);

  const multiPathMode = wfEnabled || cpcvEnabled;
  const selectedMethods = useMemo(
    () =>
      multiPathMode || family !== 'sma_crossover' ? (['h0'] as OptimizeEngine[]) : methods,
    [multiPathMode, family, methods],
  );
  const usesOptuna = selectedMethods.includes('optuna');
  const wfFoldCount = Math.max(2, Math.min(5, Number.parseInt(wfFolds, 10) || 3));
  const cpcvGroupCount = Math.max(4, Math.min(6, Number.parseInt(cpcvGroups, 10) || 5));
  const cpcvPaths = cpcvPathCount(cpcvGroupCount);
  const trialTotal = useMemo(() => {
    const perMethod = countValidCombinations(
      space,
      family === 'sma_crossover' ? (usesOptuna && selectedMethods.length === 1 ? 100 : 200) : 80,
    );
    // Rough total when stacking methods (Optuna capped at 100).
    let total = 0;
    for (const method of selectedMethods) {
      total += method === 'optuna' ? Math.min(100, perMethod) : perMethod;
    }
    if (cpcvEnabled) {
      total = Math.min(perMethod, 80) * cpcvPaths;
    } else if (wfEnabled) {
      total = Math.min(perMethod, 80) * wfFoldCount;
    }
    return Math.max(1, total);
  }, [space, family, selectedMethods, usesOptuna, wfEnabled, wfFoldCount, cpcvEnabled, cpcvPaths]);

  const result = lastAsyncResult ?? optimizeMutation.data?.data ?? null;
  const resultFamily = (result?.strategyFamily as OptimizeStrategyFamily | undefined) ?? family;
  const seedValidationHint = seed
    ? (seed.validationHint ?? suggestOptimizeValidation(seed.barLimit))
    : null;

  useEffect(() => {
    if (!result?.trials?.length || !onOptimizeComplete) return;
    const best = result.trials[0]!;
    const key = [
      seedKey(seed),
      result.engine,
      best.score,
      best.totalReturnPct,
      best.fastPeriod ?? '',
      best.period ?? '',
    ].join('|');
    if (optimizeNotifyRef.current === key) return;
    optimizeNotifyRef.current = key;
    onOptimizeComplete({ seed, result });
  }, [result, seed, onOptimizeComplete]);

  const showOos = Boolean(result?.oosPct && result.oosPct > 0);
  const walkForward = result?.walkForward ?? null;
  const cpcv = result?.cpcv ?? null;
  const edgeReport = result?.edgeReport ?? null;
  const pbo = result?.pbo ?? result?.cpcv?.pbo ?? null;
  const labWfeHint = useMemo(() => {
    if (edgeReport) return null;
    const wfe = cpcv?.walkForwardEfficiency ?? walkForward?.walkForwardEfficiency;
    if (wfe == null || !Number.isFinite(wfe)) return null;
    return credibilityHintFromLabWfe(wfe, result?.trialsTotal ?? 1);
  }, [cpcv, walkForward, result?.trialsTotal, edgeReport]);

  const isRunning =
    multiRunning ||
    optimizeMutation.isPending ||
    enqueueMutation.isPending ||
    activeRunId !== null;

  const selectedInstrument = instruments.find((item) => item.id === instrumentId);
  const activeRun = activeRunQuery.data?.data;
  const payloadTotal =
    typeof activeRun?.payload?.trialsTotal === 'number'
      ? activeRun.payload.trialsTotal
      : trialTotal;

  const progressPhase = (() => {
    if (multiRunning || optimizeMutation.isPending || enqueueMutation.isPending) {
      return 'running' as const;
    }
    if (activeRunId) {
      const status = activeRun?.status;
      if (status === 'pending') return 'pending' as const;
      if (status === 'failed') return 'failed' as const;
      if (status === 'completed') return 'completed' as const;
      return 'processing' as const;
    }
    return null;
  })();

  const liveTrialDone =
    activeRun?.status === 'processing' || activeRun?.status === 'completed'
      ? (activeRun.trialCount ?? 0)
      : null;

  useEffect(() => {
    onActivityChangeRef.current = onActivityChange;
  }, [onActivityChange]);

  useEffect(() => {
    const notify = onActivityChangeRef.current;
    if (!notify) return;
    const id = zoneId ?? (seed ? seedKey(seed) : 'lab-zone');
    notify({
      zoneId: id,
      rank: zoneRank ?? 1,
      label: seed?.strategyLabel ?? `Zona #${zoneRank ?? 1}`,
      phase: progressPhase,
      trialDone: liveTrialDone,
      trialTotal: payloadTotal,
    });
  }, [
    zoneId,
    zoneRank,
    seed,
    progressPhase,
    liveTrialDone,
    payloadTotal,
  ]);

  const showLiveProgress =
    progressPhase != null &&
    progressPhase !== 'completed' &&
    progressPhase !== 'failed';

  const progressNode = progressPhase ? (
    <BacktestOptimizeProgress
      phase={progressPhase}
      trialTotal={payloadTotal}
      trialDone={liveTrialDone}
      bestScore={activeRun?.bestScore ?? result?.trials[0]?.score ?? null}
      scoreHistory={(result?.trials ?? []).slice(0, 12).map((t) => t.score).reverse()}
      compact={compact}
      engineHint={
        multiProgress
          ? 'h0+optuna'
          : (typeof activeRun?.payload?.engine === 'string' && activeRun.payload.engine) ||
            (selectedMethods.length === 1 ? selectedMethods[0] : null) ||
            family
      }
    />
  ) : null;

  const compareRows = useMemo(() => {
    if (!result) return [];
    const catalogAnchor = smaAnchorPeriods('sma_crossover') ?? { fast: 20, slow: 50 };
    let anchor = {
      fastPeriod: anchorOverride?.fast ?? catalogAnchor.fast,
      slowPeriod: anchorOverride?.slow ?? catalogAnchor.slow,
      signalPeriod: anchorOverride?.signal,
      period: anchorOverride?.period,
      oversold: anchorOverride?.oversold,
      overbought: anchorOverride?.overbought,
      totalReturnPct: anchorOverride?.returnPct ?? result.baseline.totalReturnPct,
      maxDrawdownPct: anchorOverride?.ddPct ?? result.baseline.maxDrawdownPct,
      tradeCount: anchorOverride?.tradeCount ?? result.baseline.tradeCount,
      score: anchorOverride?.score ?? result.baseline.score,
      label: anchorOverride?.label ?? 'Baseline',
      oosMetrics: result.baseline.oosMetrics,
    };

    const matched = result.trials.find((trial) => {
      if (resultFamily === 'rsi_mean_reversion') {
        return (
          trial.period === anchor.period &&
          trial.oversold === anchor.oversold &&
          trial.overbought === anchor.overbought
        );
      }
      if (resultFamily === 'macd_signal_cross') {
        return (
          trial.fastPeriod === anchor.fastPeriod &&
          trial.slowPeriod === anchor.slowPeriod &&
          trial.signalPeriod === anchor.signalPeriod
        );
      }
      return trial.fastPeriod === anchor.fastPeriod && trial.slowPeriod === anchor.slowPeriod;
    });
    if (matched && (anchorOverride?.returnPct == null || seed == null)) {
      anchor = {
        ...anchor,
        totalReturnPct: matched.totalReturnPct,
        maxDrawdownPct: matched.maxDrawdownPct,
        tradeCount: matched.tradeCount,
        score: matched.score,
        oosMetrics: matched.oosMetrics,
      };
    }

    return buildCompareRows({
      family: resultFamily,
      anchor,
      trials: result.trials,
      topN: 10,
      rankBy: showOos ? rankBy : 'is',
    });
  }, [anchorOverride, rankBy, result, resultFamily, seed, showOos]);

  const bestVsAnchor = useMemo(() => {
    const best = compareRows.find((row) => row.status === 'best');
    const anchor = compareRows.find((row) => row.status === 'anchor');
    if (!best || !anchor || best.deltaScore == null) return null;
    const useOos = showOos && rankBy === 'oos' && best.deltaOosScore != null;
    const scoreImproved = useOos ? best.deltaOosScore! > 0 : best.deltaScore > 0;
    const { improved, profileDdBlocked } = labImprovedRespectingProfileDd({
      scoreImproved,
      maxDrawdownPct: best.maxDrawdownPct,
      maxDrawdownSoftPct,
    });
    const isChamp = compareRows.find((row) => row.label === 'Mejor IS (no OOS)');
    return {
      best,
      anchor,
      improved,
      scoreImproved,
      profileDdBlocked,
      maxDrawdownSoftPct,
      rankedByOos: useOos,
      isChampDiffers: Boolean(isChamp),
      isChampParams: isChamp?.paramsLabel ?? null,
    };
  }, [compareRows, rankBy, showOos, maxDrawdownSoftPct]);

  const fieldClass = 'mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm';
  const familyReady = seed ? isOptimizableStrategy(seed.strategyType) : true;

  function setFamilyAndSpace(next: OptimizeStrategyFamily) {
    setFamilyUserPicked(true);
    setFamily(next);
    setSpace(scaleSearchSpace(defaultSpaceForFamily(next), riskSpaceFactor));
  }

  function patchSma(side: 'fast' | 'slow', patch: Partial<{ min: number; max: number; step: number }>) {
    setSpace((current) => {
      if (current.family !== 'sma_crossover') return current;
      return {
        ...current,
        [side]: clampRange({ ...current[side], ...patch }),
      } satisfies SmaSearchSpace;
    });
  }

  function patchRsi(
    side: 'period' | 'oversold' | 'overbought',
    patch: Partial<{ min: number; max: number; step: number }>,
  ) {
    setSpace((current) => {
      if (current.family !== 'rsi_mean_reversion') return current;
      const floor = side === 'period' ? 2 : 5;
      return {
        ...current,
        [side]: clampRange({ ...current[side], ...patch }, floor),
      } satisfies RsiSearchSpace;
    });
  }

  function buildRequest(engine: OptimizeEngine): OptimizeSmaGridRequestDto {
    const limit = Number.parseInt(barLimit, 10);
    const oos = !multiPathMode && oosEnabled ? Number.parseFloat(oosPct) : null;
    const purge = Math.max(0, Math.min(20, Number.parseInt(cpcvPurge, 10) || 5));
    const embargo = Math.max(0, Math.min(20, Number.parseInt(cpcvEmbargo, 10) || 5));
    const base: OptimizeSmaGridRequestDto = {
      instrumentId,
      strategyFamily: family,
      initialCash: Number.parseFloat(initialCash) || 10000,
      timeframe,
      engine: multiPathMode || family !== 'sma_crossover' ? 'h0' : engine,
      maxTrials: multiPathMode
        ? 80
        : family === 'sma_crossover'
          ? engine === 'optuna'
            ? 100
            : 200
          : 80,
      ...(Number.isFinite(limit) && limit > 0 ? { barLimit: limit } : {}),
      ...(oos != null && oos > 0 ? { oosPct: oos } : {}),
      ...(wfEnabled && !cpcvEnabled ? { walkForwardFolds: wfFoldCount } : {}),
      ...(cpcvEnabled
        ? {
            cpcvGroups: cpcvGroupCount,
            cpcvPurgeBars: purge,
            cpcvEmbargoBars: embargo,
          }
        : {}),
    };

    if (space.family === 'sma_crossover') {
      return {
        ...base,
        fastPeriods: expandRange(space.fast),
        slowPeriods: expandRange(space.slow),
      };
    }
    if (space.family === 'rsi_mean_reversion') {
      return {
        ...base,
        periods: expandRange(space.period),
        oversoldLevels: expandRange(space.oversold, 5),
        overboughtLevels: expandRange(space.overbought, 50),
      };
    }
    return base;
  }

  function toggleMethod(method: OptimizeEngine) {
    setMethods((current) => {
      if (current.includes(method)) {
        const next = current.filter((item) => item !== method);
        return next.length > 0 ? next : current;
      }
      return [...current, method];
    });
  }

  async function handleRun() {
    setSavedRowId(null);
    setSaveError(null);
    setJobError(null);
    setLastAsyncResult(null);
    setMultiProgress(null);

    const engines = selectedMethods;
    if (engines.length > 1 && runInBackground) {
      setJobError(
        'Con varios métodos a la vez, desactiva «Segundo plano» (se ejecutan uno tras otro y se unen los resultados).',
      );
      return;
    }

    if (engines.length === 1) {
      const request = buildRequest(engines[0]!);
      if (runInBackground) enqueueMutation.mutate(request);
      else optimizeMutation.mutate(request);
      return;
    }

    setMultiRunning(true);
    try {
      const parts: OptimizeSmaGridResultDto[] = [];
      for (let index = 0; index < engines.length; index += 1) {
        const engine = engines[index]!;
        setMultiProgress(`Método ${index + 1}/${engines.length}: ${engine}…`);
        const response = await api.optimizeBacktest(buildRequest(engine));
        parts.push(response.data);
      }
      setLastAsyncResult(mergeOptimizeResults(parts));
      setJobError(null);
      void queryClient.invalidateQueries({ queryKey: ['optimize-runs'] });
      void queryClient.invalidateQueries({ queryKey: ['research'] });
    } catch (error) {
      setJobError(
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'Error al optimizar',
      );
    } finally {
      setMultiRunning(false);
      setMultiProgress(null);
    }
  }

  function buildDefinitionForRow(row: OptimizeCompareRow): {
    name: string;
    definition: StrategyDefinitionV1;
  } {
    const symbol = selectedInstrument?.symbol ?? seed?.symbol;
    if (resultFamily === 'rsi_mean_reversion') {
      const period = row.period ?? 14;
      const oversold = row.oversold ?? 30;
      const overbought = row.overbought ?? 70;
      const name = suggestOptimizedRsiName({ period, oversold, overbought, symbol });
      return {
        name,
        definition: strategyDefinitionFromOptimizedRsi({
          name,
          period,
          oversold,
          overbought,
          timeframe,
          instrumentIds: instrumentId ? [instrumentId] : [],
        }),
      };
    }
    if (resultFamily === 'macd_signal_cross') {
      const fastPeriod = row.fastPeriod || 12;
      const slowPeriod = row.slowPeriod || 26;
      const signalPeriod = row.signalPeriod ?? 9;
      const name = suggestOptimizedMacdName({ fastPeriod, slowPeriod, signalPeriod, symbol });
      return {
        name,
        definition: strategyDefinitionFromOptimizedMacd({
          name,
          fastPeriod,
          slowPeriod,
          signalPeriod,
          timeframe,
          instrumentIds: instrumentId ? [instrumentId] : [],
        }),
      };
    }
    const name = suggestOptimizedSmaName({
      fastPeriod: row.fastPeriod,
      slowPeriod: row.slowPeriod,
      symbol,
    });
    return {
      name,
      definition: strategyDefinitionFromOptimizedSma({
        name,
        fastPeriod: row.fastPeriod,
        slowPeriod: row.slowPeriod,
        timeframe,
        instrumentIds: instrumentId ? [instrumentId] : [],
      }),
    };
  }

  function plateauMetaForAdoption(): LabAdoptionPlateauMeta | null {
    if (!result?.trials?.length) return null;
    return plateauAdoptionMetaFromTrials({
      trials: result.trials,
      family: resultFamily,
      scoreMode: showOos && rankBy === 'oos' ? 'oos' : 'is',
    });
  }

  function handleSave(
    row: OptimizeCompareRow,
    adopt = false,
    opts?: { skipAutoRun?: boolean },
  ): Promise<boolean> {
    const { name, definition } = buildDefinitionForRow(row);
    const oosEvidence = buildOosEvidenceForAdopt(result ?? undefined, row);

    if (adopt) {
      skipAutoRunRef.current = Boolean(opts?.skipAutoRun);
    }

    return saveStrategyMutation
      .mutateAsync({
        rowId: row.id,
        name,
        definition,
        adopt,
        skipAutoRun: opts?.skipAutoRun,
        oosEvidence,
        rowScore: row.score,
        rowReturnPct: row.totalReturnPct ?? null,
        rowMaxDrawdownPct: row.maxDrawdownPct ?? null,
        paramsLabel: row.paramsLabel,
        params: {
          fastPeriod: row.fastPeriod,
          slowPeriod: row.slowPeriod,
          signalPeriod: row.signalPeriod,
          period: row.period,
          oversold: row.oversold,
          overbought: row.overbought,
        },
        plateau: plateauMetaForAdoption(),
      })
      .then(() => true)
      .catch(() => false);
  }

  const zoneImproved = Boolean(bestVsAnchor?.improved);

  useEffect(() => {
    onAdoptReadyChange?.({
      canAdopt: zoneImproved,
      improved: zoneImproved,
      label: bestVsAnchor?.best.paramsLabel ?? seed?.strategyLabel ?? '—',
      score: bestVsAnchor?.best.score ?? 0,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    zoneImproved,
    bestVsAnchor?.best.paramsLabel,
    bestVsAnchor?.best.score,
    seed?.strategyLabel,
  ]);

  useImperativeHandle(
    ref,
    () => ({
      getHandoff: () => {
        if (!bestVsAnchor) {
          return seed
            ? {
                zoneId: zoneId ?? seedKey(seed),
                rank: zoneRank ?? 1,
                improved: false,
                hasResult: false,
                label: seed.strategyLabel,
                score: seed.anchorScore ?? 0,
                strategyType: seed.strategyType,
                seedLabel: seed.strategyLabel,
                ensureBestStrategy: async () => null,
              }
            : null;
        }
        return {
          zoneId: zoneId ?? seedKey(seed),
          rank: zoneRank ?? 1,
          improved: bestVsAnchor.improved,
          hasResult: true,
          label: bestVsAnchor.best.paramsLabel,
          score: bestVsAnchor.best.score,
          strategyType: seed?.strategyType ?? family,
          seedLabel: seed?.strategyLabel,
          ensureBestStrategy: async () => {
            if (!bestVsAnchor.improved) return null;
            try {
              const { name, definition } = buildDefinitionForRow(bestVsAnchor.best);
              const oosEvidence = buildOosEvidenceForAdopt(
                result ?? undefined,
                bestVsAnchor.best,
              );
              const created = await api.createStrategy({ name, definition });
              if (oosEvidence.kind !== 'none') {
                stashOosEvidenceForStrategy(created.data.id, oosEvidence);
              }
              if (instrumentId) {
                rememberLabAdoption({
                  instrumentId,
                  timeframe,
                  family,
                  params: {
                    fastPeriod: bestVsAnchor.best.fastPeriod,
                    slowPeriod: bestVsAnchor.best.slowPeriod,
                    signalPeriod: bestVsAnchor.best.signalPeriod,
                    period: bestVsAnchor.best.period,
                    oversold: bestVsAnchor.best.oversold,
                    overbought: bestVsAnchor.best.overbought,
                  },
                  paramsLabel: bestVsAnchor.best.paramsLabel,
                  strategyId: created.data.id,
                  oosKind: oosEvidence.kind,
                  oosScore: oosEvidence.oosScore ?? oosEvidence.meanOosScore ?? null,
                  score: bestVsAnchor.best.score,
                  maxDrawdownPct: bestVsAnchor.best.maxDrawdownPct,
                  profileId,
                  plateau: plateauMetaForAdoption(),
                });
              }
              setSavedRowId(bestVsAnchor.best.id);
              void queryClient.invalidateQueries({ queryKey: ['strategies'] });
              return {
                ok: true as const,
                strategyId: created.data.id,
                name,
                definition,
                // Identidad ejecutable = preset de la def (grid SMA), no seed proxy (SuperTrend…).
                presetKey: definition.presetKey ?? family ?? seed?.strategyType ?? null,
              };
            } catch (err) {
              return {
                ok: false as const,
                error: err instanceof Error ? err.message : 'Error al guardar el Mejor',
              };
            }
          },
        };
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [bestVsAnchor, zoneRank, zoneId, seed, family, result, instrumentId, timeframe, profileId],
  );

  // savedRowId es señal de refresco: readLabAdoption lee localStorage no reactivo,
  // la dependencia fuerza recalcular el hint cuando se guarda la fila del Lab.
  const adoptionHint = useMemo(() => {
    const id = seed?.instrumentId || instrumentId;
    const tf = seed?.timeframe || timeframe;
    const rec = readLabAdoption(id, tf);
    return rec ? formatLabAdoptionHint(rec) : null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.instrumentId, seed?.timeframe, instrumentId, timeframe, savedRowId]);

  return (
    <Card
      className={cn(
        'w-full',
        compact && 'border-border/70 shadow-none',
        showLiveProgress && 'border-sky-500/40 ring-1 ring-sky-400/25',
      )}
    >
      <OptimizeCardHeader
        compact={compact}
        seed={seed}
        zoneRank={zoneRank}
        zoneStars={zoneStars}
        zoneStarsCapped={zoneStarsCapped}
        showLiveProgress={showLiveProgress}
        progressPhase={progressPhase}
        adoptionHint={adoptionHint}
        oosEnabled={oosEnabled}
      />
      <CardContent className={cn('space-y-4', compact && 'px-3 pb-3')}>
        {compact && showLiveProgress && progressNode}

        {seed && (
          <OptimizeSeedBanner
            seed={seed}
            validationHint={seedValidationHint}
            proxyNote={optimizeFamilyProxyNote(seed.strategyType)}
            familyReady={familyReady}
            onClearSeed={onClearSeed}
          />
        )}

        {!seed && <OptimizeEmptyTip />}

        <div className="rounded-lg border border-border/70 bg-muted/20 px-3 py-2 text-xs">
          <p className="font-medium text-foreground">Qué se itera</p>
          <p
            className="mt-1 text-muted-foreground"
            title="Grid barre la malla de parámetros. Optuna busca de forma inteligente en el mismo rango. Puedes marcar ambos."
          >
            {family === 'sma_crossover'
              ? `Métodos activos: ${selectedMethods.join(', ')}. Si eliges varios, se unen los candidatos.`
              : 'Esta familia usa grid clásico (H0).'}
          </p>
          <p className="mt-1 tabular-nums text-muted-foreground">
            Combinaciones previstas: <strong className="text-foreground">{trialTotal}</strong>
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">
            Instrumento
            <select
              value={instrumentId}
              onChange={(e) => setInstrumentId(e.target.value)}
              className={fieldClass}
            >
              <option value="">Selecciona...</option>
              {instruments.map((instrument) => (
                <option key={instrument.id} value={instrument.id}>
                  {instrument.symbol} — {instrument.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Familia
            <select
              value={family}
              onChange={(e) => setFamilyAndSpace(e.target.value as OptimizeStrategyFamily)}
              className={fieldClass}
            >
              {(
                [
                  ['sma_crossover', 'SMA crossover'],
                  ['rsi_mean_reversion', 'RSI mean-reversion'],
                  ['macd_signal_cross', 'MACD signal cross'],
                ] as const
              )
                .slice()
                .sort((a, b) => {
                  const ia = preferredLabFamilies.indexOf(a[0]);
                  const ib = preferredLabFamilies.indexOf(b[0]);
                  return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
                })
                .map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                    {preferredLabFamilies[0] === value ? ' · perfil' : ''}
                  </option>
                ))}
            </select>
          </label>
        </div>
        <p className="text-[11px] text-muted-foreground">{labFamiliesHint}</p>
        {labRiskHint ? (
          <p className="text-[11px] text-muted-foreground">{labRiskHint}</p>
        ) : null}
        {!preferredLabFamilies.includes(family) ? (
          <p className="text-[11px] text-amber-800 dark:text-amber-200">
            Familia actual fuera del prior del perfil — ok si viene del Coach/semilla.
          </p>
        ) : null}

        <div className="space-y-2 rounded-lg border border-border p-3">
          <p className="text-sm font-medium text-foreground">Espacio de búsqueda</p>
          {space.family === 'sma_crossover' && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1 pr-2">Variable</th>
                  <th className="py-1 pr-2">Desde</th>
                  <th className="py-1 pr-2">Hasta</th>
                  <th className="py-1 pr-2">Paso</th>
                  <th className="py-1">Valores</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ['fast', 'SMA rápida', space.fast, expandRange(space.fast).length],
                    ['slow', 'SMA lenta', space.slow, expandRange(space.slow).length],
                  ] as const
                ).map(([key, label, range, count]) => (
                  <tr key={key} className="border-t border-border/50">
                    <td className="py-1.5 pr-2 font-medium">{label}</td>
                    {(['min', 'max', 'step'] as const).map((field) => (
                      <td key={field} className="py-1.5 pr-2">
                        <input
                          type="number"
                          className="w-16 rounded border border-border bg-background px-1.5 py-1"
                          value={range[field]}
                          onChange={(e) =>
                            patchSma(key, { [field]: Number(e.target.value) })
                          }
                        />
                      </td>
                    ))}
                    <td className="py-1.5 tabular-nums text-muted-foreground">{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {space.family === 'rsi_mean_reversion' && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1 pr-2">Variable</th>
                  <th className="py-1 pr-2">Desde</th>
                  <th className="py-1 pr-2">Hasta</th>
                  <th className="py-1 pr-2">Paso</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ['period', 'Periodo RSI', space.period],
                    ['oversold', 'Oversold', space.oversold],
                    ['overbought', 'Overbought', space.overbought],
                  ] as const
                ).map(([key, label, range]) => (
                  <tr key={key} className="border-t border-border/50">
                    <td className="py-1.5 pr-2 font-medium">{label}</td>
                    {(['min', 'max', 'step'] as const).map((field) => (
                      <td key={field} className="py-1.5 pr-2">
                        <input
                          type="number"
                          className="w-16 rounded border border-border bg-background px-1.5 py-1"
                          value={range[field]}
                          onChange={(e) =>
                            patchRsi(key, { [field]: Number(e.target.value) })
                          }
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {space.family === 'macd_signal_cross' && (
            <p className="text-xs text-muted-foreground">
              Vecindario clásico (~25 triples around 12/26/9). Puedes resetear con el selector de
              familia.
              <button
                type="button"
                className="ml-2 underline"
                onClick={() => setSpace(defaultMacdSpace())}
              >
                Restablecer
              </button>
            </p>
          )}
          {space.family === 'rsi_mean_reversion' && (
            <button
              type="button"
              className="text-[11px] underline text-muted-foreground"
              onClick={() => setSpace(defaultRsiSpace())}
            >
              Restablecer rangos RSI
            </button>
          )}
        </div>

        {expanded && (
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-sm">
              Capital
              <input
                value={initialCash}
                onChange={(e) => setInitialCash(e.target.value)}
                className={fieldClass}
                inputMode="decimal"
              />
            </label>
            <label
              className="block text-sm"
              title="Ventana total en barras. Con hold-out, el tramo final es OOS."
            >
              Barras (total)
              <input
                value={barLimit}
                onChange={(e) => setBarLimit(e.target.value)}
                className={fieldClass}
                inputMode="numeric"
              />
            </label>
            <label className="block text-sm">
              Timeframe
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value as ChartTimeframe)}
                className={fieldClass}
              >
                <option value="1d">1 día</option>
                <option value="1h">1 hora</option>
                <option value="4h">4 horas</option>
                <option value="1wk">1 semana</option>
              </select>
            </label>
            <div
              className="col-span-2 space-y-1.5 text-sm"
              title="Puedes marcar varios. Grid + Optuna es lo más útil: uno barre la malla y el otro busca en el rango. VectorBT suele repetir el grid. Tarda más si combinas."
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium text-foreground">Métodos</p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  title="Grid + Optuna + hold-out 20% · listo para adoptar TOP"
                  onClick={() => {
                    setMethods(family === 'sma_crossover' ? ['h0', 'optuna'] : ['h0']);
                    setOosEnabled(true);
                    setOosPct('0.2');
                    setWfEnabled(false);
                    setCpcvEnabled(false);
                    setRankBy('oos');
                    setExpanded(true);
                  }}
                >
                  Preset: Validar y adoptar
                </Button>
              </div>
              <div className="flex flex-wrap gap-3">
                {METHOD_OPTIONS.map((option) => (
                  <label
                    key={option.id}
                    className="flex items-center gap-1.5 text-xs"
                    title={option.title}
                  >
                    <input
                      type="checkbox"
                      checked={selectedMethods.includes(option.id)}
                      disabled={
                        multiPathMode ||
                        (family !== 'sma_crossover' && option.id !== 'h0')
                      }
                      onChange={() => toggleMethod(option.id)}
                      className="rounded border-border"
                    />
                    {option.label}
                  </label>
                ))}
              </div>
              {selectedMethods.length > 1 && (
                <p className="text-[11px] text-muted-foreground">
                  Se lanzarán en serie y se unirán los candidatos (quedará el mejor score por
                  parámetros).
                </p>
              )}
            </div>
            <label
              className="col-span-2 flex items-center gap-2 text-sm"
              title={`${OPTIMIZE_OOS_HELP} Incompatible con WF/CPCV.`}
            >
              <input
                type="checkbox"
                checked={oosEnabled && !multiPathMode}
                disabled={multiPathMode}
                onChange={(e) => {
                  setOosEnabled(e.target.checked);
                  if (e.target.checked) {
                    setWfEnabled(false);
                    setCpcvEnabled(false);
                  }
                }}
                className="rounded border-border"
              />
              Reservar tramo final (hold-out OOS)
              <select
                value={oosPct}
                onChange={(e) => setOosPct(e.target.value)}
                disabled={!oosEnabled || multiPathMode}
                className="ml-auto w-28 rounded-md border border-border bg-background px-2 py-1 text-xs"
              >
                <option value="0.15">15%</option>
                <option value="0.2">20%</option>
                <option value="0.25">25%</option>
                <option value="0.3">30%</option>
              </select>
            </label>
            <label
              className="col-span-2 flex items-center gap-2 text-sm"
              title={`${OPTIMIZE_WF_HELP} Requiere historial largo (≥ ~600 barras recomendado).`}
            >
              <input
                type="checkbox"
                checked={wfEnabled && !cpcvEnabled}
                disabled={cpcvEnabled}
                onChange={(e) => {
                  setWfEnabled(e.target.checked);
                  if (e.target.checked) {
                    setOosEnabled(false);
                    setCpcvEnabled(false);
                    setMethods(['h0']);
                    setRunInBackground(false);
                  }
                }}
                className="rounded border-border"
              />
              Walk-forward (pliegues)
              <select
                value={wfFolds}
                onChange={(e) => setWfFolds(e.target.value)}
                disabled={!wfEnabled || cpcvEnabled}
                className="ml-auto w-28 rounded-md border border-border bg-background px-2 py-1 text-xs"
              >
                <option value="2">2 pliegues</option>
                <option value="3">3 pliegues</option>
                <option value="4">4 pliegues</option>
                <option value="5">5 pliegues</option>
              </select>
            </label>
            {wfEnabled && !cpcvEnabled && (
              <p className="col-span-2 text-[11px] text-muted-foreground" title={OPTIMIZE_WF_HELP}>
                Solo grid H0 · ~{trialTotal} trials (×{wfFoldCount} pliegues). Optuna/VectorBT no
                aplican en WF v1.
              </p>
            )}
            <label
              className="col-span-2 flex items-center gap-2 text-sm"
              title={`${OPTIMIZE_CPCV_HELP} Requiere historial largo (≥ ~800 barras recomendado).`}
            >
              <input
                type="checkbox"
                checked={cpcvEnabled}
                onChange={(e) => {
                  setCpcvEnabled(e.target.checked);
                  if (e.target.checked) {
                    setOosEnabled(false);
                    setWfEnabled(false);
                    setMethods(['h0']);
                    setRunInBackground(false);
                  }
                }}
                className="rounded border-border"
              />
              CPCV ligero (combinatorial)
              <select
                value={cpcvGroups}
                onChange={(e) => setCpcvGroups(e.target.value)}
                disabled={!cpcvEnabled}
                className="ml-auto w-28 rounded-md border border-border bg-background px-2 py-1 text-xs"
              >
                <option value="4">4 grupos</option>
                <option value="5">5 grupos</option>
                <option value="6">6 grupos</option>
              </select>
            </label>
            {cpcvEnabled && (
              <>
                <div className="col-span-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  <label className="flex items-center gap-1.5">
                    Purge
                    <input
                      type="number"
                      min={0}
                      max={20}
                      value={cpcvPurge}
                      onChange={(e) => setCpcvPurge(e.target.value)}
                      className="w-14 rounded-md border border-border bg-background px-1.5 py-1"
                    />
                  </label>
                  <label className="flex items-center gap-1.5">
                    Embargo
                    <input
                      type="number"
                      min={0}
                      max={20}
                      value={cpcvEmbargo}
                      onChange={(e) => setCpcvEmbargo(e.target.value)}
                      className="w-14 rounded-md border border-border bg-background px-1.5 py-1"
                    />
                  </label>
                  <span title={OPTIMIZE_CPCV_HELP}>
                    Solo H0 · ~{trialTotal} trials (C({cpcvGroupCount},2)={cpcvPaths} paths) · PBO
                    CSCV lab al cerrar.
                  </span>
                </div>
              </>
            )}
          </div>
        )}

        <label
          className="flex items-center gap-2 text-sm"
          title="Desactivado por defecto: espera el resultado y muestra la tabla al terminar. Actívalo solo si quieres progreso k/N mientras corre un worker en segundo plano."
        >
          <input
            type="checkbox"
            checked={runInBackground}
            onChange={(e) => setRunInBackground(e.target.checked)}
            className="rounded border-border"
          />
          Segundo plano (progreso en vivo; requiere worker)
        </label>

        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            size="sm"
            className="h-8 w-8 p-0"
            disabled={!instrumentId || isRunning}
            title={isRunning ? 'Optimización en curso…' : 'Lanzar experimento'}
            aria-label="Lanzar optimización"
            onClick={handleRun}
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0"
            title={expanded ? 'Ocultar opciones' : 'Más opciones'}
            aria-label={expanded ? 'Menos opciones' : 'Más opciones'}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
          <span className="text-[11px] text-muted-foreground">
            {multiProgress
              ? multiProgress
              : isRunning
                ? 'Explorando…'
                : `Listo · ~${trialTotal} trials · ${selectedMethods.length} método(s)`}
          </span>
        </div>

        {progressPhase && (!compact || !showLiveProgress) && progressNode}

        {jobError && <p className="text-sm text-destructive">{jobError}</p>}
        {saveError && <p className="text-sm text-destructive">{saveError}</p>}
        {promoteMsg && <p className="text-xs text-muted-foreground">{promoteMsg}</p>}

        {result && (cpcv || walkForward || edgeReport || result.trials?.[0]?.oosMetrics) && (
          <OptimizeSummaryStrip
            mode={cpcv ? 'CPCV' : walkForward ? 'walk-forward' : 'hold-out / IS'}
            wfe={
              cpcv?.walkForwardEfficiency ?? walkForward?.walkForwardEfficiency ?? null
            }
            pbo={pbo}
            edgeBand={edgeReport ? edgeReport.band : null}
          />
        )}

        {walkForward && (
          <OptimizeWalkForwardReport
            walkForward={walkForward}
            labWfeHint={cpcv ? null : labWfeHint}
          />
        )}

        {edgeReport && <OptimizeEdgeReport edgeReport={edgeReport} />}

        {cpcv && (
          <OptimizeCpcvReport cpcv={cpcv} pbo={pbo} labWfeHint={labWfeHint} />
        )}

        {bestVsAnchor && (
          <div className="space-y-3">
            <LabZoneVerdictHero
              improved={bestVsAnchor.improved}
              rankedByOos={bestVsAnchor.rankedByOos}
              beforeParams={bestVsAnchor.anchor.paramsLabel}
              afterParams={bestVsAnchor.best.paramsLabel}
              deltaScore={bestVsAnchor.best.deltaScore}
              deltaOosScore={bestVsAnchor.best.deltaOosScore}
              deltaReturnPct={bestVsAnchor.best.deltaReturnPct}
              deltaDrawdownPct={bestVsAnchor.best.deltaDrawdownPct}
              engine={result?.engine}
              trialsDone={result?.trials?.length ?? null}
              trialsTotal={
                result?.engine?.includes('+')
                  ? result.trials?.length ?? null
                  : (result?.trialsTotal ?? result?.trials?.length ?? null)
              }
              oosPct={result?.oosPct ?? null}
              walkForwardFolds={walkForward?.nFolds ?? walkForward?.foldCount ?? null}
              cpcvPaths={cpcv?.pathCount ?? null}
            />
          <div
            className={cn(
              'space-y-3 rounded-lg border px-3 py-3 text-sm',
              bestVsAnchor.improved
                ? 'border-emerald-500/40 bg-emerald-500/10'
                : 'border-amber-500/40 bg-amber-500/10',
            )}
          >
            {bestVsAnchor.improved ? (
              <>
                <div>
                  <p className="font-medium text-foreground">
                    {bestVsAnchor.rankedByOos ? 'Mejor OOS' : 'Mejor IS'} ·{' '}
                    {bestVsAnchor.best.paramsLabel}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {bestVsAnchor.rankedByOos ? (
                      <>
                        Score OOS{' '}
                        {bestVsAnchor.best.deltaOosScore != null &&
                        bestVsAnchor.best.deltaOosScore >= 0
                          ? '+'
                          : ''}
                        {bestVsAnchor.best.deltaOosScore?.toFixed(2)} vs ancla
                        {' · '}
                        IS{' '}
                        {bestVsAnchor.best.deltaScore != null && bestVsAnchor.best.deltaScore >= 0
                          ? '+'
                          : ''}
                        {bestVsAnchor.best.deltaScore?.toFixed(2)}
                      </>
                    ) : (
                      <>
                        Score IS{' '}
                        {bestVsAnchor.best.deltaScore != null && bestVsAnchor.best.deltaScore >= 0
                          ? '+'
                          : ''}
                        {bestVsAnchor.best.deltaScore?.toFixed(2)} vs tu prueba origen
                        {bestVsAnchor.best.oosMetrics
                          ? ` · OOS ${bestVsAnchor.best.oosMetrics.score.toFixed(2)}`
                          : ''}
                      </>
                    )}
                    .
                  </p>
                  {bestVsAnchor.isChampDiffers && bestVsAnchor.isChampParams && (
                    <p className="mt-1 text-xs text-amber-200/90">
                      Ojo: el pico IS ({bestVsAnchor.isChampParams}) no es el mejor OOS. Priorizamos
                      OOS para reducir sobreajuste.
                    </p>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Lab no escribe Finalistas. Cuando terminen las zonas, usa{' '}
                  <strong className="text-foreground">Reanalizar con Coach</strong> y guarda
                  Finalistas desde el Coach.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={saveStrategyMutation.isPending || savedRowId === bestVsAnchor.best.id}
                    onClick={() => void handleSave(bestVsAnchor.best, false)}
                    title="Guarda el Mejor en Optimizadas (clone Lab · origin preset; no toca Finalistas)"
                  >
                    {savedRowId === bestVsAnchor.best.id
                      ? 'Ya en Optimizadas'
                      : 'Guardar en Optimizadas'}
                  </Button>
                </div>
              </>
            ) : (
              <div className="space-y-2">
                {bestVsAnchor.profileDdBlocked ? (
                  <>
                    <p>
                      Score mejor, pero DD{' '}
                      {formatPct(Math.abs(bestVsAnchor.best.maxDrawdownPct))} supera el techo del
                      perfil ({bestVsAnchor.maxDrawdownSoftPct}%). No se adopta como Mejor (CORE-P).
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Cambia de perfil o sube el riesgo en Configuración → Perfil inversor si quieres
                      aceptar más drawdown.
                    </p>
                  </>
                ) : (
                  <>
                    <p>
                      Completado · ningún candidato mejora el score{' '}
                      {bestVsAnchor.rankedByOos ? 'OOS' : 'IS'} de la ancla en esta ventana.
                      No hace falta reanalizarla en Coach.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Opcional: márcala «Llevar al Coach» en el tablero para verla allí con el aviso
                      «no mejoró» (sin re-score).
                    </p>
                  </>
                )}
              </div>
            )}
          </div>
          </div>
        )}

        {result && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-medium text-foreground">Comparación vs ancla</p>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                {showOos && (
                  <label
                    className="flex items-center gap-1"
                    title="Con OOS activo, por defecto elegimos el Mejor por score fuera de muestra (más fiable que el pico IS)."
                  >
                    Elegir Mejor por
                    <select
                      value={rankBy}
                      onChange={(e) => setRankBy(e.target.value as OptimizeRankBy)}
                      className="rounded border border-border bg-background px-1.5 py-0.5 text-[11px] text-foreground"
                    >
                      <option value="oos">Score OOS</option>
                      <option value="is">Score IS</option>
                    </select>
                  </label>
                )}
                <span>
                  {result.barCount} barras
                  {result.isBarCount != null && result.oosBarCount != null
                    ? ` · IS ${result.isBarCount} / OOS ${result.oosBarCount}`
                    : ''}
                  {' · '}
                  {result.engine}
                </span>
              </div>
            </div>
            <BacktestOptimizeHeatmapPanel
              trials={result.trials}
              family={resultFamily}
              scoreMode={showOos && rankBy === 'oos' ? 'oos' : 'is'}
              compact={compact}
            />
            <BacktestOptimizeCompareTable
              rows={compareRows}
              family={resultFamily}
              showOos={showOos}
              oosMode={cpcv ? 'walkforward' : walkForward ? 'walkforward' : 'holdout'}
              onSave={(row) => handleSave(row, false)}
              savingId={
                saveStrategyMutation.isPending
                  ? (saveStrategyMutation.variables?.rowId ?? null)
                  : null
              }
              savedId={savedRowId}
            />
            <p className="text-[11px] text-muted-foreground">
              El icono Guardar de cada fila crea una estrategia propia (
              {formatTrialParams(result.trials[0] ?? {}, resultFamily)}
              …). Luego puedes probarla en el wizard.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
},
);
