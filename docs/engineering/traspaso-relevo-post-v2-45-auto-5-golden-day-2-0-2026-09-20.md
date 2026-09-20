# Traspaso de relevo — post `v2.45-beta` (AUTO-5 cerrado) → **AUTO-6** (Crash/Recovery + Concurrent)

**Fecha:** 2026-09-20 · **Versión:** `1.70.0-beta` · **Tag:** `v2.45-beta` → `1abfc7fb` · **Migración:**
**ninguna** (Alembic head sigue en `043_exit_identity_and_kill_state`). Sello **verde**: commit de fase
`ad800262` (17 ficheros, `+2581/−16`), corrección `0fc85c17`, sello docs-only `1abfc7fb` y evidencia de CI
`9ef57aff`; `Python CI` **5/5** en `main`
([`35520898909`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35520898909); `quality` **2087 passed /
38 skipped**, `auto-v2-durable-pg` **43 passed / 0 skipped**) y `Release tag CI`
([`35522747332`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35522747332)) **GREEN** con `certify` en
`success` (job `python` offline **2098 passed / 35 skipped**, `lifecycle-pg` **148 + 45 passed** y el paso
dedicado del día real **1 passed en 9,32 s**; `a7-gate`, `dr-verify`, `shared`, `spine`, `security` y
`frontend` en `success`; `playwright` `skipped` por opt-in).

**Punto de entrada obligatorio:** el
[audit-pack v2.45](./audit-pack-v2.45-auto-5-golden-day-2-0-2026-09-20.md) (§7 = límites declarados y deuda
diferida), el [arranque del auditor](./arranque-auditor-v2.45-auto-5-golden-day-2-0-2026-09-20.md) y el
[plan de fase](./plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md) (§7 = estado de ejecución y desviaciones
**D1–D5**). Después, este documento. **La especificación de `AUTO-6` es el §8 del
[roadmap](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md)** (sección `AUTO-6 — Crash/Recovery + Concurrent`).

---

## 1. Estado en una frase

`AUTO-5` deja instalado que **el día AUTO completo se certifica en dos capas**: por commit, el **embudo
hermético** del día (`seen == traded + rejected + expired + missed`, con motivo tipificado en cada no
operada y coste de oportunidad **declarado** cuando falta el dato); y al sellar el tag, el **día real** con
**proceso de scheduler real sobre PostgreSQL real** (`test_golden_day_v2_process_pg.py`, gate
`AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`, guard anti-skip). Lo que queda es **`AUTO-6`**: demostrar que AUTO
**sobrevive a la muerte del proceso y a la concurrencia sin duplicar ni perder dinero**.

## 2. Lo que este ciclo deja instalado (y cómo se mide)

| Invariante                                                            | Dónde vive                                                            | Cómo se mide                                             |
| --------------------------------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------- |
| Toda oportunidad del día tiene estado **final** y motivo              | `packages/py/application/src/bolsa_application/auto_daily_journal.py` | `test_auto_daily_journal.py` (9 tests nuevos)            |
| `seen == traded + rejected + expired + missed` (partición exhaustiva) | `auto_daily_journal.py` (`_opportunity_breakdown`)                    | idem + `v2_45_mutation_audit.py` M1–M3                   |
| Lo no medido se **declara** (`UNKNOWN`/`PARTIAL`), nunca `0`          | `auto_daily_journal.py` (`MEASUREMENT_*`, `notes`)                    | idem + M4/M5                                             |
| Identidad de estrategia **aditiva** en el `payload` JSONB             | `auto_v2_entry.py`, `auto_simulation_worker.py`                       | `test_auto_v2_golden_day_evidence.py` + M7/M8            |
| La fuente `auto-2.0:<version>` se reconoce (sin ella, versión NULL)   | `auto_simulation_worker.py` (`_strategy_version_from_source`)         | `test_auto_simulation_worker.py`                         |
| El **día real** abre y cierra el libro (PG + proceso)                 | `apps/api-python/tests/test_golden_day_v2_process_pg.py` (NUEVO)      | paso dedicado de `lifecycle-pg` del tag, fail-if-skipped |

**Cifras del sello (del run que las produjo):** `quality` **2087/38/0** en `main` (los **+12** exactos de
tests nuevos sobre los 2075 de `v2.44`), `auto-v2-durable-pg` **43** (sin cambio: no hay migración),
`sellado` `python` del tag **2098/35** (los **+12** sobre 2086); `ruff` 0, `mypy` 489 ficheros 0 issues,
`lint-imports` 4 kept / 0 broken; matriz de mutaciones **8/8 muerden** con huella del árbol intacta.

