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

import {
  AUTO_HOME_NO_DATA_LABEL,
  type AutoHomeRiskTone,
} from "@/features/auto/auto-home-summary";

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
  /** `Cuadra` | `Con retraso` | `Desajuste` | `Bloqueado` | `Sin dato todavía`. */
  portfolioLabel: string;
  /** `Sin incidencias` | `N incidencias` | `Sin dato todavía`. */
  fillLinkIssuesLabel: string;
  /** Riesgo por posición / máxima pérdida / límite diario: no materializados aquí. */
  positionRiskLabel: string;
  positionRiskAvailable: boolean;
};

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
      return { tone: "unknown", label: AUTO_HOME_NO_DATA_LABEL };
  }
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
      return AUTO_HOME_NO_DATA_LABEL;
  }
}

function fillLinkIssuesLabelFromCount(
  count: number | null | undefined,
  loaded: boolean,
): string {
  if (!loaded || count === null || count === undefined) {
    return AUTO_HOME_NO_DATA_LABEL;
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
  return {
    loaded,
    isLoading,
    isError,
    stateTone: state.tone,
    stateLabel: loaded ? state.label : AUTO_HOME_NO_DATA_LABEL,
    portfolioLabel: loaded
      ? portfolioLabelFromStatus(input.portfolioStatus)
      : AUTO_HOME_NO_DATA_LABEL,
    fillLinkIssuesLabel: fillLinkIssuesLabelFromCount(
      input.fillLinkIssuesCount,
      loaded,
    ),
    // Nunca materializado en el read-model de AUTO: se declara, no se inventa.
    positionRiskLabel: AUTO_HOME_NO_DATA_LABEL,
    positionRiskAvailable: false,
  };
}
