/**
 * Narrativa corta de evolución por instrumento (usuario / IA / sistema).
 * No vive en el maestro `instruments`: entidad versionada por alcance.
 *
 * @see docs/engineering/instruments-hub-narrative-2026-08-04.md
 */

export const INSTRUMENT_NARRATIVE_SCOPES = ['estudio', 'global', 'trading'] as const;
export type InstrumentNarrativeScope = (typeof INSTRUMENT_NARRATIVE_SCOPES)[number];

export const INSTRUMENT_NARRATIVE_SOURCES = ['user', 'ai', 'system'] as const;
export type InstrumentNarrativeSource = (typeof INSTRUMENT_NARRATIVE_SOURCES)[number];

/** Tope blando de líneas (UI + API). */
export const INSTRUMENT_NARRATIVE_MAX_LINES = 20;
/** Tope duro de caracteres. */
export const INSTRUMENT_NARRATIVE_MAX_CHARS = 4000;

/** Días tras los cuales una narrativa IA/sistema se considera caduca para contexto. */
export const INSTRUMENT_NARRATIVE_FRESH_DAYS = 14;

export type InstrumentNarrativeV1 = {
  id: string;
  instrumentId: string;
  scope: InstrumentNarrativeScope;
  body: string;
  source: InstrumentNarrativeSource;
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type UpsertInstrumentNarrativeRequestV1 = {
  scope?: InstrumentNarrativeScope;
  body: string;
  source?: InstrumentNarrativeSource;
};

export function countNarrativeLines(body: string): number {
  if (!body) return 0;
  return body.replace(/\r\n/g, '\n').split('\n').length;
}

export function validateInstrumentNarrativeBody(body: string): {
  ok: boolean;
  chars: number;
  lines: number;
  error?: string;
} {
  const chars = body.length;
  const lines = countNarrativeLines(body);
  if (chars > INSTRUMENT_NARRATIVE_MAX_CHARS) {
    return {
      ok: false,
      chars,
      lines,
      error: `Máximo ${INSTRUMENT_NARRATIVE_MAX_CHARS} caracteres`,
    };
  }
  if (lines > INSTRUMENT_NARRATIVE_MAX_LINES) {
    return {
      ok: false,
      chars,
      lines,
      error: `Máximo ${INSTRUMENT_NARRATIVE_MAX_LINES} líneas`,
    };
  }
  return { ok: true, chars, lines };
}

export function isInstrumentNarrativeFresh(
  updatedAt: string,
  nowMs = Date.now(),
  freshDays = INSTRUMENT_NARRATIVE_FRESH_DAYS,
): boolean {
  const t = Date.parse(updatedAt);
  if (!Number.isFinite(t)) return false;
  return nowMs - t <= freshDays * 24 * 60 * 60 * 1000;
}
