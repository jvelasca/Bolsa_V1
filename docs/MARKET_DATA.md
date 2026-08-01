# Datos de mercado

> **Sync Ayuda:** `HELP_CONTENT_AS_OF` = **2026-07-23**  
> UI: Ayuda → **Datos de mercado** (`data-market-tracker.ts` + `DataCaptureSection`).  
> ADR: [002-yahoo-primary-xtb-secondary](./adr/002-yahoo-primary-xtb-secondary.md) · intradía [007](./adr/007-intraday-ohlcv-persistence.md).

## Resumen (no técnico)

1. **Yahoo Finance** descarga el histórico de precios y la ficha fundamental de cada valor.
2. Todo se **guarda en PostgreSQL**. Gráficos, backtests, escáneres e IA leen de la BD, no de Yahoo en caliente.
3. **XTB** (bridge local, opcional) solo aporta cotización en vivo y una **validación** frente al cierre guardado. No escribe el histórico.

## Estrategia de proveedores

| Proveedor | Rol | Persiste en BD |
|-----------|-----|----------------|
| **Yahoo Finance** | Primario: OHLCV, perfil, fundamentales v3, dividendos | Sí (`ohlcv_bars`, `instruments.profile_snapshot`) |
| **XTB Bridge** | Secundario: quote live + validación vs cierre | Solo auditoría (`last_xtb_validation`, `data_sync_log`) |

La app **nunca** llama a Yahoo desde el frontend. Flujo: UI → API Python → Yahoo/XTB → BD → UI.

Implementación actual (Python, no el antiguo paquete TS `market-data`):

| Pieza | Ruta |
|-------|------|
| Cliente Yahoo (chart + quoteSummary) | `packages/py/market/src/bolsa_market/yahoo_client.py` |
| Provider velas | `packages/py/market/src/bolsa_market/yahoo_chart.py` |
| Sync diaria | `packages/py/application/src/bolsa_application/sync_instrument.py` |
| Fundamentales v3 | `packages/py/market/src/bolsa_market/instrument_fundamentals.py` |
| Refresh ficha | `packages/py/application/src/bolsa_application/refresh_instrument_fundamentals.py` |
| Validación XTB | `packages/py/application/src/bolsa_application/validate_instrument_xtb.py` |
| Bridge client | `packages/py/market/src/bolsa_market/providers.py` |
| Worker auto-sync | `apps/api-python/src/bolsa_api/background/auto_sync_worker.py` |

## Datos técnicos vs fundamentales

### Técnicos (velas OHLCV)

