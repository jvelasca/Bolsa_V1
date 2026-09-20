# Audit-pack v2.46-beta — AUTO-6 · Crash/Recovery + Concurrent AUTO (un crash no duplica ni pierde)

**Fecha:** 2026-09-20 · **Ref:** `v2.46-beta` (`1.71.0-beta`) · **Plan de fase:**
[`plan-v2-46-auto-6-crash-recovery-concurrent-2026-09-20.md`](./plan-v2-46-auto-6-crash-recovery-concurrent-2026-09-20.md)
§7 (estado y desviaciones declaradas) y §8 (verificación medida) · **Arranque del auditor:**
[`arranque-auditor-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md`](./arranque-auditor-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md).

- **Bump:** `1.70.0-beta` → `1.71.0-beta`.
- **Migración:** **NINGUNA** (Alembic head sigue en `043_exit_identity_and_kill_state`). El claim
  atómico no la necesitó: usa la **PK existente** de `portfolio_reservations` como árbitro
  (`INSERT … ON CONFLICT DO NOTHING` sobre el `reservation_id` derivado).
- **Gobernador:** `apps/api-python/scripts/v2_43_governor_evidence.py` **intacto** (`git diff`
  vacío) y **`exit 0`**, con `"bump"` conservado en `1.68.0-beta`.
- **Tags previos:** `v2.43-beta`…`v2.45-beta` **no se mueven**; `v2.46-beta` es ref nueva y aditiva.

---

## 1. El invariante que instala (en una frase)

> _Un crash **no duplica nada y no pierde nada** — orden, fill, ledger, posición, protección y
> riesgo se recuperan — y **1 señal ⇒ 1 decisión ⇒ 1 orden ⇒ fills correctos** bajo concurrencia._

Hasta `v2.45`, el día se certificaba **funcionando**: el motor corría, cerraba su embudo y el
libro quedaba plano. AUTO-6 certifica lo que pasa cuando las cosas van **mal**: la RAM del
proceso **muere** (y sólo sobrevive lo durable), y varias instancias del motor compiten por la
**misma** oportunidad. Lo que se mide:

1. **Capa hermética (por commit):** el día se reconstruye y **converge** tras descartar el objeto
   worker (crash) y **no se duplica** cuando tres workers evalúan la misma señal a la vez.
2. **Capa real (al sellar el tag):** el **proceso real** del scheduler se mata **en sucio** sobre
   PostgreSQL real y se reinicia sobre la misma BD; y tres **sesiones** concurrentes compiten
   sobre la misma cuenta. Cada escenario con su gate fail-if-skipped propio.

---

## 2. Piezas nuevas (se extiende, no se reinventa)

### 2.1 Claim atómico de la reserva (la única costura de producción que cambia)

El escenario concurrente descubrió que la reserva de cartera se comprometía con
«leer presupuesto → reservar»: dos workers podían apilar **dos** compromisos de capital sobre la
**misma** oportunidad. El arreglo es el **mínimo sin migración** que el plan autorizaba
(§2.2, «derivar la identidad de la reserva de la identidad determinista de la señal/orden»):

| Pieza                                | Qué hace                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `auto_v2_entry.py:entry_decision_id` | Identidad **determinista** de la decisión de una señal: `dec-<sha256(cuenta ␟ signal_id)[:12]>`. Dos workers/procesos que evalúan la **misma** señal de la **misma** cuenta producen la **misma** identidad. Sin `signal_id` (señal sin barra) se conserva la identidad aleatoria histórica: **no hay clave estable que reclamar** (fail-open al azar de siempre, nunca a un id compartido por accidente). |
| `reservation_store.py:save_claim`    | Método **nuevo** del protocolo y de sus dos implementaciones: `True` sólo si el **compromiso VIVO** pasa a ser de este llamante. `INSERT … ON CONFLICT DO NOTHING … RETURNING` y, si no hay fila nueva, un `UPDATE` **condicional** (`status != OPEN OR remaining_qty <= 0`) con `RETURNING`. Las **dos** sentencias son atómicas: no hay ventana leer→escribir.                                           |
| `auto_simulation_worker.py`          | `_v2_persist_tick_reservations` usa `save_claim` y, si el claim se pierde, **veta su propia emisión** (`reservation_already_live`, sumado al carryover de veteo — el mismo desenlace que «ya hay reserva viva», con el mismo motivo, sin inventar uno nuevo).                                                                                                                                              |

