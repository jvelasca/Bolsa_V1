/**
 * R-2 — traducción de los códigos del parte diario ESTUDIO a frases de PRIMER NIVEL.
 *
 * El backend publica códigos estables (`positions_unavailable`,
 * `composite_chips_unavailable:12_ids`, …) porque son contrato y evidencia. El usuario de
 * nivel 1 no debe leerlos: aquí se convierten en frases que dicen QUÉ no se sabe y qué
 * implica. El código crudo viaja en `technical` y solo se pinta dentro del disclosure
 * técnico (`AutoTechnicalDetail`), nunca en la superficie principal.
 *
 * Un código DESCONOCIDO no se oculta ni se disfraza: se declara que hay un dato sin medir y
 * el crudo queda en el detalle técnico.
 */

export type EstudioDailyNoteV1 = {
  /** Código original (clave de lista y contenido del disclosure técnico). */
  code: string;
  /** Frase de nivel 1. */
  headline: string;
  /** Texto crudo del backend (solo dentro del detalle técnico). */
  technical: string;
};

const UNKNOWN_HEADLINE = "Hay un dato del parte que no se pudo medir.";

const POSITIONS_UNAVAILABLE =
  "No se pudo leer tu cartera: el dictamen no sabe si ya tienes este valor.";
const COMPOSITE_CHIPS =
  "No se pudieron leer los indicadores del motor en {n} valores; esos valores aparecen sin medida.";
const FUNDAMENTALS_CHIPS =
  "No se pudieron leer los indicadores fundamentales en {n} valores; esos valores aparecen sin medida.";
const OPINION_ERRORS =
  "El dictamen falló en {n} valores; su parte aparece como error, no como «sin señal».";
const PROPOSE_UNAVAILABLE =
  "La propuesta de planes no estuvo disponible: los valores con señal pueden aparecer sin plan.";
const ADVISORY =
  "El parte es informativo: la ejecución real se decide en el camino de ejecución.";
const UNIVERSE_TRUNCATED =
  "El universo se recortó: este parte no cubre todos los valores de la lista.";
const VALUES_NOT_REPORTED =
  "El parte no trajo {n} valores del universo: su estado no se pudo declarar.";
const SELECTOR_UNAVAILABLE =
  "No se pudo leer el selector del día: no se sabe qué estrategia quedó primera en el ranking.";
const SELECTOR_NOT_CONFIGURED =
  "Este parte no incluye la identidad del selector; no se puede afirmar qué estrategia ganó.";
const SELECTOR_NO_SNAPSHOT =
  "No hay foto del selector para este día: el ganador no se puede afirmar.";
const SELECTOR_NO_RANK_ONE =
  "La foto del selector no trae un ganador identificable.";
const ALL_VALUES_FAILED =
  "Ningún valor del universo se pudo medir: el parte de hoy no es utilizable.";

const CHIP_PATTERN = /^(composite|fundamentals)_chips_unavailable:(\d+)_ids$/;
const OPINION_ERRORS_PATTERN = /^opinion_errors:(\d+)_values$/;
const TRUNCATED_PATTERN = /^Universo recortado a (\d+) valores/i;
//: C-2 — códigos ESTABLES del parte cuando el universo se recorta o faltan valores.
const UNIVERSE_TRUNCATED_CODE = /^universe_truncated(?::(\d+))?$/;
const VALUES_NOT_REPORTED_CODE = /^values_not_reported:(\d+)$/;

/**
 * Traduce UN código del parte a `{ headline, technical }`. PURA y total: siempre devuelve
 * una frase (los códigos desconocidos se declaran como hueco, no se silencian).
 */
export function describeEstudioDailyNote(raw: string): EstudioDailyNoteV1 {
  const code = String(raw ?? "").trim();
  const technical = code;

  if (!code) {
    return { code, headline: UNKNOWN_HEADLINE, technical };
  }

  const chip = CHIP_PATTERN.exec(code);
  if (chip) {
    const template =
      chip[1] === "composite" ? COMPOSITE_CHIPS : FUNDAMENTALS_CHIPS;
    return {
      code,
      headline: template.replace("{n}", chip[2] ?? ""),
      technical,
    };
  }

  const opinionErrors = OPINION_ERRORS_PATTERN.exec(code);
  if (opinionErrors) {
    return {
      code,
      headline: OPINION_ERRORS.replace("{n}", opinionErrors[1] ?? ""),
      technical,
    };
  }

  // C-2 — el recorte del universo llega como código desde `degradedReasons`; sin esto
  // caía en el texto genérico y el banner de parcial no decía QUÉ faltaba.
  if (UNIVERSE_TRUNCATED_CODE.test(code)) {
    return { code, headline: UNIVERSE_TRUNCATED, technical };
  }

  const notReported = VALUES_NOT_REPORTED_CODE.exec(code);
  if (notReported) {
    return {
      code,
      headline: VALUES_NOT_REPORTED.replace("{n}", notReported[1] ?? ""),
      technical,
    };
  }

  switch (code) {
    case "positions_unavailable":
      return { code, headline: POSITIONS_UNAVAILABLE, technical };
    case "propose_unavailable":
      return { code, headline: PROPOSE_UNAVAILABLE, technical };
    case "selector_identity_unavailable":
      return { code, headline: SELECTOR_UNAVAILABLE, technical };
    case "selector_not_configured":
      return { code, headline: SELECTOR_NOT_CONFIGURED, technical };
    case "no_snapshot_for_day":
      return { code, headline: SELECTOR_NO_SNAPSHOT, technical };
    case "no_rank_one_row":
      return { code, headline: SELECTOR_NO_RANK_ONE, technical };
    case "all_values_failed":
      return { code, headline: ALL_VALUES_FAILED, technical };
    default:
      break;
  }

  if (code.startsWith("propose no disponible")) {
    return { code, headline: PROPOSE_UNAVAILABLE, technical };
  }
  if (code.startsWith("allowTrading=true")) {
    return { code, headline: ADVISORY, technical };
  }
  if (TRUNCATED_PATTERN.test(code)) {
    return { code, headline: UNIVERSE_TRUNCATED, technical };
  }
  return { code, headline: UNKNOWN_HEADLINE, technical };
}

/**
 * Traduce una lista de códigos sin repetir frases (el mismo hueco puede llegar por `notes`
 * y por `degradedReasons`). El `code` repetido se conserva una sola vez.
 */
export function describeEstudioDailyNotes(
  notes: readonly (string | null | undefined)[] | null | undefined,
): EstudioDailyNoteV1[] {
  const out: EstudioDailyNoteV1[] = [];
  const seen = new Set<string>();
  for (const note of notes ?? []) {
    const described = describeEstudioDailyNote(String(note ?? ""));
    if (!described.code || seen.has(described.code)) continue;
    seen.add(described.code);
    out.push(described);
  }
  return out;
}

/** Etiqueta de la posición abierta en TRI-ESTADO (`null` = cartera sin medir). */
export function describePositionOpen(
  value: boolean | null | undefined,
): string {
  if (value === true) return "Con posición abierta";
  if (value === false) return "Sin posición abierta";
  return "Cartera sin medida";
}

/** Explicación del hueco de cartera (solo cuando `positionOpen` no se midió). */
export const POSITION_UNMEASURED_DETAIL =
  "Sin dato de cartera: no se pudo leer tu cartera, así que el dictamen no sabe si ya tienes el valor. No se recomienda operar con este dato.";
