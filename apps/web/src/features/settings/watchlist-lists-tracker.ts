/**
 * Tracker Ayuda → Watchlist (Listas / Valores / Índices).
 *
 * @see docs/WORKSPACE_PERSISTENCE.md
 * @see docs/engineering/lists-universes-design-2026-07-30.md
 */

import { HELP_CONTENT_AS_OF } from '@/features/help/help-content-as-of';

export const WATCHLIST_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  persistenceDoc: 'docs/WORKSPACE_PERSISTENCE.md',
  listsDesignDoc: 'docs/engineering/lists-universes-design-2026-07-30.md',
} as const;

export const WATCHLIST_SUMMARY = {
  title: 'En pocas palabras',
  body:
    'El panel izquierdo de la watchlist tiene dos vistas: Listas (gestión) y Valores (contenido + carrusel). Hay dos familias claras: listas personales (tú editas) e índices de mercado (IBEX, S&P… sincronizados). Comparten la misma lista activa y el carrusel del espacio.',
  bullets: [
    'Listas — secciones Sistema / Índices / Personales; crear, fijar al carrusel, congelar copia desde un índice.',
    'Índices — catálogo + búsqueda; Suscribir importa constitutivos (misma tubería A→B→C para todos).',
    'Valores — tickers de la lista activa; carrusel y menú ⋯; quitar de lista ≠ borrar de BD.',
    'Atajos al expandir — Rastreadores / Alertas / Backtesting (con ?listId=).',
  ],
} as const;

export const WATCHLIST_LISTS_UI = [
  {
    id: 'families',
    title: 'Familias Sistema / Índices / Personales',
    body: 'El hub agrupa filas en tres bloques. Índices = source catalog / linked_universe. Personales = custom y copias (snapshot). Sistema = cartera, pendientes, visualización.',
  },
  {
    id: 'select',
    title: 'Clic en el nombre de la lista',
    body: 'Selecciona la lista y pasa a Valores. El ✓ marca la activa. Bajo el nombre de un índice aparece «Últ. sync» si hay lastSyncedAt.',
  },
  {
    id: 'subscribe',
    title: 'Suscribir / Sync índice',
    body: 'Buscador o chips del catálogo (IBEX, SPX, OEX, DAX, NDX, DJI, FTSE…). Suscribir materializa constitutivos e importa faltantes. Leave = solo desvincula; el Instrument permanece.',
  },
  {
    id: 'freeze',
    title: 'Congelar copia',
    body: 'Icono copiar en un índice → lista personal snapshot editable. El índice sigue vivo y sincronizable.',
  },
  {
    id: 'carousel-check',
    title: 'Checkbox «Carrusel»',
    body: 'Añade o quita la lista del carrusel de Valores (mismo origen que el menú ⋯).',
  },
  {
    id: 'membership',
    title: 'Checkbox junto al valor del gráfico',
    body: 'Solo lectura: el ticker del gráfico activo ¿está en esta lista? Indeterminado mientras carga.',
  },
  {
    id: 'expand',
    title: 'Chevron expandir',
    body: 'Atajos: Rastreadores, Alertas y Backtesting (?listId=). El contenido se ve en Valores.',
  },
] as const;

export const WATCHLIST_VALUES_UI = [
  {
    id: 'carousel',
    title: 'Carrusel',
    body: 'Chips de listas fijadas + virtuales. Clic = lista activa. Menú ⋯ = pin/unpin.',
  },
  {
    id: 'visualization',
    title: 'Lista Visualización',
    body: 'Espejo de pestañas de gráfico abiertas. Nombre real; «visto N×» es metadato de sesión.',
  },
  {
    id: 'one-tab',
    title: 'Una pestaña por valor',
    body: 'Aunque el ticker esté en varias listas, solo hay una pestaña de gráfico.',
  },
  {
    id: 'remove-closes-chart',
    title: 'Quitar de lista cierra el gráfico',
    body: 'Si desmarcas un valor con pestaña abierta, esa pestaña se cierra y sale de Visualización.',
  },
  {
    id: 'rows',
    title: 'Filas de valores',
    body: 'Abrir gráfico, info (i), pertenencia, sync. Expandir para cotización live.',
  },
  {
    id: 'remove-bd',
    title: 'Quitar de lista ≠ borrar de BD',
    body: 'Desmarcar solo quita membresía. Si era la última lista persistente, puedes dejarlo en BD o purgar (salvo posición/orden). Configuración → BD para mantenimiento.',
  },
] as const;

export const WATCHLIST_NEXT = [
  'Suscribe un índice (p. ej. S&P 100) y comprueba badge Últ. sync + familia Índices.',
  'Congela una copia y edítala sin afectar al índice.',
  'Desde el chevron, abre Backtesting con esa lista (?listId=) y mira el resumen por valor.',
  'En Listas, marca Carrusel y confirma el chip en Valores → ⋯.',
] as const;
