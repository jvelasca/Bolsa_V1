# Visualizados + UX listas (2026-08-06)

Complemento ADR-024: scratch de pestañas, orden por IO, columnas de recomendación y foco al cambiar de gráfico.

## Modelo

| Lista | Rol |
|-------|-----|
| **Visualizados** (`__builtin:visualization__`) | Espejo de **pestañas de gráfico abiertas** (SoT = `workspace.charts`). Cerrar pestaña = sale. No es supervisión. |
| **Estudio** (`estudio` API) | Universo supervisable (membresía explícita). Abrir gráfico **no** añade. |
| **Cartera** / índices / personal | Igual que antes. |

Dump legacy `visualizationEntries` del workspace **no** se restaura como lista (evita 100+ = Estudio).

## Acciones en Visualizados (selección)

- **A Estudio** — pasa a supervisión.
- **Quitar** — cierra pestañas (un solo update; el autosave no reinyecta tabs).
- **Por IO** — ordena pestañas por Índice Operativo (0–100), mejor a la **izquierda**. Misma métrica que Operativa («El N de M en Estudio» = puesto; el factor es el IO).
- **Abrir gráficos** — solo en listas que no son Visualizados.
- Sort por cabecera de columna: reordena la tabla; en Visualizados también realinea pestañas (arriba = izq). Sin sort → orden de pestañas.

## Columnas opcionales (⋯)

Activables por lista: **IO · TA · FA · ★ Dict. · Postura**. Off por defecto. Fetch solo si están visibles.

## Foco al buscar / cambiar pestaña

1. Elegir lista con prioridad **Cartera → Estudio → resto** (`resolvePreferredListIdForInstrument`).
2. Scroll del valor al **tope del viewport** bajo la cabecera sticky (sin cambiar su orden en la lista).

## Código clave

- `apps/web/src/lib/chart-list-membership.ts` — prioridad de lista.
- `apps/web/src/lib/scroll-list-instrument-into-view.ts` — scroll + offset sticky.
- `apps/web/src/features/trading/lists-tab/use-chart-visualization-sync.ts` — reconcile Visualizados ↔ charts.
- `apps/web/src/features/trading/lists-tab/fetch-io-scores-for-sort.ts` — IO en trozos (no tumba API).
- `apps/web/src/features/trading/lists-tab/list-recommendation-scores-context.tsx` — scores para columnas.
- `packages/shared/src/chart-defaults.ts` — `RECOMMENDATION_OPTIONAL_LIST_COLUMNS`.
- `packages/shared/src/default-lists.ts` — labels Visualizados / Estudio.

## Tests

- `chart-list-membership.test.ts`
- `scroll-list-instrument-into-view.test.ts`
- `sort-visualizados-by-io.test.ts` · `fetch-io-scores-for-sort.test.ts`
- `list-recommendation-columns.test.ts` · `list-sort-with-recommendation.test.ts`

@see docs/adr/024-estudio-supervision-universe.md
@see docs/engineering/session-handoff-2026-08-06-visualizados-list-ux.md
