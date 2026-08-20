/**
 * IDs de listas virtuales del panel Watchlist y lista API canónica «Estudio».
 *
 * - `VIRTUAL_LIST_VISUALIZATION` («Visualizados») = espejo de pestañas abiertas (local).
 * - `ESTUDIO_LIST_ID` («Estudio») = universo supervisable API (ADR-024).
 * Abrir gráfico → Visualizados; NO añade a Estudio. Foco UI: Cartera → Estudio → resto.
 *
 * @see docs/adr/024-estudio-supervision-universe.md
 * @see docs/engineering/visualizados-list-ux-2026-08-06.md
 * @see docs/engineering/estudio-supervision-model-2026-08-06.md
 */
export const VIRTUAL_LIST_PORTFOLIO = "__builtin:portfolio__" as const;
export const VIRTUAL_LIST_PENDING_ORDERS =
  "__builtin:pending-orders__" as const;
/** Lista virtual «Visualizados» (pestañas abiertas / buscador). No es Estudio. */
export const VIRTUAL_LIST_VISUALIZATION = "__builtin:visualization__" as const;

export type VirtualListId =
  | typeof VIRTUAL_LIST_PORTFOLIO
  | typeof VIRTUAL_LIST_PENDING_ORDERS
  | typeof VIRTUAL_LIST_VISUALIZATION;

export const VIRTUAL_LIST_IDS: readonly VirtualListId[] = [
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_VISUALIZATION,
];

export const VIRTUAL_LIST_LABELS: Record<VirtualListId, string> = {
  [VIRTUAL_LIST_PORTFOLIO]: "Cartera",
  [VIRTUAL_LIST_PENDING_ORDERS]: "Órdenes pendientes",
  [VIRTUAL_LIST_VISUALIZATION]: "Visualizados",
};

/** ID estable de la lista de catálogo IBEX 35 en API (coincide con `DEFAULT_LIST_CONFIG.id`). */
export const CATALOG_IBEX_LIST_ID = "ibex35";

/** Lista API canónica de supervisión (ADR-024). */
export const ESTUDIO_LIST_ID = "estudio";
export const ESTUDIO_LIST_NAME = "Estudio";

/** Carrusel por defecto: Cartera + Órdenes + Visualizados (Estudio/IBEX se pinan desde API). */
export const DEFAULT_VIRTUAL_CAROUSEL_IDS: readonly VirtualListId[] = [
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_VISUALIZATION,
];

export function isVirtualListId(id: string): id is VirtualListId {
  return (VIRTUAL_LIST_IDS as readonly string[]).includes(id);
}

export function isEstudioListId(id: string): boolean {
  return id === ESTUDIO_LIST_ID;
}

/** Match case-insensitive del nombre canónico «Estudio». */
export function isEstudioListName(name: string): boolean {
  const n = name.trim().toLowerCase();
  return n === "estudio" || n === "en estudio";
}

/**
 * Evita chip duplicado en carrusel: oculta listas API llamadas «Estudio»
 * (la UI de watchlist usa el chip virtual; Lab/CORE-R resuelven `ESTUDIO_LIST_ID`).
 */
export function isEstudioListNameCollision(name: string): boolean {
  return isEstudioListName(name);
}

/**
 * @deprecated ADR-024 — usar {@link ESTUDIO_LIST_NAME} / {@link resolveEstudioListId}.
 * Se mantiene para migración / tests legacy.
 */
export const ESTUDIO_PERSONAL_LIST_NAME = "Estudio personal";

/** @deprecated ADR-024 */
export function isEstudioPersonalListName(name: string): boolean {
  return name.trim().toLowerCase() === ESTUDIO_PERSONAL_LIST_NAME.toLowerCase();
}

/**
 * Resuelve el id de la lista API «Estudio» (canónica).
 * Preferencia: id estable → nombre «Estudio» → legacy «Estudio personal».
 */
export function resolveEstudioListId(
  lists: ReadonlyArray<{ id: string; name: string }>,
): string | null {
  const byId = lists.find((l) => l.id === ESTUDIO_LIST_ID);
  if (byId) return byId.id;
  const byName = lists.find((l) => isEstudioListName(l.name));
  if (byName) return byName.id;
  const personal = lists.find((l) => isEstudioPersonalListName(l.name));
  return personal?.id ?? null;
}
