/**
 * AUTO UI — Explicación P3→P4 de la ESTRATEGIA SELECCIONADA (read-model PURO).
 *
 * Une, sin recalcular nada, las dos piezas que el usuario exige juntas:
 *
 *   P3 (estrategia)  → la EJECUTADA del ciclo resuelta en el TOP del valor (`presetKey` EXACTO),
 *                      con sus indicadores y las razones del coach.
 *   P4 (DÍA-D)       → la evidencia medida del VALOR (cuatro capas, sin promoción) + los
 *                      contadores y suelos de muestra + la verificación durable por ciclo + la
 *                      sesión LAB local.
 *
 * Invariantes (falsables):
 * - **La evidencia DÍA-D es del VALOR, no de la estrategia.** El artefacto agrega el veredicto
 *   por `symbol`; no existe identidad de estrategia por valor. La superficie lo declara.
 * - **Sin promoción de capas.** Se reutiliza `buildDiaDEvidenceAggregate` (probado): `READY`,
 *   `MATCH` y `OOS_SUPPORTED` NO confirman; `CONFIRMED` no se emite.
 * - **`UNKNOWN ≠ 0`.** Un contador ausente es `null`, nunca `0`; un hueco se declara con el
 *   rótulo de `absent-data`.
 * - **Fail-closed.** Sin símbolo resuelto o sin artefacto, la vista declara el hueco; un fallo de
 *   lectura se declara «No disponible» (nunca «Sin dato todavía») y `loading` deja el hueco en
 *   `null` (transitorio, no ausencia).
 * - **No se toca el motor ni el contrato HTTP.** Es UI pura (`Δ motor = 0`, `Δ contrato = 0`).
 *
 * @see docs/engineering/explicacion-estrategia-p3-p4-2026-10-16.md
 * @see docs/PROJECT_PREMISES.md §5.2 (cuatro capas) y §6 (prioridades P1–P4)
 */

import type { components } from "@/api/schema";
import type { DiaDCycleVerificationV1Dto } from "@bolsa/shared";
import {
  ABSENT_DATA_NOT_AVAILABLE,
  absentDataLabel,
} from "@/components/absent-data";
import {
  AUTO_OPERATION_STRATEGY_NO_DATA,
  type AutoOperationStrategyMatch,
  type AutoOperationStrategyViewV1,
} from "@/features/auto/auto-operation-strategy";
import {
  buildDiaDEvidenceAggregate,
  type DiaDEvidenceAggregateInput,
  type DiaDEvidenceAggregateV1,
} from "@/features/auto-monitor/dia-d-evidence-aggregate";
import {
  DIA_D_CYCLE_VERIFICATION_LABELS,
  resolveDiaDCycleVerificationState,
  type DiaDCycleVerificationState,
} from "@/features/auto-monitor/dia-d-cycle-verification-status";

type DiaDFeedbackDto = components["schemas"]["DiaDFeedbackDto"];

export const AUTO_STRATEGY_EXPLANATION_TITLE =
  "Por qué se sostiene (evidencia medida)" as const;

export const AUTO_STRATEGY_EXPLANATION_DESCRIPTION =
  "La evidencia medida del valor y la verificación D→hoy enlazada a esta operación. La evidencia es del valor; no se atribuye a una estrategia si el artefacto no la declara." as const;

/** Etiqueta de la evidencia cuyo alcance es el VALOR (no una estrategia concreta). */
export const AUTO_STRATEGY_EXPLANATION_SCOPE_VALUE_LABEL =
  "Del valor (no de la estrategia)" as const;

/** Etiqueta de la evidencia EXACTA por ciclo (el único alcance atribuible con precisión). */
export const AUTO_STRATEGY_EXPLANATION_SCOPE_CYCLE_LABEL =
  "Del ciclo (exacta)" as const;

/** Nota de honestidad sobre la atribución: el artefacto agrega el veredicto por valor. */
export const AUTO_STRATEGY_EXPLANATION_ATTRIBUTION_NOTE =
  "La evidencia se agrega por valor (símbolo): NO es atribuible a una estrategia concreta. Lo único exacto es la fila del ciclo enlazado." as const;

/** Nota de la capa LAB: la sesión vive en el navegador y no es evidencia durable. */
export const AUTO_STRATEGY_EXPLANATION_LAB_LOCAL_NOTE =
  "Sesión local del navegador: no es evidencia durable. La evidencia durable es la verificación enlazada al ciclo." as const;

export const AUTO_STRATEGY_EXPLANATION_LAB_INACTIVE_LABEL =
  "Sin sesión LAB abierta para esta operación" as const;

