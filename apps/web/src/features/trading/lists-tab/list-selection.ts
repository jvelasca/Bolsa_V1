/**
 * Selección multi-fila estilo Windows (columna de checks):
 * - Clic en check → marca/desmarca esa fila (estado explícito del input).
 * - Ctrl/Cmd + Mayús → rango sumado; Mayús → rango sustitutivo.
 * - Ctrl no es necesario para sumar dos checks sueltos: cada check mantiene el resto.
 */

export type ListSelectModifiers = {
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
};

export function applyInstrumentSelection(opts: {
  prev: Set<string>;
  instrumentId: string;
  index: number;
  orderedIds: string[];
  modifiers: ListSelectModifiers;
  anchorIndex: number | null;
  /** Valor `checked` del input (onChange). Permite despulsar con claridad. */
  checked: boolean;
}): { next: Set<string>; anchorIndex: number } {
  const { prev, instrumentId, index, orderedIds, modifiers, checked } = opts;
  const additive = Boolean(modifiers.ctrlKey || modifiers.metaKey);
  const range = Boolean(modifiers.shiftKey);

  if (range && opts.anchorIndex != null && orderedIds.length > 0) {
    const from = Math.min(opts.anchorIndex, index);
    const to = Math.max(opts.anchorIndex, index);
    const slice = orderedIds.slice(from, to + 1);
    if (additive) {
      const next = new Set(prev);
      for (const id of slice) next.add(id);
      return { next, anchorIndex: opts.anchorIndex };
    }
    return { next: new Set(slice), anchorIndex: opts.anchorIndex };
  }

  const next = new Set(prev);
  if (checked) next.add(instrumentId);
  else next.delete(instrumentId);
  return { next, anchorIndex: index };
}
