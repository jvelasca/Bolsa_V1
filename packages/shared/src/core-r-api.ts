/**
 * DTOs CORE-R multi-dispositivo (Q3.4) — espejo API camelCase.
 */

export type CoreRBundleDto = {
  accountId: string;
  queue: Array<Record<string, unknown>>;
  reports: Record<string, unknown>;
  scheduler: Record<string, unknown>;
  updatedAt?: string | null;
};
