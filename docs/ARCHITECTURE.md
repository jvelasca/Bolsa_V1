# Arquitectura

## Visión

Bolsa V1 es un monorepo con **backend Python (FastAPI)** como API por defecto, frontend **React + Vite**, y PostgreSQL como fuente de verdad. El backend TypeScript fue **retirado** (backup en `archive/legacy-ts/`).

```
┌─────────────┐     HTTP      ┌──────────────────┐
│  apps/web   │ ────────────► │ apps/api-python  │
│  React SPA  │   :8000       │  FastAPI         │
└─────────────┘               └────────┬─────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
             ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
             │ packages/py │    │ packages/py │    │ @bolsa/     │
             │ application │    │ analytics   │    │ shared      │
             │ domain      │    │ market      │    │ (DTOs TS)   │
             │ infra       │    └──────┬──────┘    └─────────────┘
             └──────┬──────┘           │
                    │            ┌─────▼─────┐
             ┌──────▼──────┐     │ Yahoo/XTB │
             │ PostgreSQL  │     └───────────┘
             └─────────────┘
```

## Paquetes

### Python (`packages/py/`)

| Paquete | Responsabilidad |
|---------|-----------------|
| `bolsa_domain` | Entidades, enums, Protocol de repos |
| `bolsa_application` | Casos de uso (sync, portfolio, backtest) |
| `bolsa_infrastructure` | SQLAlchemy, config, repos |
| `bolsa_analytics` | SMA, EMA, RSI, motor backtest |
| `bolsa_market` | Yahoo provider, XTB bridge |

### TypeScript (frontend + tooling BD)

| Paquete | Responsabilidad |
|---------|-----------------|
| `@bolsa/shared` | Tipos DTO compartidos frontend/API |
| `@bolsa/web` | UI React, TanStack Query, gráficos, shell ProRealTime |
| `@bolsa/database` | Prisma schema + seed (bootstrap BD) |

Stack TS legacy archivado en `archive/legacy-ts/` — ver [LEGACY.md](./LEGACY.md).

## Flujo de datos

1. Seed carga catálogo IBEX en `instruments` (Prisma seed / scripts).
2. Usuario pulsa **Sincronizar** → API Python → caso de uso sync.
3. Provider Yahoo obtiene OHLCV diario.
4. Upsert en `ohlcv_bars` + `data_sync_log`.
5. Frontend consulta `/ohlcv` → datos desde PostgreSQL.
6. Indicadores calculados en `bolsa_analytics` (sin pandas).

## Auth (cutover 2026)

- Opcional: `APP_PASSWORD` en `.env`.
- Middleware FastAPI valida `Authorization: Bearer <token>`.
- Frontend: `AuthGate` → login o shell según `/api/auth/status`.

Ver [CUTOVER_PYTHON.md](./CUTOVER_PYTHON.md).

## UI shell (ADR-004)

- Menú estilo ProRealTime, toolbar, panel listas IBEX, workspace local JSON.
- Ver [UI_PLATFORM.md](./UI_PLATFORM.md).

## Principios

- **Provider-agnostic:** dominio no depende de Yahoo ni XTB.
- **Local first:** Docker Compose + `.env`.
- **Endpoint parity first:** migración TS→Python validada por tests.
- **Solo acciones:** sin CFD en dominio ni BD.

## Despliegue local

- PostgreSQL: `docker compose up -d` (automático con `pnpm dev`)
- API Python: puerto **8000**
- Web: puerto **5173**, `VITE_API_URL=http://localhost:8000`
