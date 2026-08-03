/**
 * DTOs SEMI Confirm F3 queue multi-dispositivo — espejo API camelCase.
 */

export type SupervisedF3BundleDto = {
  accountId: string;
  items: Array<Record<string, unknown>>;
  activeId?: string | null;
  updatedAt?: string | null;
};