/** Fila del ciclo dentro del artefacto (el único eje con identidad de estrategia). */
export type AutoStrategyExplanationCycleEvidenceV1 = {
  cycleId: string;
  symbol: string;
  entryDay: string | null;
  exitDay: string | null;
  /** Sello opaco de estrategia que declara el artefacto para ESE ciclo. */
  strategyVersion: string | null;
  /** Clave EXACTA que declara el artefacto para ESE ciclo. */
  strategyPresetKey: string | null;
  realizedR: number | null;
};

/** Suelos de muestra DECLARADOS por el artefacto (no se relajan aquí). */
export type AutoStrategyExplanationSampleFloorsV1 = {
  minCycles: number | null;
  minHitRate: number | null;
  supportedMinCycles: number | null;
  strongMinCycles: number | null;
};

export type AutoStrategyExplanationVerificationV1 = {
  state: DiaDCycleVerificationState;
  stateLabel: string;
  /** Fecha de la verificación durable enlazada (o `null`). */
  createdAt: string | null;
  /** Clave EXACTA que la verificación declaró (o `null`). */
  strategyPresetKey: string | null;
  /** Sello opaco que la verificación declaró (o `null`). */
  strategyVersion: string | null;
  /** Motivo del hueco cuando no hay verificación (o `null` si la hay). */
  gapReason: string | null;
};

export type AutoStrategyExplanationLabV1 = {
  active: boolean;
  label: string;
  diaD: string | null;
  endDate: string | null;
  mode: string | null;
  note: string;
};

export type AutoStrategyDiaDExplanationV1 = {
  symbol: string;
  /** Identidad EXACTA declarada por el ciclo (mismo espacio de claves que Finalistas). */
  cyclePresetKey: string | null;
  /** Sello opaco declarado por el ciclo. */
  cycleStrategyVersion: string | null;
  /** Estrategia EJECUTADA resuelta en el TOP del valor (lo que se verifica). */
  executedStrategyDefinitionId: string | null;
  executedStrategyLabel: string | null;
  executedStrategyRank: number | null;
  indicators: string[];
  reasons: string[];
  /** Eco del emparejamiento EXACTO de P3 (declarado vs TOP). */
  match: AutoOperationStrategyMatch;
  matchLabel: string;
  /**
   * `true` solo cuando la estrategia bajo explicación es PROVADAMENTE la que declara el ciclo:
   * clave exacta presente y emparejada con el TOP (`match === "same"`).
   */
  strategyIsDeclaredByCycle: boolean;
  /** Alcance REAL de la evidencia del valor: siempre el VALOR (nunca una estrategia). */
  valueScopeLabel: string;
  attributionNote: string;
  /** Veredicto de la capa OOS del VALOR (o `null`). */
  valueVerdict: string | null;
  evidenceQuality: string | null;
  /** Contadores del valor: un hueco es `null`, jamás `0`. */
  measuredCycles: number | null;
  expectancyR: number | null;
  hitRate: number | null;
  errorTotal: number | null;
  /** Total de errores del artefacto (capa agregada) o `null`. */
  artifactErrorTotal: number | null;
  sampleFloors: AutoStrategyExplanationSampleFloorsV1;
  /** Fila EXACTA del ciclo en el artefacto (o `null` si el artefacto no la trae). */
  cycleEvidence: AutoStrategyExplanationCycleEvidenceV1 | null;
  /** Las CUATRO capas sin promoción (reutiliza el agregado probado). */
  evidence: DiaDEvidenceAggregateV1;
  /** Verificación durable enlazada al ciclo (tri-estado). */
  verification: AutoStrategyExplanationVerificationV1;
  /** Sesión LAB local vigente (no durable). */
  lab: AutoStrategyExplanationLabV1;
  /** Motivo del hueco de la cadena completa (o `null`). */
  gapReason: string | null;
  /** Lecturas en vuelo: un hueco es TRANSITORIO (no se declara ausencia). */
  loading: boolean;
};

export type AutoStrategyDiaDExplanationInput = {
  /** Vista P3 ya compuesta (NO se recalcula aquí). */
  strategy: AutoOperationStrategyViewV1;
  /** Identidad declarada por el CICLO (el UUID del ciclo no basta: hace falta la clave). */
  cycle: {
    cycleId?: string | null;
    strategyPresetKey?: string | null;
    strategyVersion?: string | null;
  } | null;
  /** Artefacto DÍA-D de la ventana (`null` = no leído). */
  artifact: DiaDFeedbackDto | null;
  /** Capa de reconciliación (sandbox por día) si está disponible; si no, se declara hueco. */
  reconciliation?: DiaDEvidenceAggregateInput["reconciliation"];
  /** Verificaciones durables del principal (read-only). */
  verifications?: readonly DiaDCycleVerificationV1Dto[] | null;
  /** Sesión LAB local vigente para este instrumento, si la hay (no durable). */
  labSession?: {
    instrumentId?: string | null;
    strategyPresetKey?: string | null;
    diaD?: string | null;
    endDate?: string | null;
    mode?: string | null;
  } | null;
  /** La lectura del ARTEFACTO falló (HTTP/red): se declara «No disponible». */
  artifactError?: boolean;
  /** La lectura de las VERIFICACIONES falló: se declara «No disponible». */
  verificationsError?: boolean;
  loading?: boolean;
};

