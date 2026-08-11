# Traspaso — F3a Arquitectura de procesos y DB (2026-08-11)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de la Auditoría consolidada, junto a F1/F2/F3b/F5a).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (P0.4/P0.5/P1.2 + D0–D5) · [traspaso-f5a-contratos-fe-be-2026-08-11.md](./traspaso-f5a-contratos-fe-be-2026-08-11.md) (§6 deuda → F3a) · [traspaso-f3b-alembic-data-epoch-2026-08-11.md](./traspaso-f3b-alembic-data-epoch-2026-08-11.md) (§6 deuda → F3a/F4).
> **Rama de ejecución:** `stage/f3a-procesos-db-2026-08-11` (desgajada desde `stage/f1-*`, tras merge PR #32).
> **Regla del hilo:** NO tocar código fuera del alcance F3a pactado. Cambios validados con la batería antes del commit.
> **Estado:** F3a EN CURSO (por sub-área, commits atómicos). Ver §7.

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

### P1.2 — ensure_migrated fuera del path (segundo commit atómico)

Detalle en §4 conforme se implementa.

### P0.5 / D2 — Portar DDL a Alembic (tercer commit atómico)

Detalle en §4 conforme se implementa.

[Listado pendiente de completarse en cada sub-área]

## 5. Batería (aplicada)

- Ver §7 por sub-área. Batería obligatoria: `ruff check` + `mypy` (ficheros tocados) + `pytest` (infra/app/analytics/api-python; + infraestructura si se tocan DB/repos) + `pnpm test`/CI si toca web.

## 6. Deuda / fuera de alcance (registrado, NO resuelto)

- **P1.9 (API thin)** — diferido a hilo propio (decidido por el usuario en el arranque de F3a).
- **P0.6 (ciclo analytics↔market) · P1.6 (mypy gate duro) · ruff gates en `packages/py/infrastructure`** → F4.
- **D4 auth** → F5b. **Deuda F5a §6** (fidelidad DTOs, `openapi-fetch`) → fase posterior.

## 7. Registro

| Fecha      | Acción                                                                                                                                                                                                |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Arranque F3a: rama `stage/f3a-procesos-db-2026-08-11` desde `stage/f1-*` (HEAD `8e6d4ee`, tras merge PR #32). Alcance pactado con el usuario: workers + DDL→Alembic + ensure_migrated; P1.9 diferido. |
| 2026-08-11 | P0.4/D3: `scheduler_worker.py` + `main.py` limpio + `pyproject` script + `run-dev.mjs` + tests (3). Battery: ruff✓ · mypy✓ (scheduler_worker + test) · pytest scheduler 3✓.                           |

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto. Al cerrar: preparar el siguiente con su `traspaso-*`, entrada única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 9. Texto exacto de traspaso — siguiente hilo (rellenar al cierre F3a)

_Se completa al cerrar F3a (§4/§5/§6 finales)._
