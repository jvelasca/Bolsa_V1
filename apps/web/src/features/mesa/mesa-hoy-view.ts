/**
 * Vistas de Hoy (`?view=`) + compat `?focus=` (ADR-040).
 *
 * V1.41 — Daily Desk: inbox único por attention. Detalles detrás de
 * «Ver detalles» o deep-link `?view=` (no segundo Mercado).
 */

import {
  HOY_VIEW,
  OPERATIONAL_CONSOLE_PATH,
  hoyViewHref,
  type HoyView,
} from "@/features/confirm/daily-nav";

const VALID: ReadonlySet<string> = new Set(Object.values(HOY_VIEW));

/**
 * Resuelve la vista activa.
 * Compat V1.19: focus=spine → decisiones; focus=libro → posiciones.
 * `view=confirmar` (V1.22) cae en resumen: la firma vive en `/confirm`.
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

/** V1.41 — chrome de Hoy = un solo inbox por attention (sin paneles L2). */
export const HOY_INBOX_BLOCKS = [
  { id: "requiere-atencion", title: "Requiere atención" },
] as const;

export type HoyInboxBlockId = (typeof HOY_INBOX_BLOCKS)[number]["id"];

/** Menú «Ver detalles» — no son puertas L1 ni pestañas. */
export const HOY_DETAIL_ITEMS: ReadonlyArray<{
  id: string;
  label: string;
  href: string;
  hint: string;
}> = [
  {
    id: "oportunidades",
    label: "Oportunidades",
    href: hoyViewHref(HOY_VIEW.oportunidades),
    hint: "Ranking Estudio — no es una orden",
  },
  {
    id: "decisiones",
    label: "Decisiones",
    href: hoyViewHref(HOY_VIEW.decisiones),
    hint: "Sesiones, gates y vetos",
  },
  {
    id: "journal",
    label: "Journal",
    href: hoyViewHref(HOY_VIEW.journal),
    hint: "Tesis, evolución e historial",
  },
  {
    id: "posiciones",
    label: "Libro / Posiciones",
    href: hoyViewHref(HOY_VIEW.posiciones),
    hint: "Posiciones abiertas y órdenes",
  },
  {
    id: "consola",
    label: "Consola",
    href: OPERATIONAL_CONSOLE_PATH,
    hint: "Salud operativa, recon e incidentes",
  },
];
