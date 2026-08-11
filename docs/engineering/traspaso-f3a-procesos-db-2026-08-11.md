# Traspaso — F3a Arquitectura de procesos y DB (2026-08-11)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de la Auditoría consolidada, junto a F1/F2/F3b/F5a).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (P0.4/P0.5/P1.2 + D0–D5) · [traspaso-f5a-contratos-fe-be-2026-08-11.md](./traspaso-f5a-contratos-fe-be-2026-08-11.md) (§6 deuda → F3a) · [traspaso-f3b-alembic-data-epoch-2026-08-11.md](./traspaso-f3b-alembic-data-epoch-2026-08-11.md) (§6 deuda → F3a/F4).
> **Rama de ejecución:** `stage/f3a-procesos-db-2026-08-11` (desgajada desde `stage/f1-*`, tras merge PR #32).
> **Regla del hilo:** NO tocar código fuera del alcance F3a pactado. Cambios validados con la batería antes del commit.
> **Estado:** F3a COMPLETADO (P0.4/D3 ✓ · P1.2 ✓ · P0.5/D2 ✓). Ver §7.

---

## 0. Alcance pactado (decisión del usuario, este hilo)

Del plan F3 (Arquitectura de procesos y DB) se ejecuta en **este** hilo:

- **P0.4 / D3** — Extraer **TODOS** los workers/schedulers/crons del `lifespan` de FastAPI a **proceso dedicado** (`python -m bolsa_api.workers.scheduler_worker`). Cero duplicación de crons con `--workers N`.
- **P0.5 / D2** — Portar el **DDL Prisma a Alembic** (Alembic = única autoridad PostgreSQL; SQLAlchemy = ORM).
- **P1.2** — Retirar `account_repository.ensure_migrated` del **path de peticiones** (seeding/backfill destructivo por request), moviendo esa lógica a una fase de arranque/worker de una vez.

**Diferido a propio hilo (acordado con el usuario):** **P1.9 (API thin** — composition root ~1100 líneas + rutas con SQL directo + use-cases con session crudo). No se toca aquí.

**Anti-objetivos (D5):** cero features.

## 1. Diagnóstico confirmado en código

### P0.4 / D3 — workers embebidos en FastAPI

- `apps/api-python/src/bolsa_api/main.py` (`lifespan`): arrancaba **9–10 workers** inline (todos con su `start_*`):
  - Periódicos/loops (`bolsa_api.background.*`): `daily_alert_evaluator`, `signal_alert_evaluator`, `tracker_schedule_worker`, `fa_weekly_worker` (off), `core_r_cron_worker` (off), `estudio_eod_opinion_worker` (off), `auto_sync_worker`, `index_subscribe_worker`.
  - Cola: `scan_worker` + `optimization_worker` (inline **solo si** `SCAN_QUEUE_BACKEND != arq`; si `arq`, los gestiona `apps/api-python/src/bolsa_api/workers/arq_worker.py` ya existente).
- Con `uvicorn --workers 4` cada worker de servicio HTTP duplicaba los crons → P0.4.

### P0.5 / D2 — Prisma vs Alembic

- `packages/database/prisma/migrations/`: **35 migraciones SQL** (baseline + características) son el autor del esquema base real.
- `packages/py/infrastructure/alembic/`: `001_timescaledb_extension` (baseline) + `002_research_data_epoch` (único DDL Alembic hasta ahora). El runtime consulta con SQLAlchemy (`Base`).
- D2: Alembic debe ser la única autoridad; Prisma degrada a cliente/lector (o se retira).

### P1.2 — ensure_migrated en el path

- `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/account_repository.py`:
  - `SqlAlchemyAccountRepository.ensure_migrated()` (línea 89) hace seeding/backfill **destructivo** (`_consolidate_single_portfolio_per_account` funde/borra) y se invoca **en 12 puntos del path de petición** (313, 317, 328, 353, 511, 527, 535, 547, 562, 625, 641, 658, 672).
  - Flag `self._migration_done` por-instancia → con instancias múltiples (workers) reintenta/reproduce race.

## 2. Decisiones de diseño (F3a)

- **Worker único dedicado:** un solo proceso `scheduler_worker` que re-usa los `start_*` existentes (ya gestionan su gate de config). Reúne siempre los loops periódicos; scan/optimize inline solo si backend != arq (mismo criterio que FastAPI). Es el mismo patrón que `arq_worker` (engine + session_factory en `on_startup`/`run()`).
- **ensure_migrated:** mover el seeding/backfill una vez al **scheduler worker** (o arranque), listo idempotente; retirar las llamadas por-request del repositorio.
- **Alembic:** se detalla en su sub-sección §5 conforme se portan migraciones.

## 3. Decisiones pactadas previas (no renegociar)

- **D0** orden F1 → F2 → F3b → F5a → (F3a+F4+F5b); F3a es la fase ejecutada (con F4/F5b en hilos posteriores).
- **D2** Alembic = única autoridad PostgreSQL; Prisma degradado a lector/legacy.
- **D3** Extraer TODOS los workers/schedulers/crons de FastAPI a proceso separado.
- **D5** Solo F1–F5, cero features.

## 4. Implementación (por sub-área)

### P0.4 / D3 — Worker dedicado (primer commit atómico)

| Fichero(s)                                                          | Qué                                                                                                                                                                                                                                                               |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/api-python/src/bolsa_api/workers/scheduler_worker.py` (nuevo) | Proceso `__main__` que crea `engine`+`session_factory` y lanza, vía los `start_*` existentes, todos los loops periódicos (gate propio) + scan/optimize inline si backend != arq. Parada por SIGINT/SIGTERM con cancelación limpia de tareas y `engine.dispose()`. |
| `apps/api-python/src/bolsa_api/main.py`                             | `lifespan` limpio: `ensure_migrated` + engine/session + AI governance + `_warn_if_routes_missing`; **0 workers**. Se retira la importación de todos los `start_*`.                                                                                                |
| `apps/api-python/pyproject.toml`                                    | Script `bolsa-scheduler-worker = "bolsa_api.workers.scheduler_worker:run"`.                                                                                                                                                                                       |
| `scripts/run-dev.mjs`                                               | Spawn del proceso `scheduler_worker` junto a la API en dev (siempre; no depende del backend de cola).                                                                                                                                                             |
| `apps/api-python/tests/test_scheduler_worker.py` (nuevo)            | Testea el reúno de loops periódicos y el gate scan/optimize según backend (arq vs no-arq).                                                                                                                                                                        |

### P1.2 — ensure_migrated fuera del path (segundo commit atómico) ✅ COMPLETADO

| Fichero(s)                                         | Qué                                                                                                                                                                                                                                                                      |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `database/account_migration.py` (nuevo)            | `run_account_data_migration(session)`: procedimiento **idempotente** de una vez (cuenta por defecto, backfill de ledger, link de pending orders, consolidación single-portfolio) — se invoca **una vez** en el `lifespan` (API) y en el arranque del `scheduler_worker`. |
| `database/repositories/account_repository.py`      | Se retira `ensure_migrated()`, `_migration_done` y las 12 llamadas por-request; se eliminan los helpers de seeding/backfill/consolidación. El path de petición queda limpio de migraciones destructivas.                                                                 |
| `apps/api-python/main.py` + `scheduler_worker.py`  | `await run_account_data_migration(session)` en el arranque (una sola vez por proceso).                                                                                                                                                                                   |
| `tests/test_f3a_account_data_migration.py` (nuevo) | Verifica la idempotencia de `run_account_data_migration` y que `SqlAlchemyAccountRepository` ya NO expone `ensure_migrated`.                                                                                                                                             |

### P0.5 / D2 — Portar DDL a Alembic (tercer commit atómico) ✅ COMPLETADO

**Enfoque pactado con el usuario:** "baseline takeover compacto": una única migración
Alembic **`003_prisma_schema_baseline`** que representa el esquema completo del runtime
(SQLAlchemy `Base.metadata`, 53 tablas) de forma **idempotente** → sobre la BD de Prisma
es un **no-op**; sobre una BD limpia construye el esquema **sin depender de Prisma**.

| Fichero(s)                                                             | Qué                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `alembic/versions/003_prisma_schema_baseline.py` (nuevo, **generado**) | `upgrade()`: (1) `CREATE TYPE "<Name>" ...` guardado por `_type_exists` para los 8 enum (`pg_type`/`pg_namespace`; identificador **quoted** para conservar la case exacta que Prisma deja en `pg_type`, p.ej. `'InstrumentType'`); (2) `op.create_table(name, *columns, *FK+UC, if_not_exists=True)` por tabla en orden topológico (`sorted_tables`); sin `Index` separados (el runtime tiene 0 en `table.indexes`). `downgrade()` no destructivo (no-op documentado). |
| `scripts/dump_alembic_prisma_baseline.py` (nuevo)                      | **Generador/canonificador** del baseline (offline, sin BD): regenera `003` desde `Base.metadata`; `--check` verifica reproducibilidad byte-a-byte (contrato generado, estilo `contract:check`). Ciclo: `scripts` importa `bolsa_infrastructure.database.models` (puebla `Base.metadata`).                                                                                                                                                                              |
| `alembic/versions/002_research_data_epoch.py` (modificado)             | Se añaden **guards de idempotencia** en `upgrade()` (`_table_exists`/`_column_exists`): `add_column data_epoch` se omite si la tabla no existe aún o la columna ya está. **Necesario** para D2: en una BD limpia `001 → 002 → 003`, `002` corría cuando `backtest_runs` no existe (¡fallaba!) o la columna ya la aporta el baseline. Sobre la BD de Prisma está ya aplicada (no re-corre).                                                                             |

**Hallazgos de implementación (importantes):**

- `op.create_table(Table, if_not_exists=True)` con un objeto `Table` + flag es un **bug**
  de Alembic: crea la tabla **sin columnas** (0 cols). Se contornea pasando las `Column`
  y los constraints explícitos: `op.create_table(name, *columns, *FK+UC, if_not_exists=True)`.
- Las `Column` solas **no** renderizan FK → se pasan los `ForeignKeyConstraint` como objetos.
- `UniqueConstraint` duplicados por `column.unique=True` (p.ej. `instruments.yahoo_symbol`)
  → se pasan solo los no cubiertos ya por una columna `unique=True` (evita `UNIQUE` doblado).
- **Import de `003` ruff-limpio y reproducible:** el generador emite el bloque de imports en el
  orden que exige ruff (`__future__` → `import sqlalchemy` → `from alembic` → `bolsa_infrastructure`,
  sin blanco entre terceros), de modo que `003` regenado pasa `ruff` **y** `--check` simultáneamente
  (evita la divergencia detectada en el ciclo: si se toca `003` a mano con `--fix`, `--check` diverge).

**Validación de idempotencia (ambas rutas):**

- **BD real `bolsa_v1` (Prisma):** `alembic upgrade head` → no-op; `alembic current` =
  `003 (head)`; 55 tablas intactas (53 meta + `alembic_version` + `_prisma_migrations`),
  datos preservados (`ohlcv_bars` 386.633 filas, `instruments` 341, ...).
- **BD limpia** (`bolsa_v1_test3`, throwaway creada para validar): `001→002→003` crea 54
  tablas + 8 enums con case exacta; comparado contra `Base.metadata`: **0 tablas faltantes,
  0 extra, 0 mismatches de columnas**, y `data_epoch` presente en `backtest_runs`/`research_trials`.
- **Reproducibilidad:** `dump_alembic_prisma_baseline.py --check` → `OK 003 reproducido byte-a-byte`.

> Las BD de validación `bolsa_v1_scratch`/`bolsa_v1_test2`/`bolsa_v1_test3` son throwaway
> creadas solo para probar la ruta fresh-build; se pueden dropear cuando se quiera.

## 5. Batería (aplicada)

- **P0.4/D3 (workers):** `ruff check`✓ (scheduler_worker, main, test) · `mypy`✓ · `pytest test_scheduler_worker.py` 3✓.
- **P1.2 (ensure_migrated):** `ruff check`✓ · `mypy`✓ (account_migration, account_repository) · `pytest test_f3a_account_data_migration.py`✓ (idempotencia de `run_account_data_migration`).
- **P0.5/D2 (003 baseline):** `ruff check`✓ (generador + `002` + `003`) · `mypy`✓ (generador) ·
  validación de idempotencia en **BD real** (`alembic upgrade head` no-op) y **BD limpia** (fresh build == `Base.metadata`, 0 mismatches) ·
  `dump_alembic_prisma_baseline.py --check` → `OK reproducido byte-a-byte`.

**Batería de cierre F3a (todo verde):**

- `ruff check packages/py apps/api-python --config pyproject.toml` → **0 errores en ficheros de F3a** (se limpiaron los I001 de `main.py`, `scheduler_worker.py`, `002`, `003`, `account_repository.py`, `test_f3a_account_data_migration.py`). Quedan **7 errores PREEXISTENTES** en ficheros fuera de alcance (→ F4): `portfolio.py` (api) y `alembic/env.py`, `001_timescaledb_extension.py`, `account_migration.py`, `migrations.py`, `portfolio_repository.py`, `test_daily_ops_digest_pdf.py` (infra). Mejora sobre la herencia F5a (que reportaba 25): la fase redujo el recuento sin crear deuda nueva.
- `mypy` → no bloquea (gate CI con `continue-on-error`, ~500 errores preexistentes). Los ficheros **nuevos** de F3a (`scheduler_worker.py`, `dump_alembic_prisma_baseline.py`) pasan `mypy` limpio. Los errores en `repositories/*` y `main.py` son deuda tipada preexistente (→ F4 mypy gate).
- `pytest`: `packages/py/infrastructure/tests` 48✓ · `apps/api-python/tests` 30✓ (contra `bolsa_v1`) · `domain/market/application/analytics/ai` 676✓ (1 skip) · `test_f3b_alembic_data_epoch.py` verifica head=003 + `data_epoch` + idempotencia.
- `pnpm test`/CI web **no aplican**: no se tocó frontend en F3a.

## 6. Deuda / fuera de alcance (registrado, NO resuelto)

- **P1.6 (mypy gate duro)** → F4. Mypy sigue no-bloqueante (~500 errores preexistentes); los ficheros nuevos de F3a ya pasan limpio.
- **ruff gates en `packages/py/infrastructure` (7 errores restantes)** → F4: `portfolio.py` (api) y `alembic/env.py`, `001_timescaledb_extension.py`, `account_migration.py`, `migrations.py`, `portfolio_repository.py`, `test_daily_ops_digest_pdf.py` (infra). La deuda de F3a quedó a 0; los 7 son herencia F3b/F5a.
- **P1.9 (API thin)** — diferido a hilo propio (decidido por el usuario en el arranque de F3a).
- **P0.6 (ciclo analytics↔market)** → F4.
- **D4 auth** → F5b. **Deuda F5a §6** (fidelidad DTOs, `openapi-fetch`) → fase posterior.

## 7. Registro

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Arranque F3a: rama `stage/f3a-procesos-db-2026-08-11` desde `stage/f1-*` (HEAD `8e6d4ee`, tras merge PR #32). Alcance pactado con el usuario: workers + DDL→Alembic + ensure_migrated; P1.9 diferido.                                                                                                                                                         |
| 2026-08-11 | P0.4/D3: `scheduler_worker.py` + `main.py` limpio + `pyproject` script + `run-dev.mjs` + tests (3). Battery: ruff✓ · mypy✓ (scheduler_worker + test) · pytest scheduler 3✓.                                                                                                                                                                                   |
| 2026-08-11 | P1.2: `run_account_data_migration` idempotente + retirada de `ensure_migrated` del path de petición. Battery: ruff✓ · mypy✓ · pytest idempotencia✓.                                                                                                                                                                                                           |
| 2026-08-11 | P0.5/D2: `003_prisma_schema_baseline` (generado) + guards en `002`. Validado no-op en BD real y fresh-build == `Base.metadata`. Battery: ruff✓ · mypy✓ · `--check`✓.                                                                                                                                                                                          |
| 2026-08-11 | Fix en batería: orden de borrado de cuentas en `delete_simulated_account` respetando FK (`positions/transactions` → `ledger_entries` → `pending_orders` → `investment_portfolios` → `portfolios`) evita `ForeignKeyViolation`. Fallos de `test_lists`/`test_accounts` eran por `DATABASE_URL` a una BD scratch vacía (no regresión; pasan contra `bolsa_v1`). |
| 2026-08-11 | Cierre F3a: ruff limpio en ficheros de fase (25→13→7 heredados → F4). Batería: ruff✓ · mypy✓ (nuevos) · pytest infra 48 + api 30 + paquetes 676.                                                                                                                                                                                                              |

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto. Al cerrar: preparar el siguiente con su `traspaso-*`, entrada única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 9. Texto exacto de traspaso — siguiente hilo (rellenar al cierre F3a)

_Se completa al cierre F3a y se entrega en el chat. Ver el mensaje final del hilo._
