# Plan de fase — `V2.46` / `AUTO-6` — Crash/Recovery + Concurrent (`1.71.0-beta`)

**Fecha:** 2026-09-20 · **Punto de partida:** tag `v2.45-beta` → `1abfc7fb` (AUTO-5 Golden Day 2.0
cerrado) · **Migración:** **propuesta: ninguna** (head sigue en `043_exit_identity_and_kill_state`; a
confirmar por el owner, ver §0) · **Roadmap:** §8 de
[`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).
**Relevo de entrada:** [`traspaso-relevo-post-v2-45-auto-5-golden-day-2-0-2026-09-20.md`](./traspaso-relevo-post-v2-45-auto-5-golden-day-2-0-2026-09-20.md).

> **Estado de este documento.** Las decisiones marcadas **«fijado (roadmap §8)»** vienen del roadmap y no
> se re-debaten. Las marcadas **«propuesta»** son la recomendación de este plan y **las confirma el owner
> al arrancar** la fase; §7 y §8 quedan **reservadas** para el estado de ejecución y la verificación
> (mismo patrón que `plan-v2-45`).

---

## 0. Decisiones del owner

| Decisión                      | Elección                                                                                                                                                                                                            | Estado              |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| Alcance                       | **Los dos escenarios completos**: `Crash/Recovery Day` (BUY → **fill parcial** → MUERTE → REINICIO → reconciliación → continuar → salida limpia) y `Concurrent AUTO` (A/B/C sobre la misma cuenta/cartera/señales). | fijado (roadmap §8) |
| Gate                          | **Obligatorio de certificación**: los dos escenarios verdes y **presentes en el CI del tag**, con guard `no skip silencioso`. Si no corren, la versión no se pone.                                                  | fijado (roadmap §8) |
| Base de la que se apoya       | Secuenciación financiera **ya certificada**: lock de cuenta y de cartera (`with_for_update`), `next_executed_at`, fencado de leases (`025`/`026`).                                                                  | fijado (roadmap §8) |
| Migración                     | **NINGUNA** salvo que un escenario demuestre que falta una restricción; si aparece, **es migración y se declara** (no se cuela como “arreglo de test”).                                                             | **propuesta**       |
| Dónde vive el gate            | **Paso dedicado** dentro del job `lifecycle-pg` del tag (ya es `needs:` de `certify`), no un job nuevo. `a7-gate` es el plan B si el crash exige aislamiento SIGKILL.                                               | **propuesta**       |
| Alcance del `Concurrent AUTO` | **Dos capas**: núcleo **hermético** en `quality` (3 workers sobre stores durables compartidos) + **gemelo PG real** estrecho en el tag (3 sesiones concurrentes sobre la misma cuenta).                             | **propuesta**       |
| Arranque                      | **Agente nuevo** con este plan y el relevo; no se continúa la sesión de `v2.45`.                                                                                                                                    | fijado (relevo)     |

## 1. Invariante que instala

> _Un crash **no duplica nada y no pierde nada**: orden, fill, ledger, posición, protección y riesgo se
> recuperan; y **1 señal ⇒ 1 decisión ⇒ 1 orden ⇒ fills correctos** bajo concurrencia._

Corolario operativo: tras la muerte del proceso, el estado reconstruido (`expected == actual == projection`)
tiene que **converger**, y ninguna fila puede quedar a medias: todo `ExecutionEvent` **`APPLIED`**, todo
fill de la cola SIM con su **transacción** en el ledger, y el **libro plano** cuando el día termina. Bajo
concurrencia, `Σ` capital reservado **≤** presupuesto, sin **doble BUY** y sin **reserva duplicada**.

## 2. Qué NO cambia (freeze)

- **`v2_43_governor_evidence.py` byte a byte igual y `exit 0`**, con su `"bump"` conservado en
  `1.68.0-beta`.
- **Sin migración** (head `043`) por defecto; cualquier excepción se declara en el audit-pack.
- **Byte-identidad con el flag OFF** (`AUTO_ENGINE_SIM_V2_OPTIMIZER=0`) ⇒ el camino V2 sigue siendo
  `v2.43.3`; **`AUTO-ENGINE_SIM_V2=0`** sigue siendo el camino legacy.
- **Los tags no se mueven**: `v2.45-beta` y anteriores quedan donde están; `v2.46-beta` será ref nueva.
- **Los gates PG** (`*_PG_REQUIRED`) y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo
  **no** certifica.
- **El spine de settlement y la identidad de salida no se rediseñan**: si un escenario descubre un fallo,
  se arregla **con** su mutación, no se reescribe la pieza.

## 3. Piezas (qué se extiende, no qué se reinventa)

### 3.1 El escenario `Crash/Recovery Day` (capa de proceso real)

El patrón **ya está medido** en `AUTO-5` (`apps/api-python/tests/test_golden_day_v2_process_pg.py`): dos
fases, dos arranques del **mismo** engine, `subprocess.Popen([sys.executable, "-m",
"bolsa_api.workers.scheduler_worker"])`, gate `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1` y presupuestos declarados
(`_STARTUP_GRACE_S`, `_OPEN_POLLS`, `_CLOSE_POLLS`, `_CLOSED_DAY_POLLS`) con fallo **al instante** si el
subproceso muere. Se **copia el patrón**, no el fichero.

Lo nuevo es la **muerte sucia en medio de un fill parcial**:

1. **Apertura con fill parcial.** Hace falta que la orden quede **a medias** (una trancha aplicada y cola
   pendiente) **cuando** se mata el proceso. La palanca ya existe y es determinista: el ruido de la cola
   SIM sale de `sha256(seed, instrument_id, side, …)`, así que un `instrument_id` **barrido** (el truco
   `_filling_instrument_id` de `AUTO-5`) da el reparto de tranchas **fijo** en toda la ventana de ticks;
   si ningún candidato cumple el reparto exigido, el test **falla con diagnóstico**, no por sorteo.
2. **MUERTE.** `terminate()` (y `SIGKILL` en POSIX) — la RAM se pierde **de verdad**; nada de un
   reinicio “limpio” del objeto worker.
3. **REINICIO.** El mismo engine sobre la **misma BD**: el worker debe **rehidratar** el plan
   (`_v2_plan`) y **reconciliar** (§3.3).
4. **RECONCILIACIÓN + continuar.** La cola pendiente se materializa (su `ExecutionEvent` pasa a
   `APPLIED` con su transacción) o se libera; **nunca** se duplica el efecto financiero.
5. **SALIDA LIMPIA.** Cierre por el seam durable (llevar `holdingDeadlineAt` al pasado y reiniciar, como
   `AUTO-5` D1 — el precio SIM es plano y el horizonte de 21–90 días no cabe en un test).

**Invariantes que se certifican:** `fills > orders` (hubo tranchas), **todo** `ExecutionEvent` en
`APPLIED`, **cada** fill con su transacción (`transactions.idempotency_key`), `POSITION == Σ APPLIED BUY −
Σ APPLIED SELL`, libro plano y **equity invariante** al final.

### 3.2 El escenario `Concurrent AUTO`

**Hermético (por commit).** Tres workers A/B/C (objetos `AutoSimulationWorker` sobre **los mismos stores
durables** compartidos) con reloj determinista, sobre **la misma cuenta / cartera / señales**. Se reutiliza
la infraestructura de `apps/api-python/tests/test_a9_1_crash_battery.py` y
`test_auto_v44_exit_crash_matrix.py` (stores in-memory durables + `step_minute_clock`). Invariantes:

- **1 señal ⇒ 1 orden**: `count(distinct venue_order_id)` por señal **≤ 1** (la identidad de señal ya es
  obligatoria desde `V2.40.1`: `signal_id` + `canonical_candidate_key`; el dedupe no se reinventa).
- **Sin sobre-riesgo**: `Σ capital reservado ≤ presupuesto` en **todo** instante intermedio.
- **Sin reserva duplicada**: `Σ all() == Σ live()` (el invariante de doble vía que ya existe en
  `packages/py/application/tests/test_portfolio_reservation.py`).
- **Fills correctos**: `Σ` cantidades de fills `APPLIED` == cantidad pedida, sin doble efecto.

**Gemelo PG real (al sellar).** Un escenario **estrecho** contra PostgreSQL real, en la línea de
`apps/api-python/tests/test_live_order_recovery_concurrency_pg.py` (dos transacciones simultáneas con
`SKIP LOCKED`) y de `test_lifecycle_outbox_worker_pg.py::test_two_workers_same_position_fifo_open_t1_exit`
(dos workers sobre la misma posición): tres sesiones concurrentes que ejecutan el tick sobre la **misma**
cuenta y se comprueba que la unión de órdenes **no duplica** ninguna y que el capital reservado no se
sobrepasa. **Decisión abierta (§0):** ¿tres **procesos** `scheduler_worker` reales (máxima fidelidad,
job más caro y más frágil) o tres **sesiones** concurrentes sobre un PG real (fidelidad suficiente,
presupuesto acotado)? Este plan propone **sesiones** y deja los procesos como escalada si el owner lo pide.

### 3.3 Reconciliación en el reinicio — **reutilizar, no reinventar**

El motor ya mantiene **tres vistas** de la misma verdad y ya sabe decidir (`sim_reconciliation.py`):
`expected` (Σ `ExecutionEvent` aplicados) vs `actual` (estado financiero canónico) vs `projection`
(`sim_auto_positions`), con veredictos `OK` / `REBUILT` / `DIVERGENT` / `UNKNOWN`. Regla de oro ya
declarada: **una proyección no autoriza por sí sola una compra**; ante `DIVERGENT`/`UNKNOWN` se bloquean
las aperturas. El worker ya la consume en el arranque (`auto_simulation_worker.py:903`, `:929`, `:1102`,
`:2774`). `AUTO-6` **no** añade motor de reconciliación: **exige que converja** tras la muerte y **mide**
el resultado (`REBUILT`/`OK`, nunca `DIVERGENT` al final).

Para la cola en vuelo se reutilizan las piezas que ya cerraron el P0 de dinero de `V2.40.3`: la **clave de
idempotencia sin pérdida** (`packages/py/application/src/bolsa_application/idempotency_key.py`) y el
**libro de pendientes** de `V2.40.4`/`AUTO-1A` (`ExecutionEventStore.list_unapplied`, `OpenOrder`).

### 3.4 Reason codes y journal

Si un escenario necesita **declarar** un desenlace nuevo (p. ej. «reconciliación tras crash», «reserva
liberada por reinicio»), el literal va a `auto_reason_codes.py` — la **casa única** — y **no** reutiliza un
texto existente que signifique otra cosa (lección de `v2.44`: `edge_below_threshold` para una candidata no
elegida habría sido **falso**). `RESERVATION_RELEASED_BY_RESTART` ya existe.

### 3.5 Matriz de mutaciones y docs de auditoría

Script propio de la fase (`apps/api-python/scripts/v2_46_mutation_audit.py`, patrón
`v2_45_mutation_audit.py`): cada invariante nuevo debe tener **su mutación que ponga la suite en rojo**, con
la **huella del árbol intacta** antes y después (`git status --porcelain`) y restauración **desde memoria**
(nunca `git checkout --`). Cierre documental: `audit-pack-v2.46-…`, `arranque-auditor-v2.46-…`, bump
`1.70.0-beta → 1.71.0-beta` en `package.json` + `CHANGELOG.md`, y una línea `AUDIT-PACK` nueva en
`PROJECT_STATE.md` e `engineering-index-2026-08-03.md`.

## 4. Gate (lo que mide el roadmap §8)

| Capa                       | Dónde                        | Escenario                    | Gate                                            |
| -------------------------- | ---------------------------- | ---------------------------- | ----------------------------------------------- |
| Hermética (núcleo)         | `quality` de `python-ci.yml` | `Concurrent AUTO` (A/B/C)    | sin gate PG (no toca la BD)                     |
| Hermética (núcleo)         | `quality` de `python-ci.yml` | `Crash/Recovery` (inyección) | sin gate PG                                     |
| **Real (PG + proceso)**    | `lifecycle-pg` del **tag**   | `Crash/Recovery Day`         | `AUTO_CRASH_RECOVERY_PG_REQUIRED=1` + anti-skip |
| **Real (PG, concurrente)** | `lifecycle-pg` del **tag**   | `Concurrent AUTO`            | `AUTO_CONCURRENT_PG_REQUIRED=1` + anti-skip     |

Requisitos de cableado (un fichero nuevo **no entra solo**, y esto ya mordió en `AUTO-5`):

- Ficheros nuevos en `apps/api-python/tests` entran por el **pase de directorio** (`python-ci.yml:189`)
  **salvo** que estén en los `--ignore`. Ficheros nuevos en `packages/py/application/tests` o
  `packages/py/infrastructure/tests` **NO entran solos**: esa lista es **explícita, fichero a fichero**, y
  una ruta inexistente aborta pytest con `exit 4`.
- Ficheros PG a los `--ignore` de **los dos** jobs offline (`quality` en `python-ci.yml:190-219`; job
  `python` del tag en `release-tag-ci.yml:427-429`).
- **Paso dedicado** por escenario en `lifecycle-pg` con `set -o pipefail` + `tee` a log + guard anti-skip
  (`log no vacío` + `grep` de `skipped`), como el paso del día real de `AUTO-5`
  (`release-tag-ci.yml:654-674`). **Comentarios FUERA del bloque `run: >`** (un `#` intercalado convirtió
  un step en 936 tests en `V2.40.2`).
