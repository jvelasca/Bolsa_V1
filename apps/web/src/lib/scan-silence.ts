import {
  isWarmupInsufficientReason,
  type ScanRunResultDto,
  type ScanSkippedInstrumentDto,
} from "@bolsa/shared";

/**
 * P1-12b — el titular del scan deja de confundir «no evaluable» con «sin señal».
 *
 * Tres causas distintas desembocaban en el mismo texto: (1) el instrumento se evaluó y
 * no había señal, (2) se saltó por falta de barras (`MIN_SCAN_BARS`), (3) el preset no
 * puede disparar con la ventana disponible (warmup > barras, motivo
 * `warmup_insufficient`). La (3) es la que produce B-1/B-6 y era la más engañosa: el
 * panel decía «sin señales» sobre un instrumento que el motor nunca llegó a evaluar.
 *
 * Se clasifica por el **prefijo estable** del motivo, no por el texto libre.
 */

/** Motivo de `scans.py` cuando el instrumento no llega a `MIN_SCAN_BARS`. */
const INSUFFICIENT_BARS_PREFIX = "menos de";

export type ScanSilenceCause = "not_evaluable" | "insufficient_data" | "other";

export interface ScanSilenceBreakdown {
  /** Instrumentos que SÍ se evaluaron y no dieron señal. */
  evaluated: number;
  notEvaluable: number;
  insufficientData: number;
  other: number;
}

export interface ScanSilenceSummary {
  breakdown: ScanSilenceBreakdown;
  headline: string;
  detail: string | null;
}

export function skippedCause(reason: string): ScanSilenceCause {
  if (isWarmupInsufficientReason(reason)) return "not_evaluable";
  if (reason.trimStart().toLowerCase().startsWith(INSUFFICIENT_BARS_PREFIX)) {
    return "insufficient_data";
  }
  return "other";
}

export function scanSilenceBreakdown(
  result: Pick<ScanRunResultDto, "scannedCount" | "skipped">,
): ScanSilenceBreakdown {
  let notEvaluable = 0;
  let insufficientData = 0;
  let other = 0;
  for (const item of result.skipped) {
    const cause = skippedCause(item.reason);
    if (cause === "not_evaluable") notEvaluable += 1;
    else if (cause === "insufficient_data") insufficientData += 1;
    else other += 1;
  }
  const evaluated = Math.max(0, result.scannedCount - result.skipped.length);
  return { evaluated, notEvaluable, insufficientData, other };
}

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

/**
 * Titular honesto para un scan **sin hits**.
 *
 * Dos reglas, y ninguna adorna el dato:
 *
 * 1. Si **nada** se llegó a evaluar, no se puede afirmar «sin señal»: se dice que no
 *    hubo evaluación y se desglosa el motivo.
 * 2. Si algo se evaluó pero además hay no evaluables, el titular los separa: «N sin
 *    señal · M no evaluables». El número de «sin señal» cuenta solo lo evaluado.
 */
export function scanSilenceSummary(
  result: Pick<ScanRunResultDto, "scannedCount" | "skipped">,
): ScanSilenceSummary {
  const breakdown = scanSilenceBreakdown(result);
  const notEvaluated =
    breakdown.notEvaluable + breakdown.insufficientData + breakdown.other;

  if (breakdown.evaluated === 0 && notEvaluated > 0) {
    return {
      breakdown,
      headline: "Ningún instrumento pudo evaluarse",
      detail: describeNotEvaluated(breakdown),
    };
  }

  if (notEvaluated > 0) {
    return {
      breakdown,
      headline:
        `${breakdown.evaluated} sin señal · ` +
        `${plural(notEvaluated, "instrumento no evaluable", "instrumentos no evaluables")}`,
      detail: describeNotEvaluated(breakdown),
    };
  }

  return {
    breakdown,
    headline: "Sin señales en la última barra de la lista.",
    detail: null,
  };
}

function describeNotEvaluated(breakdown: ScanSilenceBreakdown): string | null {
  const parts: string[] = [];
  if (breakdown.notEvaluable > 0) {
    parts.push(
      `${plural(breakdown.notEvaluable, "no evaluable", "no evaluables")} por warmup: ` +
        "el preset necesita más barras que la ventana disponible",
    );
  }
  if (breakdown.insufficientData > 0) {
    parts.push(
      `${plural(breakdown.insufficientData, "sin barras suficientes", "sin barras suficientes")} ` +
        "— sincroniza el instrumento",
    );
  }
  if (breakdown.other > 0) {
    parts.push(
      `${plural(breakdown.other, "omitido por otro motivo", "omitidos por otros motivos")}`,
    );
  }
  return parts.length ? `${parts.join(" · ")}.` : null;
}

/** Los no evaluables, para listarlos junto al titular sin abrir el desplegable. */
export function notEvaluableSkipped(
  skipped: ScanSkippedInstrumentDto[],
): ScanSkippedInstrumentDto[] {
  return skipped.filter(
    (item) => skippedCause(item.reason) === "not_evaluable",
  );
}
