# Cierre del ciclo de reservas al cierre de turno — `AUTO-MATERIAL-16` / `v2.88`

> **AsOf:** 2026-09-29 · **Fase:** cierre de motor (`real_turn`) + **sello conjunto** de tres incrementos.
> **Tipo de entrega:** código de motor (`apps/api-python/src/`) + tests + informe + evidencia.
> **Bump:** `2.10.2-beta` → `2.11.0-beta` · **SIN migración** (Alembic head sigue en `046_fill_reference_mid`).
> **Sello:** tag anotado **`v2.88-beta`** (lo crea el propietario) · **base (HEAD antes del sello):** `3483b6b5` · **tag anterior:** `v2.85.2-beta`.
> **Incrementos que sella:** `v2.86` (`AUTO-MATERIAL-14`) + `v2.87` (`AUTO-MATERIAL-15`) + el cierre de `OBS-14` (`AUTO-MATERIAL-16`).
> **Padre:** [replay-oos-ciclo-durable-v2.87-2026-09-29.md](./replay-oos-ciclo-durable-v2.87-2026-09-29.md) · **Índice:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) · **Deuda:** [deuda-p3-post-auditoria-v2.70-2026-09-26.md](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
> **Relevo de esta fase:** este documento hace también de relevo (ver §10).

---

## 1. Qué clase de evidencia produce esto — y qué NO

**Es evidencia de CÓDIGO del motor (cierre de `OBS-14`) dentro de un sello documental, no evidencia de OPERACIÓN.**

| | Ventana PAPER real (`P3-2`/`P3-3`) | Esta fase |
| --- | --- | --- |
| Reloj | Pared (`datetime.now(UTC)`) | Sin medición de ventana nueva |
| Objeto | Material durable por días reales | Un **hunk** del motor + tests + sello |
| Sustituye a la ventana | — | **NO. Nunca.** |

Consecuencia dura: **`P3-2`/`P3-3` siguen ABIERTAS.** Este sello **no las cierra ni las mueve**. La fase
de `OBS-14` **sí cierra** una observación **de motor** (una parada de apertura evitable), y lo hace con
**un solo hunk sobre el camino durable**; todo lo demás viaja como **incrementos ya implementados y
sin commitear** (`v2.86` + `v2.87`).

## 2. Qué se implementó (y con qué garantías)

### 2.1 El cambio de motor (D) — cierre de `OBS-14`

Fichero `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`: diff **+7 / -0**, **un solo
hunk** (líneas **4937-4943**), en `real_turn`, justo **después** de `report = await self.auto_turn()` y
**antes** de `if auto_store is not None:`. La línea añadida es
`await self._v2_reconcile_reservations(startup=False)`.

```python
            # OBS-14 — CIERRE del ciclo de reservas del turno: retira las reservas MUERTAS
            # (la orden no llegó a materializarse dentro del tick) sobre la MISMA sesión del
            # turno, sin reiniciar. ``startup=False`` porque la reserva no murió por un
            # reinicio sino porque su orden no se materializó (``RESERVATION_RELEASED_BY_CANCEL``).
            # Es el análogo de lo que el instrumento ``v2.87`` hace en su ``close_tick``; corre
            # en CADA turno, no solo en la reconciliación de arranque.
            await self._v2_reconcile_reservations(startup=False)
```

### 2.2 Por qué en `real_turn` y no en `auto_turn`

Razón **medida en código** (no interpretada): AUTO es **solo** `{paper, simulated}` y **sin bridge LIVE**
(docstring del módulo, `auto_simulation_worker.py:5` y `:13`: «sólo {paper, simulated}, kill OFF (jamás
LIVE)» y «AUTO jamás toca LIVE: venues ∈ {paper, simulated}; no hay bridge LIVE»). La orden, por tanto,
o **liquida dentro del tick** (`submit_simulated_order`) o **no se materializa nunca**. De ahí que una
reserva viva al cerrar el turno cuya orden **no está en vuelo** *está muerta*: retirarla al cierre es
**fiel al motor**, no un atajo.

El cierre va en `real_turn` (el **camino durable de producción**, invocado por `_PostgresRuntime.run_tick`)
y **no** en `auto_turn` (el **camino hermético**, usado por decenas de tests y por el **instrumento de
replay**), para **no perturbarlos**. `startup=False` ⇒ la etiqueta de la retirada es
**`RESERVATION_RELEASED_BY_CANCEL`**, no `RESERVATION_RELEASED_BY_RESTART`
(`auto_simulation_worker.py:2702-2704`).

**No** se tocó `auto_turn`, ni el interior de `_v2_reconcile_reservations`, ni la regla de retirada, ni
ningún umbral.

### 2.3 Tests nuevos (4) en la costura del ciclo durable

`apps/api-python/tests/test_auto_v2_durable_cycle.py` pasa de **7 a 11** tests:

- `test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn`
- `test_two_real_turns_do_not_drip_the_book_between_them`
- `test_control_without_tick_close_reproduces_the_drip`
- `test_closing_reconcile_keeps_captured_unapplied_capital_in_flight`

Mutación **`M246`** («cierre de turno revertido»): muerde **3/3 en rojo**, árbol restaurado **byte a byte**.

### 2.4 Revisión interna (C) — dos subagentes

- **Bugbot: 1 hallazgo (medium)** en `apps/api-python/scripts/v2_86_replay_oos_viability.py:448`:
  `_print_census` estaba escrito contra el objeto `CensusReport` (acceso por atributo) pero `main` le
  pasa `evidence["census"]`, que es `census.to_dict()` (un **`dict`**). El modo **texto** (sin `--json`)
  reventaba con `AttributeError: 'dict' object has no attribute 'watch'`. **Silencioso**: el `--out` JSON
  se escribe **antes** del render, así que el artefacto sobrevivía y solo lo veía quien leyese la consola.
- **Security review: sin hallazgos.** Se confirmó que el cambio **no** cruza fronteras de
  auth/tenant/privilegio/secretos/filesystem; el único sumidero de escritura es
  `Path(args.out).write_text(...)` con la ruta que teclea el operador; las lecturas de BD son read-only y
  parametrizadas; los stores de la simulación son **en memoria** (cuarentena «cero escrituras a
  PostgreSQL»).
- **Arreglo del hallazgo:** `_print_census` consume ya el **`dict`** (renderer **idéntico** al de `v2.87`);
  test nuevo `apps/api-python/tests/test_replay_oos_cli_renderers.py` con **3 tests** —uno de ellos exige
  que los renderers de `v2.86` y `v2.87` **coincidan con el mismo payload**: la divergencia era la
  **huella del defecto**; mutación **`M245`** que muerde **3/3**.

### 2.5 Dos defectos extra encontrados y arreglados

1. **Versión inexistente.** **6 documentos** afirmaban `2.11.0-beta`, que **nunca existió**:
   `package.json`, `CHANGELOG.md` y **toda** la historia de git dicen `2.10.2-beta`. Corregidas **7
   ocurrencias** en `docs/engineering/PROJECT_STATE.md`, `docs/engineering/engineering-index-2026-08-03.md`,
   `docs/engineering/deuda-p3-post-auditoria-v2.70-2026-09-26.md`, `docs/engineering/evidence/v2.86/README.md`,
   `docs/engineering/evidence/v2.87/README.md`, `docs/engineering/replay-oos-viabilidad-auto-v2.86-2026-09-29.md`
   y `docs/engineering/replay-oos-ciclo-durable-v2.87-2026-09-29.md`. Sin esto, un auditor que clone el
   tag tiene un **hallazgo garantizado**.
2. **7 errores `I001` que habrían hecho fallar el job `quality` de CI.** Los ficheros de `v2.86`/`v2.87`
   nunca se commitearon, así que nunca se lintaron con la config de raíz. El comando **exacto** de CI es
   `uv run ruff check packages/py apps/api-python --config pyproject.toml` (ojo: invocar `ruff` por
   fichero **sin** `--config` descubre la config anidada `apps/api-python/pyproject.toml` y da un
   resultado **distinto**). Corregidos; el comando **exacto** de CI pasa.

### 2.6 Verificación

- **Guardarraíles (10 suites): 142 passed.**
- `uv run ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed!** (exit 0).
- **Matriz de mutaciones: 246** en total (eran **239** al sellar `v2.85.2`).
- `M245` muerde **3/3**; `M246` muerde **3/3**; en ambos casos árbol restaurado **byte a byte**.
- `git diff --numstat` del motor: **`7  0`**.
- Suite de costura del ciclo durable: **11** tests. Suite del instrumento puro: `test_replay_oos.py` **18**,
  `test_replay_oos_durable_cycle.py` **29**. Renderers: **3**.

## 3. Hipótesis a refutar

> «La retirada de una reserva muerta al **cierre de turno** es fiel al motor (no una degradación) y, con
> ella, el libro de compromisos deja de gotear entre turnos **sin reiniciar el proceso**.»

La contraprueba es el test de **control** (`test_control_without_tick_close_reproduces_the_drip`): mismo
harness, **solo** con el cierre de turno inerte ⇒ el libro **gotea** (reproduce el comportamiento previo).
Y `test_closing_reconcile_keeps_captured_unapplied_capital_in_flight` refuta la lectura ingenua «todo lo
vivo al cierre muere»: la guarda `instrument not in in_flight` **conserva** el capital capturado y no
aplicado.

## 4. Medición

### 4.1 El hunk (D)

| Métrica | Valor |
| --- | --- |
| Fichero | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` |
| Diff (`--numstat`) | **`7  0`** |
| Hunks | **1** (líneas **4937-4943**) |
| Función | `real_turn` (camino durable de producción) |
| Etiqueta de la retirada | `RESERVATION_RELEASED_BY_CANCEL` (`startup=False`) |
| `auto_turn` / `_v2_reconcile_reservations` interior / regla / umbrales | **NO tocados** |

### 4.2 Compuertas (números exactos)

| Compuerta | Resultado |
| --- | --- |
| Guardarraíles (10 suites) | **142 passed** |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** (exit 0) |
| Matriz de mutaciones | **246** total (eran **239** en `v2.85.2`) |
| `M245` | **3/3** muerden, árbol restaurado byte a byte |
| `M246` | **3/3** muerden, árbol restaurado byte a byte |
| `test_auto_v2_durable_cycle.py` | **11** (7 → 11) |
| `test_replay_oos.py` | **18** |
| `test_replay_oos_durable_cycle.py` | **29** |
| `test_replay_oos_cli_renderers.py` | **3** |

### 4.3 Titulares del instrumento que sella el tag (leídos de `evidence/v2.87/README.md`, no recalculados)

`v2.87` (ciclo durable): **1224 ticks**, **210 órdenes / 752 fills / 62 ciclos**, reservas vivas máx **1**
y final **0**, `horizon.completed=true`. Control `--no-durable-cycle`: **31 / 118 / 13**, máximas vivas
**15**, `finalReservedRisk` **5 999.9998**, `risk_budget_exceeded` **1 400** frente a **11**.

## 5. Hallazgo principal — el cierre de turno cierra `OBS-14` por la ruta (a), y queda medido

`OBS-14` (abierta al cerrar `v2.87`) observó que el motor real retiraba reservas muertas **solo al
arranque** (`_v2_reconcile_reservations(startup=True)`, `auto_simulation_worker.py:4927`); entre reinicios
el libro de compromisos podía retener huérfanas y el motor **infra-abría** de forma legítima pero evitable.

La fase elige la **ruta (a)** del criterio de cierre de `OBS-14` —*reconciliar en el cierre de turno/tick,
lo que el replay de `v2.87` demuestra fiel al motor SIM y seguro*— y la implementa sobre el **camino durable**
con **un solo hunk** (§2.1, §2.2). La etiqueta es `RESERVATION_RELEASED_BY_CANCEL` (no `..._BY_RESTART`),
la guarda de **capital en vuelo** se respeta (§3) y el **control** reproduce el goteo previo (§3).

**No** se degradó ninguna compuerta para conseguirlo: no se tocó la regla de retirada, ni los umbrales, ni
`auto_turn`, ni el interior de `_v2_reconcile_reservations`.

## 6. Hallazgos colaterales (declarados)

1. **El hallazgo de Bugbot era silencioso por diseño del CLI.** El `--out` JSON se escribe **antes** del
   render de consola, así que el artefacto sobrevivía al `AttributeError`. Solo lo veía quien leyese la
   consola. El guardarraíl nuevo (`test_both_renderers_agree_on_the_same_payload`) fija el contrato del
   **`dict`**, no el formato.
2. **El comando exacto de CI importa.** `ruff` por fichero **sin** `--config` descubre la config anidada
   `apps/api-python/pyproject.toml` y da un resultado **distinto** al del job `quality`. Los `I001`
   corregidos solo se ven con el comando **exacto** de CI.
3. **Deuda nueva `OBS-15` (alcance motor), registrada y NO arreglada en esta fase.** El techo de lectura
   de **1000 filas `APPLIED`** puede **parar el motor**; se declara en §7 y en la
   [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md). El propietario decidió **registrar**, no
   arreglar, en esta fase.

## 7. Límites declarados (lo que este informe NO afirma)

- **NO** cierra `P3-2`/`P3-3` ni sustituye la ventana PAPER real: no hay medición de ventana en esta fase.
- **NO** afirma edge ni cambia ninguna cifra del material real: cierra una **parada de apertura** del motor.
- **`OBS-15` (nueva, MEDIUM, alcance motor) — ABIERTA.** El techo de lectura de **1000 filas `APPLIED`**
  puede **parar el motor**: `read_applied_fill_facts` lee
  `list_applied(account_id, limit=DEFAULT_APPLIED_LIMIT=1000)`; `PostgresExecutionEventStore.list_applied`
  ordena `applied_at ASC` y aplica `LIMIT` ⇒ **no** está acotado a una jornada, pese al comentario de
  `applied_fills` («fills aplicados de una jornada AUTO»). `truncated = len(events) >= limit` ⇒
  `MEASUREMENT_UNKNOWN`. En `_v2_reconcile_reservations`, una lectura `UNKNOWN` implica que (a) la regla 1
  no puede casar ningún fill (`facts=()`), (b) la regla 2 **nunca** libera (no es `measurable`) y (c)
  `_v2_reservations_measurement` queda `UNKNOWN` ⇒ el libro pendiente es `UNKNOWN` ⇒ el motor **veta
  aperturas**. Con `>=1000` filas `APPLIED` acumuladas, la reconciliación de reservas **no puede** ser
  COMPLETE y el motor deja de abrir. **Es preexistente** (la reconciliación de arranque lee idénticamente)
  y **NO** lo introdujo la fase de `OBS-14`. **Radio de impacto:** afecta también a la reconstrucción de
  **posición** (`read_position_ledger` y las posiciones canónicas usan el mismo límite por defecto).
  **Severidad declarada:** fail-closed y **declarado** en el journal (no es corrupción silenciosa), pero
  es una **parada dura alcanzable por operación normal**. **Disparador:** `>=1000` filas con
  `status='APPLIED'` para la cuenta (derivado del código). La madurez de la cuenta real está **NO MEDIDA**
  (una sonda read-only fue **bloqueada por la revisión automática**); no se estima. **Criterio de cierre:**
  hacer que la lectura de fills de la reconciliación de reservas sea COMPLETA **para su propósito**,
  acotándola a la ventana viva (p. ej. `since = min(created_at)` de las reservas vivas, ya que la regla 1
  solo casa fills con `applied_at >= created_at`), y/o acotar honestamente la lectura de posición; exige
  tocar `applied_fills` + protocolo del store + InMemory + Postgres + tests + mutaciones. **Nota:** la
  ventana de retención de **900** de `v2.87` es una mitigación **interna al instrumento**
  (`_RetentionExecutionEventStore`, solo replay); **no** existe en producción.
- Los artefactos `operability_runs/*.json` viven en un directorio **gitignoreado** (`.gitignore:102`): el
  resumen viaja en `docs/engineering/evidence/`; el JSON completo se regenera con los comandos de §8.
- **`mypy` / `lint-imports` de esta fase: NO MEDIDO** — no forman parte del paquete de verificación
  citado para el sello.

## 8. Reproducción (PowerShell)

```powershell
# Guardarraíles de la fase (10 suites)
uv run --no-sync python -m pytest apps/api-python/tests/test_auto_v2_durable_cycle.py `
  apps/api-python/tests/test_replay_oos_cli_renderers.py -q

# Compuerta EXACTA de CI (ojo con --config)
uv run ruff check packages/py apps/api-python --config pyproject.toml

# Matriz de mutaciones (bloque del cierre de turno + renderers)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py --only M245,M246
```

**Requisito del instrumento (v2.86/v2.87):** PostgreSQL arriba y alcanzable en `127.0.0.1:5432`
(Docker Desktop iniciado); una caída de Docker mata el paso read-only con `psycopg.errors.ConnectionTimeout`.

## 9. Artefacto y evidencia cruda

- `v2.86`: `operability_runs/replay-oos-viability-20260929.json`, **2 054 030 B**,
  SHA-256 `91A871FBD5B43335C1197DA74D5D91663730A12FD0929FB8A3CB3F4C35143A90`.
- `v2.87`: `operability_runs/replay-oos-ciclo-durable-20260929.json`, **3 165 540 B**,
  SHA-256 `DC61B3B912C6C7CE6455837BF8E6E6BDD6C03CE6B900D6B73D7925B203C6C54F`; control
  `--no-durable-cycle`: `...-control.json`, **2 949 320 B**, SHA-256
  `FE4CBF79E221A27E2A517A10976664FB6149BB4AAB8635851B5558A28378CCD1`.
- Resumen versionado y verificable de este cierre: [evidence/v2.88/README.md](./evidence/v2.88/README.md).

## 10. Relevo — estado tras esta fase

- **Hecho:** hunk **+7 / -0** del motor (`real_turn`), **4 tests** nuevos (7 → 11), mutaciones **`M245`** y
  **`M246`** (3/3 cada una, árbol restaurado byte a byte), **2 defectos extra** corregidos (versión
  inexistente; 7 `I001`), **revisión interna** (Bugbot medium + security sin hallazgos) y este informe + evidencia.
- **Cerrado (medido):** **`OBS-14`**, por la **ruta (a)** de su criterio de cierre (reconciliación al
  cierre de turno).
- **Deuda nueva declarada (`OBS-15`, MEDIUM, alcance motor, NO se arregla aquí):** el techo de **1000
  filas `APPLIED`** puede parar el motor (§7).
- **Deuda abierta (NO se cierra por este informe):** `P3-2`, `P3-3`, **`OBS-15`** (nueva), `OBS-13`,
  `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`.
- **Sello pendiente (lo crea el propietario, no este informe):** tag anotado **`v2.88-beta`** sobre el
  commit del sello; su cita de CI es **POST-TAG** por construcción (`Release tag CI` solo corre al empujar).
