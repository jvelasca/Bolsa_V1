/**
 * Deep-links Mesa → Journal / Confirm (ADR-037 P4).
 */

export function mesaJournalTesisHref(
  instrumentId: string,
  options?: { ficha?: boolean },
): string {
  const params = new URLSearchParams({
    tab: "tesis",
    instrument: instrumentId,
  });
  if (options?.ficha) params.set("ficha", "1");
  return `/decision-journal?${params.toString()}`;
}

export function mesaJournalEvolutionHref(instrumentId: string): string {
  const params = new URLSearchParams({
    tab: "evolucion",
    instrument: instrumentId,
  });
  return `/decision-journal?${params.toString()}`;
}

export function mesaOperationsHref(): string {
  return "/operations";
}

export function mesaOperationalConsoleHref(): string {
  return "/operational-console";
}