**`save` vs `save_claim` (el defecto que la medición destapó, declarado en §7.1 del plan).**
`save` responde «¿la fila existía?» (idempotencia de **replay**). Leído como claim, `False`
significaba «esta señal ya tiene un compromiso» **aunque estuviera liberado**: una re-entrada
legítima sobre la misma barra (tras cancelación/restart) quedaba vetada **para siempre**.
`save_claim` responde la pregunta correcta («¿soy el dueño del compromiso **vivo**?») y una
identidad **liberada** se **re-compromete**. Confundirlas falla en las dos direcciones: vetar la
re-entrada legítima, o comprometer dos veces el mismo capital.

### 2.2 Crash/Recovery hermético — `apps/api-python/tests/test_auto_v46_crash_recovery.py` (NUEVO)

Descartar el objeto `AutoSimulationWorker` y construir uno **nuevo sobre los MISMOS espejos
durables** = «la RAM se pierde». Secuencia: `BUY` (fill **parcial**: la cola SIM corta la orden)
→ **muerte** → **reinicio** → `readopt_positions()` + reconciliación de arranque → continuar →
`time_exit` limpio. Un segundo test aísla la **liberación de la cola NO llenada** de la reserva
parcial. Invariantes: reconciliación **convergente** (nunca `DIVERGENT`/`UNKNOWN`), **todo**
`ExecutionEvent` en `APPLIED`, **cada** fill con su contexto financiero durable, `POSITION ==
Σ APPLIED BUY − Σ APPLIED SELL`, **sin doble efecto** (reiniciar no añade ni una traza BUY más),
libro plano y reservas vivas a **0**. Determinismo: ids por barrida pura (`sha256(seed,
instrument_id, side, …)`) con fallo **con diagnóstico**, no por sorteo. Se añadió además una fase
que prueba que la señal ya consumida **no re-abre** la oportunidad en la misma barra.

### 2.3 Concurrent AUTO hermético — `apps/api-python/tests/test_auto_v46_concurrent.py` (NUEVO)

Tres workers A/B/C sobre **los mismos** stores in-memory durables, mismo `account_id`,
`engine_id`, reloj y barra/señales. La concurrencia es **real**, no un `gather` secuencial: las
operaciones de los espejos **ceden el control** (`await asyncio.sleep(0)`), que es lo que hace una
ida y vuelta a PostgreSQL (sin eso, un store in-memory corre hasta el final y el `gather` sería
una mentira). Invariantes: `count(distinct venue_order_id)` por señal/barra **≤ 1**; **un solo**
worker abre y los demás **declaran por qué** no (`reservation_already_live`, ni un veto en
silencio); **una sola fila** de reserva por `(cuenta, instrumento)`; `Σ reserved_cash` viva == la
cola **NO llenada** (nunca la cola × nº de workers); contabilidad cerrada; y una **segunda
oleada** de workers no añade **ni una** orden más.

### 2.4 Crash/Recovery real — `apps/api-python/tests/test_crash_recovery_day_process_pg.py` (NUEVO)

