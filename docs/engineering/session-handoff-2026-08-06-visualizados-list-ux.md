# Handoff — Visualizados + UX listas (2026-08-06)

Retomar desde aquí tras el stage de Visualizados / IO / foco de lista.

## Hecho en esta racha

1. **Visualizados ≠ Estudio** — SoT pestañas; prune + no restaurar dump legacy.
2. **Quitar** selección — cierre atómico de tabs; fix autosave que resucitaba charts.
3. **Por IO** — orden tabs por Índice Operativo; fetch en trozos + caché Operativa.
4. **Columnas** IO/TA/FA/★/Postura en (⋯); sort por columna (Visualizados realinea tabs).
5. **Foco** — prioridad lista Cartera → Estudio → resto; scroll bajo cabecera sticky.
6. Composite/FA `execute_chips` traga errores por id (menos 500 en batch).

## No hecho / siguiente agente

- Pulir copy / tracker `watchlist-lists-tracker` si hace falta sync formal.
- Si Estudio no está en `apiLists` al buscar, `listConfigForSelection` cae a Cartera — edge raro.
- Rank «N de M» como columna opcional (hoy solo IO/TA/FA/dictamen/postura).
- No mezclar Visualizados con supervisión (ADR-024).

## Docs

- [visualizados-list-ux-2026-08-06.md](./visualizados-list-ux-2026-08-06.md)
- [ADR-024](../adr/024-estudio-supervision-universe.md)
- HELP / Ayuda in-app (`HELP_CONTENT_AS_OF` 2026-08-06)

## Verificar rápido

```bash
cd apps/web
npx vitest run src/lib/chart-list-membership.test.ts \
  src/lib/scroll-list-instrument-into-view.test.ts \
  src/lib/list-sort-with-recommendation.test.ts \
  src/features/trading/lists-tab/fetch-io-scores-for-sort.test.ts \
  src/features/trading/lists-tab/sort-visualizados-by-io.test.ts \
  src/features/trading/lists-tab/list-recommendation-columns.test.ts
```

UI: 1 pestaña → Visualizados count 1 · Por IO · sort columna · buscar valor en Estudio → lista Estudio + scroll arriba.
