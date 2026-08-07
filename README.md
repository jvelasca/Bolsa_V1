# Bolsa V1

Plataforma personal de gestión bursátil: IBEX, Europa y acciones (sin CFD).

**Stack actual:** React + Vite (frontend) · **FastAPI Python** (API por defecto) · PostgreSQL.

**Producto (v1.0.0 · sync docs 2026-08-06):** Embudo + Lista AUTO · Finalistas · **DÍA D** · **CORE-R v1.12** · **CORE-P** · FA/FIE · DEMO only · **Operativa SEMI** · **Estudio ADR-024** (Supervisión 3 capas · Actualizar/Redescubrir) · Asesor/Canales · **prep AUTO A0–A5** (`PAPER_D_EXECUTE` off).  
Changelog: [`CHANGELOG.md`](./CHANGELOG.md) · GitHub: [jvelasca/Bolsa_V1](https://github.com/jvelasca/Bolsa_V1) · PR stage: [#29](https://github.com/jvelasca/Bolsa_V1/pull/29) · Handoff Estudio UI: [`session-handoff-2026-08-06-estudio-process-ui`](./docs/engineering/session-handoff-2026-08-06-estudio-process-ui.md) · ADR-024: [`024-estudio-supervision-universe`](./docs/adr/024-estudio-supervision-universe.md) · Auditoría Lab: [`docs/engineering/audit-pack-post-audits-2026-08-03.md`](./docs/engineering/audit-pack-post-audits-2026-08-03.md) · Canales: [`audit-pack-estudio-asesor-canales`](./docs/engineering/audit-pack-estudio-asesor-canales-2026-08-04.md) · Prep AUTO: [`audit-pack-pre-auto-a0-a5`](./docs/engineering/audit-pack-pre-auto-a0-a5-2026-08-04.md) · HELP: [`docs/HELP.md`](./docs/HELP.md).

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

Documentación completa del cutover: [`docs/CUTOVER_PYTHON.md`](./docs/CUTOVER_PYTHON.md).

## Scripts

| Comando                           | Descripción                                                 |
| --------------------------------- | ----------------------------------------------------------- |
| `pnpm dev`                        | API Python + Web (recomendado)                              |
| `pnpm dev:web`                    | Solo frontend                                               |
| `pnpm dev:log`                    | Igual que dev con logs en `logs/dev/`                       |
| `pnpm test`                       | Tests unitarios frontend                                    |
| `pnpm test:py`                    | Tests Python (API, analytics, market)                       |
| `pnpm test:py:install`            | Instalar paquetes Python editables                          |
| `pnpm test:operativa`             | **DÍA D + CORE-R** (web + py + smoke API opcional)          |
| `pnpm test:operativa:smoke`       | Smoke API live (FA asOf, Evidence, CORE-R)                  |
| `pnpm test:semi`                  | **SEMI DEMO** libro + F3 + geo + cola BD (web + py + smoke) |
| `pnpm test:semi:smoke`            | Smoke API live cola F3 + propose country                    |
| `pnpm test:fa`                    | Batería FA / FIE                                            |
| `pnpm test:coach`                 | Embudo / Lista AUTO / CORE-P (+ smoke API opcional)         |
| `pnpm test:coach:smoke`           | Smoke API CORE-P multi-perfil (SKIP si API down)            |
| `pnpm test:coach:api`             | ASGI multi-perfil (DB) + smoke live                         |
| `pnpm health`                     | Health check API (:8000) + Web                              |
| `pnpm db:ensure`                  | Docker + PostgreSQL + seed IBEX                             |
| `pnpm setup`                      | Setup completo del proyecto                                 |
| `pnpm build`                      | Build monorepo                                              |
| `node scripts/dev-api-python.mjs` | Solo API Python                                             |

## Auth (opcional)

En `.env` raíz:

```env
# APP_PASSWORD=mi-clave   # descomenta para exigir login
# APP_AUTH_SECRET=<token aleatorio>  # obligatorio (y nunca 'bolsa-dev-secret') si APP_PASSWORD está definido
```

Sin `APP_PASSWORD` la app entra directamente (modo desarrollo), y `APP_AUTH_SECRET` puede quedar vacío. Si activas `APP_PASSWORD`, define `APP_AUTH_SECRET` con un valor aleatorio (p. ej. `python -c "import secrets; print(secrets.token_urlsafe(48))"`); el arranque falla si lo dejas vacío o igual a `bolsa-dev-secret`.

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
packages/database → Prisma schema + seed PostgreSQL
scripts/          → run-dev, db-ensure, health-check, research batteries
docs/             → arquitectura, cutover, ADRs, engineering
```

## Documentación

| Documento                                                                                                                  | Contenido                                    |
| -------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| [`docs/HELP.md`](./docs/HELP.md)                                                                                           | Mapa Ayuda ↔ trackers (`HELP_CONTENT_AS_OF`) |
| [`docs/engineering/session-handoff-2026-08-01.md`](./docs/engineering/session-handoff-2026-08-01.md)                       | **Handoff** cierre racha · smoke UI humano   |
| [`docs/engineering/session-handoff-2026-07-31.md`](./docs/engineering/session-handoff-2026-07-31.md)                       | Handoff cierre DÍA D + CORE-R                |
| [`docs/engineering/operativa-test-plan-2026-07-31.md`](./docs/engineering/operativa-test-plan-2026-07-31.md)               | Plan smoke UI DÍA D + CORE-R                 |
| [`docs/engineering/backtesting-dia-d-premises-2026-07-31.md`](./docs/engineering/backtesting-dia-d-premises-2026-07-31.md) | Premisas DÍA D                               |
| [`docs/engineering/research-lifecycle.md`](./docs/engineering/research-lifecycle.md)                                       | Flujo BT → Finalistas → Monitor              |
| [`docs/ONBOARDING.md`](./docs/ONBOARDING.md)                                                                               | Guía para nuevos desarrolladores             |
| [`docs/API_REFERENCE.md`](./docs/API_REFERENCE.md)                                                                         | Endpoints HTTP                               |
| [`docs/UI_PLATFORM.md`](./docs/UI_PLATFORM.md)                                                                             | Shell ProRealTime                            |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)                                                                           | Capas y diagrama                             |
| [`docs/adr/008-investment-accounts-and-ledger.md`](./docs/adr/008-investment-accounts-and-ledger.md)                       | Cuentas + ledger                             |
| [`docs/LEGACY.md`](./docs/LEGACY.md)                                                                                       | Stack TS archivado (git history)             |
| [`docs/README.md`](./docs/README.md)                                                                                       | Índice completo                              |

## Rutas frontend

`/overview` · `/trading` · `/backtests` · `/portfolio` · `/accounts` · `/operations` · `/history` · `/fiscal`

## Roadmap

- **Cuentas + ledger + comisiones + fiscal** ✓
- **Backtesting embudo + Lista AUTO + Finalistas A/C** ✓
- **DÍA D v0.11 + CORE-R v1.8** ✓ 2026-07-31 / 2026-08-01
- **FA / FIE** ✓ código (Composite **v1.1** · CAPM Tarjeta v0 · cobertura Yahoo); **smoke UI / checklist APP** pendiente
- **CORE-B Lab** ✓ v0.2 (meseta + familia por horizonte)
- **Congelado:** auto-paper D execute · Lab UI P3–P9 / Belief · CORE-R multi-dispositivo
- **Deuda:** Alembic baseline, transferencias, dividendos, OpenAPI client