Copia el patrón **medido** del Golden Day 2.0 (`test_golden_day_v2_process_pg.py`: semilla de
cuenta/instrumento/`EdgeReport`, `subprocess.Popen([sys.executable, "-m",
"bolsa_api.workers.scheduler_worker"])`, presupuestos declarados y fallo al instante si el
proceso muere) — reutiliza sus helpers **importándolos**, no reimplementándolos. Lo propio es la
identidad del instrumento con fill **parcial** (`_crash_instrument_id`: BUY parcial con ≥2
tranchas y SELL completo, barrida pura determinista). Secuencia: `BUY` parcial **durable** →
**muerte sucia** (`kill()` en POSIX / `terminate()` en Windows) → **reinicio** del mismo engine
→ reconciliación + cierre limpio por el **seam durable** (`holdingDeadlineAt` al pasado).
Invariantes: `fills > orders`, reserva **viva** por la cola no llenada al morir, todo `APPLIED`,
cada fill con su `transactions.idempotency_key`, `POSITION == Σ APPLIED`, libro plano, **ni una
reserva viva al final** y cero trazas de venue LIVE. Gate: `AUTO_CRASH_RECOVERY_PG_REQUIRED=1`.

### 2.5 Concurrent AUTO real (gemelo estrecho) — `apps/api-python/tests/test_concurrent_auto_pg.py` (NUEVO)

**Sesiones** concurrentes (no tres procesos: eso es el crash test) sobre PG real, misma
cuenta/engine/instrumento/barra/señales, con el tick conducido por **la misma costura de
producción** (`AutoSimRuntime.run_tick` con stores `Postgres*`); cada `await` a PostgreSQL es un
punto de interleaving real. Invariantes: **un solo INTENT de orden** (`Σ _order_seq == 1`) —
medir el **intent** y no `count(distinct venue_order_id)` es deliberado: la identidad de orden del
venue es determinista por `(engine, minuto, lado, símbolo, seq)`, así que una emisión duplicada
tendría **el mismo** `venue_order_id`/`execution_id` y sería financieramente idempotente —
**invisible** a un `count`; el intent sí la ve. Además: **una sola fila** de reserva por
`(cuenta, instrumento)`, `Σ reserved_cash` viva == la cola no llenada, contabilidad cerrada
(`released_qty == Σ APPLIED`, `remaining_qty == pedido − Σ`) y **toda** instancia que no abre
declara por qué. Gate: `AUTO_CONCURRENT_PG_REQUIRED=1`.

### 2.6 Cableado de CI (un fichero nuevo no entra solo)

- Los **dos herméticos** entran por el **pase de directorio** de `apps/api-python/tests`: **no**
  requieren registro explícito.
- Los **dos PG** se añaden al `--ignore` de **los dos** jobs offline (sin PG, skipearían en mudo):
  `quality` de `python-ci.yml` y `python` del tag en `release-tag-ci.yml`.
- En `lifecycle-pg` del tag: `AUTO_CRASH_RECOVERY_PG_REQUIRED: '1'` y
  `AUTO_CONCURRENT_PG_REQUIRED: '1'` en `env:`, y **dos pasos dedicados** de pytest (uno por
  escenario) con `set -o pipefail` + `tee` a log + **guard anti-skip** (`log no vacío` +
  `grep -qE '(^|[0-9]+ )skipped|SKIPPED'`). \*\*Comentarios FUERA del bloque `run: >`.
- **No** se tocan los `needs:` de `certify`: ya depende de `lifecycle-pg`.

---

## 3. Matriz afirmación → código → test

