/**
 * IDs de listas virtuales del panel Watchlist (no persistidas en API).
 *
 * `VIRTUAL_LIST_VISUALIZATION` («Estudio») = universo operativo TRADING (membresía explícita).
 * Abrir gráfico añade; cerrar pestaña no quita. SEMI/AUTO exigen pertenencia.
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */
export const VIRTUAL_LIST_PORTFOLIO = '__builtin:portfolio__' as const;
export const VIRTUAL_LIST_PENDING_ORDERS = '__builtin:pending-orders__' as const;
/** Lista «Estudio» (id legacy `visualization`). */
export const VIRTUAL_LIST_VISUALIZATION = '__builtin:visualization__' as const;

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
  [VIRTUAL_LIST_PORTFOLIO]: 'Cartera',
  [VIRTUAL_LIST_PENDING_ORDERS]: 'Órdenes pendientes',
  [VIRTUAL_LIST_VISUALIZATION]: 'Estudio',
};

/** ID estable de la lista de catálogo IBEX 35 en API (coincide con `DEFAULT_LIST_CONFIG.id`). */
export const CATALOG_IBEX_LIST_ID = 'ibex35';

/** Carrusel por defecto: Cartera + Órdenes pendientes + Estudio (IBEX se añade al cargar catálogo API). */
export const DEFAULT_VIRTUAL_CAROUSEL_IDS: readonly VirtualListId[] = [
  VIRTUAL_LIST_PORTFOLIO,
  VIRTUAL_LIST_PENDING_ORDERS,
  VIRTUAL_LIST_VISUALIZATION,
];

export function isVirtualListId(id: string): id is VirtualListId {
  return (VIRTUAL_LIST_IDS as readonly string[]).includes(id);
}

/** Evita chip duplicado si hay una lista API llamada igual que la virtual Estudio. */
export function isEstudioListNameCollision(name: string): boolean {
  const n = name.trim().toLowerCase();
  return n === 'estudio' || n === 'en estudio';
}
