# Traspaso M4 — Infraestructura / modelo de datos (Prisma vs SQLAlchemy · Alembic · repos) · 2026-08-10

> **Este documento es el punto de entrada para el chat/hilo que ejecute M4.**
> Resumen ejecutivo del **estado verificado** del repo tras cerrar M3 (2026-08-10, mañana),
> preparado para continuar en un **hilo nuevo** sin perder contexto. No se re-descubre nada:
> cada hecho de abajo está confirmado en el repo/CI.

## 0. Qué es M4 (fuente: `docs/engineering/general-audit-plan-2026-08-10.md` §5)

Fila de la tabla de módulos:

> **M4 — Infraestructura / modelo de datos** (Prisma vs SQLAlchemy) | Fuente de verdad única del
> modelo, Alembic, repos | Riesgo **Alto** | Prioridad ★★★

Orden sugerido del plan 08-10:
1. **M0** (docs) — cerrado
2. **M1 + M2** (reproducibilidad/versiones) — cerrados
3. **M3 / M4 / M6** (backend por capas) → **M3 cerrado** (`db7e5e5`), **M4 es el siguiente**
4. **M5** (frontend por features) — lo más grande, dividido
5. **M7** (dev-stack residual F3.7)

## 1. Protocolo sagrado (leer y respetar — mismo que M1/M2/M3)

1. **Tolerancia cero a fallos.** No asumir: verificar siempre en el repo/CI.
2. **Preservación funcional absoluta.** Un cambio solo si es necesario y probado.
3. **Alcance atómico.** Un módulo por hilo; no tocar nada ajeno a M4 (ni M3 domain/application, ni
   M5 frontend).
4. **Flujo en 3 fases:** FASE 1 (diagnóstico, sin cambios) → FASE 2 (plan atómico + aprobación del
   usuario) → FASE 3 (ejecución + batería + commit + push + registro). Sin aprobación explícita
   **no se toca código ni se commitea.**
5. **Docs como fuente de verdad.** Anclar decisiones a ficheros reales.
6. «No romper NADA»: batería completa de tests antes y después.

## 2. Estado del repo al crear este traspaso (2026-08-10, tras M3)

- Rama activa: `stage/estudio-membership-operativa-2026-08-04`.
- HEAD: `db7e5e5` (cierre M3 — retirada de código muerto + registro §7.3). **Working tree limpio**,
  sincronizado con `origin/<rama>`.
- Commit M3: `db7e5e5` "M3: retirar código muerto en capa de dominio (portfolio.py huérfano,
  bar_timestamp_from_date) + privatizar compute_realized_gains + registro docs" (6 ficheros, +55/−14).

### Commits de módulos anteriores (todos pusheados, CI verde)

| Commit | Módulo / contenido |
| ------ | ----------------- |
| `20ecad0` | M2 · @types react/react-dom 19.2.18/19.2.4 (range ^) |
| `ae79c62` | M2 · Fix CI frontend: paso `Build shared` (dist de @bolsa/shared) |
| `57d81cd` | M2 · Fix CI: declarar @types/node en web (TS2580 process) |
| `0469fa2` | M2 · Registro docs §7.2 |
| `b82b48c` | docs · Traspaso M3 (entrada) |
| `db7e5e5` | M3 · Cierre capa de dominio + registro §7.3 |

## 3. Hechos de diagnóstico confirmados (relevantes para M4)

- **Python:** todo `hatchling`, `requires-python >=3.12`, un gestor (uv). `uv.lock` commiteado en M1
  → reproducible. `vectorbt` conservado/fijado (`==1.1.0`, mantenimiento parado).
- **Batería (verde tras M3):**
  - `ruff` solo el `B007` conocido (`packages/py/infrastructure/tests/test_daily_ops_digest_pdf.py:54`,
    variable `day`) — mini-módulo de higiene M0 **alternativo/independiente** a M4.
  - `pytest` **663 passed / 2 failed** — los 2 fallos (`test_list_unsubscribe_index.py`) son
    **pre-existentes** (documentados en dev-continuation §4j / M1), ajenos.
  - `mypy` deuda pre-existente no bloqueante (`continue-on-error` en CI): 561 en el conjunto CI
    (domain 8, application 107).
