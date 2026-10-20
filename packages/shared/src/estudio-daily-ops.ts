/**
 * Operativa diaria AUTO por valor + cola de trabajos operativos — contrato compartido.
 *
 * Cuatro estados que la UI NUNCA mezcla, por valor:
 *   1. señal calculada (opinión + indicadores);
 *   2. decisión tomada (plan `TRIGGERED` o `whyNot`);
 *   3. operación ejecutada (ciclos durables DÍA-D, se leen aparte);
 *   4. operativa validada (veredicto/K/expectancy del audit, se lee aparte).
 *
 * Doctrina «Sin dato todavía»: cualquier hueco viaja `null`; nunca un `0` de relleno.
 */

export const ESTUDIO_DAILY_OPS_SCHEMA = "estudio_daily_ops_v1" as const;

/** Estado del universo del parte diario (infra `unavailable` ≠ `empty`). */
export type EstudioDailyReportStatusV1 = "ok" | "empty" | "unavailable";

/** Estado por valor: el batch aísla fallos y nunca convierte un error en `ok`. */
export type EstudioDailyValueStatusV1 =
  | "ok"
  | "no_signal"
  | "no_plan"
  | "error";

export type AutoOpsJobKindV1 =
  | "estudio_daily"
  | "dia_d_replay"
  /** Verificación DÍA-D acotada a UN valor (`payload.symbol` obligatorio). */
  | "dia_d_value_replay";

export type AutoOpsJobStatusV1 = "queued" | "running" | "completed" | "failed";

/** Estados que ocupan el hueco de idempotencia `(kind, cuenta, día)`. */
export const AUTO_OPS_ACTIVE_STATUSES: readonly AutoOpsJobStatusV1[] = [
  "queued",
  "running",
];

export const isAutoOpsJobActive = (
  status: string | null | undefined,
): boolean => AUTO_OPS_ACTIVE_STATUSES.includes(status as AutoOpsJobStatusV1);

/** Progreso observable del job. `percent` puede faltar: no se inventa un 0. */
export type AutoOpsJobProgressV1 = {
  phase?: string;
  done?: number;
  total?: number;
  percent?: number | null;
  updatedAt?: string;
  [key: string]: unknown;
};

export type AutoOpsJobV1 = {
  id: string;
  kind: AutoOpsJobKindV1 | string;
  status: AutoOpsJobStatusV1 | string;
  day: string;
  accountId: string | null;
  payload: Record<string, unknown>;
  progress: AutoOpsJobProgressV1;
  result: Record<string, unknown>;
  error: string | null;
  attempt: number;
  createdAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  heartbeatAt: string | null;
};

export type AutoOpsJobListV1 = {
  jobs: AutoOpsJobV1[];
  notes: string[];
};

export type AutoOpsJobCreateRequestV1 = {
  kind: AutoOpsJobKindV1;
  day?: string | null;
  payload?: Record<string, unknown>;
};

/** Niveles EXCLUSIVAMENTE del `TradePlan`; un hueco es `null`, jamás `0`. */
export type EstudioDailyPlanV1 = {
  status: string | null;
  direction: string | null;
  entry: number | null;
  structuralStop: number | null;
  target1: number | null;
  target2: number | null;
  riskAmount: number | null;
  expectedRR: number | null;
  entryCondition?: string | null;
  entrySetup?: string | null;
  expiresAt?: string | null;
  executionAllowed?: boolean | null;
  whyNot: string[];
};

export type EstudioDailyIndicatorsV1 = {
  io: number | null;
  fa: number | null;
  ta: number | null;
  confidence: string | null;
  regime: string | null;
};

export type EstudioDailyOpinionV1 = {
  stance: string | null;
  dictamenStars: number | null;
  channel: string | null;
  autoSource: string | null;
  reasons: string[];
  gateStatus: string | null;
  engineVersion: string | null;
  /** TOP que consumió la opinión (evidencia real). `null` ⇒ el motor no lo declaró. */
  topId?: string | null;
  topVersion?: number | null;
};

export type EstudioDailyStrategyV1 = {
  /**
   * Preset de **origen** del camino Estudio (constante `estudio_auto`). NO es la identidad
   * de la estrategia ejecutada: para eso están `strategyDefinitionId` y `strategyVersion`.
   */
  presetKey: string | null;
  strategyDefinitionId: string | null;
  strategyVersion: number | null;
  planId: string | null;
  /** Identidad estable de la señal que originó el plan (`signal.id`). `null` si no existe. */
  signalId?: string | null;
};