| Afirmación                                                        | Código                                                        | Test                                                                        |
| ----------------------------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Una señal ya consumida no re-abre la oportunidad de la barra      | `auto_v2_entry.py` (`consumed_signal_ids`)                    | `test_crash_recovery_day_partial_fill_survives_kill_and_restart` (fase 4)   |
| La identidad de la decisión es determinista por `(cuenta, señal)` | `auto_v2_entry.py:entry_decision_id`                          | `test_concurrent_auto_three_workers_claim_one_signal_one_order`             |
| El claim del compromiso vivo es atómico y no duplica la reserva   | `reservation_store.py:save_claim` (InMemory + Postgres)       | `test_concurrent_auto_three_workers_claim_one_signal_one_order`             |
| El perdedor del claim **no** emite (veta con motivo declarado)    | `auto_simulation_worker.py` (`_v2_persist_tick_reservations`) | `test_concurrent_auto_three_workers_claim_one_signal_one_order`             |
| Una identidad **liberada** se puede re-comprometer                | `reservation_store.py:save_claim`                             | `test_auto_v46_crash_recovery.py` (re-entrada tras cierre)                  |
| El fill materializado **libera** la cola no llenada               | `auto_simulation_worker.py` (`_v2_reconcile_reservations`)    | `test_crash_recovery_releases_the_unfilled_tail_of_the_partial_reservation` |
| Una proyección divergente **veta** aperturas                      | `auto_simulation_worker.py` (`_openings_vetoed`)              | `test_unreadable_ledger_vetoes_openings_and_keeps_position`                 |
| Un `ExecutionEvent` ya `APPLIED` no vuelve a tocar dinero         | `execution_event.py` (`apply_execution_financial_once`)       | `test_durable_apply_skips_when_already_applied`                             |
| El proceso real sobrevive a la muerte sucia y converge (PG)       | `test_crash_recovery_day_process_pg.py`                       | `test_crash_recovery_day_real_process_survives_dirty_kill_pg`               |
| Tres sesiones concurrentes no duplican orden ni reserva (PG)      | `test_concurrent_auto_pg.py`                                  | `test_concurrent_auto_three_sessions_claim_one_signal_pg`                   |

---

## 4. Matriz de mutaciones (MEDIDA, no esperada)

`apps/api-python/scripts/v2_46_mutation_audit.py` — seis mutaciones, **una por invariante nuevo**,
cada una apuntando a la **costura de producción** que el escenario ejercita; restauración **desde
memoria** (nunca `git checkout --`); aborta si el fragmento no es único. **6/6 muerden** y la
huella (`sha256` del raw) de los ficheros tocados queda **idéntica**. Línea base: **ningún rojo**.

| #   | Mutación                                        | Suite(s) corrida(s)                                               | Test(s) en rojo                                                                                                  |
| --- | ----------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| M1  | la señal ya consumida deja de filtrarse         | `test_auto_v2_entry.py` + `test_auto_v46_crash_recovery.py`       | `test_plan_v2_tick_blocks_consumed_signal`, `test_crash_recovery_day_partial_fill_survives_kill_and_restart`     |
| M2  | el fill deja de liberar el compromiso           | `test_auto_v46_crash_recovery.py` + `test_auto_v46_concurrent.py` | `test_crash_recovery_releases_the_unfilled_tail_of_the_partial_reservation`                                      |
| M3  | lo divergente deja de vetar aperturas           | `test_auto_v2_partial_fills.py`                                   | `test_unreadable_ledger_vetoes_openings_and_keeps_position`                                                      |
| M4  | el `APPLIED` deja de atajarse                   | `test_execution_event.py`                                         | `test_durable_apply_skips_when_already_applied`                                                                  |
| M5  | la decisión de entrada deja de ser determinista | `test_auto_v46_concurrent.py`                                     | `test_concurrent_auto_three_workers_claim_one_signal_one_order`, `test_concurrent_auto_second_wave_adds_nothing` |
| M6  | el perdedor del claim emite igualmente          | `test_auto_v46_concurrent.py`                                     | `test_concurrent_auto_three_workers_claim_one_signal_one_order`                                                  |

**Desviación declarada frente al patrón de `v2_45`** (importa, porque cambia el mecanismo de dos
garantías de la sonda):

1. **Sondeo de puerto** en vez de asumir el DSN fast-fail. En Windows un puerto cerrado **no**
   rechaza al instante: con el DSN a `127.0.0.1:9` las suites de `apps/api-python` **se colgaban**
   (se reprodujo: 120 s por suite, `TIMEOUT`) en vez de devolver el rojo **con nombre**. La sonda
   comprueba si hay PG viva (`socket.create_connection`, 0,75 s) y usa el DSN fast-fail **solo**
   cuando no la hay. En esta máquina había PG, así que las mutaciones se midieron **contra la base
   real**.
