# Traspaso de relevo — post `V2.52` (`AUTO-11` Estado Adaptive durable y recuperación)

**Fase:** `AUTO-11` (`V2.52` / `1.77.0-beta`) · **Fecha:** 2026-09-23 · **Fase anterior:** `V2.51`
(`AUTO-10` Journal durable por ciclo).
**Documentos de la fase:** [audit-pack](./audit-pack-v2-52-auto-11-estado-adaptive-durable-2026-09-23.md)
· [plan](./plan-v2-52-auto-11-estado-adaptive-durable-2026-09-23.md).
**Rótulo ratificado por el propietario:** `AUTO-11` sobre `V2.52` / `1.77.0-beta`, con tres
decisiones explícitas: **cooldown durable hoy por el journal (sin migración)**, **alcance `AUTO-11`
core** (`confidence` y la ventana recent/long/decay quedan para `AUTO-12`/`AUTO-13`) y **higiene
incluida en la misma fase**.

---

## 0. Posición en la línea AUTO

`v2.48` = `AUTO-8` (Adaptive AUTO) · `v2.49` = `AUTO-8.1` (Adaptive correcto, explícito y
reproducible) · `v2.50` = `AUTO-9` (Strategy × Regime y net expectancy_R) · `v2.51` = `AUTO-10`
(Journal durable por ciclo) · **`v2.52` = `AUTO-11` (Estado Adaptive durable y recuperación)**: el
**cooldown deja de vivir en la memoria del proceso** y se reconstruye del journal durable, la
recomendación Adaptive queda publicada como evidencia y el rastro de ciclo se reconcilia al arrancar.
**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`).

---

## 1. Qué quedó HECHO y medido en esta fase

1. **Contrato puro** `auto_adaptive_journal.py`: `AUTO_ADAPTIVE_RECOMMENDATION_EVENT =
   "adaptive_recommendation"`, `adaptive_recommendation_decision_id(account, asOf)` determinista
   (`dec-adap-<hash>`, único si no hay sello) y `build_adaptive_recommendation_entry(...)` con payload
   **proyectado por lista blanca** (`asOf`, `readOnly`, `policyVersion`, `regime`, `rotation`,
   `allocation`, `pausedCycles`, `healthByStrategy`). `None` sin plan.
2. **Recuperación pura** `auto_adaptive_recovery.py`: `AdaptiveStateReading` +
   `rebuild_paused_cycles(rows, *, min_pause_cycles)` → racha **trailing** por versión (nueva→vieja),
   **saturada** en `min_pause_cycles + 1`, con dedupe **por turno** (`collapsed`) y cuatro huecos
   declarados: `read_ok=False`, `insufficient_history`, `unreadable` y `policy_version_mismatch`.
3. **Reconciliación** `auto_cycle_reconciliation.py` + `list_recent_with_cycle` en `reservation_store`
   (Protocol + `InMemory` + `Postgres`, por la columna `cycle_id` indexada desde `044`): cuatro
   desajustes con nombre (`missing` con motivo, `unrequested`, `not_derivable`, `orphan`).
4. **Cableado en el worker**: `build_adaptive_recommendation_sink(session)` (con **`commit`** propio y
   `rollback` en el fallo) y `build_adaptive_state_reader(session, *, policy)`; inyección por sesión
   con reset en `finally`; `_v2_recover_adaptive_state()` y `_v2_reconcile_cycle_traces()` **una vez
   por proceso** en `run_tick`, gateadas por `adaptive_enabled` (con el flag OFF, **cero** I/O);
   publicación tras `plan_v2_tick` con el contador que **entró** (`_v2_adaptive_paused_cycles_entered`).
5. **Higiene (los tres hallazgos de la auditoría de `v2.51-beta`)**: `duplicates` cuenta **solo trazas
   confirmantes** de más y `extra_rows` **todas** las filas de más; el denominador de `R` se ordena por
   **instante** (`_instant`/`_antiquity_key`) con el no-parseable al final y **declarado**
   (`CYCLE_RISK_UNDATED_RESERVATION`); y el régimen del turno se **hojea fuera** del bucle de reservas
   (todos los ciclos del turno publican el régimen que decidió).
6. **Un cuarto hallazgo, de cobertura, y el cierre**: `M39` había dejado de morder porque la guarda de
   `cycleId` quedó **duplicada e inobservable** al filtrar por identidad antes de leer el régimen. La
   identidad de la traza pasa a vivir en **un solo sitio** (`_is_trace`, compartida por el recuento de
   trazas y la lectura) y `M39` muerde otra vez. Ver §3.1 — es la trampa más importante de esta fase.
7. **Verificación**: **+64 tests** exactos, simétricos en los dos bloques offline — `quality`
   **2398 passed / 38 skipped** y job `python` del tag **2409 passed / 35 skipped**, **0 rojos** en
   ambos (la base de CI de `v2.51` era 2334/38 y `2334 + 64 = 2398`: los `skipped` cuadran uno a uno);
   `mypy` **0 errores / 497 ficheros**, `import-linter` **4/4**, `ruff` limpio; **59/59** mutaciones
   muerden con el árbol intacto y **0** no detectadas.
8. **El delta se midió fichero a fichero contra `HEAD`**, no restando totales de fases anteriores:
   +13 `test_auto_adaptive_journal.py` · +16 `test_auto_adaptive_recovery.py` · +10
   `test_auto_cycle_reconciliation.py` · +21 `test_auto_v52_auto11_adaptive_state_seam.py` · +3
   `test_cycle_risk.py` (`HEAD` 23 → 26) · +1 `test_auto_cycle_regime_reader.py` (`HEAD` 17 → 18). Y
   los dos ficheros **modificados** se corrieron en su versión de `HEAD` contra el código de la fase:
   `test_cycle_risk.py` pasa **23/23** (el cambio de orden es retrocompatible) y del lector de régimen
   falla **exactamente 1**, que es la expectativa que la fase actualiza (rojo **nombrado**).

---

## 2. Límites declarados (no silenciosos)

- **La ventana de lectura es finita** (`ADAPTIVE_STATE_WINDOW_DEFAULT = 50`). Con menos filas que la
  ventana, `insufficient_history` está **declarado**: la racha es un **suelo**, no una promesa.
- **`bounded` no es el número exacto**: el contador se satura en `min_pause_cycles + 1`. El plan no
  necesita más (su único consumo es `< min_pause_cycles` y `<= 0`) y la lectura lo dice.
- **El pasado no se reescribe.** Si el journal no tiene evidencia de una pausa (se decidió antes de
  esta fase), el contador arranca **vacío y declarado**: `AUTO-11` **no** inventa historia ni hace
  backfill.
- **`confidence` y la ventana recent/long/decay siguen fuera**: son `AUTO-12`/`AUTO-13`.
- **La tabla de estado dedicada no existe**: el cooldown vive **derivado** del journal. Si el volumen
  lo pide, la decisión es una tabla (o un índice), **nunca** cambiar la semántica del contador.
- **Sin UI** para `AUTO-7`/`AUTO-8`/`AUTO-9`/`AUTO-10`/`AUTO-11`.
- **`governor.json` sigue sin trackear.**

---

## 3. Trampas del entorno y de método medidas (para no repetirlas)

1. **Una guarda DUPLICADA es una guarda inobservable, y la sonda no puede morderla.** Al separar
   `duplicates` de `extra_rows`, el camino de lectura pasó a filtrar por identidad (`traces`) antes de
   pedir el régimen, así que la comprobación de `cycleId` en `_confirmed_regime` quedó **redundante**:
   `M39` dejó de morder y la matriz **afirmaba cobertura que no tenía** (la lección del `33/33` de
   `V2.51`, en su forma pura). Cierre: **una sola puerta de identidad** (`_is_trace`) compartida por
   los dos consumidores, y `M39` muta esa guarda compartida. **Regla de método**: antes de dar por
   buena una matriz, comprobar que **ninguna mutación devuelve `NADA`** — la sonda falla si falta un
   fragmento, pero **no** si un fragmento muerde el aire; eso hay que mirarlo a mano.
2. **Un `replace(..., 1)` sobre un fragmento que aparece dos veces muta la PRIMERA.** El sink de
   `AUTO-11` es calcado del de `AUTO-10` (mismo `append` + `commit`), así que `M38` pasó a aparecer
   **dos** veces: la sonda **abortó** (hizo lo correcto) y el fragmento se reescribió con la cola del
   `except`, que es única de cada sink. **Regla**: cuando se copia un patrón, revisar las mutaciones
   que lo citaban.
3. **La base de un delta se mide, no se hereda.** Aquí se midió **fichero a fichero** contra `HEAD`
   (`git show HEAD:<path>` a un fichero temporal y contar), en lugar de restar totales de fases
   anteriores: los targets y el entorno cambian, y el número restado sería inventado.
4. **Un bloque offline se mide con la MISMA extracción que CI.** La lista de targets se lee del propio
   YAML y se corre **sin PostgreSQL** (DSN a un puerto cerrado + `PGCONNECT_TIMEOUT`), para que los
   `skipped` sean los del job (`38` en `quality`) y la comparación signifique algo. Con la base de
   desarrollo levantada, suites PG **con** `--ignore` en el YAML corren igual en local y pueden fallar
   por **orden**.
5. **`ruff format` no se corre en masa**: el repo tiene *drift* de formato respecto a la config raíz y
   formatear en masa reescribe cientos de ficheros ajenos (lección de `V2.50`). El `I001` de esta fase
   se corrigió con `ruff check --fix` **solo sobre el fichero nuevo**.
6. **Escribir muchos `.py` seguidos en Windows puede dar `OSError [Errno 22]`** en la restauración
   masiva de la sonda; por eso la sonda reintenta y usa `os.replace`, y **aborta** en vez de dejar el
   mutante dentro.
7. **No usar `git push --follow-tags`** con tags locales antiguos: más de tres tags en un push **no**
   disparan los workflows de tag en GitHub.
8. **`ruff` da resultados distintos según desde dónde se invoque.** El gate de CI es
   `uv run ruff check packages/py apps/api-python --config pyproject.toml` (config **raíz**, con
   `known-first-party = [bolsa_ai, bolsa_analytics, bolsa_api, bolsa_application, …]`). Invocarlo con
   rutas sueltas y **sin** `--config` resuelve el `pyproject.toml` **de la distribución**
   (`packages/py/application/pyproject.toml`, que **no** declara `known-first-party`), así que los
   `bolsa_*` pasan a terceros y aparecen **11 `I001`** que el gate **no** ve. Medido en esta fase:
   con rutas sueltas `11 errors`, con el comando de CI `All checks passed!`. **Regla**: medir siempre
   con el comando exacto del YAML antes de declarar «ruff limpio» (o de «arreglar» formatos que CI
   no pide).

---

## 4. Qué mirar primero si hay que auditar esta fase

1. **El invariante**: `packages/py/application/src/bolsa_application/auto_adaptive_journal.py`
   (`None` sin plan, identidad por turno, `readOnly`, proyección por lista blanca) y
   `auto_adaptive_recovery.py` (racha trailing, saturación, dedupe por turno y los cuatro huecos).
2. **El orden del efecto**: en `auto_simulation_worker.py`, `_v2_persist_tick_reservations` (primero el
   capital) y `_v2_journal_adaptive_recommendation` (después la traza); y en `run_tick`,
   `_v2_recover_adaptive_state()` **antes** del primer plan del proceso.
3. **La frontera del cooldown**: `test_a_crash_during_the_cooldown_is_healed_from_the_journal` y
   `test_the_thresholds_alone_would_lift_the_pause_before_its_minimum_window` (el bug **aislado**: sin
   memoria, los umbrales solos levantan la pausa).
4. **La guarda única de identidad**: `_is_trace` en `auto_cycle_regime_reader.py`, y que `M39` mute
   **esa** guarda (no una copia en el camino de lectura).
5. **La partición de los desajustes** en `auto_cycle_reconciliation.py` y su costura
   (`test_a_reserved_cycle_without_a_confirmed_trace_is_declared_at_startup`).
6. **La matriz**: `apps/api-python/scripts/v2_44_mutation_audit.py` (`M42…M59`), y **comprobar que
   ninguna etiqueta devuelve `NADA`** (ver §3.1).

**Siguiente fase natural:** continuar por el traspaso de la línea AUTO según el
[roadmap](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md): el **`confidence` del Adaptive** y la
**ventana recent/long/decay** (`AUTO-12`/`AUTO-13`, ya declarados fuera de alcance aquí), y/o la **UI
de `AUTO-7`…`AUTO-10`** (el cruce `strategy × regime` y la evidencia Adaptativa ya existen y **no** se
ven). Sin migración decidida todavía para ninguna de las dos.
