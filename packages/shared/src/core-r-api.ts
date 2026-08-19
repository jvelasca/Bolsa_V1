/**
 * DTOs CORE-R multi-dispositivo (Q3.4) — espejo API camelCase.
 *
 * P2.8: el wire (blob opaco versionado del BE) no cambia; aquí declaramos la
 * *forma concreta* que el FE serializa/lee, para que `core-r-sync.ts` no
 * necesite `as unknown as`. Las formas son re-declaraciones de los tipos web;
 * el traslado a un único hogar de tipos (P2.6) se resuelve al importar aquí los
 * tipos ricos de `core-r-judgment`.
 */

import type {
  CoreRActionId,
  CoreRVerdict,
  FullCycleSettleReason,
  ListAutoChangeKind,
} from "./core-r-judgment.js";

/**
 * P2.6 (F-DEBT-2): los campos que representan verdict/actions se alinean al
 * tipo rico de `core-r-judgment`. D5: el wire es un blob opaco round-trip del
 * BE y este no garantiza los literales de la union, así que TODO campo
 * verdict/action mantiene `| string` de seguridad (que en unions de literales
 * de string colapsa a `string`); el tipo rico solo documenta la forma canónica.
 */
export type CoreRQueueItemDto = {
  id: string;
  listId: string;
  instrumentId: string;
  symbol: string;
  verdict: CoreRVerdict | string;
  reason: string;
  actions: Array<{
    id: CoreRActionId | string;
    label: string;
    href?: string;
  }>;
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
  verdict: CoreRVerdict | string;
  reason: string;
  actions: Array<{
    id: CoreRActionId | string;
    label: string;
    href?: string;
  }>;
  settleReason?: FullCycleSettleReason | string;
  change?: ListAutoChangeKind | string;
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