/** Número medido o `null`: un hueco NUNCA se colapsa a 0. */
function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

/** Fila del ciclo en el artefacto: única evidencia con identidad de estrategia EXACTA. */
function resolveCycleEvidence(
  artifact: DiaDFeedbackDto | null,
  cycleId: string | null,
): AutoStrategyExplanationCycleEvidenceV1 | null {
  if (!artifact || !cycleId) return null;
  const row = (artifact.cycles ?? []).find((item) => item.cycleId === cycleId);
  if (!row) return null;
  return {
    cycleId: row.cycleId,
    symbol: row.symbol,
    entryDay: str(row.entryDay),
    exitDay: str(row.exitDay),
    strategyVersion: str(row.strategyVersion),
    strategyPresetKey: str(row.strategyPresetKey),
    realizedR: num(row.realizedR),
  };
}

function resolveVerification(
  verifications: readonly DiaDCycleVerificationV1Dto[] | null | undefined,
  cycleId: string | null,
  verificationsError: boolean,
): AutoStrategyExplanationVerificationV1 {
  const state = resolveDiaDCycleVerificationState({
    cycleId,
    verified: Boolean(
      cycleId && (verifications ?? []).some((row) => row.cycleId === cycleId),
    ),
  });
  const row =
    cycleId != null
      ? ((verifications ?? []).find((item) => item.cycleId === cycleId) ?? null)
      : null;
  let gapReason: string | null = null;
  if (state === "not-verified") {
    gapReason = verificationsError
      ? `${ABSENT_DATA_NOT_AVAILABLE}: no se pudieron leer las verificaciones DÍA-D del ciclo.`
      : "Sin dato todavía: la verificación D→hoy de esta operación todavía no se ha guardado.";
  } else if (state === "unknown") {
    gapReason =
      "Sin dato todavía: el ciclo no declara su identificador, así que no hay nada que enlazar.";
  }
  return {
    state,
    stateLabel: DIA_D_CYCLE_VERIFICATION_LABELS[state],
    createdAt: str(row?.createdAt),
    strategyPresetKey: str(row?.strategyPresetKey),
    strategyVersion: str(row?.strategyVersion),
    gapReason,
  };
}

function resolveLab(
  input: AutoStrategyDiaDExplanationInput,
): AutoStrategyExplanationLabV1 {
  const session = input.labSession ?? null;
  // Fail-closed: la sesión sólo aplica si es la MISMA estrategia que se está explicando.
  const expected =
    input.cycle?.strategyPresetKey?.trim() ||
    input.strategy.executedStrategyDefinitionId?.trim() ||
    null;
  const sessionKey = session?.strategyPresetKey?.trim() || null;
  const active =
    Boolean(session) && (expected === null || sessionKey === expected);
  if (!active) {
    return {
      active: false,
      label: AUTO_STRATEGY_EXPLANATION_LAB_INACTIVE_LABEL,
      diaD: null,
      endDate: null,
      mode: null,
      note: AUTO_STRATEGY_EXPLANATION_LAB_LOCAL_NOTE,
    };
  }
  return {
    active: true,
    label: str(session?.diaD)
      ? `DÍA D ${session?.diaD} → ${str(session?.endDate) ?? absentDataLabel()}`
      : AUTO_STRATEGY_EXPLANATION_LAB_INACTIVE_LABEL,
    diaD: str(session?.diaD),
    endDate: str(session?.endDate),
    mode: str(session?.mode),
    note: AUTO_STRATEGY_EXPLANATION_LAB_LOCAL_NOTE,
  };
}

/**
 * Compone la explicación P3→P4 de la estrategia seleccionada. Nunca lanza y nunca inventa: los
 * huecos se declaran y los fallos de lectura se distinguen de las ausencias.
 */
