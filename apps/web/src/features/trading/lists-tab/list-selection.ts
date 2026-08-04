/**
 * Selección multi-fila estilo Windows (Ctrl/Cmd toggle · Shift rango).
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
}): { next: Set<string>; anchorIndex: number } {
  const { prev, instrumentId, index, orderedIds, modifiers } = opts;
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

  if (additive) {
    const next = new Set(prev);
    if (next.has(instrumentId)) next.delete(instrumentId);
    else next.add(instrumentId);
    return { next, anchorIndex: index };
  }

  // Clic en check sin modificadores: toggle de esa fila (no limpia el resto).
  const next = new Set(prev);
  if (next.has(instrumentId)) next.delete(instrumentId);
  else next.add(instrumentId);
  return { next, anchorIndex: index };
}
