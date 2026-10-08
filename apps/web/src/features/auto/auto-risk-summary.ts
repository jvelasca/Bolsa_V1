/**
 * AUTO UI REFACTOR 3.0 (S3) — cabecera plana de RIESGO (helper puro).
 *
 * Compone el primer nivel de `/auto/riesgo` **solo** con fuentes read-only ya existentes
 * (`useFinancialIntegrity`). No re-deriva, no inventa y **no rellena con `0`**: lo que el
 * read-model de AUTO no materializa (riesgo por posición, máxima pérdida, límite diario) se declara
 * «Sin dato todavía» y se enlaza a Cartera → Riesgo (su superficie canónica).
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §5
 */

import { absentDataLabel } from "@/components/absent-data";
import { type AutoHomeRiskTone } from "@/features/auto/auto-home-summary";

/** Tono único del titular de riesgo (HOME y RIESGO comparten la escala). */
export const AUTO_RISK_TONE_CLASS: Record<AutoHomeRiskTone, string> = {
  ok: "text-emerald-600 dark:text-emerald-400",
  attention: "text-amber-600 dark:text-amber-400",
  blocked: "text-destructive",
  unknown: "text-amber-600 dark:text-amber-400",
};

export type AutoRiskSummaryInput = {
  /** `operationalState` de la integridad financiera (`OK` | `DEGRADED` | `BLOCKED`). */
  operationalState?: string | null;
  /** `portfolioStatus` de la reconciliación de cartera (`clean` | `lag` | `drift` | `blocked`). */
  portfolioStatus?: string | null;
  /** Nº de incidencias de enlace de fills (`fillLinkIssues`). */
  fillLinkIssuesCount?: number | null;
  isLoading?: boolean;
  isError?: boolean;
};

export type AutoRiskSummaryV1 = {
  loaded: boolean;
  isLoading: boolean;
  isError: boolean;
  stateTone: AutoHomeRiskTone;
  /** `Normal` | `Atención` | `Bloqueado` | `Sin dato todavía`. */
  stateLabel: string;
  /** `true` sólo si el estado operativo se materializó (no es un hueco). */
  stateAvailable: boolean;
  /** Veredicto human-first (`UI5-18`): `Controlado` | `Atención` | `Bloqueado` | `Sin dato todavía`. */
  verdict: string;
  verdictTone: AutoHomeRiskTone;
  /** Frase de primer nivel del veredicto. */
  verdictSentence: string;
  /** `Cuadra` | `Con retraso` | `Desajuste` | `Bloqueado` | `Sin dato todavía`. */
  portfolioLabel: string;
  /** `true` sólo si el cuadre de cartera se materializó (no es un hueco). */
  portfolioAvailable: boolean;
  /** `Sin incidencias` | `N incidencias` | `Sin dato todavía`. */
  fillLinkIssuesLabel: string;
  /** `true` sólo si el recuento de incidencias se materializó (no es un hueco). */
  fillLinkIssuesAvailable: boolean;
  /** Riesgo por posición / máxima pérdida / límite diario: no materializados aquí. */
  positionRiskLabel: string;
  positionRiskAvailable: boolean;
};

const VERDICT_COPY: Record<AutoHomeRiskTone, string> = {
  ok: "El riesgo está controlado. No hay bloqueos ni incidencias activas.",
  attention:
    "AUTO necesita atención: revisa las incidencias antes de confiar en nuevas entradas.",
  blocked: "Hay un bloqueo activo. No se deberían abrir nuevas posiciones.",
  unknown: "Todavía no hay una lectura de riesgo.",
};

const VERDICT_LABEL: Record<AutoHomeRiskTone, string> = {
  ok: "Controlado",
  attention: "Atención",
  blocked: "Bloqueado",
  unknown: absentDataLabel(),
};

/**
 * Veredicto human-first: colapsa estado operativo, cuadre de cartera e incidencias en un único
 * tono. `UNKNOWN ≠ 0`: sin lectura, el veredicto es «Sin dato todavía», nunca «Controlado».
 */
