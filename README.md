# Bolsa V1

Plataforma personal de gestión bursátil: IBEX, Europa y acciones (sin CFD).

**Stack actual:** React + Vite (frontend) · **FastAPI Python** (API por defecto) · PostgreSQL.

**Producto (V1.95 Beta Certification · tip vivo `v1.94-beta` · 2026-09-03):** Embudo + Lista AUTO · Finalistas · **DÍA D** · **CORE-R** · **CORE-P** · FA/FIE · DEMO / paper · **Operativa SEMI** + **AUTO UI BETA-D** (armado `ACTIVAR AUTO` · execute opt-in `PAPER_D_EXECUTE`) · Decision Spine + Lifecycle Event Store / Outbox + Financial Integrity (V1.86–V1.95) · JWT / multi-user (ADR-027 C) · Estudio ADR-024 · Asesor/Señales. **No LIVE** · package `1.35.0-beta`. Thaw estricto en deuda. Estado canónico: [`docs/CURRENT_SYSTEM.md`](./docs/CURRENT_SYSTEM.md).
Changelog: [`CHANGELOG.md`](./CHANGELOG.md) · **Sistema actual (SoT corto):** [`docs/CURRENT_SYSTEM.md`](./docs/CURRENT_SYSTEM.md) · **Fuente de coordinación: GitHub** [jvelasca/Bolsa_V1](https://github.com/jvelasca/Bolsa_V1) (`origin/main`) · Estado vivo: [`PROJECT_STATE.md`](./docs/engineering/PROJECT_STATE.md) · Relevo: [`traspaso-relevo-cierre-r13-consolidacion-beta-siguiente-2026-08-22.md`](./docs/engineering/traspaso-relevo-cierre-r13-consolidacion-beta-siguiente-2026-08-22.md) · Premisas: [`PROJECT_PREMISES.md`](./docs/PROJECT_PREMISES.md) · ADR-024: [`024-estudio-supervision-universe`](./docs/adr/024-estudio-supervision-universe.md) · HELP: [`docs/HELP.md`](./docs/HELP.md).

## Requisitos

- Node.js >= 20
- pnpm >= 10
- Python >= 3.11
- Docker Desktop (PostgreSQL local)

## Inicio rápido

```bash
# 1. Instalar dependencias
pnpm install
pnpm test:py:install

# 2. Variables de entorno
cp .env.example .env
cp apps/web/.env.example apps/web/.env

# 3. Base de datos (Docker arranca solo con pnpm dev)
pnpm db:ensure

# 4. Desarrollo — API Python :8000 + Web :5173
pnpm dev
```

- **Web:** http://localhost:5173
- **API:** http://localhost:8000/api/health
- **Docs API:** http://localhost:8000/docs

> **Nota:** La API activa es FastAPI en `:8000`. Usa `pnpm dev` o la config F5 **Bolsa: Dev (pnpm dev)**.  
> Tras pulls de código Python, **reinicia api-python** (rutas Evidence / asOf / CORE-R).

Documentación completa del cutover: [`docs/DEV_STARTUP.md`](./docs/DEV_STARTUP.md) · [`docs/README.md`](./docs/README.md).

## Scripts

| Comando                           | Descripción                                                  |
| --------------------------------- | ------------------------------------------------------------ |
| `pnpm dev`                        | API Python + Web (recomendado)                               |
| `pnpm dev:web`                    | Solo frontend                                                |
| `pnpm dev:log`                    | Igual que dev con logs en `logs/dev/`                        |
| `pnpm test`                       | Tests unitarios frontend                                     |
| `pnpm test:py`                    | Tests Python (API, analytics, market)                        |
| `pnpm test:py:install`            | Instalar paquetes Python editables                           |
| `pnpm test:operativa`             | **DÍA D + CORE-R** (web + py + smoke API opcional)           |
| `pnpm test:operativa:smoke`       | Smoke API live (FA asOf, Evidence, CORE-R)                   |
| `pnpm test:semi`                  | **SEMI DEMO** libro + F3 + geo + cola BD (web + py + smoke)  |
| `pnpm test:semi:smoke`            | Smoke API live cola F3 + propose country                     |
| `pnpm test:decision-spine`        | **Decision Spine** Runtime→Fit→confirm/router (sin API live) |
| `pnpm test:fa`                    | Batería FA / FIE                                             |
| `pnpm test:coach`                 | Embudo / Lista AUTO / CORE-P (+ smoke API opcional)          |
| `pnpm test:coach:smoke`           | Smoke API CORE-P multi-perfil (SKIP si API down)             |
| `pnpm test:coach:api`             | ASGI multi-perfil (DB) + smoke live                          |
| `pnpm health`                     | Health check API (:8000) + Web                               |
| `pnpm db:ensure`                  | Docker + PostgreSQL + seed IBEX                              |
| `pnpm setup`                      | Setup completo del proyecto                                  |
| `pnpm build`                      | Build monorepo                                               |
| `node scripts/dev-api-python.mjs` | Solo API Python                                              |

## Auth

Auth viva = **JWT + cookie HttpOnly** (ADR-027 C). Ver [`docs/CURRENT_SYSTEM.md`](./docs/CURRENT_SYSTEM.md).

`APP_PASSWORD` es un **overlay opcional de login en dev**, no el modelo de auth. En `.env` raíz:

```env
# APP_PASSWORD=mi-clave   # overlay de login en dev (no sustituye JWT)
# APP_AUTH_SECRET=<token aleatorio>  # obligatorio (y nunca 'bolsa-dev-secret') si APP_PASSWORD está definido
```

Sin `APP_PASSWORD` la app entra con el flujo JWT habitual (en local, seed/login de desarrollo). Si activas `APP_PASSWORD`, define `APP_AUTH_SECRET` con un valor aleatorio (p. ej. `python -c "import secrets; print(secrets.token_urlsafe(48))"`); el arranque falla si lo dejas vacío o igual a `bolsa-dev-secret`.

## Docker (PostgreSQL)

Docker **solo** levanta PostgreSQL; la app corre con Node + Python. Ver [`docs/docker.md`](./docs/docker.md).

## Arrancar en Cursor

### Run and Debug

1. Panel **Run and Debug** (`Ctrl+Shift+D`)
2. Configuraciones:
   - **Bolsa: Dev (pnpm dev)** — ✅ API Python + Web (recomendado)
   - **Bolsa: API Python** — solo backend FastAPI
   - **Bolsa: Web** — solo frontend
3. **F5**

## Estructura

```
apps/api-python   → FastAPI REST (API por defecto)
apps/web          → React + shell ProRealTime
packages/py/      → domain, application, infrastructure, analytics, market
packages/shared   → DTOs TypeScript
packages/database → Prisma tooling (seed / generate; DDL = Alembic)
scripts/          → run-dev, db-ensure, health-check, research batteries
docs/             → arquitectura, cutover, ADRs, engineering
```

## Documentación

| Documento                                                                                                                  | Contenido                                      |
| -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| [`docs/CURRENT_SYSTEM.md`](./docs/CURRENT_SYSTEM.md)                                                                       | **Sistema actual** (stack, spine, auth, tests) |
| [`docs/HELP.md`](./docs/HELP.md)                                                                                           | Mapa Ayuda ↔ trackers (`HELP_CONTENT_AS_OF`)   |
| [`docs/engineering/session-handoff-2026-08-01.md`](./docs/engineering/session-handoff-2026-08-01.md)                       | **Handoff** cierre racha · smoke UI humano     |
| [`docs/engineering/session-handoff-2026-07-31.md`](./docs/engineering/session-handoff-2026-07-31.md)                       | Handoff cierre DÍA D + CORE-R                  |
| [`docs/engineering/operativa-test-plan-2026-07-31.md`](./docs/engineering/operativa-test-plan-2026-07-31.md)               | Plan smoke UI DÍA D + CORE-R                   |
| [`docs/engineering/backtesting-dia-d-premises-2026-07-31.md`](./docs/engineering/backtesting-dia-d-premises-2026-07-31.md) | Premisas DÍA D                                 |
| [`docs/engineering/research-lifecycle.md`](./docs/engineering/research-lifecycle.md)                                       | Flujo BT → Finalistas → Monitor                |
| [`docs/ONBOARDING.md`](./docs/ONBOARDING.md)                                                                               | Guía para nuevos desarrolladores               |
| [`docs/API_REFERENCE.md`](./docs/API_REFERENCE.md)                                                                         | Endpoints HTTP                                 |
| [`docs/UI_PLATFORM.md`](./docs/UI_PLATFORM.md)                                                                             | Shell ProRealTime                              |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)                                                                           | Capas y diagrama                               |
| [`docs/adr/008-investment-accounts-and-ledger.md`](./docs/adr/008-investment-accounts-and-ledger.md)                       | Cuentas + ledger                               |
| [`docs/LEGACY.md`](./docs/LEGACY.md)                                                                                       | Stack TS archivado (git history)               |
| [`docs/README.md`](./docs/README.md)                                                                                       | Índice completo                                |

## Rutas frontend

`/overview` · `/trading` · `/backtests` · `/portfolio` · `/accounts` · `/operations` · `/history` · `/fiscal`

## Roadmap

- **Cuentas + ledger + comisiones + fiscal** ✓
- **Backtesting embudo + Lista AUTO + Finalistas A/C** ✓
- **DÍA D v0.11 + CORE-R v1.8** ✓ 2026-07-31 / 2026-08-01
- **FA / FIE** ✓ código (Composite **v1.1** · CAPM Tarjeta v0 · cobertura Yahoo); **smoke UI / checklist APP** pendiente
- **CORE-B Lab** ✓ v0.2 (meseta + familia por horizonte)
- **Congelado:** auto-paper D execute · Lab UI P3–P9 / Belief · CORE-R multi-dispositivo
- **Deuda:** dividendos (solo se recopila historial en instrumento; sin feature de pago/ledger) · `transfer_cash` **eliminado en R-7/B-3 (`7cffaa7`)** por código muerto sin ledger (una futura transferencia trazada reutilizaría `reference_type="transfer"` en `append_cash_movement`; consulte `docs/engineering/traspaso-r7-...`). Auth JWT-only **está viva** (R-12 / ADR-027); no es deuda diferida.
