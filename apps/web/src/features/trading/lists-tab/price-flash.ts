/**
 * Flash tick V1.31.2 — dirección breve al cambiar last price (listas).
 */

export type PriceFlashDirection = "up" | "down";

export const PRICE_FLASH_MS = 450;

/** Compara precio anterior vs nuevo. Igual / null / no-finito → null. */
export function resolvePriceFlashDirection(
  previous: number | null | undefined,
  next: number | null | undefined,
): PriceFlashDirection | null {
  if (
    previous == null ||
    next == null ||
    !Number.isFinite(previous) ||
    !Number.isFinite(next)
  ) {
    return null;
  }
  if (next > previous) return "up";
  if (next < previous) return "down";
  return null;
}

export function priceFlashClassName(
  direction: PriceFlashDirection | null,
): string | undefined {
  if (direction === "up") return "bolsa-price-flash-up";
  if (direction === "down") return "bolsa-price-flash-down";
  return undefined;
}
