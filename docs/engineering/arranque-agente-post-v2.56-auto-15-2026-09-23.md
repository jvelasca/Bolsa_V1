# Arranque del agente — post `v2.56-beta` (`AUTO-15` cerrada) · 2026-09-23

**Para qué es este documento.** `AUTO-15` está **sellada** (`v2.56-beta`, `1.81.0-beta`) y `main` la
recibió en fast-forward. Esto es el **punto de entrada** de un agente nuevo: el orden de lectura, el
método de verificación que no se improvisa, el freeze y las trampas del entorno. **No** decide el alcance
de `AUTO-16`: propone candidatos y **espera ratificación del propietario** antes de tocar código.

---

## 0. El prompt para arrancar (cópialo tal cual)

```
Continúa la línea AUTO en este repo. Lee primero, en este orden:
  1. docs/engineering/traspaso-relevo-post-v2.56-auto-15-data-gate-persistido-2026-09-23.md
  2. docs/engineering/audit-pack-v2-56-auto-15-data-gate-persistido-2026-09-23.md
  3. docs/engineering/arranque-auditor-v2.56-auto-15-data-gate-persistido-2026-09-23.md
  4. docs/engineering/PROJECT_STATE.md

AUTO-15 está CERRADA y sellada (tag v2.56-beta, 1.81.0-beta). NO reabras esa fase ni toques nada sellado.
El flag Adaptive sigue OFF: el runtime publicado es, en comportamiento, el de v2.53-beta.

Confirma primero el estado medido del repo (git log, git tag --points-at, git status limpio salvo
governor.json) y verifica que las compuertas pasan (ruff del scope CI, mypy del YAML, lint-imports) ANTES
de proponer nada.

Después, NO implementes: propónme el ALCANCE de AUTO-16 como máximo en 3 opciones, cada una con
  (a) el invariante que protege, (b) los ficheros que tocaría, (c) si exige migración y por qué,
  (d) el gate de verificación (tests, mutaciones nuevas M119+ y delta simétrico).
Candidatos declarados por la fase anterior: la UI de AUTO-7..AUTO-15 (la celda, la banda medida, el estado
del gate, la rampa y la racha durable ya existen y no se ven) y el COSTE REAL por ciclo (hoy es estimado,
así que el R neto cae a PARTIAL y la celda declara su hueco). Espera mi ratificación antes de escribir código.

Método obligatorio: compuertas del §3 de este documento, delta simétrico FICHERO A FICHERO contra HEAD
(nunca restando totales) y matriz de mutaciones COMPLETA sin ninguna etiqueta en NADA. Si algo falla, se
declara; nunca se silencia.
```

---

## 1. Estado en una tabla

| Corte | Estado | Ref |
| --- | --- | --- |
| `AUTO-15` (Data Gate persistido) | **cerrada y sellada** | tag **`v2.56-beta`**, `1.81.0-beta` |
| `main` | **recibió la fase** (fast-forward, sin merge) | `e29e6227..<commit sellado>` |
| Tag | **`v2.56-beta`** empujado **suelto** (sin `--follow-tags`) | `Release tag CI` **GREEN**, run y cifras **medidos** y citados en el §11 del [audit-pack](./audit-pack-v2-56-auto-15-data-gate-persistido-2026-09-23.md) (commit post-sello) |
| Rama de auditoría | `auto-15-data-gate-persistido` · **PR draft** (abierto **post-sello**, no es vehículo de merge) | delta completo sobre `v2.55`: base `e29e6227` → commit sellado (cifras y enlace del PR en el commit post-sello) |
| Runtime | **el de `v2.53-beta`**: flag Adaptive **OFF** | sin racha que leer ni que escribir: **cero I/O nuevo** |
| Migración | **SÍ**: head `044_auto_cycle_trace` → **`045_adaptive_gate_state`** | aditiva, sin backfill, downgrade simétrico |
| Árbol | limpio **salvo `governor.json`** (sin trackear) | — |
| Siguiente | **`AUTO-16`** (alcance **por ratificar**, no decidido) | §5 de este documento |

---

## 2. Dónde está cada cosa (anclas re-medidas sobre el árbol sellado)

