/**
 * B-5 / O-6 — lectura de las declaraciones de HOLD con su PROCEDENCIA.
 *
 * El monitor ya publica `signalHolds[]` con el motivo del vocabulario cerrado y los hechos que
 * explican con qué dato se llegó a la decisión (`facts`). Este módulo los convierte en filas
 * legibles para un usuario no técnico **sin reinterpretar nada**:
 *
 * 1. La causa y el motivo salen de `lib/decision-silence.ts` (clasificación por literal exacto,
 *    «no evaluable» ≠ «sin señal»). Aquí no se añade una segunda taxonomía.
 * 2. Sólo las claves conocidas suben al primer nivel, con una etiqueta humana. Un hecho que no
 *    se reconoce NO se presenta como causa: queda en el detalle técnico con su clave cruda.
 * 3. Un valor ausente no se convierte en `0`/`false`: no produce item de procedencia y la
 *    medición **nunca se deduce** del valor; sin medición declarada se rotula `UNKNOWN`.
 * 4. La fecha de la barra se muestra como día (estable respecto a la zona horaria); un sello no
 *    parseable se conserva crudo en lugar de inventar una fecha. Los identificadores crudos
 *    viven en el detalle técnico.
 * 5. El alcance temporal es explícito: `buildAutoHoldDeclarations(holds, { day })` filtra por el
 *    día de la **vela** (`barTimestamp`, el que la fila presenta como «barra»), declara cuántas
 *    caen fuera y cuántas no tienen fecha de barra (no se asignan a ningún día ni se cuentan como
 *    exclusión). `[]` no significa «no hubo HOLD», significa que no consta la declaración.
 *
 * @see apps/web/src/lib/decision-silence.ts
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md
 */

import { absentDataLabel } from "@/components/absent-data";
import {
  formatDate,
  formatDateTimeCompact,
  formatDateWith,
} from "@/lib/format";
import {
  decisionSilenceCause,
  decisionSilenceLabel,
  decisionSilenceReasonLabel,
  decisionSilenceSummary,
  isNotEvaluableCause,
  type DecisionSilenceCause,
  type DecisionSilenceSummary,
} from "@/lib/decision-silence";

// ---------------------------------------------------------------------------
// Entradas (forma mínima del DTO; el panel mapea `AutoMonitorSignalHoldV1`)
// ---------------------------------------------------------------------------

export type AutoHoldFactInput = {
  key: string;
  value: unknown;
  /** Medición declarada por el productor; ausente ⇒ `UNKNOWN`, nunca se deduce del valor. */
  measurement?: string | null;
};

export type AutoHoldDeclarationInput = {
  instrumentId?: string | null;
  barTimestamp?: string | null;
  at?: string | null;
  /** Motivo del vocabulario cerrado, tal cual lo selló el productor. */
  reason?: string | null;
  measurement?: string | null;
  facts?: readonly AutoHoldFactInput[] | null;
};

/** Alcance temporal de la lectura. `day` = `YYYY-MM-DD` del día explicado. */
export type AutoHoldDeclarationsOptions = {
  day?: string | null;
};

// ---------------------------------------------------------------------------
// Salidas
// ---------------------------------------------------------------------------

/** Hecho de procedencia ya legible. El valor sigue siendo el dato, no una conclusión. */
export type AutoHoldProvenanceItem = {
  key: string;
  label: string;
  /** Valor legible (o el crudo cuando la clave ya es legible por sí misma). */
  value: unknown;
  /** Medición del hecho, sin reinterpretar. */
  measurement: string;
};

export type AutoHoldDeclarationsRow = {
  key: string;
  instrumentId: string | null;
  /** Símbolo reconocible para primer nivel (`instrumentId` es la identidad declarada). */
  symbol: string | null;
  cause: DecisionSilenceCause;
  causeLabel: string;
  reasonLabel: string | null;
  /** `true` si el productor no declaró un motivo legible (ni ausente ni fuera del vocabulario). */
  reasonMissing: boolean;
  /** Literal crudo del vocabulario: sólo en el detalle técnico. */
  reasonCode: string | null;
  barTimestamp: string | null;
  /** Día legible de la barra; `null` si el productor no la declaró. */
  barLabel: string | null;
  at: string | null;
  atLabel: string | null;
  measurement: string;
  provenance: AutoHoldProvenanceItem[];
  /** Todos los hechos, incluidos los no reconocidos, para el detalle técnico. */
  technicalFacts: readonly AutoHoldFactInput[];
};