2. **Huella de integridad por `sha256` del raw**. Los ficheros del árbol están en **CRLF** y
   `read_text`/`write_text` normalizan EOL: la comparación «restaurado byte a byte» del patrón
   anterior medía la copia **normalizada** (y un `git status` de Windows marca «tocado» por la
   caché de `stat` aunque el contenido sea idéntico). Ahora la sonda lee/escribe **bytes**,
   reescribe con el EOL del fichero y compara `sha256` antes/después.
3. **Guarda anti-resto**: si al arrancar encuentra el marcador `# MUTATION:`, **aborta** — una
   corrida interrumpida a mitad de mutación no puede pasar por «original» (le pasó a esta fase al
   matar una corrida colgada: se detectó, se restauró a mano y se añadió la guarda).

---

## 5. Verificación medida (2026-09-20, máquina del autor)

**Procedencia:** esta máquina tenía **PostgreSQL alcanzable** (`localhost:5432`), así que la capa
**real** no se dejó al CI: se midió en local con los dos gates activos. Las cifras de los **runs de
CI** (y del tag) las produce el run y se registran en §9.

| Medida                                      | Comando                                                                                                              | Resultado                                                   |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Ruff (CI-style, árbol completo)             | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                              | **0** (`All checks passed!`)                                |
| Mypy (full-tree, como CI)                   | `uv run mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent` | **489 files, 0 issues**                                     |
| Import-linter                               | `uv run lint-imports --config packages/py/.importlinter`                                                             | **4 kept, 0 broken**                                        |
| Gobernador                                  | `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py`                                                     | **vacío** + `exit 0` (con `"bump": "1.68.0-beta"`)          |
| Las 4 suites nuevas juntas (**6 tests**)    | `… AUTO_CRASH_RECOVERY_PG_REQUIRED=1 AUTO_CONCURRENT_PG_REQUIRED=1 uv run pytest test_auto_v46_*.py test_*_pg.py -q` | **6 passed** en **8,92 s**                                  |
| Gemelos PG en solitario (capa real)         | `… uv run pytest test_crash_recovery_day_process_pg.py test_concurrent_auto_pg.py -q -rs`                            | **2 passed** en **8,66 s**                                  |
| Terreno AUTO-6 (no regresión)               | `uv run pytest test_auto_v2_entry.py test_execution_event.py test_auto_v2_partial_fills.py test_auto_v46_*.py -q`    | **96 passed** en **1,03 s**                                 |
| Baseline `quality` (del YAML, por JUnit)    | `offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`                                   | **2091 passed, 0 skipped, 0 failed** (v2.45: 2087 ⇒ **+4**) |
| Baseline `python` del tag (del YAML, JUnit) | `offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores`                               | **2102 passed, 0 skipped, 0 failed** (v2.45: 2098 ⇒ **+4**) |
| Mutaciones                                  | `uv run --no-sync python apps/api-python/scripts/v2_46_mutation_audit.py`                                            | **6/6 muerden**, sha256 intacto, `exit 0`                   |

El **`+4`** cuadra en **ambos** bloques offline (los dos tests herméticos por escenario entran por
pase de directorio); los **2** de la capa real viven en `lifecycle-pg` del tag.

---

## 6. Comandos exactos de CI

```bash
# El gobernador NO se movió: debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Cubo estático
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# Capa hermética nueva (por commit, en el job `quality`)
uv run pytest apps/api-python/tests/test_auto_v46_crash_recovery.py \
  apps/api-python/tests/test_auto_v46_concurrent.py -q

# Matriz de mutaciones (mide y restaura; deja la huella intacta)
uv run --no-sync python apps/api-python/scripts/v2_46_mutation_audit.py

# Bloques offline extraídos del YAML (medida por JUnit XML, no copia a mano)
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml \
  quality --with-pg-ignores
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml \
  python --with-pg-ignores

# Capa real (necesita PostgreSQL; la corre `lifecycle-pg` del tag en pasos DEDICADOS).
# OJO: no la corras en paralelo con otra sesión de pytest contra la misma base.
AUTO_CRASH_RECOVERY_PG_REQUIRED=1 AUTO_CONCURRENT_PG_REQUIRED=1 uv run pytest \
  apps/api-python/tests/test_crash_recovery_day_process_pg.py \
  apps/api-python/tests/test_concurrent_auto_pg.py -q --tb=short -rs
```

