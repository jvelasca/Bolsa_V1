/**
 * AUTO UI — Puente operación → estrategia ganadora → verificación DÍA-D (P3/P4).
 *
 * Resuelve, para UN ciclo del monitor AUTO, la cadena que el usuario exige:
 *
 *   señal del ciclo → estrategia #1 del valor (la que sustenta la señal) →
 *   indicadores detectados → razones → destino de verificación DÍA-D.
 *
 * Read-only y PURO: NO recalcula el ranking ni el score; copia el TOP ya producido
 * (`InstrumentStrategyTopV1`) y su definición. Un dato ausente se declara
 * «Sin dato todavía», nunca un valor de relleno (`UNKNOWN ≠ 0`, §5.1.4).
 *
 * Nota de honestidad: la **coincidencia** entre la versión de estrategia DECLARADA por el ciclo
 * (`cycle.strategyVersion`, un sello opaco del motor) y la identidad del #1 resuelto solo puede
 * afirmarse cuando hay un emparejamiento textual fiable. Se marca como heurística y siempre se
 * pinta el sello declarado para que el usuario juzgue; si no es comparable, se declara
 * «Sin dato todavía».
 *
 * @see docs/PROJECT_PREMISES.md §6 (P3 estrategia/indicadores · P4 DÍA-D)
 * @see packages/shared/src/instrument-strategy-top.ts
 */

import {
  strategySlotToIndicatorLabels,
  type InstrumentStrategyTopSlotV1,
  type InstrumentStrategyTopV1,
  type StrategyDefinitionV1,
} from "@bolsa/shared";
import { readRecommendationReasons } from "@/features/backtests/instrument-strategy-top-panel";
import { ABSENT_DATA_NOT_AVAILABLE } from "@/components/absent-data";
import { diaDVerifyHref } from "@/features/platform/product-universe";

/** Rótulo de primer nivel para un hueco (`UI5-14`). No se usa como comodín técnico. */
export const AUTO_OPERATION_STRATEGY_NO_DATA = "Sin dato todavía";

export const AUTO_OPERATION_STRATEGY_TITLE =
  "Estrategia que sustenta la señal" as const;

export const AUTO_OPERATION_STRATEGY_DESCRIPTION =
  "La mejor estrategia del valor en Finalistas, con los indicadores que la sustentan. Puedes verificar por tu cuenta que la operativa diaria usa esa estrategia con DÍA-D." as const;

/**
 * Rótulo del bloque de la MEJOR estrategia DISPONIBLE del valor (Finalistas TOP #1), la que
 * `getInstrumentStrategyTop` devuelve. Es lo mejor disponible, NO necesariamente lo ejecutado.
 */
export const AUTO_OPERATION_STRATEGY_BEST_AVAILABLE_LABEL =
  "Mejor estrategia del valor (Finalistas)" as const;

/**
 * Rótulo del bloque de la estrategia EJECUTADA que declara el ciclo (`cycle.strategyVersion`,
 * un sello opaco del motor; p. ej. `ActiveStrategy.version_id`). Es OTRA cosa que el TOP #1.
 */
export const AUTO_OPERATION_STRATEGY_DECLARED_LABEL =
  "Estrategia ejecutada declarada por el ciclo" as const;

/**
 * Declaración de HONESTIDAD en superficie: la coincidencia entre la estrategia EJECUTADA
 * (sello `cycle.strategyVersion`) y la MEJOR del valor (TOP #1) es una aproximación textual;
 * el enlace EXACTO no lo materializa todavía el motor del ciclo, así que no se afirma.
 */
export const AUTO_OPERATION_STRATEGY_MATCH_IS_HEURISTIC =
  "La coincidencia es una aproximación textual (igualdad por token), no una identidad exacta: el enlace entre la estrategia ejecutada y la mejor del valor todavía no lo materializa el motor del ciclo." as const;

/**
 * Tri-estado de coincidencia (`coincide` / `no coincide` / `sin dato`). Nunca se afirma
 * «coincide» sin un emparejamiento textual real; un hueco se declara.
 */
export type AutoOperationStrategyMatch = "same" | "differs" | "unknown";

export const AUTO_OPERATION_STRATEGY_MATCH_LABELS: Record<
  AutoOperationStrategyMatch,
  string
> = {
  same: "Coincide con la estrategia del ciclo",
  differs: "Distinta a la estrategia del ciclo (revisar)",
  unknown: "Sin dato todavía: no se puede emparejar",
};

