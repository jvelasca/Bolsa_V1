# Guía de onboarding — Bolsa V1

Para cualquier informático que retome el proyecto sin contexto previo.

## 1. Prerrequisitos

| Herramienta | Versión | Para qué |
|-------------|---------|----------|
| Node.js | ≥ 20 | Frontend, scripts, Prisma |
| pnpm | ≥ 10 | Monorepo |
| Python | ≥ 3.11 | API FastAPI |
| Docker Desktop | Reciente | PostgreSQL local |
| Git | Cualquiera | Control de versiones |

## 2. Setup en 10 minutos

```bash
git clone <repo-url> Bolsa_V1
cd Bolsa_V1

pnpm install
pnpm test:py:install

cp .env.example .env
cp apps/web/.env.example apps/web/.env

pnpm db:ensure    # Docker + schema + seed IBEX
pnpm dev          # API :8000 + Web :5173
```

Abrir http://localhost:5173. Si queda en "Cargando…", ver `pnpm health` y [docker.md](./docker.md).

## 3. Mapa mental del monorepo

```
Bolsa_V1/
├── apps/
│   ├── web/                 ← UI React (ACTIVO)
│   └── api-python/          ← FastAPI REST (ACTIVO)
├── packages/
│   ├── shared/              ← DTOs TypeScript compartidos
│   ├── database/            ← Prisma schema + seed
│   └── py/                  ← domain, application, infrastructure, analytics, market, ai
├── scripts/                 ← run-dev, db-ensure, health
└── docs/                    ← Documentación
```

## 4. Flujo de una petición típica

**Usuario abre gráfico de Santander desde listas:**

1. `lists-tab.tsx` → `openInstrumentChart()` → tab en `workspace-store`.
2. `ChartWorkspacePage` → `api.getOhlcv(instrumentId)`.
3. FastAPI `GET /api/instruments/{id}/ohlcv` → `GetOhlcvBars` use case.
4. `SqlAlchemyOhlcvRepository` lee PostgreSQL.
5. `OhlcvChart` pinta velas con Lightweight Charts.

**Usuario busca AAPL en Yahoo (no en catálogo):**

1. `api.searchInstruments(q)` → Yahoo + catálogo local.
2. Click resultado externo → `api.importInstrument()` → crea instrumento + sync.
3. `focusInstrument()` abre tab; si OHLCV vacío → `InstrumentSyncDialog`.

## 5. Archivos que debes leer primero

| Orden | Archivo | Por qué |
|-------|---------|---------|
| 1 | `docs/AI_PLATFORM_SOLUTION.md` | Estado plataforma + IA |
| 2 | `docs/HELP.md` | Ayuda app ↔ trackers (`HELP_CONTENT_AS_OF`) |
| 3 | `docs/rfc/README.md` | Constitución RFC-000…007 |
| 4 | `scripts/run-dev.mjs` | Cómo arranca dev |
| 5 | `apps/web/src/lib/api.ts` | Contrato frontend ↔ backend |
| 6 | `apps/api-python/src/bolsa_api/main.py` | Entry point API |
| 7 | `apps/api-python/src/bolsa_api/api/v1/router.py` | Routers HTTP |
| 8 | `packages/py/application/` | Lógica de negocio |
| 9 | `packages/py/ai/` | AIGovernanceProxy (F1) |
| 10 | `packages/database/prisma/schema.prisma` | Modelo de datos |
| 11 | `docs/UI_PLATFORM.md` | UI trading |

## 6. Capas Python (clean architecture)

```
HTTP (routes)     →  schemas Pydantic (DTO)
       ↓
dependencies.py   →  inyecta casos de uso + sesión BD
       ↓
application/      →  SyncInstrument, ImportInstrument, Portfolio…
       ↓
domain/           →  Instrument, OhlcvBar, Protocol repos
       ↓
infrastructure/   →  SQLAlchemy models + repos concretos
       ↓
market/           →  YahooMarketDataProvider, ingest
analytics/        →  SMA, EMA, RSI, backtest, Feature Registry
ai/               →  AIGovernanceProxy, Prompt Registry, adapters LLM
```