export function buildAutoStrategyDiaDExplanation(
  input: AutoStrategyDiaDExplanationInput,
): AutoStrategyDiaDExplanationV1 {
  const loading = input.loading === true;
  const strategy = input.strategy;
  const cycleId = str(input.cycle?.cycleId);
  const cyclePresetKey = str(input.cycle?.strategyPresetKey);
  const cycleStrategyVersion = str(input.cycle?.strategyVersion);

  // La estrategia es PROVADAMENTE la del ciclo sólo con clave exacta + emparejamiento exacto.
  const strategyIsDeclaredByCycle =
    cyclePresetKey !== null && strategy.match === "same";

  const artifactAvailable =
    input.artifact != null && input.artifact.available === true;
  const value =
    artifactAvailable && strategy.symbol
      ? ((input.artifact?.values ?? []).find(
          (item) => item.symbol === strategy.symbol,
        ) ?? null)
      : null;

  const limits = value?.limits ?? null;
  const evidence = buildDiaDEvidenceAggregate({
    window: artifactAvailable
      ? {
          loaded: true,
          verdict: str(input.artifact?.gate?.verdict),
          days: num(input.artifact?.gate?.days),
          episodes: num(input.artifact?.gate?.episodes),
          cycles: num(input.artifact?.gate?.cycles),
        }
      : null,
    reconciliation: input.reconciliation ?? null,
    oos: artifactAvailable
      ? {
          loaded: input.artifact?.summary != null,
          oosSupported: num(input.artifact?.summary?.oosSupported),
          mixed: num(input.artifact?.summary?.mixed),
          refuted: num(input.artifact?.summary?.refuted),
          notMeasured: num(input.artifact?.summary?.notMeasured),
        }
      : null,
  });

  // Prioridad DECLARADA del hueco: un FALLO de lectura nunca se describe como ausencia; una
  // lectura EN VUELO deja el hueco en `null` (la UI muestra carga, no un falso «sin dato»).
  let gapReason: string | null = null;
  if (input.artifactError === true) {
    gapReason = `${ABSENT_DATA_NOT_AVAILABLE}: no se pudo leer la evidencia DÍA-D del valor.`;
  } else if (loading) {
    gapReason = null;
  } else if (!strategy.instrumentId) {
    gapReason =
      "Sin dato todavía: no se pudo resolver el instrumento de la operación.";
  } else if (!artifactAvailable) {
    gapReason =
      "Sin dato todavía: no hay evidencia DÍA-D publicada para este valor.";
  } else if (!value) {
    gapReason =
      "Sin dato todavía: el valor de esta operación no figura en la evidencia DÍA-D de la ventana.";
  } else if (!strategy.executedStrategyDefinitionId) {
    gapReason =
      strategy.verifyGapReason ??
      "Sin dato todavía: la estrategia ejecutada del ciclo no se pudo resolver.";
  }

  return {
    symbol: strategy.symbol,
    cyclePresetKey,
    cycleStrategyVersion,
    executedStrategyDefinitionId: strategy.executedStrategyDefinitionId,
    executedStrategyLabel: strategy.executedStrategyLabel,
    executedStrategyRank: strategy.executedStrategyRank,
    indicators: strategy.indicators,
    reasons: strategy.reasons,
    match: strategy.match,
    matchLabel: strategy.matchLabel,
    strategyIsDeclaredByCycle,
    valueScopeLabel: AUTO_STRATEGY_EXPLANATION_SCOPE_VALUE_LABEL,
    attributionNote: AUTO_STRATEGY_EXPLANATION_ATTRIBUTION_NOTE,
    valueVerdict: value?.verdict ?? null,
    evidenceQuality: value?.evidenceQuality ?? null,
    measuredCycles: num(value?.measuredCycles),
    expectancyR: num(value?.expectancyR),
    hitRate: num(value?.hitRate),
    errorTotal: num(value?.errorTotal),
    artifactErrorTotal: num(input.artifact?.summary?.errors?.total),
    sampleFloors: {
      minCycles: num(limits?.minCycles),
      minHitRate: num(limits?.minHitRate),
      supportedMinCycles: num(limits?.supportedMinCycles),
      strongMinCycles: num(limits?.strongMinCycles),
    },
    cycleEvidence: resolveCycleEvidence(input.artifact ?? null, cycleId),
    evidence,
    verification: resolveVerification(
      input.verifications,
      cycleId,
      input.verificationsError === true,
    ),
    lab: resolveLab(input),
    gapReason,
    loading,
  };
}

/** Rótulo de la estrategia que se explica, o el hueco declarado (`Sin dato todavía`). */
export function autoStrategyExplanationLabel(
  view: AutoStrategyDiaDExplanationV1,
): string {
  if (!view.executedStrategyLabel) return AUTO_OPERATION_STRATEGY_NO_DATA;
  return view.executedStrategyRank != null
    ? `#${view.executedStrategyRank} ${view.executedStrategyLabel}`
    : view.executedStrategyLabel;
}
