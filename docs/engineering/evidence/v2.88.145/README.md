# Evidencia `v2.88.145-beta` — la operativa diaria AUTO **por valor** ya se calcula y se ve: cola durable de jobs, parte por valor y DÍA-D manual desde la UI

> **Bump:** `2.11.144-beta` → **`2.11.145-beta`** (`package.json` + `meta.bump` de los **13** CLIs; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **en verde**).
>
> **Naturaleza:** incremento **de operación + producto + observabilidad** sobre el espacio AUTO — **no** toca el motor de decisión, ni umbrales, ni pesos A/B: **`Δ motor = 0`** · **`Δ decisión = 0`** · **contrato HTTP ADITIVO** (`POST/GET /api/auto/ops-jobs`, `GET /api/auto/estudio-daily`; `contract:check` **OK**) · **migración aditiva** `056_auto_ops_jobs` (head `055_dia_d_identity_nullable`). Tag **unsigned**.
>
> **Base:** `v2.88.144-beta`.

## 1. El hueco (verificado en código, no supuesto)

| Pieza | Antes | Consecuencia |
| --- | --- | --- |
| [`estudio_eod_opinion_worker`](../../../../apps/api-python/src/bolsa_api/background/estudio_eod_opinion_worker.py) | bucle con `logger.debug("... tick (noop ...)")`; el batch real sólo corría por HTTP con `force=true` | la generación diaria **no existía** sin que alguien pulsara un botón |
| [`v2_89_dia_d_auto_replay`](../../../../apps/api-python/scripts/v2_89_dia_d_auto_replay.py) | CLI manual; la API sólo leía `operability_runs/dia-d-auto/dia-d-auto-<D>.json` | el replay DÍA-D **no se podía lanzar desde la UI** |
| [Alertas](../../../../apps/web/src/features/alerts/signal-alerts-section.tsx) | clave `["signal-alerts"]` **sin cuenta**; errores de lectura/mutación convertidos en listas vacías | fuga de caché entre cuentas y un fallo indistinguible de «no hay nada» |
| Vista AUTO | sólo OPERATIVA y DÍA-D | la señal, la decisión, la operación y la validación **nunca se veían juntas por valor** |

## 2. E1 — Alertas ancladas a la cuenta y errores visibles

- [`alerts-page.tsx`](../../../../apps/web/src/features/alerts/alerts-page.tsx) y [`signal-alerts-section.tsx`](../../../../apps/web/src/features/alerts/signal-alerts-section.tsx): claves `["alerts", effectiveAccountId]` y `["signal-alerts", effectiveAccountId]`, `enabled: Boolean(effectiveAccountId)`, `placeholderData: keepPreviousData` **no** usado para esconder un error, invalidación exacta tras cada mutación.
- Sin cuenta: consultas y acciones **deshabilitadas**. `isError`: mensaje + **Reintentar**, nunca lista vacía. Fallo de crear/borrar/reactivar/resetear: error visible; sólo la fila afectada se deshabilita (vía `mutation.variables`).
- Tests nuevos: [`alerts-page.test.tsx`](../../../../apps/web/src/features/alerts/alerts-page.test.tsx) + [`signal-alerts-section.test.tsx`](../../../../apps/web/src/features/alerts/signal-alerts-section.test.tsx): cambio A→B sin datos de A, error 500 ≠ «No hay…», fallo de borrado/reactivación visible.

## 3. E2 — Una sola ruta de ejecución: `auto_ops_jobs`