export type AutoOperationStrategyViewV1 = {
  /** Ticker visible del ciclo (identidad humana del valor). */
  symbol: string;
  /** UUID RESUELTO del instrumento (necesario para el TOP y el deep-link DÍA-D); `null` = hueco. */
  instrumentId: string | null;
  /** Estrategia #1 que sustenta la señal (identidad). */
  strategyDefinitionId: string | null;
  /** Etiqueta legible de la estrategia (o «Sin dato todavía»). */
  strategyLabel: string;
  /** Puesto del #1 en Finalistas (o `null` si no hay TOP). */
  rank: number | null;
  /** Nombres legibles de los indicadores que sustentan la estrategia. */
  indicators: string[];
  /** Razones del coach para el slot #1 (texto humano). */
  reasons: string[];
  /** Coincidencia (heurística declarada) con el sello de estrategia del ciclo. */
  match: AutoOperationStrategyMatch;
  matchLabel: string;
  /** Sello `strategyVersion` que el ciclo declara (o `null`). */
  declaredCycleStrategyVersion: string | null;
  /** Destino canónico de verificación DÍA-D (o `null` si falta instrumento/estrategia). */
  verifyHref: string | null;
  /** Motivo del hueco cuando la cadena está incompleta (o `null`). */
  gapReason: string | null;
  /**
   * Lecturas en vuelo (`instruments`/`TOP`/`definition`). Mientras es `true`, un hueco es
   * TRANSITORIO: NO se declara ausencia (`gapReason` queda `null`) y la UI muestra carga.
   */
  loading: boolean;
};

export type AutoOperationStrategyInput = {
  /** Ciclo del monitor (ticker en `instrumentId` + versión declarada). */
  cycle: {
    instrumentId?: string | null;
    strategyVersion?: string | null;
  } | null;
  /** UUID resuelto del instrumento (distinto del ticker del ciclo). */
  instrumentId: string | null;
  /**
   * La lectura del CATÁLOGO DE INSTRUMENTOS FALLÓ (HTTP/red). Distinto de «instrumento sin
   * resolver»: el UUID sí podría existir y no pudimos leerlo ⇒ se declara `No disponible`,
   * nunca «Sin dato todavía».
   */
  instrumentError?: boolean;
  top: InstrumentStrategyTopV1 | null;
  /**
   * La lectura del TOP FALLÓ (HTTP/red). Distinto de «no hay TOP»: aquí SÍ podría existir un
   * TOP que no pudimos leer ⇒ se declara `No disponible`, nunca «Sin dato todavía».
   */
  topError?: boolean;
  /** Definición de la estrategia #1 (fuente de indicadores); `null` = fallback a preset. */
  definition: Pick<StrategyDefinitionV1, "indicatorSpecs" | "presetKey"> | null;
  /**
   * La lectura de la DEFINICIÓN FALLÓ (HTTP/red). Distinto de «sin definición guardada»: no se
   * pudo leer una definición que podría existir ⇒ se declara `No disponible`.
   */
  definitionError?: boolean;
  /**
   * Lecturas en vuelo (`instruments`/`TOP`/`definition`). Mientras es `true`, un hueco es
   * TRANSITORIO: no se declara ausencia; los errores declarados siguen mandando.
   */
  loading?: boolean;
};

/**
 * Parte una cadena en TOKENS completos (lowercased) por separadores no alfanuméricos y descarta
 * los de longitud < 2. Se compara por token entero, nunca por contención: así un sello corto
 * (p. ej. «ma») no coincide con un token distinto que lo contiene (p. ej. «smacrossover»).
 */
