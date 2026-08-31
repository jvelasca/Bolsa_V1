/**
 * Resumen operativo diario (R1) — contrato compartido API ↔ web.
 *
 * @see docs/engineering/daily-ops-report-brief-2026-08-04.md
 */

import type { AccountSummaryDto, LedgerEntryDto } from "./accounts.js";
import type { PaperDailyReportV1 } from "./cognitive/paper-daily-report.js";
import type { InstrumentDailyOpinionV1 } from "./instrument-daily-opinion.js";
import type { OpinionChannelLevel } from "./opinion-channel-map.js";

export const DAILY_OPS_REPORT_SCHEMA = "daily_ops_report_v1" as const;

/** Membresía Estudio resuelta: ok | empty | unavailable (infra ≠ 0 candidatos). */
export type EstudioUniverseStatusV1 = "ok" | "empty" | "unavailable";

export type DailyOpsWeekDayV1 = {
  /** YYYY-MM-DD */
  date: string;
  tradeCount: number;
  ledgerCount: number;
  /** Último balanceAfter del día si hay ledger; null si no hubo movimiento. */
  balanceAfter: number | null;
  netAmount: number;
};

export type DailyOpsChannelSummaryV1 = {
  alarma: number;
  aviso: number;
  none: number;
};

export type DailyOpsOpinionRowV1 = {
  instrumentId: string;
  symbol?: string | null;
  channel: OpinionChannelLevel;
  stance: string;
  dictamenStars: number;
  reasons: string[];
};

export type DailyOpsReportV1 = {
  schemaVersion: typeof DAILY_OPS_REPORT_SCHEMA;
  asOf: string;
  generatedAt: string;
  accountId: string;
  summary: AccountSummaryDto;
  /** Ledger del día asOf (todos los tipos). */
  ledgerToday: LedgerEntryDto[];
  /** Subconjunto buy/sell del día. */
  tradesToday: LedgerEntryDto[];
  week: DailyOpsWeekDayV1[];
  f3PendingCount: number;
  channels: DailyOpsChannelSummaryV1;
  opinions: DailyOpsOpinionRowV1[];
  /** Opiniones crudas opcionales (debug / reuso). */
  opinionDetails?: InstrumentDailyOpinionV1[];
  notes: string[];
  /**
   * Estado del universo Estudio.
   * unavailable ≠ empty: no interpretar fallo de infra como «0 oportunidades».
   */
  estudioStatus: EstudioUniverseStatusV1;
  /** Tamaño de membresía Estudio (antes del filtro). */
  estudioCount: number;
  /**
   * V1.46 — proyección opcional del PaperDeskCycle (AUTO mesa).
   * Ausente = informe diario clásico; no rompe consumidores.
   */
  autoDesk?: PaperDailyReportV1;
};

export type DailyOpsReportResponseV1 = {
  data: DailyOpsReportV1;
};