## 3. Qué queda abierto (deuda declarada, por orden de importancia para `AUTO-6`)

1. **El día real cierra por el SEAM DURABLE, no por geometría** (D1 del plan §7.1). El precio del camino
   SIM real es **plano** y el horizonte de la plantilla es de **21–90 días**, así que un día V2 no puede
   disparar T1/trailing/régimen dentro del presupuesto de un test: la fase 2 lleva el `holdingDeadlineAt`
   al pasado y **reinicia el mismo engine** (cierre por `time_exit`). **Esto es relevante para `AUTO-6`**:
   el patrón «matar el proceso y reiniciarlo sobre la misma BD» **ya está probado** y hay que reutilizarlo,
   no reinventarlo.
2. **El bucle AUTO SIM no escribe el journal durable** (D2). El `DecisionJournalEntryRow` lo escriben los
   casos de uso de la API; el worker acumula `DecisionJournalEntryRecord` **en memoria**. Consecuencia:
   todo agregado que deba leerse **de la BD** tras un crash/reinicio exige mirar las tablas
   `execution_events` / `sim_*` / `transactions`, **no** el journal.
3. **Suites de crash/concurrencia que existen y NO están cableadas en CI** (ver §4): un rojo ahí es
   invisible. `AUTO-6` debe decidir si las incorpora al gate o las declara explícitamente.
4. **Sin productor de economía en el tick** (heredado de `AUTO-4`/`AUTO-5`): `p_win`/medias son de
   `AUTO-7`. El escenario concurrente **no** puede apoyarse en que el optimizador elija por valor esperado
   real.
5. **Dos ficheros con normalización CRLF/LF pendiente** en el worktree (`arranque-auditor-v2-40-4-…`,
   `audit-pack-v2.40.4-…`): diff de contenido **vacío**. Se dejaron **fuera** de los commits de `v2.45` a
   propósito. Un `git add` descuidado mete ruido de 2 ficheros en el sello. Y `governor.json` es
   **generado y sin trackear**: no se commitea.

## 4. El terreno de `AUTO-6` (rutas verificadas en el árbol)

**Lo que ya existe y hay que EXTENDER, no reinventar:**

| Pieza                                                        | Ruta                                                                                                                                                                 | Qué es hoy / dónde corre                                                                                                                                                                         |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Batería de crash **hermética** del AUTO SIM                  | `apps/api-python/tests/test_a9_1_crash_battery.py`                                                                                                                   | Ventanas C3-F/G/H/I (crash inyectado en la costura exacta). Sin PG. Corre en `quality` por el **pase de directorio** `apps/api-python/tests` (`python-ci.yml:189`).                              |
| Matriz de crash **hermética** de la identidad de SALIDA      | `apps/api-python/tests/test_auto_v44_exit_crash_matrix.py`                                                                                                           | C1–C4: crash antes de reservar / tras reservar / tras emitir / con fill PARCIAL; worker **NUEVO** sobre los **mismos stores durables**. Corre en `quality` (mismo pase de directorio).           |
| Readopción por proceso **real** (scheduler)                  | `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`                                                                                                   | `subprocess.Popen([sys.executable, "-m", "bolsa_api.workers.scheduler_worker"])`, gate `AUTO_SCHEDULER_PROCESS_PG_REQUIRED`. Corre en `lifecycle-pg` del tag (`release-tag-ci.yml:583`).         |
| **Día real** AUTO-5 (patrón a copiar para `AUTO-6`)          | `apps/api-python/tests/test_golden_day_v2_process_pg.py`                                                                                                             | Dos fases con **dos arranques** del mismo engine, techo durable vencido entre medias. Paso **dedicado** de `lifecycle-pg` del tag con `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1` + guard anti-skip.      |
| Concurrencia PG de **claim/lease** (2 sesiones)              | `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py`                                                                                                   | `SKIP LOCKED` + lease bajo dos transacciones simultáneas; `LIVE_PG_REQUIRED=1` hace fail duro. Corre en `lifecycle-pg` del tag (`release-tag-ci.yml:601`).                                       |
| **Dos workers** sobre la MISMA posición (FIFO)               | `apps/api-python/tests/test_lifecycle_outbox_worker_pg.py::test_two_workers_same_position_fifo_open_t1_exit`                                                         | Semilla directa del escenario «Concurrent AUTO». Corre en `lifecycle-pg` del tag (`release-tag-ci.yml:578`).                                                                                     |
| Chaos **REAL** (SIGKILL) del worker de recovery              | `apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py` + `_crash_recovery_probe.py`                                                        | Job **dedicado** `a7-gate` (`release-tag-ci.yml:767`) con BD scratch `bolsa_v1_a7` y `LIVE_A7_PG_REQUIRED=1`. El propio workflow lo marca «**C3 🟡 parcial**» (`:761`). `certify` depende de él. |
| CAS «exactly one owner» con dos workers                      | `apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py::test_v220_two_workers_cas_exactly_one_owner`                                        | Hermano del anterior, mismo job `a7-gate`.                                                                                                                                                       |
| Fencado de leases (PG)                                       | `packages/py/infrastructure/tests/test_execution_event_fence_pg.py`                                                                                                  | Corre en `lifecycle-pg` del tag (`release-tag-ci.yml:598`).                                                                                                                                      |
| Migraciones de **lease** y **fence**                         | `packages/py/infrastructure/alembic/versions/025_execution_events_lease.py`, `.../026_execution_events_fence.py`                                                     | Ya aplicadas; **head `043`**.                                                                                                                                                                    |
| Lock de cuenta/cartera y orden **UTC** del ledger            | `account_repository.py`, `portfolio_repository.py`, `ledger_repository.py`, `position_state_repository.py` (`with_for_update`), `ledger_repository.next_executed_at` | La «secuenciación financiera ya certificada» sobre la que el roadmap §8 dice que se apoyan los dos escenarios de `AUTO-6`.                                                                       |
| Escenarios de carrera (misma key, depósito/retiro, BUY/SELL) | `packages/py/infrastructure/tests/test_concurrency_scenarios.py`                                                                                                     | **Existe y NO está en ningún workflow** (ver §3.3).                                                                                                                                              |
| Crash/restart **cross-PID** (intent de submit)               | `packages/py/application/tests/test_dex2_crash_restart_cross_pid.py`, `test_confirm_crash_restart.py`                                                                | **Existen y NO están en ningún workflow** (ver §3.3).                                                                                                                                            |

