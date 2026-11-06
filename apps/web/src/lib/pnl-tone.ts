/**
 * P2-01 (`UI5-14`, `UNKNOWN ≠ 0`) — el color de un P&L solo se afirma si está medido.
 *
 * `(unrealizedPnl ?? 0) >= 0` colapsa dos estados distintos en verde: el P&L
 * **medido y no negativo** y el P&L **no medido** (`null`, porque la posición no
 * tiene mark observable). El texto ya declara el hueco (`formatPriceOrAbsent`),
 * pero el color decía «positivo», que es la lectura dominante en una tabla de
 * dinero. Un `null` y un `0,00 €` real tampoco son lo mismo: el segundo es una
 * medición plana, no una ganancia.
 *
 * El tono es **color, no aritmética**: el importe conserva su signo y su
 * formateo (`formatPriceOrAbsent`). Este helper es puro y sin React para que
 * cada superficie ancle su propia prueba de render.
 *
 * @see apps/web/src/components/absent-data.ts (vocabulario de ausencia)
 * @see docs/engineering/auditoria-ui-operativa-profunda-2026-10-28.md §4.1 / §7 I-03
 */

/** Tono visual de un P&L de primer nivel. */
export type PnlTone = "positive" | "negative" | "neutral";

/**
 * Resuelve el tono del P&L. Un valor ausente, no finito o **exactamente cero**
 * es `neutral`: no se afirma ni ganancia ni pérdida.
 */
export function pnlTone(value: number | null | undefined): PnlTone {
  if (value == null || !Number.isFinite(value) || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

/**
 * Clases del tono para el primer nivel. `neutral` usa el color de primer plano
 * apagado: un hueco o un cero medido no se disfraza de ganancia.
 */
export const PNL_TONE_CLASS: Record<PnlTone, string> = {
  positive: "text-emerald-700 dark:text-emerald-300",
  negative: "text-rose-700 dark:text-rose-300",
  neutral: "text-muted-foreground",
};
