/**
 * P2 (sello 2) — helpers PUROS de la auditoría por valor de ESTUDIO (testeables).
 *
 * Regla de oro: un dato ausente se declara «Sin dato todavía», JAMÁS un `0` que finja
 * medición; y un valor solo se rotula «Medido» si R y dinero alcanzan su suelo de muestra.
 */

export type EstudioValueState = "measured" | "unmeasured";

export const ESTUDIO_VALUE_LABELS: Record<EstudioValueState, string> = {
  measured: "Medido (R y dinero)",
  unmeasured: "Sin dato todavía",
};

export function estudioValueState(measured: boolean): EstudioValueState {
  return measured ? "measured" : "unmeasured";
}

/** R en múltiplos del riesgo; `null` ⇒ «Sin dato todavía» (nunca `0`). */
export function formatR(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Sin dato todavía";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}R`;
}

/** Porcentaje; `null` ⇒ «Sin dato todavía» (nunca `0`). */
export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Sin dato todavía";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Sin dato todavía";
  return `${(value * 100).toFixed(0)}%`;
}

/** Identidad EXACTA de la estrategia; hueco declarado si no viaja. */
export function describeStrategy(strategy: {
  presetKey?: string | null;
  version?: string | null;
}): string {
  const preset = strategy.presetKey?.trim();
  if (!preset) return "Sin dato todavía (identidad no declarada)";
  const version = strategy.version?.trim();
  return version ? `${preset} · ${version}` : preset;
}

/** Veredicto del resultado en R, con el motivo declarado si lo hay. */
export function describeVerdict(resultR: {
  verdict?: string;
  verdictReason?: string | null;
}): string {
  const verdict = (resultR.verdict || "NOT_MEASURED").trim();
  const reason = resultR.verdictReason?.trim();
  return reason ? `${verdict} · ${reason}` : verdict;
}