**Dónde vive cada gate hoy:**

- **Por commit** (`python-ci.yml`): job `quality` (hermético, sin PG; pasa `apps/api-python/tests` como
  **directorio** e **ignora** `chaos/live_a7` en `:219`) + job `lifecycle-pg` **per-commit** (`:222`).
- **Al sellar** (`release-tag-ci.yml`): `python` (offline, ignora `chaos/live_a7` en `:427` y
  `test_live_order_recovery_concurrency_pg.py` en `:429`), `lifecycle-pg` (PG real, `:601`) y `a7-gate`
  (chaos SIGKILL, `:767`).
- **`certify`** agrega: `security`, `shared`, `spine`, `frontend`, `python`, `playwright-mock`,
  `lifecycle-pg`, `dr-verify`, `a7-gate` (`:844-846`). **Un escenario que no corre en uno de estos jobs no
  certifica el tag.**

## 5. Cómo se mide `AUTO-6` (fijado por el roadmap §8)

> **Gate obligatorio de certificación**: si los dos escenarios no corren, la versión no se pone.

1. **`Crash/Recovery Day`** — BUY → **fill parcial** → **MUERTE** del proceso → **REINICIO** →
   **reconciliación** → continuar → **salida limpia**.
2. **`Concurrent AUTO`** — workers **A/B/C** sobre la **misma cuenta / cartera / señales**: **sin doble
   BUY**, **sin sobre-riesgo**, **sin reserva duplicada**, y `1 señal ⇒ 1 decisión ⇒ 1 orden ⇒ fills
correctos`.

Ambos deben quedar **verdes y presentes en el CI del tag**, con guard `no skip silencioso`. El patrón de
cableado ya está medido en `AUTO-5` (§4 del plan v2.45): **paso dedicado** + `env` de gate
(`*_PG_REQUIRED=1`) + `set -o pipefail` + `tee` a log + `grep` de `skipped`. Y **comentarios FUERA del
bloque `run: >`** (un `#` dentro convirtió un step en 936 tests en `V2.40.2`).

## 6. Trampas medidas (no las repitas)

1. **Un fichero nuevo en `packages/py/{application,infrastructure}/tests` NO entra solo en `quality`.**
   El job pasa como **directorio** `packages/py/domain/tests`, `packages/py/market/tests`,
   `packages/py/analytics/tests` y `apps/api-python/tests` (**`python-ci.yml:146-189`**), pero en
   `packages/py/application/tests` y `packages/py/infrastructure/tests` lista **fichero a fichero**: una
   ruta **inexistente** hace abortar a pytest con `exit 4`. Registra explícitamente o no corre.