**Regla:** `domain` no importa de `infrastructure` ni `market`. Los casos de uso reciben repos por constructor. LLM solo vía `bolsa_ai`.

## 7. Frontend — stores principales

**Premisa UI:** preferencias y chrome configurables → `localStorage` del navegador (por máquina/perfil). Ver [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md). El documento del workspace (contenido) va al servidor.

| Store | Clave localStorage | Contenido |
|-------|-------------------|-----------|
| `auth-store` | `bolsa-auth` | Token JWT |
| `workspace-store` | `bolsa-workspace-meta` (+ API) | Metadatos locales + documento en servidor |
| `trading-ui-store` | `trading-ui-store` | Órdenes pendientes |
| `trading-layout-store` | `bolsa-trading-layout-v1` | Visibilidad/tamaño paneles |
| `ui-store` | — (memoria) / sesión dibujo | Diálogos abiertos, herramienta dibujo |
| `alerts-store` | — | Cache alertas UI |

## 8. Base de datos

- **Bootstrap:** `pnpm db:push` (Prisma) + `pnpm db:seed` (IBEX 35).
- **Runtime:** SQLAlchemy en Python (todas las lecturas/escrituras de la API).
- **Conexión:** `DATABASE_URL` en `.env`.
- **UI explorar datos:** `pnpm db:studio` (Prisma Studio).

Tablas principales: `instruments`, `ohlcv_bars`, `data_sync_logs`, `instrument_lists`, `portfolio_*`, `price_alerts`, `backtest_runs`.

Ver [DATA_MODEL.md](./DATA_MODEL.md) (parcial — contrastar con `schema.prisma`).

## 9. Comandos del día a día

| Comando | Cuándo |
|---------|--------|
| `pnpm dev` | Desarrollo normal |
| `pnpm test:py` | Tras cambios Python |
| `pnpm typecheck` | Tras cambios TS |
| `pnpm db:ensure` | BD caída o clone nuevo |
| `pnpm health` | Verificar API + web |
| `node scripts/dev-api-python.mjs` | Solo backend |

## 10. Añadir una feature — plantilla

### Backend

1. Entidad/protocolo en `bolsa_domain` si hace falta.
2. Repo en `bolsa_infrastructure/database/repositories/`.
3. Caso de uso en `bolsa_application/nueva_feature.py` con docstring.
4. Schema Pydantic en `bolsa_api/schemas/`.
5. Ruta en `bolsa_api/api/v1/routes/`.
6. Dependency en `bolsa_api/api/dependencies.py`.
7. Test en `apps/api-python/tests/` o `packages/py/*/tests/`.

### Frontend

1. Tipo DTO en `packages/shared/src/types.ts` + `pnpm --filter @bolsa/shared build`.
2. Método en `apps/web/src/lib/api.ts`.
3. Componente en `apps/web/src/features/`.
4. Invalidación en `lib/query-invalidation.ts` si afecta cache.

## 11. Debugging frecuente

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| 404 en `/api/alerts` o `/import` | API vieja en :8000 | Matar uvicorn duplicados, `pnpm dev` |
| Web "Cargando…" infinito | `VITE_API_URL` mal o API caída | Revisar `.env`, reiniciar dev |
| Gráfico vacío | Sin sync Yahoo | Diálogo sync o botón en chart |
| `docker compose` falla | Docker apagado | Abrir Docker Desktop, `pnpm db:ensure` |
| Typecheck falla en shared | Tipos no compilados | `pnpm --filter @bolsa/shared build` |

## 12. Más lectura

- [HELP.md](./HELP.md) — mapa Ayuda en app (incl. **Backtesting DÍA D**)
- [engineering/backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) — cómo arrancar verificación D→hoy
- [engineering/research-lifecycle.md](./engineering/research-lifecycle.md) — embudo Play / Finalistas
- [API_REFERENCE.md](./API_REFERENCE.md)
- [rfc/README.md](./rfc/README.md)
- [LEGACY.md](./LEGACY.md)
- ADRs en `docs/adr/`
