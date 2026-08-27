/**
 * Vistas de Hoy (`?view=`) + compat `?focus=` (ADR-040).
 *
 * V1.23 Fase 4 — Hoy es un inbox de cuatro bloques. Las vistas de detalle ya
 * no son pestañas de chrome: se abren desde «Ver detalles» o por deep-link.
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

/** Bloques del inbox (orden de lectura garantizado). */
export const HOY_INBOX_BLOCKS = [
  { id: "requiere-accion", title: "Requiere acción" },
  { id: "oportunidades", title: "Oportunidades" },
  { id: "vigilar", title: "Vigilar" },
  { id: "sin-accion", title: "Sin acción" },
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
