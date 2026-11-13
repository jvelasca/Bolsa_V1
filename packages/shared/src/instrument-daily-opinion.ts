/**
 * Dictamen diario por instrumento (O3-C / ADR-022).
 * Artefacto de producto: stance + ★ dictamen (≠ ★ estrategia TOP).
 */

export const INSTRUMENT_DAILY_OPINION_STANCES = [
  "buy",
  "hold_watch",
  "overbought",
  "reduce",
  "sell_exit",
  "no_trade",
  "review_strategy",
] as const;

export type InstrumentDailyOpinionStance =
  (typeof INSTRUMENT_DAILY_OPINION_STANCES)[number];

export const INSTRUMENT_DAILY_OPINION_SOURCES = [
  "on_demand",
  "eod_batch",
  "manual",
] as const;

export type InstrumentDailyOpinionSource =
  (typeof INSTRUMENT_DAILY_OPINION_SOURCES)[number];

export const INSTRUMENT_DAILY_OPINION_REASON_CODES = [
  "gate_veto",
  "stale_top",
  "no_valid_top",
  "fa_distress",
  "eod_data_stale",
  "strong_buy_signal",
  "neutral_no_position",
  "overbought_or_exit",
  "holding_position",
  "top_high",
  "top_medium",
  "top_low",
  "io_high",
  "io_low",
  "io_medium",
  "position_open",
  "position_closed",
  // La cartera NO se midió: postura fail-closed, no «sin posición».
  "position_unmeasured",
  // IO sin medición: 3★ declaradas, no inventadas.
  "io_unmeasured",
] as const;

export type InstrumentDailyOpinionReasonCode =
  (typeof INSTRUMENT_DAILY_OPINION_REASON_CODES)[number];

export const INSTRUMENT_DAILY_OPINION_ENGINE_VERSION = "opinion_v1" as const;

/** Días sin actualizar TOP → review_strategy. */
export const INSTRUMENT_DAILY_OPINION_TOP_STALE_DAYS = 30;

export type InstrumentDailyOpinionV1 = {
  id: string;
  instrumentId: string;
  accountId?: string | null;
  asOfBarDate: string;
  stance: InstrumentDailyOpinionStance;
  dictamenStars: number;
  /** ★ de la estrategia mejor puntuada (Finalistas) — referencia, no la ejecutada. */
  strategyStars?: number | null;
  ioScore?: number | null;
  faScore?: number | null;
  taScore?: number | null;
  distress: boolean;
  reasons?: InstrumentDailyOpinionReasonCode[];
  gateStatus?: "PASS" | "VETO" | "WARNING" | null;
  /**
   * Referencia «mejor puntuada (Finalistas)» del TOP Lab: id de la estrategia
   * mejor puntuada. NO es la estrategia ejecutada: la identidad ejecutada se
   * sella por ciclo (`portfolio_reservations` / `sim_*` / `dia_d_cycle_verifications`).
   */
  topId?: string | null;
  /** Versión de la referencia «mejor puntuada (Finalistas)»; no implica ejecución. */
  topVersion?: number | null;
  source: InstrumentDailyOpinionSource;
  engineVersion: string;
  idempotencyKey: string;
  computedAt: string;
  createdAt: string;
  updatedAt: string;
};

/**
 * @deprecated El servidor MIDE la postura (posiciones de la cuenta) y los scores
 * (chips composite/FA); `POST /instrument-daily-opinions/query` ignora `hints`.
 * Se conserva el tipo solo por compatibilidad de contrato.
 */
export type InstrumentDailyOpinionHintV1 = {
  instrumentId: string;
  ioScore?: number | null;
  faScore?: number | null;
  taScore?: number | null;
  distress?: boolean;
  /**
   * TRI-ESTADO (C-1): `true`/`false` solo si la cartera se MIDIÓ; `null`/ausente = no
   * medida (el servidor falla cerrado con `position_unmeasured`). Enviar `false` sin
   * haber leído la cartera afirma «sin posición» y puede producir un dictamen de compra
   * sobre un valor que sí se tiene.
   *
   * @deprecated Ignorado por el servidor.
   */
  positionOpen?: boolean | null;
  /** Gate allowTrading; false = VETO → no_trade. @deprecated Ignorado. */
  allowTrading?: boolean;
  /** Si se omite, el servidor consulta última vela EOD (fail-closed). @deprecated */
  hasEodBar?: boolean;
};

export type QueryInstrumentDailyOpinionsRequestV1 = {
  instrumentIds: string[];
  asOfBarDate?: string | null;
  /** Scope de la caché y de la medición de posición. Sin él no hay dictamen cacheable. */
  accountId?: string | null;
  /** Si true, recalcula aunque exista caché del día. */
  forceRefresh?: boolean;
  /**
   * @deprecated IGNORADO por el servidor. La postura y los scores se miden en servidor.
   */
  hints?: InstrumentDailyOpinionHintV1[];
};

/**
 * Denominación visible de las 7 posturas. Se reexporta del glosario canónico
 * (`market-vocabulary.ts`) para que exista UNA sola tabla: la clave sigue siendo
 * el código del motor y solo cambia el nombre que ve el usuario.
 */
export { INSTRUMENT_DAILY_OPINION_STANCE_LABELS } from "./market-vocabulary.js";