| Superficie | Ruta | Ancla |
| --- | --- | --- |
| Migración `045` (tabla + índice) | `packages/py/infrastructure/alembic/versions/045_adaptive_gate_state.py` | `revision` `:40` · `down_revision` `:41` · tabla `:66-82` · índice `:92` · `downgrade` `:97-109` |
| Fila ORM del estado durable | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` | `AdaptiveGateStateRow` `:2736` (espejo de `AutoKillStateRow` `:2693`) |
| Contrato puro + gemelo in-memory | `packages/py/application/src/bolsa_application/adaptive_gate_store.py` | `AdaptiveGateState` `:46` · `sink_failures_from_state` `:72` · `InMemoryAdaptiveGateStore` `:153` |
| Store PG (upsert atómico + reset condicional) | `adaptive_gate_store.py` | `PostgresAdaptiveGateStore` `:207` · `record_failure` `:234` · `record_success` `:270` · `rollback`+`raise` `:255-265` / `:284-290` |
| Contador y bandera de procedencia | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `:753` / `:757` · store del constructor `:826` |
| Siembra al arrancar (antes del primer plan) | `auto_simulation_worker.py` | `_v2_recover_adaptive_state` `:3565` · siembra `:3588` · gate del flag `:3581` |
| Lectura durable (fail-open declarado) | `auto_simulation_worker.py` | `_v2_recover_adaptive_gate_streak` `:3484` |
| Incremento / reset durable | `auto_simulation_worker.py` | `_v2_record_adaptive_sink_failure` `:3524` · `_v2_record_adaptive_sink_success` `:3549` |
| Entra al gate como el mismo hecho + procedencia | `auto_simulation_worker.py` | `sink_failures=` `:3334` · `sink_failures_durable=` `:3337` |
| Cableado de producción (sesión del tick) | `auto_simulation_worker.py` | `:5599-5605` → `:5625` |
| Sello del gate + hecho de procedencia | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py` | `auto15-v1` `:76` · `sinkFailuresDurable` `:152` / `:189` · `assess_data_gate` `:250-253` |
| Sonda de mutaciones | `apps/api-python/scripts/v2_44_mutation_audit.py` | `M108…M118` |
| CI de la certificación PG | `.github/workflows/python-ci.yml` · `release-tag-ci.yml` | `ADAPTIVE_GATE_PG_REQUIRED` + test PG en `auto-v2-durable-pg` |

**Suites de la fase** (verificadas): unit del gate `packages/py/analytics/tests/test_auto_adaptive_data_gate.py`
(**32**, **+3**), unit del store `packages/py/application/tests/test_adaptive_gate_store.py` (**10**, nueva),
costura `apps/api-python/tests/test_auto_v56_auto15_data_gate_durable_seam.py` (**9**, nueva) y
`apps/api-python/tests/test_auto_v56_auto15_data_gate_pg.py` (**6**, nueva, PG real).

---

## 3. El método (no se improvisa)

1. **Compuertas** (los comandos de CI, no rutas sueltas):
   ```bash
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
               packages/py/application/src apps/api-python/src --follow-imports=silent
   uv run lint-imports --config packages/py/.importlinter
   ```
   Ojo: `ruff check <rutas>` **sin** `--config pyproject.toml` resuelve el `pyproject` del paquete y
   reporta falsos `I001` en ficheros ya certificados (medido): usa el comando de CI.
2. **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales): los tests
   **modificados** se corren también en su versión de `HEAD` contra el código nuevo. El **único rojo
   admisible** es un contrato **declarado** como cambiado (el sello de política, una regla que la fase
   cambia); cualquier otro rojo es regresión. Hazlo con un script que **lea y escriba bytes** y
   **verifique la restauración** (`git show` por PowerShell fabrica bytes nulos).
3. **Mutaciones**: `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py`. La matriz va
   por **`M118`**; una fase nueva añade **`M119+`**. Gate: la matriz **completa** sin ninguna etiqueta en
   `NADA`, sin fragmentos ausentes y el árbol **intacto** al terminar. **El `stdout` de Python va
   bufferizado en bloques**: no esperes ver progreso hasta que se llena el búfer; mira `mtime` de los
   ficheros mutados para saber por dónde va.
4. **Todo lo que no se puede medir, se declara** (`UNKNOWN`/`PARTIAL` + motivo). Nunca un `0` que se lea
   como «sano»: en esta fase, un `0` sin store se declara `sinkFailuresDurable = false`.