- Migración [`056_auto_ops_jobs.py`](../../../../packages/py/infrastructure/alembic/versions/056_auto_ops_jobs.py): tabla `auto_ops_jobs` con `kind` (`estudio_daily` | `dia_d_replay`), `status` (`queued|running|completed|failed`), `account_id`, `day`, `payload`, `progress`, `result`, `error`, `attempt`, `created_at`, `started_at`, `finished_at`, `heartbeat_at`. **Índice único parcial** `(kind, coalesce(account_id,''), day) WHERE status IN ('queued','running')`: el scheduler y el botón manual encolan el **mismo** job y el segundo encolado devuelve el activo (idempotencia por clave, no por suerte).
- Modelo [`auto_ops_job.py`](../../../../packages/py/domain/src/bolsa_domain/entities/auto_ops_job.py), repositorio [`auto_ops_job_repository.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/auto_ops_job_repository.py) y casos de uso [`auto_ops_jobs.py`](../../../../packages/py/application/src/bolsa_application/auto_ops_jobs.py): encolar, leer, reclamar, publicar progreso, completar, fallar y recuperar jobs con heartbeat viejo.
- Worker [`auto_ops_job_worker.py`](../../../../apps/api-python/src/bolsa_api/background/auto_ops_job_worker.py), registrado en [`scheduler_worker.py`](../../../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py): tick 2–5 s, heartbeat, timeout por `kind`, despacho por `kind`, `kill` y error con cola de `stderr` en el replay.
- [`estudio_eod_opinion_worker.py`](../../../../apps/api-python/src/bolsa_api/background/estudio_eod_opinion_worker.py) **deja de ser un noop**: una vez por día UTC encola `estudio_daily`; dedupe por día y reintento acotado (`_MAX_ATTEMPTS_PER_DAY`) cuando el job falló. Interruptor `ESTUDIO_EOD_OPINION_ENABLED` (**ON por defecto**, opt-out documentado).
- Rutas [`auto_ops_jobs.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_ops_jobs.py) y [`auto_estudio_daily.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_daily.py) con `require_account_access`: **cuenta ajena ⇒ 404 sin detalles**, nunca 403 con información.

### 3.1 Generación diaria por valor

[`estudio_daily_ops.py`](../../../../packages/py/application/src/bolsa_application/estudio_daily_ops.py):

- Universo con `resolve_estudio_universe` / lista canónica ESTUDIO **fail-closed**: `ok` | `empty` | `unavailable` ⇒ sin universo **no se escribe ninguna opinión** y el job **falla con motivo** (cero opiniones, medido en test).
- *Hints* **server-side** (composite `execute_chips(horizon="swing", regime="neutral")`, fundamentals `execute_chips(ids)` y posiciones de la cuenta); **nada** de `allowTrading: true` / `hasEodBar: true` hardcodeados.
- `DailyOpinionService.run_eod_batch(ids, as_of, account_id, force=True)`: idempotente por la clave natural `(instrument_id, as_of_bar_date, source)`.
- `ProposeEstudioAutoOpenings` en **dry-run** (`execute=false`) con las opiniones recién calculadas; [`estudio_auto_hits.py`](../../../../packages/py/application/src/bolsa_application/estudio_auto_hits.py) acepta `hints` y `opinionSource="eod_batch"`.
- `result` guarda **una fila por valor**: opinión, plan (`entry`, `structuralStop`, `target1`, `target2`, `riskAmount`, `expectedRr`, `whyNot`, `strategyDefinitionId`), `hits`/`skipped` y estado `ok|no_signal|no_plan|error`. **Un fallo de un valor no aborta el batch**; los contadores suman `N`.

## 4. E3 — DÍA-D ejecutable desde la UI

- [`v2_89_dia_d_auto_replay.py`](../../../../apps/api-python/scripts/v2_89_dia_d_auto_replay.py): `--progress-jsonl` con fases `starting` → `loading_bars` → `replay` → `reading_facts` → `writing_artifact` → `done`; artefacto escrito **atómicamente** (`tmp` + `os.replace`). Un fallo no deja un JSON parcial que la API lea como bueno.
- [`v2_87_replay_oos_durable_cycle.py`](../../../../apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py): callback opcional `on_tick(done, total)` ⇒ progreso **real** del replay.
- Handler `dia_d_replay`: `asyncio.create_subprocess_exec(sys.executable, script, "--at", day, "--account-id", account, "--json", "--progress-jsonl", path, cwd=repo_root)`, timeout, `stderr` (tail) y validación final: **exit 0 + artefacto existente + `meta.account == account` + día solicitado**. Un fallo **no** sustituye ni borra el artefacto anterior.
- UI [`dia-d-auto-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx): botón «Ejecutar DÍA-D ahora», estados `queued|running|completed|failed`, fase y barra de progreso, error con detalle y aviso de **artefacto anterior**; al completar invalida `["auto-dia-d-replay-days", accountId]` y `["auto-dia-d-replay", accountId, day]`.

## 5. E4 — «AUTO · Operativa diaria por valor»

- Modo `daily` en [`dia-d-auto-toolbar.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-toolbar.tsx) y [`auto-monitor-page.tsx`](../../../../apps/web/src/features/auto-monitor/auto-monitor-page.tsx); `AUTO_MONITOR_MODES` se exporta desde el toolbar (sin lista duplicada) y el sondeo de `useAutoOperationalMonitor` se desactiva también en `daily`.
- [`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx) + [`use-estudio-daily-ops.ts`](../../../../apps/web/src/features/auto-monitor/use-estudio-daily-ops.ts): cabecera con `asOf`, último run, botón «Calcular operativa diaria», progreso y error; leyenda de los **cuatro estados que nunca se mezclan**; una ficha por valor con símbolo, estrategia + IO/FA/TA, última vela y hora, entrada/stop/objetivo/horizonte, razón, opinión, decisión (`TRIGGERED`/`whyNot`), ciclos durables del audit (enlace a la historia) y validación (veredicto, K, expectancy R, evidencia, costes/drawdown).
- Todo hueco es `absentDataLabel()` = **«Sin dato todavía»**, nunca `0` ni una recomendación inventada. La validación global sigue **`INCONCLUSIVE`** mientras la ventana PAPER no cumpla; **`CONFIRMED` no se emite**.
- Contrato nuevo [`estudio-daily-ops.ts`](../../../../packages/shared/src/estudio-daily-ops.ts) (`AutoOpsJobV1`, `EstudioDailyReportV1`, `EstudioDailyValueV1`, `EstudioDailyPlanV1`, …) exportado por `@bolsa/shared`, métodos en [`api.ts`](../../../../apps/web/src/lib/api.ts), `openapi.json`/`schema.d.ts` regenerados con `contract:gen`.