- **Sin `run_tick()` manual** en los escenarios reales: el día lo conduce el proceso.
- `certify` ya depende de `lifecycle-pg` (`release-tag-ci.yml:844`): **no** hay que tocar sus `needs:` con
  esta opción.

## 5. Criterios de salida

1. **`Crash/Recovery Day` verde** en el tag: muerte sucia a mitad de fill parcial, reinicio, reconciliación
   convergente (`OK`/`REBUILT`), **todo** `APPLIED`, cada fill con su transacción, libro plano y equity
   invariante; **sin doble BUY** y **sin doble efecto financiero**.
2. **`Concurrent AUTO` verde** en las dos capas: `1 señal ⇒ 1 orden`, `Σ reservado ≤ presupuesto` en todo
   instante, sin reserva duplicada, `Σ` fills == cantidad pedida.
3. **Ambos escenarios presentes en el CI del tag** con su gate fail-if-skipped y su guard anti-skip.
4. **Matriz de mutaciones medida**: cada invariante nuevo tiene su mutación que pone la suite en rojo, con
   la huella del árbol intacta.
5. **Cifras citadas del run que las produjo** (aprendizaje de `v2.44` §5 / `v2.45` §8).

## 6. Límites previstos (declarar, no maquillar)

1. **MAE/MFE se recogen, no se calibran**; **sin productor de economía en el tick** (`p_win`/medias son de
   `AUTO-7`): el escenario concurrente **no** puede apoyarse en que el optimizador elija por valor
   esperado real.
