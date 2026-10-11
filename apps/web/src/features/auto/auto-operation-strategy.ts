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
 * Nota de honestidad: la **coincidencia** entre la identidad EXACTA que DECLARA el ciclo
 * (`cycle.strategyPresetKey`, la misma clave `presetKey` del TOP de Finalistas) y la identidad
 * del #1 resuelto es una IGUALDAD EXACTA de cadenas (sin tokenizar ni buscar contención). El
 * sello `cycle.strategyVersion` (opaco) se pinta aparte para que el usuario juzgue. Cuando el
 * ciclo no declara la clave exacta, se declara «Sin dato todavía» y NUNCA se afirma coincidencia.
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
 * Rótulo del bloque de la estrategia EJECUTADA que declara el ciclo: la clave EXACTA
 * (`cycle.strategyPresetKey`, el mismo `presetKey` del TOP #1) y el sello opaco del motor
 * (`cycle.strategyVersion`, p. ej. `ActiveStrategy.version_id`). Es OTRA cosa que el TOP #1.
 */
export const AUTO_OPERATION_STRATEGY_DECLARED_LABEL =
  "Estrategia ejecutada declarada por el ciclo" as const;

/**
 * Declaración de HONESTIDAD en superficie: la coincidencia entre la estrategia EJECUTADA que
 * declara el ciclo (clave EXACTA `cycle.strategyPresetKey`) y la MEJOR del valor (TOP #1) es
 * una IGUALDAD EXACTA (`presetKey`). Cuando el ciclo no declara esa clave, la UI dice «Sin dato
 * todavía» y NUNCA afirma una coincidencia.
 */
export const AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT =
  "La coincidencia es una identidad EXACTA (`presetKey`): el mismo espacio de claves que el TOP de Finalistas. Cuando el ciclo no declara su clave, se muestra «Sin dato todavía» y no se afirma ninguna coincidencia." as const;

/**
 * Tri-estado de coincidencia (`coincide` / `no coincide` / `sin dato`). Nunca se afirma
 * «coincide» sin una igualdad EXACTA de la clave declarada; un hueco se declara.
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
  /** Coincidencia EXACTA (`presetKey`) con la identidad declarada por el ciclo. */
  match: AutoOperationStrategyMatch;
  matchLabel: string;
  /** Clave EXACTA `strategyPresetKey` que declara el ciclo (o `null` si no la declara). */
  declaredCyclePresetKey: string | null;
  /** Sello opaco `strategyVersion` que declara el ciclo (o `null`), aparte de la clave exacta. */
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
  /** Ciclo del monitor (ticker en `instrumentId` + clave EXACTA y versión declaradas). */
  cycle: {
    instrumentId?: string | null;
    strategyPresetKey?: string | null;
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
 * Empareja la clave EXACTA de estrategia declarada por el ciclo (`presetKey`) con la identidad
 * del #1 (TOP de Finalistas).
 *
 * IGUALDAD EXACTA de cadenas: ni tokenización ni contención. Solo declara `same` cuando la clave
 * (recortada) IGUALA EXACTAMENTE a alguna de las identidades que el #1 DECLARA
 * (`slot.strategyType` o `definition.presetKey`, recortadas). Declara `unknown` si el ciclo no
 * declara la clave (vacía o solo espacios), no hay #1, o el #1 NO declara ninguna identidad
 * (`strategyType`/`presetKey` ambos ausentes): sin identidad del #1 no hay nada que comparar, así
 * que NUNCA se afirma `differs` (`UNKNOWN ≠ 0`, §5.1.4). `differs` solo con identidad comparable.
 */
export function resolveAutoOperationStrategyMatch(
  cyclePresetKey: string | null | undefined,
  slot: InstrumentStrategyTopSlotV1 | null | undefined,
  definition?: Pick<StrategyDefinitionV1, "presetKey"> | null,
): AutoOperationStrategyMatch {
  const key = cyclePresetKey?.trim() || null;
  if (!key) return "unknown";
  if (!slot) return "unknown";
  // Identidades DECLARADAS por el #1: tipo del slot y `presetKey` de su definición (si se conoce).
  // Se comparan como cadenas EXACTAS, ya recortadas (sin normalizar a minúsculas ni tokenizar).
  const identityTokens = new Set<string>();
  const slotType = slot.strategyType?.trim() || null;
  if (slotType) identityTokens.add(slotType);
  const presetKey = definition?.presetKey?.trim() || null;
  if (presetKey) identityTokens.add(presetKey);
  // Sin identidad DECLARADA por el #1 no hay término de comparación: se declara el hueco
  // («Sin dato todavía»), jamás una divergencia que no se puede probar.
  if (identityTokens.size === 0) return "unknown";
  return identityTokens.has(key) ? "same" : "differs";
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
  // Clave EXACTA declarada por el ciclo (`presetKey`): la base de la igualdad; `null` = no la
  // declara ⇒ el emparejamiento queda `unknown` («Sin dato todavía», no se finge una identidad).
  const declaredCyclePresetKey = cycle.strategyPresetKey?.trim() || null;
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
    declaredCyclePresetKey,
    slot,
    input.definition,
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
    declaredCyclePresetKey,
    declaredCycleStrategyVersion,
    verifyHref,
    gapReason,
    loading: input.loading === true,
  };
}