2. **Los ficheros PG van al `--ignore` de los jobs offline** y corren con gate propio en el job PG: sin
   `--ignore` **skipean en mudo** y el verde es fantasma.
3. **`--with-pg-ignores` del runner versionado**: mide con el runner del YAML
   (`scripts/verify/offline_ci_run_yaml.py`), **nunca** con una copia a mano de la lista; la medida es por
   **JUnit XML** (en Windows el stdout de pytest llega truncado). Baseline vigente: `quality` **2087**,
   `python` del tag **2098**.
4. **Una cifra cita el artefacto que la produjo** (aprendizaje de `v2.44` §5 y `v2.45` §8). El número puede
   ser correcto y estar **atribuido al instrumento equivocado**: eso es un defecto de honestidad, no un
   redondeo.
5. **Procesos `python` huérfanos**: las corridas matadas dejan hijos vivos que falsean la siguiente
   medición. Mátalos antes de medir. Y `pytest_winloop` (plugin local de Windows) **no es del repo**.
6. **En esta máquina SÍ hay PostgreSQL alcanzable** (contenedor `bolsa-postgres` sano en `localhost:5432`,
   DSN de `docker-compose.yml`) — corregido frente al arranque de `v2.45`. Pero **no corras dos sesiones de
   pytest en paralelo contra la misma base**: el barrido de residuos del conftest (`purge_all_residuals`:
   borra toda cuenta ajena y todo instrumento `inst-%` al terminar la **sesión**) hace que **se borren los
   datos entre sí** (reproducido: el motor reintentaba liquidaciones contra filas ya borradas). El gate del
   tag corre cada fichero en **paso dedicado**, que es la forma soportada.

## 7. Freeze (congelado, no tocar sin motivo)

- **`apps/api-python/scripts/v2_43_governor_evidence.py` byte a byte igual y `exit 0`**, con su `"bump"`
  conservado en `1.68.0-beta`. Cualquier diff ahí es un hallazgo.
- **Sin migración salvo decisión explícita del owner**: head `043`. `AUTO-6` **probablemente no la
  necesita** (los escenarios prueban **recuperación** sobre estado durable ya existente), pero si el
  escenario concurrente exige un candado o un lease nuevo, **eso sí es migración** y debe declararse.
- **Byte-identidad con el flag OFF**: `AUTO_ENGINE_SIM_V2_OPTIMIZER=0` debe seguir siendo `v2.43.3`.
- **Los tags no se mueven**: `v2.45-beta` es una ref nueva y aditiva; `v2.43*`/`v2.44-beta` quedan donde
  están.
- **Los gates PG** (`*_PG_REQUIRED`) y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo
  **no** certifica nada.

## 8. Checklist antes de tocar `AUTO-6`

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el terreno de AUTO-6 que YA existe (hermético)
uv run pytest apps/api-python/tests/test_a9_1_crash_battery.py \
              apps/api-python/tests/test_auto_v44_exit_crash_matrix.py \
              apps/api-python/tests/test_auto_daily_journal.py -q

# el gobernador NO se movió (debe salir vacío y exit 0)
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# bloques offline EXTRAÍDOS del YAML (baseline de v2.45: 2087 y 2098)
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

Con PG real: `auto-v2-durable-pg` y `lifecycle-pg` (por commit) y `lifecycle-pg`/`a7-gate` (al sellar).

## 9. Decisiones del dueño (a confirmar en el arranque de `AUTO-6`)

Fijado por el roadmap §8 — **no** hace falta re-decidirlo:

1. **Los dos escenarios son gate obligatorio de certificación** (si no corren, la versión no se pone).
2. Deben quedar **verdes y presentes en el CI del tag**, con guard `no skip silencioso`.
3. Se apoyan en la **secuenciación financiera ya certificada**: lock de cuenta y de cartera,
   `next_executed_at`, fencado de leases.

A confirmar por el owner al arrancar la fase:

4. **Migración**: ¿ninguna (reutilizar `025`/`026`/`042`/`043`) o una nueva para el candado/lease del
   escenario concurrente?
5. **Dónde vive el gate**: ¿se extiende `lifecycle-pg`/`a7-gate` del tag o se abre un job dedicado
   (`crash-recovery` + `concurrent`) con `needs:` en `certify`?
6. **Alcance del «Concurrent AUTO»**: ¿tres procesos `scheduler_worker` reales (A/B/C) sobre la misma
   cuenta (coste: alarga el job), o un escenario hermético de tres workers sobre stores compartidos y un
   gemelo PG más estrecho?

Next = **`AUTO-6` — Crash/Recovery + Concurrent (`V2.46` / `1.71.0-beta`)**, especificación:
[`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) §8.