## 6. Verificación (medida)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Tests web | `pnpm --filter @bolsa/web test` | **312 ficheros / 2289 passed** (incluye `estudio-daily-ops-panel`, `dia-d-auto-run`, `dia-d-auto-toolbar`, `alerts-page`, `signal-alerts-section`) |
| Typecheck web | `pnpm --filter @bolsa/web typecheck` | **OK** |
| Lint web | `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| Tests Python enfocados | `uv run pytest` (migración 056, repositorio/casos de uso, `estudio_daily_ops`, worker, rutas, DÍA-D, bump guard) | **48 passed** |
| Lint Python | `pnpm lint:py` | **`All checks passed!`** |
| Import Linter | `pnpm imports:py` | **`Contracts: 4 kept, 0 broken`** |
| Mypy | `pnpm types:py` | **`Success: no issues found in 565 source files`** |
| Contrato | `pnpm --filter @bolsa/web contract:check` | **OK** |
| Freeze | `pnpm window:freeze` | **OK** (`22ba29e3`; `apps` `0a49a43b` / `packages` `5bc5c3eb`) |
| Rango de migraciones | test de revisión/alembic | `056` con id ≤ 32 y linaje desde `055_dia_d_identity_nullable` |

### 6.1 E2E (medido)

| Spec | Comando | Resultado |
| --- | --- | --- |
| Mock nuevo | `E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-e2e-v290-auto-estudio-daily-mock` | **5 passed** — cuatro estados con huecos («Sin dato todavía», nunca `0`), job con progreso y desenlace, DÍA-D manual, API caída ≠ vacío, sin parte ≠ datos inventados |
| Regresión AUTO mock | `gp-e2e-s5-...-mock`, `gp-e2e-v28856`, `gp-e2e-v28865` | **20 passed** |
| Integrado | [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts) | **spec extendido, NO ejecutado aquí** (requiere API + PostgreSQL + worker + barras sembradas). Un `skipped` **no** cuenta como prueba superada. |

## 7. Límites declarados (sin fabricar)

- **Los jobs quedan `queued` si el worker no está arrancado.** La cola es durable; el progreso sólo avanza con `auto_ops_job_worker` vivo.
- **El batch diario es lento por diseño** (~20 valores × composite + fundamentals + propose): por eso va por cola y no por request síncrono.
- **El replay DÍA-D depende de las barras sembradas**; sin datos, el CLI falla cerrado y el job marca `failed` con motivo, sin tocar el artefacto anterior.
- **La vista nueva es read-only:** no promociona evidencia, no altera la decisión y no desbloquea la ventana PAPER. La ventana real sigue **`0/4` días · `0/2` regímenes · `0/32` ciclos ⇒ `INCONCLUSIVE`**. **No demuestra rentabilidad.**
- **`ESTUDIO_EOD_OPINION_ENABLED=true` por defecto**; en un entorno sin worker el flag no basta: hace falta el proceso. Opt-out documentado en el worker.
- Tag **unsigned**; el `Release tag CI` de este sello se cita **después** del tag (mismo patrón que `.136`…`.144`).

## 8. Reproducción

```powershell
# contrato y tipos
pnpm --filter @bolsa/web contract:gen
pnpm --filter @bolsa/web contract:check

# tests rápidos
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# gates completos del sello
pnpm lint:py
pnpm imports:py
pnpm types:py
pnpm window:pin
pnpm window:freeze

# E2E mock del recorrido nuevo
$env:E2E_RUN="1"; pnpm --filter @bolsa/web e2e -- gp-e2e-v290-auto-estudio-daily-mock
```

## 9. Cita POST-TAG — CI del sello

**Pendiente al escribir esta evidencia:** el tag `v2.88.145-beta` **no se ha creado** en este entorno. La cita del `Release tag CI` (run, jobs y `conclusion`) se añadirá aquí **después** del tag, como en los sellos anteriores; hasta entonces este §9 **no** afirma ningún resultado de CI.