2. **Precio SIM plano y horizonte 21–90 días**: el cierre del día sigue siendo por el **seam durable**
   (`holdingDeadlineAt` vencido), no por geometría (heredado de `AUTO-5` D1).
3. **El bucle AUTO SIM no escribe el journal durable** (D2 de `AUTO-5`): los agregados post-crash se leen
   de `execution_events` / `sim_*` / `transactions`, **no** del journal.
4. **Presupuesto de tiempo del job del tag**: dos escenarios nuevos alargan `lifecycle-pg`; cada uno
   declara su techo por fase y **falla con diagnóstico**, no se queda en silencio.
5. **Límite de método**: no correr dos sesiones de pytest en paralelo contra la misma base (el barrido de
   residuos del conftest se borra los datos entre sí) ⇒ pasos dedicados, sin solape.
6. **Window/POSIX**: la muerte sucia “de verdad” es `SIGKILL` (POSIX, CI Linux); en Windows `terminate()`
   es lo máximo disponible. El test debe **declararlo**, no fingir equivalencia.

## 7. Estado de ejecución (cerrado 2026-09-20)

**Cifras locales de esta máquina** (PostgreSQL del `docker-compose.yml` **alcanzable** en
`localhost:5432`, así que las dos capas —hermética y real— se midieron aquí; el CI del tag las
re-mide como gate).

