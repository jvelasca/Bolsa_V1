import { useEffect, useRef, useState } from "react";
import {
  PRICE_FLASH_MS,
  resolvePriceFlashDirection,
  type PriceFlashDirection,
} from "@/features/trading/lists-tab/price-flash";

/**
 * Devuelve `'up' | 'down' | null` ~PRICE_FLASH_MS tras un cambio de precio.
 * El primer valor no flashea (solo establece baseline).
 */
export function usePriceFlash(
  price: number | null | undefined,
): PriceFlashDirection | null {
  const prevRef = useRef<number | null | undefined>(undefined);
  const [flash, setFlash] = useState<PriceFlashDirection | null>(null);

  useEffect(() => {
    const previous = prevRef.current;
    prevRef.current = price;

    // Primer paint: baseline, sin flash.
    if (previous === undefined) return;

    const direction = resolvePriceFlashDirection(previous, price);
    if (!direction) return;

    setFlash(direction);
    const t = window.setTimeout(() => setFlash(null), PRICE_FLASH_MS);
    return () => window.clearTimeout(t);
  }, [price]);

  return flash;
}