export type AutoHoldDeclarations = {
  rows: AutoHoldDeclarationsRow[];
  summary: DecisionSilenceSummary;
  /** Filas no evaluables (huecos a resolver), en el orden de lectura. */
  attention: AutoHoldDeclarationsRow[];
  /** Declaraciones de la ventana que caen fuera del día explicado. */
  excludedByDay: number;
  /** Nota de alcance temporal; `null` si no se filtró por día o nada quedó fuera. */
  scopeNote: string | null;
  /**
   * Declaraciones de la ventana sin día de barra utilizable: no se asignan a ningún día y
   * **no** se cuentan como exclusión (no pertenecen a otro día; se desconoce el suyo).
   */
  withoutBarDay: number;
  /** Nota propia de las declaraciones sin fecha de barra; `null` si no las hay o no se filtró. */
  undatedNote: string | null;
};

// ---------------------------------------------------------------------------
// Etiquetas humanas de la procedencia
// ---------------------------------------------------------------------------

/**
 * Orden de lectura de la procedencia: qué dato sostuvo la señal → tamaño de la ventana →
 * calentamiento → de dónde salió la ventana → estado del libro → detalle → estrategia.
 * Un hecho fuera de esta lista no se promociona al primer nivel.
 */
export const AUTO_HOLD_PROVENANCE_ORDER: readonly string[] = [
  "featureSource",
  "signalWindowBars",
  "warmupBars",
  "signalWindowSource",
  "gatedState",
  "holdDetail",
  "strategyPresetKey",
  "strategyVersion",
] as const;

export const AUTO_HOLD_PROVENANCE_LABELS: Record<string, string> = {
  featureSource: "Fuente de indicadores",
  signalWindowBars: "Barras evaluadas",
  warmupBars: "Calentamiento requerido",
  signalWindowSource: "Origen de la ventana",
  gatedState: "Estado del libro",
  holdDetail: "Detalle del motivo",
  strategyPresetKey: "Estrategia",
  strategyVersion: "Versión de la estrategia",
};

/** `real`/`synthetic` son fuentes de dato, no una garantía de calidad. */
const FEATURE_SOURCE_LABELS: Record<string, string> = {
  real: "datos reales",
  synthetic: "datos sintéticos",
};

const SIGNAL_WINDOW_SOURCE_LABELS: Record<string, string> = {
  env: "configuración del entorno",
  preset_warmup: "calentamiento del preset",
};

const GATED_SOURCE_LABELS: Record<string, string> = {
  book: "leído del libro",
  unavailable: "libro no legible",
};

function nonEmpty(value: string | null | undefined): string | null {
  const text = (value ?? "").trim();
  return text.length > 0 ? text : null;
}

/** `true` si el hecho trae un valor afirmable (un `false`/`0` medido SÍ lo es). */
function hasValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  return true;
}

/**
 * Día `YYYY-MM-DD` de un sello, sin desplazarlo de zona horaria.
 *
 * Valida el día real: un sello imposible (`2026-13-45`) no produce día, igual que un sello no
 * parseable. Así una fecha de barra corrupta no se usa para atribuir la declaración a un día.
 */
function isoDay(value: string | null | undefined): string | null {
  const text = nonEmpty(value);
  if (!text) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  const valid =
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day;
  return valid ? `${match[1]}-${match[2]}-${match[3]}` : null;
}

/**
 * Instante legible es-ES (`dd mm yyyy, hh:mm`) para el sello de la declaración. Un sello no
 * parseable se devuelve tal cual: se prefiere el original a una fecha inventada.
 */
export function formatHoldInstant(
  value: string | null | undefined,
): string | null {
  const text = nonEmpty(value);
  if (!text) return null;
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return text;
  return formatDateTimeCompact(parsed);
}

/**
 * Día legible de la barra (`dd mm yyyy`). Se lee el prefijo `YYYY-MM-DD` y se formatea en UTC:
 * una barra diaria no debe cambiar de día por la zona horaria del navegador. Un sello que no
 * empieza por un día válido se intenta parsear; si tampoco lo es, se conserva crudo.
 */