function tokenizeStrategy(value: string | null | undefined): string[] {
  return (value ?? "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length >= 2);
}

/**
 * Empareja el sello de estrategia del ciclo con la identidad del #1 (heurística declarada).
 *
 * Solo declara `same` cuando algún token del sello IGUALA EXACTAMENTE a un token de la identidad
 * del #1 (`strategyDefinitionId`/`label`/`strategyType`); `unknown` si no hay sello válido, no hay
 * #1 o no hay tokens comparables; `differs` si hay tokens comparables y ninguno coincide.
 */
export function resolveAutoOperationStrategyMatch(
  cycleStrategyVersion: string | null | undefined,
  slot: InstrumentStrategyTopSlotV1 | null | undefined,
): AutoOperationStrategyMatch {
  const versionTokens = tokenizeStrategy(cycleStrategyVersion);
  if (versionTokens.length === 0) return "unknown";
  if (!slot) return "unknown";
  const identityTokens = new Set<string>([
    ...tokenizeStrategy(slot.strategyDefinitionId),
    ...tokenizeStrategy(slot.label),
    ...tokenizeStrategy(slot.strategyType),
  ]);
  if (identityTokens.size === 0) return "unknown";
  const matched = versionTokens.some((token) => identityTokens.has(token));
  return matched ? "same" : "differs";
}

/**
 * Compone la vista de la cadena estrategia → indicadores → razón para UN ciclo de AUTO.
 *
 * Devuelve `null` solo si no hay ciclo. Con ciclo, siempre devuelve una vista: los huecos
 * (`instrumentId` sin resolver, sin TOP, sin definición) se declaran en `gapReason` y el CTA
 * de verificación queda inhabilitado, nunca se fabrica una estrategia. Con `loading === true`
 * el hueco es transitorio: `gapReason` queda `null` para que la UI muestre carga, no ausencia.
 */
export function buildAutoOperationStrategyView(
  input: AutoOperationStrategyInput,
): AutoOperationStrategyViewV1 | null {
  const cycle = input.cycle;
  if (!cycle) return null;

  const symbol = cycle.instrumentId?.trim() || AUTO_OPERATION_STRATEGY_NO_DATA;
  const declaredCycleStrategyVersion = cycle.strategyVersion?.trim() || null;
  const resolvedInstrumentId = input.instrumentId?.trim() || null;

  const slot = input.top
    ? ([...input.top.slots].sort((a, b) => a.rank - b.rank)[0] ?? null)
    : null;

  const indicators = slot
    ? strategySlotToIndicatorLabels({ slot, definition: input.definition })
        .labels
    : [];
  const reasons = slot
    ? readRecommendationReasons(input.top?.coachFacts ?? null, slot.rank)
    : [];

  const strategyDefinitionId = slot?.strategyDefinitionId?.trim() || null;
  const strategyLabel = slot?.label?.trim() || AUTO_OPERATION_STRATEGY_NO_DATA;
  const rank = slot?.rank ?? null;

  const match = resolveAutoOperationStrategyMatch(
    declaredCycleStrategyVersion,
    slot,
  );

  // Prioridad DECLARADA del hueco: un FALLO de lectura nunca se describe como ausencia
  // (`No disponible` ≠ `Sin dato todavía`); una lectura EN VUELO deja el hueco en `null` (la UI
  // muestra carga y no un falso «sin dato»); solo el hueco real usa el rótulo de ausencia.
  // El fallo del catálogo de instrumentos va PRIMERO: sin catálogo el UUID no puede resolverse
  // (y TOP/definición ni se piden), así que manda sobre `loading` y sobre el hueco de instrumento.
  let gapReason: string | null = null;
  if (input.instrumentError === true) {
    gapReason = `${ABSENT_DATA_NOT_AVAILABLE}: no se pudo leer el catálogo de instrumentos.`;
  } else if (input.topError === true) {
    gapReason = `${ABSENT_DATA_NOT_AVAILABLE}: no se pudo leer el TOP de Finalistas.`;
  } else if (input.definitionError === true) {
    gapReason = `${ABSENT_DATA_NOT_AVAILABLE}: no se pudo leer la definición de la estrategia #1.`;
  } else if (input.loading === true) {
    gapReason = null;
  } else if (!resolvedInstrumentId) {
    gapReason =
      "Sin dato todavía: no se pudo resolver el instrumento de la operación.";
  } else if (!slot) {
    gapReason = "Sin dato todavía: no hay Finalistas (TOP) para este valor.";
  } else if (!strategyDefinitionId) {
    gapReason =
      "Sin dato todavía: la estrategia #1 no tiene definición guardada.";
  }

  // Fail-closed ante un error de lectura: sin catálogo/TOP/definición fiables no se ofrece
  // verificación.
  const verifyHref =
    resolvedInstrumentId &&
    strategyDefinitionId &&
    input.instrumentError !== true &&
    input.topError !== true &&
    input.definitionError !== true
      ? diaDVerifyHref(resolvedInstrumentId)
      : null;

  return {
    symbol,
    instrumentId: resolvedInstrumentId,
    strategyDefinitionId,
    strategyLabel,
    rank,
    indicators,
    reasons,
    match,
    matchLabel: AUTO_OPERATION_STRATEGY_MATCH_LABELS[match],
    declaredCycleStrategyVersion,
    verifyHref,
    gapReason,
    loading: input.loading === true,
  };
}