---

## 7. Límites declarados y deuda diferida

### 7.1 Desviaciones frente al plan (declaradas, no maquilladas)

1. **La «muerte en mitad del fill» no es observable en vivo.** El venue SIM aplica el **schedule
   completo** de una orden **dentro del mismo tick**, así que **no existe** una ventana «parcial en
   vuelo»: el parcial durable lo produce el propio proceso (orden cortada con cola sin llenar,
   `status='partial'` + reserva viva) y **se mata el proceso sobre ese estado**. **No se siembra
   nada.** Se certifica el **estado durable** del fill parcial y su cierre contable tras el
   reinicio, no una interrupción en vuelo imposible por construcción del venue.
2. **Muerte sucia = `terminate()` en Windows / `kill()` en POSIX.** En Windows (máquina del autor)
   `terminate()` es el máximo disponible; el `SIGKILL` real es el del CI Linux. El test lo usa por
   plataforma y lo **declara**; no finge equivalencia.
3. **El claim atómico necesitó tocar producción** (dos funciones nuevas + un método nuevo), porque
   el escenario concurrente **demostró** que la reserva no se comprometía atómicamente. Fue el
   arreglo **mínimo previsto por el plan** (identidad determinista de la señal), **sin** locks
   explícitos y **sin** migración.
4. **Alcance de la byte-identidad con el flag del optimizador OFF** (roza el freeze del plan §2 y se
   declara): `decision_id=entry_decision_id(...)` se pasa en `plan_v2_tick` **sin** depender de
   `AUTO_ENGINE_SIM_V2_OPTIMIZER`, así que con el flag **OFF** la identidad del producto se conserva
   (ninguna candidata construida, ninguna clave nueva en el journal, `V2TickPlan.optimizer is None`)
   pero la **identidad de la reserva** pasa de **aleatoria** (`portfolio_decision_engine.py:444`,
   `dec-<uuid4>`) a **determinista** por `(cuenta, señal)`. Es el arreglo autorizado por el plan y su
   efecto observable **es** el invariante nuevo. Como con ids **aleatorios** una identidad de reserva
   **no podía repetirse**, la distinción `save`/`save_claim` era **inalcanzable** en cualquier flujo
   histórico: el método nuevo es **neutro** para todo lo anterior. Con `AUTO-ENGINE-SIM-V2=0` el
   camino legacy no toca las reservas del tick.
5. **Defecto semántico destapado al medir** y arreglado en el mismo movimiento: `save` (semántica
   de replay) leído como claim vetaba para siempre la re-entrada sobre una identidad **liberada**.
   De ahí `save_claim`, con ese caso explícito y cubierto.
6. **La sonda de mutaciones se endureció** (sondeo de PG, sha256 del raw, guarda anti-resto) —
   ver §4, con el motivo medido de cada cambio.
7. **Dos tests por escenario hermético** (no uno), para que la mutación de cada invariante tenga su
   rojo propio: en el crash, «sobrevivir y converger» vs «liberar la cola no llenada»; en el
   concurrente, «la carrera» vs «la segunda oleada no añade nada».

### 7.2 Límites (heredados o confirmados)

1. **MAE/MFE se recogen, no se calibran**; **sin productor de economía en el tick** (`p_win` y
   medias son de `AUTO-7`): el escenario concurrente **no** se apoya en que el optimizador elija por
   valor esperado real.
2. **Precio SIM plano y horizonte 21–90 días** ⇒ el cierre del día real es por el **seam durable**
   (`holdingDeadlineAt` vencido + reinicio), no por geometría.
3. **El bucle AUTO SIM no escribe el journal durable** ⇒ los agregados post-crash se leen de
   `execution_events` / `sim_*` / `transactions` / `portfolio_reservations`, **no** del journal.
