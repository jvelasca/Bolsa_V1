/**
 * Desplaza el contenedor de la lista para que el valor quede arriba del viewport,
 * sin cambiar el orden de las filas. Respeta la cabecera sticky de columnas.
 */

export function stickyListHeaderOffset(container: HTMLElement): number {
  const sticky = container.querySelector('.sticky.top-0') as HTMLElement | null;
  if (!sticky) return 0;
  return sticky.getBoundingClientRect().height;
}

export function scrollListInstrumentToTop(
  container: HTMLElement | null | undefined,
  instrumentId: string | null | undefined,
  options?: { behavior?: ScrollBehavior; topOffset?: number },
): boolean {
  if (!container || !instrumentId) return false;
  const row = container.querySelector(
    `[data-instrument-id="${CSS.escape(instrumentId)}"]`,
  ) as HTMLElement | null;
  if (!row) return false;

  const topOffset = options?.topOffset ?? stickyListHeaderOffset(container);
  const cRect = container.getBoundingClientRect();
  const eRect = row.getBoundingClientRect();
  // Alinear bajo la cabecera sticky (si no, la fila queda oculta una posición arriba).
  const nextTop = container.scrollTop + (eRect.top - cRect.top) - topOffset;
  container.scrollTo({
    top: Math.max(0, nextTop),
    behavior: options?.behavior ?? 'smooth',
  });
  return true;
}
