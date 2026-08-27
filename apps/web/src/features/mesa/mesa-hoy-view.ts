/**
 * Vistas de Hoy (`?view=`) + compat `?focus=` (ADR-040).
 */

import { HOY_VIEW, type HoyView } from "@/features/confirm/daily-nav";

const VALID: ReadonlySet<string> = new Set(Object.values(HOY_VIEW));

/**
 * Resuelve la vista activa.
 * Compat V1.19: focus=spine → decisiones; focus=libro → posiciones.
 */
export function parseHoyView(
  viewRaw: string | null,
  focusRaw: string | null,
): HoyView {
  if (viewRaw && VALID.has(viewRaw)) return viewRaw as HoyView;
  if (focusRaw === "spine") return HOY_VIEW.decisiones;
  if (focusRaw === "libro" || focusRaw === "ordenes" || focusRaw === "riesgo") {
    return HOY_VIEW.posiciones;
  }
  return HOY_VIEW.resumen;
}

export const HOY_VIEW_TABS: ReadonlyArray<{
  id: HoyView;
  label: string;
}> = [
  { id: HOY_VIEW.resumen, label: "Resumen" },
  { id: HOY_VIEW.posiciones, label: "Posiciones" },
  { id: HOY_VIEW.oportunidades, label: "Oportunidades" },
  { id: HOY_VIEW.decisiones, label: "Decisiones" },
  { id: HOY_VIEW.confirmar, label: "Confirmar" },
  { id: HOY_VIEW.journal, label: "Journal" },
];
