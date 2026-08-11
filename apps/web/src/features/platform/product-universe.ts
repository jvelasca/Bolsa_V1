/**
 * Universos de producto LAB vs TRADING (ADR-019).
 *
 * @see docs/adr/019-dual-universes-lab-vs-trading.md
 * @see docs/engineering/dual-universes-lab-trading-design-2026-08-02.md
 */

export type ProductUniverse = "lab" | "trading";

export const PRODUCT_UNIVERSE_LABEL: Record<ProductUniverse, string> = {
  lab: "LAB",
  trading: "TRADING",
};

export const PRODUCT_UNIVERSE_SUBLABEL: Record<ProductUniverse, string> = {
  lab: "simulación",
  trading: "DEMO",
};

export function productUniverseFromPath(
  pathname: string,
): ProductUniverse | null {
  if (pathname.startsWith("/backtests")) return "lab";
  if (pathname.startsWith("/trading") || pathname === "/") return "trading";
  return null;
}

/** CTA canónico verificación D→hoy (antes «Simular D→hoy»). */
export const VERIFY_DIA_D_CTA = "Verificar D→hoy" as const;

export function diaDVerifyHref(instrumentId: string): string {
  const q = new URLSearchParams({
    tab: "run",
    instrumentId,
    focus: "detail",
    verify: "1",
  });
  return `/backtests?${q.toString()}`;
}
