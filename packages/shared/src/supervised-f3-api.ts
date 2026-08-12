/**
 * DTOs SEMI Confirm F3 queue multi-dispositivo — espejo API camelCase.
 *
 * P2.8: el wire (blob opaco del BE) no cambia; declaramos la *forma concreta*
 * de cada item para que `supervised-f3-sync.ts` serialice sin `as unknown as`.
 * El `payload` se mantiene opaco porque su shape deriva de `RecommendationV1`
 * y grafos web-only (deuda P2.6 de un único hogar de tipos).
 */

export type SupervisedF3QueueItemDto = {
  id: string;
  enqueuedAt: string;
  scanId?: string;
  symbol?: string;
  origin?: string;
  payload: Record<string, unknown>;
};

export type SupervisedF3BundleDto = {
  accountId: string;
  items: Array<SupervisedF3QueueItemDto>;
  activeId?: string | null;
  updatedAt?: string | null;
};
