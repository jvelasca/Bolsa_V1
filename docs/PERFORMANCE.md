# Rendimiento — Bolsa V1 (jul 2026)

Guía de diagnóstico del frontend, centrada en el workspace de gráficos y trading.

## Instrumentación integrada

Módulo: `apps/web/src/features/charts/chart-perf-analyzer.ts`

Se instala al cargar la app y expone funciones globales en `window` (consola F12).

| Comando | Descripción |
|---------|-------------|
| `bolsaPerfStart()` | Inicia sesión de grabación; resetea contadores |
| `bolsaPerfStop()` | Para, descarga JSON, guarda en `localStorage` (`bolsa-perf-last-session`) |
| `bolsaPerfReport()` | Tabla en consola sin detener |
| `bolsaPerfCopy()` | Copia último informe al portapapeles |
| `bolsaPerfLoadLast()` | Lee informe guardado |
| `bolsaPerfHud(true)` | Overlay fijo abajo-izquierda (1 s refresh) |
| `bolsaPerfHud(false)` | Oculta overlay |

Verbose adicional: `localStorage.setItem('bolsa-debug-chart', '1')` → logs `chartPerfDebug` en consola.

## Métricas capturadas

| Métrica | Origen | Interpretación |
|---------|--------|----------------|
| `reflowRequests` | Chart / lightweight-charts | Peticiones de redibujado; picos = parpadeo o CPU alta |
| `workspaceSets` | `workspace-store` | Actualizaciones de estado Zustand del workspace |
| `queryFetches` | React Query hooks instrumentados | Peticiones HTTP de datos |
| `queryCacheUpdates` | React Query | Escrituras en caché |
| `indicatorSpecCacheHits/Misses` | `indicator-compute.ts` | Memo por spec+OHLCV (H1) |

El informe JSON incluye `summary.*PerSec`, `topSources` (fuentes con más eventos) y rollups por segundo.

## Umbrales orientativos (uso normal, gráfico 1d, 1–3 indicadores)

| Métrica | OK | Revisar | Crítico |
|---------|-----|---------|---------|
| reflow/s | &lt; 5 | 5–15 | &gt; 15 |
| workspace sets/s | &lt; 3 | 3–8 | &gt; 8 |
| query fetch/s | depende de polling | — | ráfagas &gt; 10/s sostenidas |
| indicator cache hit rate | &gt; 70 % tras 30 s | 40–70 % | &lt; 40 % |

Tras `bolsaPerfStart()`, cambia timeframe, mueve cursor, abre inspector y añade/quita un indicador antes de `bolsaPerfStop()`.

## Mitigaciones implementadas (jul 2026)

### H1 — Memo indicadores

- Caché LRU por spec en `indicator-compute.ts` (`SPEC_SERIES_CACHE_MAX = 96`).
- `useMemo` en `sub-indicator-panel.tsx` y `ohlcv-chart.tsx` con fingerprint de barras.
- Stats exportadas: `getIndicatorSpecCacheStats()`, `resetIndicatorSpecCacheStats()`.

### H2 — Batch live quotes

- `useInstrumentLiveQuotesBatch` → `GET /instruments/live-quotes`.
- Consumidores: `pending-orders-monitor`, `use-expanded-instrument-live-quote`, acordeón de listas.
- Polling típico: 15 s.

### H3 — Ciclo stores

- `workspace-ui-bridge.ts` + `WorkspaceUiBridgeRegister` rompen `ui-store` ↔ `workspace-store`.
- `open-list-hub.ts` centraliza «Gestionar listas».

### M7 — Autosave debounce

- `WORKSPACE_AUTOSAVE_DEBOUNCE_MS = 1000` en `workspace-store.ts`.
- Timer único `requestWorkspaceAutoSave()`; `WorkspaceAutoSave` delega.

### H4 — Listas / catálogo (N+1 meta)

- `list_with_meta` / `get_quotes_by_ids` hidratan meta con ~4 queries batch (counts, sync, closes, last bar), no 4×N.
- `get_quotes_for_list` solo pide IDs de la lista (ya no `list_with_meta` de todo el catálogo).
- UI: panel de valores no carga `GET /instruments` al ver una lista normal; hub solo al crear lista; sync de Visualización usa labels de pestaña (sin catálogo).

### H5 — Portfolio closes + account hub

- `portfolio_repository.get_summary` batchéa últimos closes D1 (`DISTINCT ON`), no 1 query por posición.
- `GET /api/accounts/summaries` + hub UI: un fetch para equities (sin N× `/summary` ni custody side-effects).
- `pnpm dev`: skip rebuild de `@bolsa/shared` si `dist` ≥ `src`.

### H6 — Live quotes batch real

- `GetInstrumentLiveQuotes` usa `get_quotes_by_ids` (meta ligera), no `GetInstrumentDetail` / 500 barras por id.
- Un solo `check_health` XTB + `fetch_quotes` con client compartido y concurrencia acotada (8).
- `GetInstrumentLiveQuote` (single) delega al mismo batch.

### H7 — Cold start API

- `BOLSA_API_RELOAD` opt-in (`0` por defecto en `run_dev.py`): evita doble import padre+worker de uvicorn.
- Lifespan: aviso de rutas usa walk de routers, no `app.openapi()` (~0.5s+).
- Windows: `loop=bolsa_api.win_loop:selector_event_loop_factory` — sin `--reload`, uvicorn elegiría Proactor y psycopg falla.

## Hot paths pendientes

Scan híbrido universo grande.

## Re-ejecutar auditoría rápida

```bash
pnpm --filter @bolsa/web typecheck
rg "chartPerfRecord|bolsaPerf" apps/web/src
rg "useInstrumentLiveQuotesBatch" apps/web/src
```

---

---