| Pieza del plan (§)                                                           | Estado    | Fichero                                                                                                                                                                                                           |
| ---------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §3.1 Crash/Recovery **hermético** (por commit)                               | **hecho** | `apps/api-python/tests/test_auto_v46_crash_recovery.py` (NUEVO, 2 tests)                                                                                                                                          |
| §3.2 Concurrent AUTO **hermético** (por commit)                              | **hecho** | `apps/api-python/tests/test_auto_v46_concurrent.py` (NUEVO, 2 tests)                                                                                                                                              |
| §3.1 Crash/Recovery **real** (proceso + PG, al sellar)                       | **hecho** | `apps/api-python/tests/test_crash_recovery_day_process_pg.py` (NUEVO, 1 test)                                                                                                                                     |
| §3.2 Concurrent AUTO **real** (gemelo estrecho, al sellar)                   | **hecho** | `apps/api-python/tests/test_concurrent_auto_pg.py` (NUEVO, 1 test)                                                                                                                                                |
| §3.2 claim atómico (el «arreglo mínimo sin migración» que el plan autoriza)  | **hecho** | `auto_v2_entry.py` (`entry_decision_id` + `decision_id` del plan del tick) · `reservation_store.py` (`save_claim` en protocolo/InMemory/Postgres) · `auto_simulation_worker.py` (`_v2_persist_tick_reservations`) |
| §3.5 Matriz de mutaciones                                                    | **hecho** | `apps/api-python/scripts/v2_46_mutation_audit.py` (NUEVO, 6 mutaciones, 6/6 muerden)                                                                                                                              |
| §4 Cableado de CI (dos `--ignore` + dos pasos dedicados + gates + anti-skip) | **hecho** | `.github/workflows/python-ci.yml`, `.github/workflows/release-tag-ci.yml`                                                                                                                                         |
| §5 Cierre documental                                                         | **hecho** | este §7/§8 + `audit-pack-v2.46-…` + `arranque-auditor-v2.46-…` + bump/CHANGELOG/PROJECT_STATE/engineering-index                                                                                                   |

