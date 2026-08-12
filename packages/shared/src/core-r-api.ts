/**
 * DTOs CORE-R multi-dispositivo (Q3.4) — espejo API camelCase.
 *
 * P2.8: el wire (blob opaco versionado del BE) no cambia; aquí declaramos la
 * *forma concreta* que el FE serializa/lee, para que `core-r-sync.ts` no
 * necesite `as unknown as`. Las formas son re-declaraciones de los tipos web;
 * el traslado a un único hogar de tipos queda como deuda P2.6.
 */

export type CoreRQueueItemDto = {
  id: string;
  listId: string;
  instrumentId: string;
  symbol: string;
  verdict: string;
  reason: string;
  actions: Array<{ id: string; label: string; href?: string }>;
  timeframe: string;
  enqueuedAt: string;
  status: string;
};

export type CoreRSchedulerPrefsDto = {
  enabled: boolean;
  intervalMinutes: number;
  lastTickAt: string | null;
  listId: string | null;
  scope: "monitor" | "shell";
  lastTickSource?: "shell" | "server_cron" | null;
  lastRemoteEnqueueAt?: string | null;
  lastRemoteEnqueueAdded?: number;
};

export type CoreRReportRowDto = {
  instrumentId: string;
  symbol: string;
  verdict: string;
  reason: string;
  actions: Array<{ id: string; label: string; href?: string }>;
  settleReason?: string;
  change?: string;
};

export type CoreRReportDto = {
  engine: string;
  listId: string;
  timeframe: string;
  at: string;
  rows: Array<CoreRReportRowDto>;
};

export type CoreRReportsMapDto = Record<string, CoreRReportDto>;

export type CoreRBundleDto = {
  accountId: string;
  queue: Array<CoreRQueueItemDto>;
  reports: CoreRReportsMapDto;
  scheduler: CoreRSchedulerPrefsDto;
  updatedAt?: string | null;
};