function riskVerdict(input: {
  stateTone: AutoHomeRiskTone;
  portfolioStatus?: string | null;
  fillLinkIssuesCount?: number | null;
  loaded: boolean;
}): { tone: AutoHomeRiskTone; label: string; sentence: string } {
  if (!input.loaded) {
    return {
      tone: "unknown",
      label: VERDICT_LABEL.unknown,
      sentence: VERDICT_COPY.unknown,
    };
  }
  const issues = input.fillLinkIssuesCount ?? 0;
  let tone: AutoHomeRiskTone;
  if (input.stateTone === "blocked" || input.portfolioStatus === "blocked") {
    tone = "blocked";
  } else if (
    input.stateTone === "attention" ||
    input.portfolioStatus === "drift" ||
    issues > 0
  ) {
    tone = "attention";
  } else if (input.stateTone === "unknown") {
    tone = "unknown";
  } else {
    tone = "ok";
  }
  return {
    tone,
    label: VERDICT_LABEL[tone],
    sentence: VERDICT_COPY[tone],
  };
}

function stateFromOperationalState(state: string | null | undefined): {
  tone: AutoHomeRiskTone;
  label: string;
} {
  switch (state) {
    case "OK":
      return { tone: "ok", label: "Normal" };
    case "DEGRADED":
      return { tone: "attention", label: "Atención" };
    case "BLOCKED":
      return { tone: "blocked", label: "Bloqueado" };
    default:
      return { tone: "unknown", label: absentDataLabel() };
  }
}

/** `true` si el estado de cartera es un valor reconocido (medido), no un hueco. */
function portfolioStatusKnown(status: string | null | undefined): boolean {
  return (
    status === "clean" ||
    status === "lag" ||
    status === "drift" ||
    status === "blocked"
  );
}

function portfolioLabelFromStatus(status: string | null | undefined): string {
  switch (status) {
    case "clean":
      return "Cuadra";
    case "lag":
      return "Con retraso";
    case "drift":
      return "Desajuste";
    case "blocked":
      return "Bloqueado";
    default:
      return absentDataLabel();
  }
}

function fillLinkIssuesLabelFromCount(
  count: number | null | undefined,
  loaded: boolean,
): string {
  if (!loaded || count === null || count === undefined) {
    return absentDataLabel();
  }
  if (count === 0) return "Sin incidencias";
  return count === 1 ? "1 incidencia" : `${count} incidencias`;
}

export function buildAutoRiskSummary(
  input: AutoRiskSummaryInput,
): AutoRiskSummaryV1 {
  const isLoading = input.isLoading === true;
  const isError = input.isError === true;
  const loaded = !isLoading && !isError;
  const state = stateFromOperationalState(input.operationalState);
  // Un campo sólo «existe» (se pinta en el primer nivel) cuando su valor está medido: los huecos
  // NO se repiten como celdas vacías; el veredicto ya declara el hueco una única vez.
  const stateAvailable = loaded && state.tone !== "unknown";
  const portfolioAvailable =
    loaded && portfolioStatusKnown(input.portfolioStatus);
  const fillLinkIssuesAvailable =
    loaded &&
    input.fillLinkIssuesCount !== null &&
    input.fillLinkIssuesCount !== undefined;
  const verdict = riskVerdict({
    stateTone: state.tone,
    portfolioStatus: input.portfolioStatus,
    fillLinkIssuesCount: input.fillLinkIssuesCount,
    loaded,
  });
  return {
    loaded,
    isLoading,
    isError,
    stateTone: state.tone,
    stateLabel: stateAvailable ? state.label : absentDataLabel(),
    stateAvailable,
    verdict: verdict.label,
    verdictTone: verdict.tone,
    verdictSentence: verdict.sentence,
    portfolioLabel: portfolioAvailable
      ? portfolioLabelFromStatus(input.portfolioStatus)
      : absentDataLabel(),
    portfolioAvailable,
    fillLinkIssuesLabel: fillLinkIssuesLabelFromCount(
      input.fillLinkIssuesCount,
      loaded,
    ),
    fillLinkIssuesAvailable,
    // Nunca materializado en el read-model de AUTO: se declara, no se inventa.
    positionRiskLabel: absentDataLabel(),
    positionRiskAvailable: false,
  };
}