### 7.1 Desviaciones declaradas frente a lo que este plan decía

1. **La «muerte en mitad del fill» no es observable en vivo** (§2.3 del plan lo dejaba abierto
   como plan B: «si la cola SIM materializa todo dentro de un tick … se siembra el parcial
   durable y se mata el proceso»). **Medido**: el venue SIM aplica el **schedule completo de la
   orden dentro del mismo tick** (`_settle`), así que la ventana «parcial en vuelo» **no
   existe**. La capa real **no siembra nada**: el parcial durable lo produce el propio proceso
   (una orden BUY cortada con la cola sin llenar, `status='partial'` + reserva viva) y **se
   mata el proceso sobre ese estado**. Lo certificado es el **estado durable del fill parcial**
   y su cierre contable tras el reinicio, **no** una interrupción en vuelo imposible por
   construcción del venue. Está declarado en el docstring del propio test, no maquillado.
2. **Muerte sucia = `terminate()` en Windows / `kill()` en POSIX**. La plataforma de esta
   máquina es Windows: la muerte «de verdad» (`SIGKILL`) es la del CI Linux y el test usa el
   máximo disponible en cada plataforma, declarándolo. No se finge equivalencia.
3. **El arreglo de concurrencia fue el que el plan anticipó** (§2.2 «nota de honestidad»:
   derivar la identidad de la reserva de la identidad determinista de la señal): la identidad
   de la decisión de entrada pasa a derivarse de `(cuenta, señal)` y la reserva se compromete
   con **claim atómico** (`save_claim`: `INSERT … ON CONFLICT DO NOTHING` + `UPDATE`
   condicional + `RETURNING`), **sin migración**. **No** hizo falta la escalada a «serializar el
   tramo leer-presupuesto → reservar» (locks explícitos) ni una restricción de esquema nueva.