- **Batería pytest CI** (`python-ci.yml`): `pytest packages/py/market/tests packages/py/analytics/tests
  apps/api-python/tests` con `--ignore=apps/api-python/tests/integration --ignore=apps/api-python/tests/
  test_lists.py --ignore=apps/api-python/tests/test_workspaces.py`. `mypy` corre sobre
  `domain/src market/src infrastructure/src apps/api-python/src --follow-imports=silent`.
- **Nota entorno Windows:** `uv` **NO** está en PATH de PowerShell; usar ruta completa
  `$env:USERPROFILE\.local\bin\uv.exe`. Patrón de commit: `git commit --no-verify` (hook lint-staged
  dispara prettier sobre ficheros legacy con CRLF desincronizado; documentado desde M1).

## 4. Frentes a resolver (para el chat M4 — heredados, no consensuados)

Esto **no** es un plan consensuado, es el diagnóstico heredado + elaborado. El chat M4 debe, en FASE 1
(diagnóstico, **sin cambios**):

1. **Mapear `packages/py/infrastructure` + `packages/database` + `apps/api-python`**: paquetes,
   módulos, dependencias entre ellos y hacia la aplicación/dominio. Confirmar el inventario real.
   - `bolsa_infrastructure` (~60 ficheros): `database/repositories/*` (repos `SqlAlchemy*` concretos),
     `database/models/` (`__init__.py`, `tables.py`), `alerts/*` (channels, digest PDF/email),
     `cache/*` (redis_feature_cache, feature_cache_factory), `queue/*` (worker_heartbeat),
     `config.py`, `ids.py`, `database/session.py`.
   - `packages/database/prisma/schema.prisma` (**fuente del modelo Prisma**, PostgreSQL, enums
     InstrumentType/Timeframe/DataProvider/SyncStatus/TransactionType...).
   - `apps/api-python` (FastAPI · "capa HTTP fina" de la que se importan use-cases de application).
2. **Auditar la fuente de verdad única del modelo**: `Prisma (packages/database)` vs
   `SQLAlchemy (bolsa_infrastructure)` — ¿quién es el dueño del esquema? Alembic vs Prisma migrate.
   Ver `docs/adr/*` (especialmente el de backend Python, p.ej. ADR-003) y `docs/DATA_MODEL.md`.
3. **Alembic / migraciones**: `alembic>=1.14` en infrastructure; evaluar consistencia con Prisma
   (`packages/database`), fuentes actuales de migración y cómo se aplican.
4. **Repos en infrastructure**: implementaciones concretas `SqlAlchemy*` que application consumen en
   el cuerpo (no solo inyectadas). Frente de acoplamiento detectado en M3: **application importa
   infrastructure en el cuerpo** (no solo en handlers de api) — p.ej. `accounts.py`, `execution_router.py`,
   `instrument_lifecycle.py`, `account_lifecycle.py`, `scan_jobs.py`, `market_indices.py`, ... M4 puede
   abordar la consolidación del modelo de datos y repos sin tocar la semántica de use-cases.
5. **Preservación funcional absoluta**: el modelo de datos es lo más sensible (riesgo **Alto**); cada
   decisión (crear/renombrar/borrar tablas, unificar modelo) requiere plan atómico + batería completa.
6. **No tocar** `py/domain` + `py/application` (M3, salvo el acoplamiento de import que ya apunta a
   M4) ni el frontend web por features (M5).
7. **Batería backend del módulo** (plan §5): `ruff` + `mypy` + `pytest` (referencia del cierre M3:
   ruff solo `B007`, pytest 663 passed / 2 pre-existentes, mypy deuda no bloqueante).

## 5. Documentos fuente de verdad / índices

- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/general-audit-plan-2026-08-10.md` (§4 hallazgos, §5 módulos, §7 registros M0)
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.1 M1, §7.2 M2, §7.3 M3)
- `docs/engineering/traspaso-m3-dominio-2026-08-10.md` (precedente más reciente del patrón)
- `docs/engineering/traspaso-m2-versiones-frontend-2026-08-10.md` · `traspaso-m1-reproducibilidad-backend-2026-08-10.md`
- `docs/ARCHITECTURE.md` · `docs/PROJECT_PREMISES.md` · `docs/DATA_MODEL.md` · `docs/adr/*` ·
  `packages/py/*/pyproject.toml` · `packages/database/prisma/schema.prisma`

> Al cierre de M4 (FASE 3), actualizar `dev-continuation-plan-2026-08-09.md` con una sección 7.4
> nueva y añadir/confirmar este fichero en el índice engineering (bajo Product/Ops, junto a los
> traspasos).
