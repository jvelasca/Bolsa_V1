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
  strategyStars?: number | null;
  ioScore?: number | null;
  faScore?: number | null;
  taScore?: number | null;
  distress: boolean;
  reasons?: InstrumentDailyOpinionReasonCode[];
  gateStatus?: "PASS" | "VETO" | "WARNING" | null;
  topId?: string | null;
  topVersion?: number | null;
  source: InstrumentDailyOpinionSource;
  engineVersion: string;
  idempotencyKey: string;
  computedAt: string;
  createdAt: string;
  updatedAt: string;
};

/** Hint opcional del cliente (hub ya tiene FA/IO/posición). */
export type InstrumentDailyOpinionHintV1 = {
  instrumentId: string;
  ioScore?: number | null;
  faScore?: number | null;
  taScore?: number | null;
  distress?: boolean;
  positionOpen?: boolean;
  /** Gate allowTrading; false = VETO → no_trade. */
  allowTrading?: boolean;
  /** Si se omite, el servidor consulta última vela EOD (fail-closed). */
  hasEodBar?: boolean;
};

export type QueryInstrumentDailyOpinionsRequestV1 = {
  instrumentIds: string[];
  asOfBarDate?: string | null;
  accountId?: string | null;
  /** Si true, recalcula aunque exista caché del día. */
  forceRefresh?: boolean;
  hints?: InstrumentDailyOpinionHintV1[];
};

export const INSTRUMENT_DAILY_OPINION_STANCE_LABELS: Record<
  InstrumentDailyOpinionStance,
  string
> = {
  buy: "Comprar",
  hold_watch: "Vigilar",
  overbought: "Sobrecomprado",
  reduce: "Reducir",
  sell_exit: "Vender",
  no_trade: "Sin operar",
  review_strategy: "Revisar estrategia",
};