4. **La identidad determinista entra en la costura que el camino V2 usa con o sin optimizador**
   (declarado, porque roza el freeze del plan §2). `decision_id=entry_decision_id(...)` se pasa en
   `plan_v2_tick` **sin** depender de `AUTO_ENGINE_SIM_V2_OPTIMIZER`, así que la **byte-identidad**
   del camino V2 con el flag del optimizador **OFF** se conserva en **producto** (no se construye
   ninguna candidata, el journal **no** gana claves y `V2TickPlan.optimizer` queda `None`) pero
   **no** en la identidad de la reserva: los ids pasan de **aleatorios**
   (`portfolio_decision_engine.py:444`, `dec-<uuid4>`) a **deterministas** por `(cuenta, señal)`.
   Eso **es** el arreglo que el plan autoriza (§2.2) y su efecto observable es precisamente el que
   el escenario concurrente demostró: dos compromisos de capital sobre la misma oportunidad dejan
   de ser posibles. Nota de alcance: como con ids **aleatorios** la identidad de una reserva **no
   podía repetirse**, la distinción `save`/`save_claim` era **inalcanzable** en cualquier flujo
   histórico: el método nuevo es **neutro** para todo lo anterior y sólo muerde ahora que la
   identidad es estable. Con `AUTO-ENGINE-SIM-V2=0` el camino legacy no toca las reservas del tick
   y no cambia nada.
5. **Defecto semántico encontrado al medir la matriz (y arreglado, no tapado)**: el `save`
   histórico del store responde «¿la fila existía?» (idempotencia de replay). Leído como
   claim, **vetaba para siempre** la re-entrada sobre una identidad ya **liberada**
   (re-intento legítimo dentro de la barra). De ahí el método nuevo y explícito `save_claim`
   («¿soy el dueño del compromiso **vivo**?»), con su caso cubierto: la identidad liberada se
   **re-compromete**.
6. **La sonda de mutaciones se endureció sobre el patrón de `v2_45`** (declarado, porque
   cambia el mecanismo de dos garantías): (a) **sondeo de puerto** en vez de asumir el DSN
   fast-fail — en Windows un puerto cerrado **no** rechaza al instante y las suites de
   `apps/api-python` **se colgaban** en vez de devolver el rojo con nombre; (b) huella de
   integridad por **sha256 del raw** (los ficheros del árbol están en CRLF y
   `read_text`/`write_text` normalizan EOL: la comparación «byte a byte» habría medido la copia
   **normalizada**); (c) guarda que **aborta** si encuentra el marcador `# MUTATION:` al
   arrancar (una corrida interrumpida a mitad de mutación no puede pasar por «original»).
7. **Dos tests herméticos por escenario, no uno**: el escenario de crash hermético separa
   «sobrevive a la muerte y converge» de «libera la cola NO llenada de la reserva parcial»
   (esta última es la que mordió la mutación M2). El concurrente separa «la carrera de la
   primera oleada» de «la segunda oleada no añade ni una orden» (esta última es la que detecta
   la no-determinación de la identidad, M5).

### 7.2 Límites (heredados del plan §6, confirmados al ejecutar)

- MAE/MFE se **recogen**, no se calibran; sin productor de economía en el tick (`AUTO-7`).
- Precio SIM **plano** y horizonte 21–90 d ⇒ el cierre del día real es por **seam durable**
  (`holdingDeadlineAt` vencido + reinicio), no por geometría.
- El bucle AUTO SIM **no** escribe el journal durable ⇒ los agregados post-crash se leen de
  `execution_events` / `sim_*` / `transactions` / `portfolio_reservations`.
- **Límite de método**: no correr dos sesiones de pytest en paralelo contra la misma base (el
  purgado de residuos del conftest es de sesión) ⇒ cada escenario real va en **paso dedicado**
  del tag, sin solape.

## 8. Verificación (cada cifra, con el artefacto que la produjo)