5. **No tocar nada sellado** ni editar los planes de fases cerradas: son documento histórico.

---

## 4. Freeze que hereda `AUTO-16`

- **NO LIVE** · sin SHORT · **migración** solo si la fase lo justifica y se ratifica (la `045` es ahora el
  head: la siguiente cadena lineal arranca de ahí).
- **No se toca:** `auto_adaptive_journal.py` (**byte a byte igual**), el contrato de la tabla
  `decision_journal_entries` (sin claves nuevas ni backfill), `yahoo_circuit_breaker.py`,
  `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación **ni los del Data Gate**
  (`sink_failures_stale = 3`, `journal_gap_blocked = 10`, `evaluation_cycle_seconds = 60.0`), la tabla
  estado→efecto, el **gobernador** (`v2_43_governor_evidence.py`, diff vacío) y el esquema previo.
- **No se mezclan los ejes:** operativo (`ACTIVE`/`PAUSED`/`RECOVERING`), datos
  (`OK`/`DEGRADED`/`STALE`/`BLOCKED`), calidad (`LOW`/`MEDIUM`/`HIGH`), base de reparto
  (`allocationCells`) y **procedencia de la racha** (`sinkFailuresDurable`) van en campos propios.
- **El flag Adaptive sigue OFF**: nada de lo nuevo puede cambiar el comportamiento publicado por
  defecto; con OFF, esta fase no hace ni un I/O.
- `*.md` **sin `prettier`**.

---

## 5. Candidatos para `AUTO-16` (declarados, **no decididos**)

| # | Candidato | Invariante que protege | Migración |
| --- | --- | --- | --- |
| B | **UI de `AUTO-7`…`AUTO-15`** (el cruce `strategy × regime`, la base de CELDA, la banda medida, el estado del gate, la rampa y la **racha durable con su procedencia** ya existen y no se ven) | Lo medido se **publica**, no se oculta; el operador no lee un `0` donde no hubo medida | No |
| C | **Coste REAL por ciclo** (hoy es **estimado**, el R neto cae a `PARTIAL` y la celda declara `cell_net_unmeasured`) | «Lo que no se midió, se declara» deja de ser el caso común: el eje del R neto y las celdas actúan donde hoy se abstienen | Probablemente **sí** (productor de coste) |
| D | **Caducidad declarada de una racha vieja** (una racha durable de un proceso muerto mantiene el gate degradado hasta la primera publicación) | Una prueba **fechada** no puede juzgar sin fecha: hoy no hay TTL y se declara | No |

**Pregunta abierta que el propietario debe cerrar antes de elegir:** ¿el siguiente movimiento es
**explicabilidad** (B, todo lo medido ya está en el journal y los logs), **capacidad nueva** (C, la deuda
más repetida en los límites declarados) o **afinar la durabilidad** que `AUTO-15` acaba de instalar (D)?

---

## 6. Trampas del entorno (Windows / este repo)

1. `git show HEAD:<f> > <f>` **fabrica bytes nulos** en PowerShell: leer y reescribir **como bytes** con
   Python y **comprobar la restauración**.
2. `asyncpg` ausente y teardown PG del conftest de `apps/api-python`: las suites PG **no** corren offline
   (la del gate `AUTO-15` lo **exige** con `ADAPTIVE_GATE_PG_REQUIRED=1` en la CI); la CI las mide. Con el
   PostgreSQL del compose (`127.0.0.1:5432`, `bolsa/bolsa_dev`) y `ADAPTIVE_GATE_PG_REQUIRED=1` la suite
   PG del gate corre en **~2 s**.
3. Escribir mensajes de commit a un **fichero** y usar `git commit -F` (PowerShell no traga heredocs).
4. Salida no-ASCII por `python -c` revienta en `cp1252`: escribir a **fichero UTF-8**.
5. Interrumpir la consola **no mata** al hijo de la matriz de mutaciones (sigue reescribiendo ficheros):
   comprueba procesos y `git status` **antes** de dar una corrida por cerrada. Y el **pipe del `tee`
   bufferiza**: el log de la corrida puede aparecer **entero** al final, no por líneas.
6. Copiar del visor puede dejar el **prefijo de línea** dentro del código: `rg "^\s*\d+\|"` antes de
   commitear.
7. **El `ruff` de la fase no incluye `ruff format`**: formatear en masa reescribe ficheros ajenos.