- Tabla: `ohlcv_bars` — unique `(instrument_id, timeframe, timestamp)`.
- Timeframes: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1wk`, `1mo`.
- **Sync explícita** → siempre diaria (`1d`). Primera vez ~5 años; luego incremental (última fecha − 7 días de solape).
- **Lazy / caché** → otros TF se piden a Yahoo si la caché está caducada (TTL por timeframe) y se upsertan.
- Source enum: `yahoo` \| `xtb` (hoy las escrituras de histórico son Yahoo).

### Fundamentales (snapshot)

- Campo: `instruments.profile_snapshot` (JSONB).
- Bloque `fundamentals` con `sourceVersion: "yahoo_quote_summary_v3"` (ROE, márgenes, crecimiento, D/E, currentRatio, Altman Z, etc.).
- Módulos Yahoo quoteSummary: `summaryProfile`, `summaryDetail`, `financialData`, `defaultKeyStatistics`, `calendarEvents`, `balanceSheetHistory`, `incomeStatementHistory`.
- Refresh: junto a sync diaria y/o `RefreshFundamentalsBatch` (concurrencia limitada).
- Stale típico para gates: ~30 días (`fetchedAt`).

Noticias Yahoo y macro (VIX / curva) se usan en el camino cognitivo con TTL en memoria; **no** son el almacén principal de mercado documentado aquí.

## Alcance: listas vs cola vs gráfico vs rastreadores

| Superficie | ¿Actualiza OHLCV solo? | Notas |
|------------|------------------------|-------|
| **Cola automática** | Sí — por defecto **valores en listas** (`scope=lists`) desfasados/vacíos/error | Independiente de pestañas. Scan cada `scanIntervalMinutes` (def. 30); 1 ítem/~15 s + `minDelaySeconds` + throttle Yahoo. `scope=stale` = todos los activos |
| **Listas** | No al abrir | Meta + `freshnessStatus` / icono sync; live quote solo filas expandidas (~15 s) |
| **Gráfico abierto (1d)** | Sí, una vez si empty/stale | Atajo; no sustituye a la cola |
| **Rastreadores** | No (OHLCV) | Usan barras en BD; híbrido puede refrescar solo fundamentales stale |

Ajustes: **Configuración → Otras** (universo listas vs todos, pausas, post-cierre).  
Estado y mantenimiento PostgreSQL: **Configuración → BD** (conteos, huérfanos, demos cerradas, purga).  
Ayuda → Datos de mercado → «¿Qué se actualiza solo?» / «Quitar de lista y limpiar BD».

## Ciclo de vida: listas ↔ BD

| Acción | Efecto |
|--------|--------|
| Quitar de **una** lista (sigue en otras) | Solo membresía; OHLCV intacto; sigue en cola si `scope=lists` |
| Quitar de la **última** lista persistente | Candidato a huérfano. Diálogo: dejar en BD o purgar. Virtuales (Visualización/Cartera/Pendientes) no anclan. |
| Purga | `DELETE` instrumento → cascade OHLCV, alertas, list items, sync queue… Bloqueada si hay **posición** u **orden pendiente**. Avisa de alertas/rastreadores. |
| Catálogo | Instrumentos de listas `source=catalog` no se editan desde la UI |

API: `GET /api/instruments/{id}/removal-preview`, `POST /api/lists/{listId}/instruments/{id}/remove`, `GET/POST /api/database/orphans[/purge]`, `DELETE /api/instruments/{id}`.

## Modos de sincronización

| Modo | Comportamiento | Entrada |
|------|----------------|---------|
| Manual | `POST /api/instruments/{id}/sync` → diarias + metadatos | Gráfico, ficha instrumento, API |
| Automática | Worker ~15 s; scan cada `scanIntervalMinutes` → cola | `sync_settings` + `sync_queue` |
| Lazy intradía | GET OHLCV con TF ≠ 1d refresca si TTL stale | Charts / API barras |
| Fund lote | Refresh concurrente de `profile_snapshot` | Escáneres / calidad |

Ajustes API: `GET/PATCH /api/sync/settings`, `GET /api/sync/queue`, `POST /api/sync/queue/enqueue-stale`.  
UI editable: **Configuración → Otras**.

Claves principales (`sync_settings`): `autoSyncEnabled`, `scanIntervalMinutes`, `minDelaySeconds`, `postMarketOnly`, `maxRetries`, `retryBackoffMinutes`, `scope`.

## Validación

1. **Ingesta / sanity** — OHLC coherente, sin fechas futuras; errores bloquean escritura; huecos / movimientos extremos → warnings.
2. **Consolidación** — no sobrescribe a ciegas velas existentes al re-sync.
3. **Frescura** — calendario de mercado → `current` / `stale` / `empty` / `gap_detected` / `error`.
4. **XTB** — Δ% vs último cierre; `<2%` → `aligned`, si no `review`; persiste `last_xtb_validation`.
5. **Calidad v1** — score de frescura, profundidad, sync, gaps, fundamentales.

## Yahoo: símbolos y límites

| Ticker | Yahoo | Mercado |
|--------|-------|---------|
| Santander | SAN.MC | BME |
| Iberdrola | IBE.MC | BME |
| Inditex | ITX.MC | BME |

Límites: sin SLA; riesgo 429. Mitigación: User-Agent/crumb, throttle (`YAHOO_MIN_INTERVAL_SEC`), reintentos (`YAHOO_MAX_RETRIES`), alternancia query1/query2, logs en `data_sync_log`.

```env
YAHOO_MIN_INTERVAL_SEC=2.0
YAHOO_MAX_RETRIES=4
XTB_BRIDGE_URL=http://localhost:3002
```

## XTB Bridge

API retail XTB cerrada → adaptador habla con **bridge HTTP local** (mock o conector propio).

```bash
pnpm xtb:mock          # http://localhost:3002
# .env: XTB_BRIDGE_URL=http://localhost:3002
```

| Método | Ruta | Uso en app |
|--------|------|------------|
| GET | `/health` | Estado proveedor |
| GET | `/symbols/:symbol/quote` | Live + validación |

Símbolos tip. IBEX bridge: `IBE.ES`, `SAN.ES`. El cliente Python **no** usa `/bars` para persistir histórico.

## Modelos de consulta (BD)

Ver también [DATA_MODEL.md](./DATA_MODEL.md).

| Tabla / campo | Uso |
|---------------|-----|
| `instruments` | Catálogo; `profile_snapshot`; `last_xtb_validation` |
| `ohlcv_bars` | Velas por timeframe |
| `data_sync_log` | Auditoría sync / validación |
| `sync_settings` | Knobs de cola automática |
| `sync_queue` | Trabajo pendiente / reintentos |
| `instrument_lists` / `instrument_list_items` | Membresía; al quedarse vacío el valor es huérfano (candidato a purga) |

SQLAlchemy: `packages/py/infrastructure/.../tables.py` · Prisma: `packages/database/prisma/schema.prisma`.