Todo lo de esta tabla es **medición local de esta máquina el 2026-09-20**, con
`PostgreSQL` alcanzable (excepto las dos líneas de baseline offline, que no lo tocan). El sello
(commit de fase, runs de CI del `main` y del tag, ref `v2.46-beta`) se registra en §9 del
audit-pack: su mitad **producida** está en §8.2 de aquí abajo y en el §9.1 del pack, y **no se
atribuye ninguna cifra a un run que no exista**.

| Medida                                                    | Comando                                                                                                                                                 | Resultado medido                                                                       |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Ruff (CI-style, árbol completo)                           | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                                                                 | **0** (`All checks passed!`) — se corrigieron 12 `I001` propios **antes** de medir     |
| Mypy (full-tree, como CI)                                 | `uv run mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent`                                    | **489 files, 0 issues**                                                                |
| Import-linter                                             | `uv run lint-imports --config packages/py/.importlinter`                                                                                                | **4 kept, 0 broken**                                                                   |
| Gobernador congelado                                      | `git diff -- apps/api-python/scripts/v2_43_governor_evidence.py`                                                                                        | **vacío** (byte a byte igual)                                                          |
| Gobernador, ejecución                                     | `uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py`                                                                            | **`exit 0`** con `"bump": "1.68.0-beta"` conservado                                    |
| Las 4 suites nuevas de AUTO-6 (2 herm. + 2 PG)            | `AUTO_CRASH_RECOVERY_PG_REQUIRED=1 AUTO_CONCURRENT_PG_REQUIRED=1 uv run pytest <4 ficheros> -q`                                                         | **6 passed** (2+2+1+1) en **8,92 s**                                                   |
| Gemelos PG en solitario (capa real del tag)               | `AUTO_CRASH_RECOVERY_PG_REQUIRED=1 AUTO_CONCURRENT_PG_REQUIRED=1 uv run pytest test_crash_recovery_day_process_pg.py test_concurrent_auto_pg.py -q -rs` | **2 passed** en **8,66 s** (9,21 s de pared)                                           |
| Terreno AUTO-6 existente (no regresión)                   | `uv run pytest test_auto_v2_entry.py test_execution_event.py test_auto_v2_partial_fills.py test_auto_v46_*.py -q`                                       | **96 passed** en **1,03 s**                                                            |
| Baseline `quality` (`python-ci.yml`, del YAML, por JUnit) | `uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`                               | **2091 passed, 0 skipped, 0 failed** (v2.45: 2087 ⇒ **+4** exactos)                    |
| Baseline `python` del tag (del YAML, por JUnit)           | `uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores`                           | **2102 passed, 0 skipped, 0 failed** (v2.45: 2098 ⇒ **+4** exactos)                    |
| Matriz de mutaciones                                      | `uv run --no-sync python apps/api-python/scripts/v2_46_mutation_audit.py`                                                                               | **6/6 muerden**, `sha256` de los ficheros tocados **idéntico** antes/después, `exit 0` |

Los **`+4`** cuadran en los **dos** bloques offline porque los dos ficheros herméticos entran por
el **pase de directorio** de `apps/api-python/tests` (y sus gemelos PG van en `--ignore` de
**ambos** jobs offline, sin PG). Los **2** de la capa real viven en `lifecycle-pg` del tag con
paso dedicado y guard anti-skip.

### 8.1 Matriz de mutaciones (MEDIDA, no esperada)

`apps/api-python/scripts/v2_46_mutation_audit.py` — restauración **desde memoria** (nunca
`git checkout --`), aborta si el fragmento no es único, y **guarda anti-resto** (`# MUTATION:`
presente ⇒ aborta). Línea base de las cinco suites implicadas: **ningún rojo**.