export function formatHoldBarDay(
  value: string | null | undefined,
): string | null {
  const text = nonEmpty(value);
  if (!text) return null;
  // Mismo criterio de día válido que el filtro diario: lo que no se puede atribuir a un día
  // tampoco se pinta como si lo fuera.
  const day = isoDay(text);
  if (day) {
    const [year, month, dayOfMonth] = day.split("-");
    return formatDateWith(
      new Date(Date.UTC(Number(year), Number(month) - 1, Number(dayOfMonth))),
      {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      },
    );
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return text;
  return formatDate(parsed);
}

/**
 * Resumen legible del estado del libro (ADR-048). No deriva el libro: copia lo declarado y
 * declara el hueco cuando `holdsLong` no consta. Devuelve `null` si no reconoce la forma.
 */
export function describeGatedState(value: unknown): string | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const state = value as Record<string, unknown>;
  const parts: string[] = [];
  if (typeof state.holdsLong === "boolean") {
    parts.push(
      state.holdsLong ? "libro con posición larga" : "libro sin posición larga",
    );
  }
  const source = nonEmpty(
    typeof state.source === "string" ? state.source : null,
  );
  if (source) {
    parts.push(GATED_SOURCE_LABELS[source] ?? `fuente ${source}`);
  }
  const exit = nonEmpty(
    typeof state.exitEvaluated === "string" ? state.exitEvaluated : null,
  );
  if (exit) {
    parts.push(
      exit === "last_bar"
        ? "salida evaluada en la última barra"
        : `salida evaluada en ${exit}`,
    );
  }
  // Un objeto con campos conocidos pero sin `holdsLong` declara el hueco: el estado del libro
  // se publicó, pero no se sabe si había posición.
  if (parts.length > 0 && typeof state.holdsLong !== "boolean") {
    if (!parts.includes("no se sabe si había posición")) {
      parts.unshift("no se sabe si había posición");
    }
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

/**
 * Quita el código del vocabulario que el productor antepone al detalle
 * (`"gated_unavailable: el libro no se pudo leer"`). Sólo se retira cuando el prefijo es un
 * código reconocido: un texto que empieza por una palabra con dos puntos no se recorta.
 * El valor crudo completo sigue en el detalle técnico.
 */
export function stripHoldDetailCode(value: string): string {
  const match = /^([a-z][a-z0-9_]*)\s*:\s*([\s\S]+)$/.exec(value.trim());
  if (!match) return value;
  const code = match[1] ?? "";
  const rest = (match[2] ?? "").trim();
  if (!rest) return value;
  return decisionSilenceReasonLabel(code) !== null ? rest : value;
}

/** Valor legible de una clave conocida. `null` ⇒ se conserva el crudo (objeto/texto). */
function describeProvenanceValue(key: string, value: unknown): unknown {
  switch (key) {
    case "featureSource": {
      const text = nonEmpty(typeof value === "string" ? value : null);
      if (!text) return value;
      return FEATURE_SOURCE_LABELS[text] ?? text;
    }
    case "signalWindowSource": {
      const text = nonEmpty(typeof value === "string" ? value : null);
      if (!text) return value;
      return SIGNAL_WINDOW_SOURCE_LABELS[text] ?? text;
    }
    case "signalWindowBars":
    case "warmupBars":
      return typeof value === "number" && Number.isFinite(value)
        ? `${value} barras`
        : value;
    case "gatedState":
      return describeGatedState(value) ?? value;
    case "holdDetail":
      return typeof value === "string" ? stripHoldDetailCode(value) : value;
    default:
      return value;
  }
}

/** La medición NO se deduce del valor: un hecho sin medición declarada es `UNKNOWN`. */
function factMeasurement(fact: AutoHoldFactInput): string {
  return nonEmpty(fact.measurement) ?? "UNKNOWN";
}

function buildProvenance(
  facts: readonly AutoHoldFactInput[],
): AutoHoldProvenanceItem[] {
  const byKey = new Map<string, AutoHoldFactInput>();
  for (const fact of facts) {
    // Primera declaración gana: el orden del journal es determinista y no se reordena aquí.
    if (!byKey.has(fact.key)) byKey.set(fact.key, fact);
  }
  const items: AutoHoldProvenanceItem[] = [];
  for (const key of AUTO_HOLD_PROVENANCE_ORDER) {
    const fact = byKey.get(key);
    if (!fact || !hasValue(fact.value)) continue;
    items.push({
      key,
      label: AUTO_HOLD_PROVENANCE_LABELS[key] ?? key,
      value: describeProvenanceValue(key, fact.value),
      measurement: factMeasurement(fact),
    });
  }
  return items;
}

/**
 * El día canónico es el de la **vela** (`barTimestamp`): es lo que la fila muestra como «barra».
 * `at` es el sello de registro y no decide la pertenencia al día; si difiere, sigue visible en el
 * detalle técnico pero no mueve la declaración de día.
 */
function matchesDay(hold: AutoHoldDeclarationInput, day: string): boolean {
  return isoDay(hold.barTimestamp) === day;
}

/** `true` si la declaración tiene un día de barra utilizable (sin él no se asigna a un día). */
function hasBarDay(hold: AutoHoldDeclarationInput): boolean {
  return isoDay(hold.barTimestamp) !== null;
}

function toRow(
  hold: AutoHoldDeclarationInput,
  index: number,
): AutoHoldDeclarationsRow {
  const facts = hold.facts ?? [];
  const instrumentId = nonEmpty(hold.instrumentId);
  const barTimestamp = nonEmpty(hold.barTimestamp);
  const at = nonEmpty(hold.at);
  const reasonCode = nonEmpty(hold.reason);
  const cause = decisionSilenceCause(hold.reason);
  const reasonLabel = decisionSilenceReasonLabel(hold.reason);
  return {
    key: `${instrumentId ?? "?"}-${barTimestamp ?? index}-${index}`,
    instrumentId,
    symbol: instrumentId,
    cause,
    causeLabel: decisionSilenceLabel(cause),
    reasonLabel,
    reasonMissing: reasonLabel === null,
    reasonCode,
    barTimestamp,
    barLabel: formatHoldBarDay(barTimestamp),
    at,
    atLabel: formatHoldInstant(at),
    measurement: nonEmpty(hold.measurement) ?? "UNKNOWN",
    provenance: buildProvenance(facts),
    technicalFacts: facts,
  };
}

/**
 * Read-model puro: filas + el titular honesto del conjunto.
 *
 * `[]` NO significa «no hubo HOLD»: significa que no consta la declaración, y el titular lo dice
 * así. Con `{ day }` el conjunto se limita al día explicado y `excludedByDay` declara lo que
 * queda fuera (el monitor conserva la ventana completa).
 */
export function buildAutoHoldDeclarations(
  holds: readonly AutoHoldDeclarationInput[] | null | undefined,
  options: AutoHoldDeclarationsOptions = {},
): AutoHoldDeclarations {
  const all = holds ?? [];
  const day = nonEmpty(options.day);
  const scoped = day ? all.filter((hold) => matchesDay(hold, day)) : all;
  // Sólo cuentan como exclusión las declaraciones CON día de barra que caen en otro día.
  const excludedByDay = day
    ? all.filter((hold) => hasBarDay(hold) && !matchesDay(hold, day)).length
    : 0;
  // Las que no tienen día de barra no pertenecen a otro día: se desconoce el suyo. Se cuentan
  // aparte para que el hueco de trazabilidad no desaparezca del alcance temporal.
  const withoutBarDay = day ? all.filter((hold) => !hasBarDay(hold)).length : 0;
  const rows = scoped.map((hold, index) => toRow(hold, index));
  const summary = decisionSilenceSummary(
    scoped,
    day ? "el día explicado" : "la ventana",
  );
  return {
    rows,
    summary,
    attention: rows.filter((row) => isNotEvaluableCause(row.cause)),
    excludedByDay,
    scopeNote:
      excludedByDay > 0
        ? `${excludedByDay} declaraci${
            excludedByDay === 1 ? "ón queda" : "ones quedan"
          } fuera del día explicado; el monitor conserva la ventana completa.`
        : null,
    withoutBarDay,
    undatedNote:
      withoutBarDay > 0
        ? `${withoutBarDay} declaraci${
            withoutBarDay === 1
              ? "ón sin fecha de barra"
              : "ones sin fecha de barra"
          }; ${
            withoutBarDay === 1 ? "no se puede asignar" : "no se pueden asignar"
          } a este día.`
        : null,
  };
}

/** Rótulo de primer nivel cuando el productor no declaró ningún hecho de procedencia. */
export const AUTO_HOLD_PROVENANCE_ABSENT = "Procedencia no declarada";

/** Rótulo de la fila cuando el productor no declaró el símbolo. */
export function autoHoldSymbolLabel(row: AutoHoldDeclarationsRow): string {
  return row.symbol ?? absentDataLabel();
}

/** Rótulo de la fila cuando el productor no declaró un motivo legible. */
export const AUTO_HOLD_REASON_ABSENT = "Motivo no declarado";

export function autoHoldReasonLabel(row: AutoHoldDeclarationsRow): string {
  return row.reasonLabel ?? AUTO_HOLD_REASON_ABSENT;
}
