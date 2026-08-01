/**
 * CORE-R v1.5–v1.8 — chip barra + toast + claves estables para zustand.
 *
 * Solo lectura: no encola aquí, no pisa TOP, no auto-paper D.
 *
 * @see stores/core-r-review-queue-store.ts
 * @see docs/engineering/list-auto-ops-2026-07-29.md § CORE-R
 */

export type OpenHelpBacktestingOpts = {
  /** Scroll al Monitor Finalistas (cola CORE-R) en Ayuda → Backtesting. */
  panel?: 'monitor';
};

/** Abre Ayuda → Backtesting (escuchado por AppHelpMenu). */
export function openHelpBacktesting(opts?: OpenHelpBacktestingOpts): void {
  window.dispatchEvent(
    new CustomEvent('bolsa:open-help', {
      detail: { section: 'backtesting', panel: opts?.panel },
    }),
  );
}

/** Texto del chip; `null` si no hay cola abierta. */
export function formatCoreRStatusChip(openCount: number): string | null {
  const n = Math.max(0, Math.floor(Number(openCount) || 0));
  if (n <= 0) return null;
  return n === 1 ? 'CORE-R 1' : `CORE-R ${n}`;
}

/** Tooltip con símbolos abiertos (máx. 4). */
export function formatCoreRStatusTitle(
  openCount: number,
  symbols: ReadonlyArray<string>,
): string {
  const chip = formatCoreRStatusChip(openCount);
  if (!chip) return 'Sin cola CORE-R abierta';
  const uniq = [...new Set(symbols.map((s) => s.trim()).filter(Boolean))];
  const preview = uniq.slice(0, 4).join(', ');
  const more = uniq.length > 4 ? ` +${uniq.length - 4}` : '';
  const list = preview ? ` · ${preview}${more}` : '';
  return `${chip} a revisar${list}\nClic → Ayuda · Monitor (cola)`;
}

/**
 * Clave estable de símbolos open (para selectores zustand).
 * No devolver arrays desde el selector — provoca Maximum update depth.
 */
export function formatCoreROpenSymbolsKey(
  items: ReadonlyArray<{ status: string; symbol: string }>,
): string {
  return items
    .filter((i) => i.status === 'open')
    .map((i) => i.symbol.trim())
    .filter(Boolean)
    .join('\u0001');
}

/**
 * Toast tras tick cron que añade filas a la cola.
 * `null` si no hubo altas (evitar ruido).
 */
export function formatCoreREnqueueToast(added: number): string | null {
  const n = Math.max(0, Math.floor(Number(added) || 0));
  if (n <= 0) return null;
  if (n === 1) return 'CORE-R · 1 valor encolado · revisa Monitor / chip barra';
  return `CORE-R · ${n} valores encolados · revisa Monitor / chip barra`;
}
