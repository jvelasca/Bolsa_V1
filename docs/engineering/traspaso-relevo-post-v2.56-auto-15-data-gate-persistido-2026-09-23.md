# Traspaso de relevo — `AUTO-15` **CERRADA** (`V2.56` / `1.81.0-beta`)

**Fase:** `AUTO-15` (Data Gate **persistido**) · **Fecha:** 2026-09-23 · **Fase anterior:** `V2.55` /
`AUTO-14` (sellada: tag `v2.55-beta` → `e29e6227`, `Release tag CI` `35889751810` **GREEN**,
`1.80.0-beta`, PR de auditoría [#64](https://github.com/jvelasca/Bolsa_V1/pull/64)).
**Documentos de la fase:**
[plan](./plan-v2-56-auto-15-data-gate-persistido-2026-09-23.md) (ratificado) ·
[audit-pack](./audit-pack-v2-56-auto-15-data-gate-persistido-2026-09-23.md) ·
[arranque del auditor](./arranque-auditor-v2.56-auto-15-data-gate-persistido-2026-09-23.md) ·
[arranque del agente siguiente](./arranque-agente-post-v2.56-auto-15-2026-09-23.md) · este relevo.
**Estado:** **fase CERRADA** — Pasos 1–5 hechos y verificados, tag **`v2.56-beta`** con su CI (cifras
medidas en §6). **El runtime sigue siendo el de `v2.53-beta`** con el flag Adaptive **OFF**: sin racha que
leer ni que escribir, esta fase **no ejecuta ni un I/O nuevo**. `main` recibe la fase **al sellar**
(fast-forward lineal, como en `v2.50`–`v2.55`), sin merge commit.

> **Este documento es la fuente de verdad de la fase CERRADA.** Se lee **antes** que
> [`PROJECT_STATE.md`](./PROJECT_STATE.md), que ya publica esta fase como la última cerrada y apunta
> aquí como relevo vivo.

---

## 0. Qué está ratificado y qué se ejecutó

**Rótulo ratificado por el propietario:** `AUTO-15` sobre **`V2.56` / `1.81.0-beta`**, **Opción A** del
arranque anterior, con alcance **core backend**, **sin UI**, **sin tocar el gobernador** y **sin clave
nueva en el journal durable**. **SÍ exige migración**, y quedó justificado y medido: la racha nace de un
**fallo de escritura** que no dejó fila en `decision_journal_entries`, y el ancla durable de `AUTO-13`
mide *publicación*, no *error*.

**Las dos decisiones abiertas del plan se cerraron a favor de lo propuesto:**

1. **Granularidad de la PK:** `(account_id, engine_id)`. Con `(account_id)` a secas, dos motores de la
   misma cuenta compartirían racha y uno **curaría** el fallo del otro.
2. **Reset en el éxito:** `UPDATE … WHERE sink_failures > 0` (sin amplificación). Escribir siempre pagaría
   una escritura por tick para no ganar nada.

**Los candidatos declarados por `AUTO-14` y qué pasó con ellos:**

| # | Candidato | Decisión |
| --- | --- | --- |
| **A** | **Data Gate persistido** (el contador de fallos se perdía al reiniciar) | **RATIFICADO y EJECUTADO** (esta fase) |
| B | **UI** de `AUTO-7`…`AUTO-15` | **Fuera de alcance**, declarado (§7) |
| C | **Coste REAL por ciclo** (hoy estimado ⇒ R neto `PARTIAL`) | **Fuera de alcance**, declarado (§7) |

**Lo que la ejecución confirmó y conviene no perder:**

1. **La persistencia es de la RACHA, no del gate.** El estado del gate sigue siendo una **lectura** del
   tick: lo que viaja a la BD es el hecho que el gate no puede reconstruir.
2. **El camino sano no escribe.** Sin racha viva no hay `UPDATE` (ni fila creada): el «sin amplificación»
   del plan es un hecho medido en PG (`record_success` devuelve `0` y `updated_at` no se mueve).
3. **La procedencia se declara, no gradua.** `sinkFailuresDurable` es un campo **propio** y por defecto
   `false`: el gate da el **mismo** estado con la racha durable que con la de proceso.
4. **La siembra va ANTES de los atajos del lector del journal.** El escenario donde más importa —el
   journal **roto**— es justo el que deja `read_ok = False`; sembrar después habría reiniciado la racha
   a `0` precisamente cuando hacía falta (`M108`).
5. **Un fallo de escritura no envenena la sesión del tick.** El store hace `rollback` y **sube** el
   error (contrato de `AUTO-10`): sin él, el siguiente store del turno moriría con
   `PendingRollbackError` (`M117`/`M118`).
6. **El sello del gate sube sin consecuencia de mismatch.** `policy_version_mismatch` que recibe el gate
   sale del **estado Adaptive**, no de `DATA_GATE_POLICY_VERSION`: por eso `auto15-v1` **no** marca un
   tick `STALE` en filas históricas (a diferencia de `auto14-v1`, que **sí** se compara sobre el journal).

---

## 1. Estado medido del repo (2026-09-23)

- **Rama:** `main` (la fase **viajó** en fast-forward lineal, **sin merge commit y sin rama de fase en el
  sello**). **Superficie de auditoría abierta POST-sello** (declarada, no silenciosa): la rama
  `auto-15-data-gate-persistido` con su **PR draft** sobre una base anclada en `b96ae624` (el commit
  justo anterior a la fase: el plan ratificado), abierto
  **después** del sello **solo** para que el auditor externo revise el delta con comentarios en línea; su
  **diff medido** y el enlace del PR se declaran en el commit de docs **posterior** al sello (mismo patrón
  que `AUTO-14`). **No** es vehículo de merge: `main` ya la recibió. Árbol limpio **salvo `governor.json`**
  (sin trackear, como estaba).
- **Base:** `e29e6227` (el commit sellado de `AUTO-14`) más sus dos commits de documentación de sello.
- **RE-SELLO declarado (no silencioso):** el **primer** CI del tag apuntó a `c62ac459` y salió **ROJO** —
  causa raíz única, repetida en los tres jobs PG afectados:
  `assert '045_adaptive_gate_state' == '044_auto_cycle_trace'`, porque
  `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` ancla la head de Alembic en
  `_ALEMBIC_HEAD` (**5** aserciones que solo corren en los jobs PG, que la matriz offline **ignora**) y la
  fase subió la head a `045` sin bumpearla. Fix de **una línea** verificado **replicando los dos jobs de CI**
  contra el PostgreSQL real del compose: `auto-v2-durable-pg` **`51 passed`** y `grammar-discovery-pg`
  **`21 passed`**. El tag `v2.56-beta` se **borra y se re-crea** en el commit del fix, **`8ad54416`**
  (patrón `v2.40.2-beta`/`v2.16-beta`), porque un CI de tag rojo **no certifica nada**:
  `c62ac459` queda en la historia con su rojo **declarado** en el §11 del [audit-pack](./audit-pack-v2-56-auto-15-data-gate-persistido-2026-09-23.md).
- **Migración SÍ:** head `044_auto_cycle_trace` → **`045_adaptive_gate_state`** (aditiva, sin backfill,
  `upgrade`/`downgrade` **simétricos** y certificados en el roundtrip del test PG).
- **Tag anterior `v2.55-beta` → `e29e6227`:** **no se reabre**. Sus cifras de CI (job `python` del tag
  `2575 passed / 38 skipped`, `check-runs` `26 success` + `1 skipped`) son el **delta de referencia** de
  esta fase.

---

## 2. Lo ya HECHO y verificado (Pasos 1 a 5)

### Paso 1 — Migración `045` + fila ORM + store (contrato puro + PG)

- **`045_adaptive_gate_state`** (`revision` `:40`, `down_revision = "044_auto_cycle_trace"` `:41`) crea
  la tabla `adaptive_gate_state` (PK `(account_id, engine_id)`, `sink_failures` con `server_default='0'`,
  `last_failure_at`, `last_success_at`, `updated_at`) y el índice
  `adaptive_gate_state_account_failures_idx` `(account_id, sink_failures)`. **Idempotente** y
  **simétrico** (`_table_exists` / `_index_exists`, `downgrade` retira índice y después tabla).
- **`AdaptiveGateStateRow`** (`tables.py:2736`, espejo de `AutoKillStateRow` `:2693`).
- **`adaptive_gate_store.py`** (nuevo): `AdaptiveGateState` (`:46`), `sink_failures_from_state` (`:72`,
  clamp defensivo), `AdaptiveGateStore` (Protocol), `InMemoryAdaptiveGateStore` (`:153`, gemelo con la
  **misma** semántica) y `PostgresAdaptiveGateStore` (`:207`) con **incremento atómico**
  (`ON CONFLICT DO UPDATE SET sink_failures = sink_failures + 1`, `:234-268`) y **reset condicional**
  (`WHERE sink_failures > 0`, `:270-292`), `autocommit` explícito y `rollback` + `raise` en el fallo
  (`:255-265`, `:284-290`).

### Paso 2 — El contador durable en el worker (gateado por el flag)

- Contador y bandera de procedencia (`auto_simulation_worker.py:753` / `:757`), store del constructor
  (`:826`) y **cableado de producción sobre la MISMA sesión del tick** (`:5599-5605` → `:5625`).
- **Siembra al arrancar** (`_v2_recover_adaptive_gate_streak`, `:3484`) llamada **antes** del primer plan
  y de los atajos del lector (`:3588`), **gateada por `adaptive_enabled`** (`:3581-3583`): con el flag
  OFF **no hay I/O** y el camino publicado no cambia.
- **Incremento** al fallar el sink (`:3469` → `:3524`) y **reset** al publicar (`:3481` → `:3549`), ambos
  fail-open **declarados**: si el store falta o falla, la racha cae al proceso con
  `sinkFailuresDurable = false` y el motivo en el log.

### Paso 3 — La declaración: sello `auto15-v1` + `sinkFailuresDurable`

- `DATA_GATE_POLICY_VERSION = "auto15-v1"` (`auto_adaptive_data_gate.py:76`); **sin tocar** umbrales
  (`:80`), tabla estado→efecto ni precedencia, y **sin tocar** `ADAPTIVE_POLICY_VERSION` (`auto14-v1`).
- `sinkFailuresDurable` (`:152`) en `as_dict()` (`:189`), **por defecto `false`** (`:253`): sin
  declaración **no** se afirma durable.

### Paso 4 — La costura del reinicio, con control, y la certificación PG

- **Costura hermética** (`test_auto_v56_auto15_data_gate_durable_seam.py`, **9** tests) por el camino
  real del worker: `3` fallos ⇒ `STALE`; proceso **nuevo** ⇒ sigue `STALE`; publicación intermedia ⇒ el
  reinicio lee `0`; **control negativo**: **sin** store el proceso nuevo lee `0` y vuelve a `OK`.
- **PG real** (`test_auto_v56_auto15_data_gate_pg.py`, **6** tests) en el job `auto-v2-durable-pg` con
  `ADAPTIVE_GATE_PG_REQUIRED=1` (un skip es **FALLO**): roundtrip de la `045`, racha que **sobrevive a la
  sesión nueva**, incremento atómico por clave, reset sin amplificación y sesión del tick **usable** tras
  un fallo de escritura.

### Paso 5 — Cierre: mutaciones, compuertas, delta, docs, bump y sello

- Sonda `v2_44_mutation_audit.py`: **`M108`…`M118`** (11 etiquetas nuevas).
- Matriz **completa** `M1…M118`, compuertas de CI, delta simétrico, paquete de docs, bump a
  `1.81.0-beta` y tag `v2.56-beta` (cifras medidas en §6).

---

## 3. Anclas de código (verificadas sobre el árbol que se sella)

| Superficie | Ruta | Ancla |
| --- | --- | --- |
| Migración `045` (tabla, índice, downgrade) | `packages/py/infrastructure/alembic/versions/045_adaptive_gate_state.py` | `:40` / `:41` · tabla `:66-82` · índice `:92` · `downgrade` `:97-109` |
| Fila ORM del estado durable | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` | `:2736` |
| Contrato puro + clamp | `packages/py/application/src/bolsa_application/adaptive_gate_store.py` | `AdaptiveGateState` `:46` · `sink_failures_from_state` `:72` |
| Gemelo in-memory | `adaptive_gate_store.py` | `:153` |
| Store PG (load / upsert / reset / commit) | `adaptive_gate_store.py` | `:207` · `load` `:218` · `record_failure` `:234` · `record_success` `:270` · `commit` `:294` |
| Contador + bandera de procedencia | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `:753` / `:757` · store `:826` |
| Siembra (antes del primer plan) | `auto_simulation_worker.py` | `_v2_recover_adaptive_state` `:3565` · siembra `:3588` · gate del flag `:3581` |
| Lectura durable + fail-open | `auto_simulation_worker.py` | `:3484` |
| Incremento / reset | `auto_simulation_worker.py` | `:3524` / `:3549` |
| Hecho + procedencia en el gate | `auto_simulation_worker.py` | `:3334` / `:3337` |
| Cableado de producción | `auto_simulation_worker.py` | `:5599-5605` → `:5625` |
| Sello del gate + hecho | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py` | `:76` · `:152` · `:189` · `:253` |
| Proyección durable (lista blanca, **intacta**) | `packages/py/application/src/bolsa_application/auto_adaptive_journal.py` | `:58` (`riskMultipliers`, `evidenceAxis`) |

**Suites de la fase** (verificadas): unit del gate (`packages/py/analytics/tests/test_auto_adaptive_data_gate.py`,
**32**, HEAD 29) + unit del store (`packages/py/application/tests/test_adaptive_gate_store.py`, **10**,
nueva) + costura (`test_auto_v56_auto15_data_gate_durable_seam.py`, **9**, nueva) + PG
(`test_auto_v56_auto15_data_gate_pg.py`, **6**, nueva).

**Sonda:** `apps/api-python/scripts/v2_44_mutation_audit.py` amplía **11 etiquetas** (`M108`…`M118`).

---

## 4. El método de verificación del repo (no improvisar)

1. **Compuertas** (los comandos de CI, no rutas sueltas):
   ```bash
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
               packages/py/application/src apps/api-python/src --follow-imports=silent
   uv run lint-imports --config packages/py/.importlinter
   ```
   **Trampa medida:** `ruff check <rutas>` **sin** `--config pyproject.toml` resuelve el `pyproject` del
   paquete y reporta falsos `I001` en ficheros ya certificados (le pasó a esta fase, y también a
   `kill_switch_store.py`): usa **el comando de CI**.
2. **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales): los tests
   **modificados** se corren también en su versión de `HEAD` contra el código nuevo. El **único rojo
   admisible** es un contrato que la fase **declara** como cambiado (un sello de política, una regla que
   se mueve): cualquier otro rojo es regresión. En esta fase se midió **`0` rojos** (§6), porque el sello
   no tenía literal en `HEAD` y el campo nuevo es aditivo. `git show HEAD:<f>` **fabrica bytes nulos** en
   PowerShell: lee y reescribe **bytes** con Python y **verifica la restauración**.
3. **Mutaciones**: `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` (filtro por
   rótulo: `… M108 M109`). Gate: la matriz **completa** (`M1…M118`) sin ninguna etiqueta en `NADA`, sin
   fragmentos ausentes y con el árbol **intacto** al terminar. **El `stdout` de Python bufferiza por
   bloques** (y el `tee` con él): el log de la corrida puede aparecer **entero al final**; para seguir el
   avance, mira el `mtime` de los ficheros mutados.
4. **Todo lo que no se puede medir, se declara** (`UNKNOWN`/`PARTIAL` + motivo). Nunca un `0` que se lea
   como «sano»: en esta fase, un `0` sin constancia durable se declara `sinkFailuresDurable = false`.
5. **No tocar nada sellado** ni editar los planes de fases cerradas: son documento histórico.

---

## 5. Trampas conocidas del entorno (Windows / este repo)

1. `git show HEAD:<f> > <f>` **fabrica bytes nulos** en PowerShell: leer y reescribir **como bytes** con
   Python y **comprobar la restauración**.
2. **Suites PG** (`asyncpg` ausente, teardown de sesión del conftest): **no** corren offline. La suite PG
   nueva **exige** PostgreSQL real (`ADAPTIVE_GATE_PG_REQUIRED=1`); con el compose en `127.0.0.1:5432`
   corre en **~2 s**. No confundir un error de entorno con un fallo de la fase.
3. Escribir mensajes de commit a un **fichero** y usar `git commit -F` (PowerShell no traga heredocs).
4. Salida no-ASCII por `python -c` revienta en `cp1252`: escribir a **fichero UTF-8**.
5. Interrumpir la consola **no mata** al hijo de la matriz de mutaciones (sigue reescribiendo ficheros):
   comprueba procesos y `git status` **antes** de dar una corrida por cerrada.
6. El `ruff` de la fase **no** incluye `ruff format`: formatear en masa reescribe ficheros ajenos.

---

## 6. El cierre, hecho y medido

- **Compuertas:** `ruff check packages/py apps/api-python --config pyproject.toml` → **`All checks
  passed!`** · `mypy` (comando de CI) → **`0` errores en `498` ficheros** · `lint-imports` →
  **`4 kept, 0 broken`**. *(El primer intento de `ruff` se corrió **sin** `--config` y devolvió falsos
  `I001` —también sobre `kill_switch_store.py`, ya certificado—: se declara la trampa en el §4.)*
- **Tramo de la fase:** **`51 passed`** (`test_auto_adaptive_data_gate.py` 32 + `test_adaptive_gate_store.py`
  10 + `test_auto_v56_auto15_data_gate_durable_seam.py` 9), `0` rojos; **`+ PG 6`** contra el PostgreSQL
  real del compose ⇒ **`57`**.
- **Delta simétrico fichero a fichero:** **`0` rojos**. Un solo fichero de test modificado
  (`test_auto_adaptive_data_gate.py`: HEAD **`29 passed`** contra el código de la fase, `13817` B →
  `16090` B) y tres **nuevos** (no existen en `HEAD`). **Desviación medida y declarada:** el plan preveía
  rojos declarados (el sello y el campo nuevo) y la medida dice **cero** — el literal `auto13-v1` no
  estaba fijado en ningún test de `HEAD` y `sinkFailuresDurable` es **aditivo** en `as_dict()`. La
  restauración quedó verificada por `sha256`.
- **Matriz de mutaciones COMPLETA:** **`118/118` muerden**, **`0`** en `NADA`, **`0`** fragmentos
  ausentes, restauración **byte a byte** y huella `git status` **idéntica** (`intacto: la sonda no
  altero el arbol`). Las **11** nuevas (`M108…M118`) matan, como mínimo, un test **con nombre**.
- **Gobernador y contrato durable intactos** (medido): diffs **vacíos** y script del gobernador **`exit 0`**.
- **Sello y RE-SELLO:** el tag apunta al commit del fix de la guardia de Alembic, **`8ad54416`** —el CI del
  primer empuje (`c62ac459`) salió **rojo** por esa guardia y un tag rojo no certifica nada—, empujado **de
  uno en uno** (sin `--follow-tags`) con `main` en **fast-forward**. Verificación replicando los dos jobs PG
  contra el PostgreSQL real: **`51 passed`** + **`21 passed`**.
- **CI del tag, MEDIDA (no predicha):** `Release tag CI` [`35928080874`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35928080874)
  **GREEN (attempt 2)** — `10 success` + `1 skipped` (`playwright (integrated E2E, opt-in)`) y `certify` en
  `success`—; job `python` del tag: ruff `All checks passed!`, mypy **`498` ficheros**, pytest **`2608
  passed / 35 skipped`** (**+22** passed y **0** skips nuevos sobre los `2586 / 35` de `v2.55`);
  `Python CI` per-commit [`35928080842`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35928080842)
  **`5/5` jobs verdes** (los **4 jobs PG** incluidos: cierra el límite offline declarado) con `quality`
  **`2597 passed / 38 skipped`**; `check-runs` del commit sellado: **`23 success` + `1 skipped`**.
- **Dos rojos iniciales por tests PREEXISTENTES ajenos a la fase, declarados y re-ejecutados:** el test PG
  intermitente de `V2.46` (`test_concurrent_auto_pg.py`, `UniqueViolation` en `auto_engine_ticks_pkey`, con
  **`1` roja en `5` corridas** medidas en local) y el teardown de vitest que envenena el exit code con los
  **`1290`** tests en verde (`mandate-tenure-pnl.test.ts`). Ninguno de los dos ficheros está en el diff de
  la fase: **no** son hallazgos de `AUTO-15` y **no** se silencian (deuda declarada).
- **Lo que no se pudo medir aquí:** la batería offline **completa** de los jobs `quality`/`python` del
  tag (su recolección incluye suites PG que importan `asyncpg`, ausente, y el teardown de sesión exige
  PostgreSQL). **Ese límite lo cerró la CI del tag** — y fue justo ahí donde apareció la guardia de head
  sin bumpear (§11.1 del audit-pack), que ya está corregida y re-verificada.

---

## 7. Límites declarados y freeze

- **Solo se persiste la racha**, no el estado del gate ni el plan.
- **Sin TTL ni decadencia:** una racha durable de un proceso muerto mantiene el gate degradado hasta la
  **primera publicación**, que la resetea. Es una decisión declarada (candidato **D** para la siguiente
  fase), no un olvido.
- **Granularidad `(account_id, engine_id)`**, no por venue ni por sink.
- **El peor caso declarado:** si el **reset** falla tras publicar, la racha durable se queda viva —el
  proceso pierde la memoria de la curación— hasta el siguiente reinicio (que la vuelve a sembrar).
- **El flag Adaptive sigue OFF**: sin él, esta fase **no ejecuta** ni lectura ni escritura.
- **Fuera de alcance, sin tocar (declarado para una fase siguiente):** la **UI** de `AUTO-7`…`AUTO-15` y
  el **coste REAL** por ciclo.
- **Freeze respetado:** `auto_adaptive_journal.py` **byte a byte igual**, contratos de las tablas
  anteriores intactos, sello de `V2.53`/`V2.54`/`V2.55` intacto, `yahoo_circuit_breaker.py`,
  `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación **y los del Data Gate** sin tocar, el
  **gobernador** con diff **vacío** (`exit 0`), **sin backfill**, **sin SHORT**, **sin UI**. `*.md`
  **sin `prettier`**. `governor.json` sigue **sin trackear**.

---

## 8. Punto de entrada para el siguiente agente

El **punto de entrada** de la fase siguiente es
[`arranque-agente-post-v2.56-auto-15-2026-09-23.md`](./arranque-agente-post-v2.56-auto-15-2026-09-23.md)
(con el prompt listo para copiar). Los **candidatos declarados** para `AUTO-16` y el estado del epic
están en su §5. **No** se decide alcance aquí: se propone y se **espera ratificación**.