4. **Presupuesto de tiempo del job del tag**: cada escenario declara su techo por fase
   (`_STARTUP_GRACE_S=150 s`, `_OPEN_POLLS`/`_CLOSE_POLLS=240`) y **falla con diagnóstico**; medido
   ~8,7 s por corrida de los dos juntos en local.
5. **Límite de método**: no correr dos sesiones de pytest en paralelo contra la misma base (el
   barrido de residuos del conftest es de sesión) ⇒ pasos **dedicados**, sin solape.
6. **El gemelo PG no arranca tres procesos**: usa tres **sesiones** concurrentes (decisión del
   owner, §0 del plan). Escalar a tres procesos `scheduler_worker` queda como plan B declarado, no
   como deuda oculta.

---

## 8. Reproducibilidad e inventario

Ficheros tocados por la fase (**10 de código/CI + 7 de documentación**):

```
.github/workflows/python-ci.yml                                  (2 --ignore)
.github/workflows/release-tag-ci.yml                             (2 --ignore + env gates + 2 pasos + 2 guards)
packages/py/application/src/bolsa_application/auto_v2_entry.py   (entry_decision_id + decision_id del tick)
packages/py/application/src/bolsa_application/reservation_store.py (save_claim: protocolo + InMemory + Postgres)
apps/api-python/src/bolsa_api/background/auto_simulation_worker.py (_v2_persist_tick_reservations)
apps/api-python/tests/test_auto_v46_crash_recovery.py            (NUEVO, hermético, 2 tests)
apps/api-python/tests/test_auto_v46_concurrent.py                (NUEVO, hermético, 2 tests)
apps/api-python/tests/test_crash_recovery_day_process_pg.py      (NUEVO, real PG + proceso, 1 test)
apps/api-python/tests/test_concurrent_auto_pg.py                 (NUEVO, real PG, 3 sesiones, 1 test)
apps/api-python/scripts/v2_46_mutation_audit.py                  (NUEVO, 6 mutaciones)
package.json                                                     1.70.0-beta → 1.71.0-beta
CHANGELOG.md
docs/engineering/plan-v2-46-auto-6-crash-recovery-concurrent-2026-09-20.md  (§7 y §8, sin tocar el resto)
docs/engineering/audit-pack-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md   (NUEVO)
docs/engineering/arranque-auditor-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md (NUEVO)
docs/engineering/PROJECT_STATE.md
docs/engineering/engineering-index-2026-08-03.md
```

**NO se toca:** `apps/api-python/scripts/v2_43_governor_evidence.py`, ninguna migración Alembic,
`packages/py/application/src/bolsa_application/execution_event.py` (sólo se **muta** en la sonda,
que restaura), ni `governor.json` (generado, sin trackear).

---

## 9. Sello

**Completo.** §9.1 es el sello en `main` (commit de fase) y §9.2 el sello en la ref del **tag**. Cada
cifra **cita el run que la produjo**: no se atribuye ninguna a un artefacto que no exista, y la medición
local de §5 **no** se mezcla con la del CI.

### 9.1 Producido en `main` (commit de fase)