| #   | Mutación                                                            | Costura de producción                                         | Test(s) en rojo                                                                                                  |
| --- | ------------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| M1  | la señal ya **consumida** deja de filtrarse                         | `auto_v2_entry.py` (`consumed_signal_ids`)                    | `test_plan_v2_tick_blocks_consumed_signal`, `test_crash_recovery_day_partial_fill_survives_kill_and_restart`     |
| M2  | el fill materializado deja de **liberar** el compromiso             | `auto_simulation_worker.py` (`_v2_reconcile_reservations`)    | `test_crash_recovery_releases_the_unfilled_tail_of_the_partial_reservation`                                      |
| M3  | una proyección **divergente** deja de vetar aperturas               | `auto_simulation_worker.py` (`_openings_vetoed`)              | `test_unreadable_ledger_vetoes_openings_and_keeps_position`                                                      |
| M4  | un `ExecutionEvent` ya **`APPLIED`** deja de atajarse               | `execution_event.py` (`apply_execution_financial_once`)       | `test_durable_apply_skips_when_already_applied`                                                                  |
| M5  | la identidad de la decisión de entrada deja de ser **determinista** | `auto_v2_entry.py` (`entry_decision_id`)                      | `test_concurrent_auto_three_workers_claim_one_signal_one_order`, `test_concurrent_auto_second_wave_adds_nothing` |
| M6  | el **perdedor** del claim emite igualmente su orden                 | `auto_simulation_worker.py` (`_v2_persist_tick_reservations`) | `test_concurrent_auto_three_workers_claim_one_signal_one_order`                                                  |

Artefacto de la corrida: `logs/agent/v2_46_mutation_audit.txt` (log local, no versionado).

### 8.2 Sello (producido: `main` y ref del tag)

Medido **en el CI real**, no en local, sobre el commit de fase
[`a14b71d7`](https://github.com/jvelasca/Bolsa_V1/commit/a14b71d750fd28f60b6ca7ec9db6e6cca020700e):

| Medida                                                            | Run / job                                                                                                                                                                                                                                                                                                                         | Resultado medido                                                                                                                                                                                                                                                               |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Python CI` en `main` (5/5 verde, 2m40s)                          | [`35534775724`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775724)                                                                                                                                                                                                                                                    | —                                                                                                                                                                                                                                                                              |
| · job `quality`                                                   | (mismo run)                                                                                                                                                                                                                                                                                                                       | **2091 passed, 38 skipped** en 115,49 s (los **+4** exactos sobre 2087)                                                                                                                                                                                                        |
| · job `auto-v2-durable-pg`                                        | (mismo run)                                                                                                                                                                                                                                                                                                                       | **43 passed**, **0 skipped** (sin cambio: no hay migración)                                                                                                                                                                                                                    |
| · jobs `lifecycle-pg` / `paper-forward-pg`                        | (mismo run)                                                                                                                                                                                                                                                                                                                       | **13** / **2 passed**; `grammar-discovery-pg` verde                                                                                                                                                                                                                            |
| `Gitleaks` / `Frontend CI` / `Optimize lab` / `Fase 2 scientific` | [`35534775676`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775676) · [`35534775682`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775682) · [`35534775681`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775681) · [`35534775675`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35534775675) | **GREEN** (11s / 3m25s / 1m30s / 1m18s)                                                                                                                                                                                                                                        |
| `Release tag CI` + tag `v2.46-beta`                               | [`35535111995`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535111995) (8m5s) · `Python CI` en la ref del tag [`35535111988`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35535111988)                                                                                                                              | `certify` **success**; job `python` offline **2102 passed, 35 skipped**; `lifecycle-pg` **148 + 45** y los **dos pasos dedicados nuevos** (**1 passed** cada uno: 9,44 s y 1,64 s) con sus guards anti-skip verdes; en la ref del tag `quality` **2091** / `durable-pg` **43** |

El `quality` de CI da **2091 passed** y el baseline local del **mismo YAML** (medido aquí con el runner
versionado, por JUnit: `{'tests': 2091, 'failures': 0, 'errors': 0, 'skipped': 0, 'passed': 2091}`)
también **2091 passed**: cuadra al dígito, así que la predicción del §9 del pack («debe dar 2091») se
cumple. **Divergencia declarada, no inventada**: el job de CI publica además **38 skipped** que el runner
local **no recolecta** (CI total `2129` vs local `2091`) — es la **misma** divergencia estable de
`v2.45-beta` (CI `2087 passed / 38 skipped` frente a local `2087 passed / 0 skipped`), es decir
**pre-existente y ajena a esta fase**; no se le atribuye aquí una causa medida porque no se ha medido.
