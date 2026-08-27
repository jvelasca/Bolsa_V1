/**
 * Deep-links Hoy → Journal / Confirm / Decisiones / Cartera (ADR-037 + ADR-040).
 */

import { hoyViewHref, HOY_VIEW } from "@/features/confirm/daily-nav";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";

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
  return hoyViewHref(HOY_VIEW.posiciones);
}

export function mesaSpineHref(): string {
  return hoyViewHref(HOY_VIEW.decisiones);
}

export function mesaOperationalConsoleHref(): string {
  return "/operational-console";
}

export function mesaOportunidadesHref(): string {
  return hoyViewHref(HOY_VIEW.oportunidades);
}

/** V1.23 — la firma no es vista de Hoy: drawer + `/confirm`. */
export function mesaConfirmarHref(): string {
  return CONFIRM_PATH;
}

export function mesaJournalHref(): string {
  return hoyViewHref(HOY_VIEW.journal);
}