1. **Commit de fase** [`a14b71d7`](https://github.com/jvelasca/Bolsa_V1/commit/a14b71d750fd28f60b6ca7ec9db6e6cca020700e)
   — los **17 ficheros** del §8 (`+2869/−25`). Nota de honestidad sobre el diff: el `git diff --cached`
   del staging daba `+2856/−11`; el commit sale `+2869/−25` porque `lint-staged` corrió `prettier --write`
   sobre los `*.md`/`*.json` (reflujo de tablas y listas, **sin cambio de contenido**: verificado que
   `version` sigue en `1.71.0-beta`, la línea `AUDIT-PACK v2.46` sigue en `PROJECT_STATE.md` y los §7/§8 del
   plan y §7/§8/§9 del pack siguen presentes).
2. **`Python CI`** en `main` — run [`35534775724`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775724)
   **GREEN 5/5** (2m40s):
   - `quality` **2091 passed, 38 skipped** en **115,49 s** ⇒ los **+4** exactos sobre los 2087 de
     `v2.45-beta` (los 4 tests herméticos nuevos, que entran por el **pase de directorio**).
   - `auto-v2-durable-pg` **43 passed** / **0 skipped** ⇒ **sin cambio**, que es justo lo predicho
     (no hay migración).
   - `lifecycle-pg` **13 passed** · `paper-forward-pg` **2 passed** · `grammar-discovery-pg` verde.
   - `Ruff`: _All checks passed_ (el `quality` vuelve a correr el linter sobre el árbol).
3. **En el mismo commit**, el resto de workflows en **GREEN**: `Gitleaks`
   [`35534775676`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775676) (11s), `Frontend CI`
   [`35534775682`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775682) (3m25s), `Optimize lab`
   [`35534775681`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775681) (1m30s) y
   `Fase 2 scientific` [`35534775675`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775675) (1m18s).

### 9.2 Producido en la ref del tag (cierra el sello)

4. **Tag anotado `v2.46-beta`** sobre la ref de sellado docs-only `5eb654b9` (aditivo: los seis tags
   anteriores — `v2.43*`, `v2.44-beta`, `v2.45-beta` — **no se mueven**).
5. **`Release tag CI`** — run [`35535111995`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535111995)
   **GREEN** (8m5s) con `certify (aggregate + artifact)` en `success`:
   - job `python` offline: **2102 passed, 35 skipped** en 58,91 s ⇒ los **+4** exactos sobre los 2098 de
     `v2.45-beta`, tal y como predecía la versión **pre-sello** de este §9 (recuperable, para verificar
     que no se ajustó a posteriori: `git show 5eb654b9:docs/engineering/audit-pack-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md`).
   - `lifecycle-pg`: **148 passed** + **45 passed** (account-isolation) y **tres pasos dedicados** en
     verde — `Golden Day 2.0` **1 passed in 10,68 s**, **`Crash/Recovery Day` (NUEVO) 1 passed in
     9,44 s** y **`Concurrent AUTO` (NUEVO) 1 passed in 1,64 s** — cada uno con su guard
     `Fail on skipped … (no skip silencioso)` **pasando** y sus `*_PG_REQUIRED=1` presentes en el `env:`
     del step (`AUTO_CRASH_RECOVERY_PG_REQUIRED` y `AUTO_CONCURRENT_PG_REQUIRED` visibles en el log).
   - `security (gitleaks)`, `dr-verify`, `decision-spine`, `shared`, `frontend`, `playwright (mock E2E)`,
     `a7-gate` y `certify`: **success**; `playwright (integrated E2E)` `skipped` por **opt-in**.
6. **`Python CI` en la ref del tag** — run
   [`35535111988`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535111988) **GREEN 5/5**:
   `quality` **2091 passed, 38 skipped** (idéntico al de `main`, que es lo exigible: un commit docs-only
   no debe mover la cifra) y `auto-v2-durable-pg` **43 passed**. En el mismo push del tag:
   `Gitleaks` [`35535110216`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535110216) (main),
   `Frontend CI` [`35535112005`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535112005),
   `Optimize lab` [`35535112002`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535112002) y
   `Fase 2 scientific` [`35535112008`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535112008)
   **GREEN**.

### 9.3 Cómo se verifica este sello (sin creerme)

```bash
# la ref del tag y su commit
git rev-parse v2.46-beta^{commit}          # 5eb654b9…  (sello docs-only)
git log --oneline -3 v2.46-beta

# los dos pasos dedicados del gate, en el log del job lifecycle-pg del tag
gh run view 35535111995 --log | rg 'Pytest (Crash/Recovery|Concurrent)'
#   => "1 passed in 9.44s"  y  "1 passed in 1.64s"

# el guard anti-skip existe y pasó
gh run view 35535111995 --log | rg 'Fail on skipped (Crash/Recovery|Concurrent)'
```

Nota de honestidad sobre la cifra del job `python` del tag (**2102**): es una predicción escrita **antes**
del tag (en `5eb654b9`) y cumplida **después**; no se ajustó a posteriori.
