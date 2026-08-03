/**
 * ↑/↓ recorre la lista de valores (vertical) y abre el gráfico.
 * Evita que las flechas desplacen el eje temporal del chart (horizontal).
 */

import { useEffect } from 'react';

export type ListKeyboardNavItem = {
  id: string;
  symbol: string;
};

export function useListInstrumentKeyboardNav(
  items: ListKeyboardNavItem[],
  activeInstrumentId: string | undefined,
  onOpenChart: (instrumentId: string, symbol: string) => void,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled || items.length === 0) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      if (event.altKey || event.ctrlKey || event.metaKey) return;

      const target = event.target as HTMLElement | null;
      if (!target) return;
      const tag = target.tagName;
      if (
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        target.isContentEditable
      ) {
        return;
      }
      // Menús / diálogos con foco propio
      if (target.closest('[role="dialog"], [role="menu"], [role="listbox"]')) return;

      const index = activeInstrumentId
        ? items.findIndex((item) => item.id === activeInstrumentId)
        : -1;
      const delta = event.key === 'ArrowDown' ? 1 : -1;
      const nextIndex =
        index < 0
          ? event.key === 'ArrowDown'
            ? 0
            : items.length - 1
          : Math.min(items.length - 1, Math.max(0, index + delta));
      const next = items[nextIndex];
      if (!next || next.id === activeInstrumentId) {
        event.preventDefault();
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      onOpenChart(next.id, next.symbol);
      requestAnimationFrame(() => {
        document
          .querySelector(`[data-instrument-id="${CSS.escape(next.id)}"]`)
          ?.scrollIntoView({ block: 'nearest' });
      });
    }

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [items, activeInstrumentId, onOpenChart, enabled]);
}