export type EstudioDailyValueV1 = {
  instrumentId: string;
  symbol: string | null;
  status: EstudioDailyValueStatusV1 | string;
  reason: string | null;
  asOfBarDate: string | null;
  computedAt: string | null;
  opinion: EstudioDailyOpinionV1;
  indicators: EstudioDailyIndicatorsV1;
  plan: EstudioDailyPlanV1 | null;
  whyNot: string[];
  strategy: EstudioDailyStrategyV1 | null;
};

export type EstudioDailyReportV1 = {
  asOf: string;
  accountId: string;
  status: EstudioDailyReportStatusV1 | string;
  scannedCount: number;
  counts: Record<EstudioDailyValueStatusV1, number>;
  values: EstudioDailyValueV1[];
  notes: string[];
  generatedAt: string | null;
  truncated: boolean;
  countsConsistent: boolean;
  /** Tamaño del universo ESTUDIO **antes** del recorte. `0`/ausente ⇒ no medido. */
  universeCount?: number | null;
};

export type EstudioDailyResponseV1 = {
  asOf: string;
  accountId: string | null;
  job: AutoOpsJobV1 | null;
  latestJob: AutoOpsJobV1 | null;
  report: EstudioDailyReportV1 | null;
  notes: string[];
};

/* ────────────────────────────────────────────────────────────────────────────
 * Evidencia de la CADENA durable por valor de ESTUDIO (`GET /auto/estudio-chain`)
 *
 * Una etapa sin traza durable viaja `null` (hueco declarado), NUNCA `0`. La identidad de
 * estrategia se LEE del hecho durable del ciclo; no se infiere del ranking.
 * ──────────────────────────────────────────────────────────────────────────── */

export const AUTO_ESTUDIO_CHAIN_SCHEMA = "auto-estudio-chain-v1" as const;

/** Cadena canónica, en orden. Se usa para pintar los huecos sin inventar etapas. */
export const ESTUDIO_CHAIN_STEPS = [
  "SIGNAL",
  "TOP_N",
  "RISK",
  "RESERVATION",
  "ORDER",
  "FILL",
  "PROTECTION",
  "SETTLEMENT",
  "CYCLE_CLOSED",
] as const;

export type EstudioChainStepV1 = (typeof ESTUDIO_CHAIN_STEPS)[number];

/**
 * Estado de medición de una magnitud del read-model, en tri-estado:
 * - `COMPLETE`: se midió todo lo que la magnitud exige.
 * - `PARTIAL`: se midió una parte (p. ej. solo el preset, no la versión).
 * - `UNKNOWN`: no se pudo afirmar nada (hueco declarado, nunca un `0`).
 */
export type MeasurementV1 = "COMPLETE" | "PARTIAL" | "UNKNOWN";

/** Conciliación al quantum del dinero: `null` cuando falta una de las dos cifras. */
export type EstudioChainPnlV1 = {
  cycleClosedPnl: string | null;
  settlementPnl: string | null;
  reconciled: boolean | null;
  measurement: MeasurementV1 | string;
};

/** Estado crudo por etapa (`reached`/`pending`/`absent`/`unknown`). */
export type EstudioChainGapsV1 = {
  reached: string[];
  notReached: Record<string, string>;
  complete: boolean;
  steps: number;
};

/** Identidad de la estrategia EJECUTADA, sellada por el ciclo durable. */
export type EstudioChainExecutedIdentityV1 = {
  strategyPresetKey: string | null;
  strategyVersion: string | null;
  rank: number | null;
  score: number | null;
  measurement: MeasurementV1 | string;
};

/** Afirmación de tres estados: `true`/`false` medidos, `null` = no se puede afirmar. */
export type EstudioChainFlagV1 = boolean | null;

/** Contraste ejecutada vs mejor puntuada. `null` = no se puede afirmar (hueco). */
export type EstudioChainCompareV1 = {
  executedIsTopRanked: EstudioChainFlagV1;
  executedIsBestScoredAsset: EstudioChainFlagV1;
  executedRank: number | null;
  bestScoredAssetId: string | null;
  /**
   * Identidad de la estrategia MEJOR PUNTUADA, tal cual la declara la foto durable del TOP3
   * (migración 057). `null` cuando la foto no la declara (históricas): hueco, no inferencia.
   */
  bestScoredPresetKey: string | null;
  bestScoredStrategyVersion?: string | null;
  executedPresetKey?: string | null;
  executedStrategyVersion?: string | null;
  presetMatch: EstudioChainFlagV1;
  versionMatch?: EstudioChainFlagV1;
  measurement: MeasurementV1 | string;
  /** Medición de la IDENTIDAD (preset/versión), separada del veredicto rank/activo. */
  strategyMeasurement?: MeasurementV1 | string;
};

