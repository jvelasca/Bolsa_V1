/**
 * Vocabulario de producto canónico (V1.24).
 * Una palabra → un significado → un sitio de cálculo.
 * No inventar «Preparada» / «Datos» / «Prioridad» con otra semántica en superficies nuevas.
 *
 * @see ADR-041 · Mercado cockpit phase · opportunity ranking
 */

/** Fase cockpit Mercado — única dueña de «Preparada». */
export const PRODUCT_PHASE_PREPARADA = "Preparada" as const;
export const PRODUCT_PHASE_BLOQUEADA = "Bloqueada" as const;
export const PRODUCT_PHASE_CADUCADA = "Caducada" as const;
export const PRODUCT_PHASE_DISPARADA = "Disparada" as const;

/**
 * Resultado de ranking (≠ fase cockpit).
 * No usar «PREPARADA» aquí: colisiona con resolveMercadoCockpitPhase.
 */
export const RANKING_RESULT_ENCAJA = "Encaja" as const;
export const RANKING_RESULT_VIGILABLE = "Vigilable" as const;
export const RANKING_RESULT_BLOQUEADA = "Bloqueada" as const;

/** Eje de score honesto: quality alone ≠ «Prioridad» compuesta. */
export const QUALITY_SCORE_PREFIX = "Calidad" as const;

/** Frescura del barrido Estudio (48h) — no confundir con OHLCV/DS-05 «Datos». */
export const SCAN_FRESHNESS_PREFIX = "Barrido" as const;

/** Frescura de barras OHLCV / DS-05 (cabecera operativa). */
export const MARKET_DATA_FRESHNESS_PREFIX = "Datos" as const;

export const PRODUCT_VOCABULARY = {
  phasePreparada: PRODUCT_PHASE_PREPARADA,
  phaseBloqueada: PRODUCT_PHASE_BLOQUEADA,
  phaseCaducada: PRODUCT_PHASE_CADUCADA,
  phaseDisparada: PRODUCT_PHASE_DISPARADA,
  rankingEncaja: RANKING_RESULT_ENCAJA,
  rankingVigilable: RANKING_RESULT_VIGILABLE,
  rankingBloqueada: RANKING_RESULT_BLOQUEADA,
  qualityScorePrefix: QUALITY_SCORE_PREFIX,
  scanFreshnessPrefix: SCAN_FRESHNESS_PREFIX,
  marketDataFreshnessPrefix: MARKET_DATA_FRESHNESS_PREFIX,
} as const;