export type EstudioChainExecutedVsDiaDV1 = {
  matches: EstudioChainFlagV1;
  cyclePresetKey: string | null;
  diaDPresetKey: string | null;
  measurement: MeasurementV1 | string;
};

export type EstudioChainDiaDLinkV1 = {
  linkable: boolean;
  draft: Record<string, unknown> | null;
  measurement: MeasurementV1 | string;
};

/** Un ciclo del valor con sus nueve etapas, identidad, P&L y DÍA-D. */
export type EstudioChainCycleV1 = {
  cycleId: string | null;
  instrumentId: string | null;
  direction: string | null;
  closed: boolean | null;
  opportunityId: string | null;
  /** Día de ENTRADA durable (`at` de la reserva); `null` si la etapa no lo declara. */
  entryDay?: string | null;
  /** Día de cierre durable (`closedAt` del resultado); `null` si no se puede afirmar. */
  exitDay?: string | null;
  executed: EstudioChainExecutedIdentityV1;
  bestScored: Record<string, unknown> | null;
  executedVsBest: EstudioChainCompareV1;
  /** `1` en la etapa con hecho durable; `null` en el hueco. Nunca `0`. */
  steps: Partial<Record<EstudioChainStepV1, 1 | null>> &
    Record<string, 1 | null>;
  chain: EstudioChainGapsV1;
  pnl: EstudioChainPnlV1;
  diaD: Record<string, unknown> | null;
  executedVsDiaD: EstudioChainExecutedVsDiaDV1;
  diaDLink: EstudioChainDiaDLinkV1;
  result: Record<string, unknown> | null;
  notes: string[];
};

/** Identidad declarada por el VALOR (única o AMBIGUA: nunca se elige «ganadora»). */
export type EstudioChainStrategyV1 = {
  presetKey: string | null;
  version: string | null;
  presetKeyAmbiguous: boolean;
  versionAmbiguous: boolean;
  cycles?: number;
  unlinkedCycles?: number;
  duplicateCycles?: number;
  verifications?: number;
};

export type EstudioChainValueV1 = {
  instrumentId: string;
  cycles: EstudioChainCycleV1[];
  measured: boolean;
  complete: boolean;
  /** Huecos declarados del valor (`no_cycles_for_value`, …). */
  unmeasured: string[];
  strategy: EstudioChainStrategyV1;
  strategyDiaD: EstudioChainStrategyV1;
};

export type EstudioChainSummaryV1 = {
  values: number;
  measured: number;
  complete: number;
  cycles: number;
  cyclesComplete: number;
  bestScoredPresent: boolean;
};

/**
 * Respuesta de `GET /api/auto/estudio-chain`. `available=false` declara el hueco o el error
 * (`error` no vacío); NUNCA significa «no pasó nada».
 */
export type EstudioChainResponseV1 = {
  available: boolean;
  readOnly: boolean;
  accountId: string | null;
  asOf: string | null;
  engineId: string | null;
  estudio: { status: string | null; values: number } | null;
  summary: EstudioChainSummaryV1 | null;
  bestScored: Record<string, unknown> | null;
  values: EstudioChainValueV1[];
  cyclesOutsideEstudio: EstudioChainCycleV1[];
  meta: Record<string, unknown>;
  limits: string[];
  notes: string[];
  error: string | null;
};

/* ────────────────────────────────────────────────────────────────────────────
 * DÍA-D del valor (`GET /auto/dia-d-replay/{day}/value/{symbol}`)
 * Artefacto PROPIO (`values/<SÍMBOLO>`): no se rellena desde el del día completo.
 * ──────────────────────────────────────────────────────────────────────────── */

export type DiaDValueReplayStepV1 = {
  step: string;
  declared: unknown;
  executed: unknown;
  verdict: string;
  measurement: string;
};

export type DiaDValueReplayV1 = {
  available: boolean;
  readOnly: boolean;
  day: string;
  symbol: string | null;
  artifactModifiedAt: string | null;
  schemaVersion: string | null;
  summary: {
    verdict: string;
    match: number;
    divergent: number;
    notMeasured: number;
    steps: number;
  } | null;
  steps: DiaDValueReplayStepV1[];
  oos: Record<string, unknown> | null;
  meta: Record<string, unknown>;
  limits: string[];
  executedDetail: Record<string, unknown>;
  notes: string[];
};
