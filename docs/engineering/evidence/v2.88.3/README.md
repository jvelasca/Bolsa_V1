# Evidencia cruda — la costura del journal no declaraba el libro de propiedad (`v2.88.3`, 2026-09-29)

Resumen **verificable** del RE-SELLO 3, que sustituye a `v2.88.2-beta`. Conserva el **rojo original** de
`v2.88.2-beta` (no se borra: es parte de la evidencia), la causa raíz, la verificación **completa** de la
batería offline del CI y el certificado de la matriz de mutaciones. Las cifras están transcritas de las
corridas, sin edición.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-16c` (`v2.88.3`) — RE-SELLO 3: costura del journal + arnés + docs (motor intacto) |
| Versión de paquete | `2.11.2-beta` → **`2.11.3-beta`** |
| Tag (lo crea el propietario) | **`v2.88.3-beta`** (anotado) |
| Tags SUPERADOS | `v2.88-beta` (rojo: crash/recovery) · `v2.88.1-beta` (rojo: carrera concurrente) · **`v2.88.2-beta`** (rojo: costura offline) |
| Base del diff | **`41e7e679`** (= `v2.88.2-beta`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Diff del arreglo | **1 fichero de test, +5** (`test_auto_v51_auto10_cycle_journal_seam.py`: 1 línea funcional + el comentario que explica el porqué) · el **motor no se toca** |

## 1. El rojo que motiva este RE-SELLO (`v2.88.2-beta` = `41e7e679`)

`Release tag CI` run [`36553839085`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36553839085):

| Job | Resultado |
| --- | --- |
| shared / frontend / playwright (mock) / decision-spine / security | success |
| dr-verify | success |
| a7-gate (A7 C3 chaos live_a7 · dedicated real-PG) | success |
| **lifecycle-pg (Alembic + auth + golden restart)** | **success** ← crash/recovery **y** la carrera de 3 sesiones |
| **python (ruff/imports/mypy/pytest offline)** | **failure** |
| certify (aggregate + artifact) | failure (agrega el fallo de `python`) |

Sub-pasos del job `python`:

```
✓ Ruff            ✓ Import-linter        ✓ Mypy
X Pytest offline   →  6 failed, 3034 passed, 37 skipped, 6 warnings in 54.15s
```

Aserto exacto (repetido en los 6):

```
AttributeError: 'AutoSimulationWorker' object has no attribute '_v2_owned_reservations'.
  Did you mean: '_v2_reservations'?
apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:2335
  (self._v2_owned_reservations.add(reservation.reservation_id) dentro de _v2_persist_tick_reservations)
```

Los 6 tests rojos, todos del **mismo fichero**:

```
FAILED apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py::test_each_opened_cycle_publishes_its_regime_durably
FAILED apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py::test_one_opening_is_one_trace
FAILED apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py::test_a_cycle_without_identity_is_not_faked
FAILED apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py::test_an_absent_regime_is_published_declared_not_skipped
FAILED apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py::test_without_a_sink_the_turn_is_untouched
FAILED apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py::test_a_broken_sink_degrades_declaring_and_keeps_the_commitment
```

Workflows de `main` del **mismo commit**, citados para no dejar el árbol a medias:

| Workflow (`main`) | Run | Resultado |
| --- | --- | --- |
| Python CI | [`36553838466`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36553838466) | **failure** (misma causa) |
| Frontend CI | [`36553838471`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36553838471) | success |
| Optimize lab | [`36553838505`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36553838505) | success |
| Fase 2 scientific | [`36553838422`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36553838422) | success |
| Gitleaks | [`36553838420`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36553838420) | success |

### 1.b Lo que este rojo **confirma** de `v2.88.2` (la parte buena)

`lifecycle-pg` en **verde** significa, medido por el CI del tag:

- el **crash/recovery del día real** (proceso matado en sucio, cola de reserva viva) pasa;
- las **3 sesiones concurrentes** sobre la misma señal pasan (`test_concurrent_auto_pg.py`) — el fallo de
  `FFF` con `released=200.000000` vs `materializado=147.000000` **no** reaparece;
- el **golden day**, el aislamiento de cuenta y `a7-gate` (`chaos live_a7`, PG real) pasan.

Es la primera corrida en la que el cierre de turno pasa **a la vez** el gate de correctitud y el de la
carrera. El tercer rojo es de otro sitio: la **costura de un test**.

## 2. Causa raíz (de la VALIDACIÓN, no del motor)

La costura construye el worker **sin `__init__`** y declara a mano el estado que su ruta necesita:

```python
def _worker(*, sink=None, regime=_REGIME) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._reservation_store = InMemoryReservationStore(seed=())
    worker._v2_reservations = ()
    worker._v2_reservation_blocked = frozenset()
    worker._v2_reservation_carryover = frozenset()
    worker._v2_tunables = SimpleNamespace(regime_override=None)
    ...
```

`v2.88.2` añadió `self._v2_owned_reservations` al `__init__` **y** un `add()` en
`_v2_persist_tick_reservations`, que es justo la ruta que esta costura ejerce. El libro de propiedad nunca
se creó ⇒ `AttributeError`. En producción `__init__` siempre corre: **el motor no tenía el defecto**.

**Por qué no se vio en local:** la validación corrió suites vecinas (carrera `7 passed`, ciclo durable `14`,
instrumento `14`, vecinos del motor `49 passed`, pasos saltados de CI `5 passed`) pero **no** la batería
offline completa del workflow, que es la puerta real. Declarado como **`OBS-16`** (proceso, MEDIUM).

**Radio acotado (medido):** de las **15** costuras con `object.__new__(AutoSimulationWorker)`, solo **una**
ejerce esas rutas; por eso el CI falló en 1 fichero y no en 15.

```
$ rg "object\.__new__\(AutoSimulationWorker\)" apps/api-python/tests   →  15 ficheros
$ rg "_v2_persist_tick_reservations|_v2_reserve_exit|_v2_reconcile_reservations" apps/api-python/tests
  →  test_auto_v51_auto10_cycle_journal_seam.py:130  (llamada real)
  →  test_auto_v74_producer_seam.py:4                 (solo docstring)
```

## 3. Verificación completa de la batería offline (lo que faltaba)

El comando del step `Pytest offline` se **extrae del propio workflow** y se corre **entero** en local. Los
ejecutables `pytest`/`mypy` están bloqueados por Windows Application Control, así que se usa el sustituto
`python -m pytest` con los **mismos argumentos** (115 tokens).

```
$ # comando extraído de .github/workflows/release-tag-ci.yml :: step "Pytest offline"
$ uv run --no-sync python -m pytest <115 argumentos idénticos>
...
FAILED apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it
1 failed, 3076 passed, 4 warnings in 74.23s (0:01:14)
```

El único fallo es el de **entorno ya declarado** en este proyecto:

```
>           assert document["measuredCycles"] == len(e2e._SPECS)
E           AssertionError: assert 17 == 26
apps\api-python\tests\test_auto_v70_auto23_evidence_validation.py:244
```

Es el material sembrado de la **BD de desarrollo** (17 ciclos frente a los 26 de `_SPECS`); en CI ese job
**no tiene Postgres** y el test se **salta**. Coincidencia exacta de recuentos con el CI: **3077
recolectados** en ambos lados —

| | CI (`v2.88.2-beta`, tag) | Local (tras el arreglo) |
| --- | --- | --- |
| passed | 3034 | 3076 |
| failed | 6 (costura) | 1 (entorno `17 == 26`) |
| skipped | 37 | (ese 1 no se salta: hay PG local) |
| recogidos | 3077 | 3077 |

Los **6** fallos de la costura **desaparecen** con el arreglo de una línea.

## 4. Certificado de mutaciones (matriz completa)

```
### M252 (alta sin propiedad): el tick persiste la reserva pero NO registra quien es su dueno
  rojo en: test_book_does_not_drip_over_n_ticks_when_the_cycle_is_durable,
           test_closing_reconcile_does_not_touch_another_sessions_reservation,
           test_closing_reconcile_keeps_captured_unapplied_capital_in_flight,
           test_orphan_reservation_is_released_as_cancel_at_tick_close,
           test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn,
           test_two_real_turns_do_not_drip_the_book_between_them
  restaurado byte a byte: si

=== huella del arbol ===
  intacto: la sonda no altero el arbol
  medidas: 252/252 (ninguna se quedo sin fragmento)
```

| Medición | Resultado |
| --- | --- |
| Mutación nueva `M252` (filtrada) | **1/1** detectada · matriz `251` → **`252`** |
| Matriz COMPLETA | **`252/252`** medidas · árbol **intacto** · `exit 0` |
| Estilo | `ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed** |

## 5. Contenido del diff (motor intacto)

| Fichero | Cambio |
| --- | --- |
| `apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py` | la costura declara `worker._v2_owned_reservations = set()` (con el porqué en comentario) |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `M252` (el alta sin propiedad) → matriz `251` → `252` |
| `CHANGELOG.md` · `package.json` | entrada y bump `2.11.2-beta` → `2.11.3-beta` |
| `docs/engineering/*` | este README, informe `obs-14c`, cita POST-TAG en `evidence/v2.88.2` §7, `PROJECT_STATE`, índice, deuda P3 (`OBS-16`), audit-pack y arranque del auditor |

**NO se toca**: `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`,
`packages/py/application/src/bolsa_application/replay_oos.py` ni ningún módulo de producción. El objeto
`v2.88.3-beta` es, en el motor, **idéntico** a `v2.88.2-beta`.

## 6. Límites declarados (no se maquilla)

- **`OBS-16` (MEDIUM, proceso) — ABIERTA:** la verificación local puede no cubrir la batería offline del CI;
  mecanismos: (a) la batería no se corría entera y (b) **15 costuras `object.__new__` duplican a mano** el
  estado del worker (todo atributo nuevo del `__init__` puede romper el job offline sin aviso local).
  **Mitigación medida:** extraer el comando del workflow y correrlo entero con `python -m pytest`.
  **Mejora posible, no implementada:** fábrica de costura compartida.
- **Sin cobertura de mutación para la pata de SALIDA:** `M252` acota el alta de la pata de entrada
  (`_v2_persist_tick_reservations`); el registro de propiedad de `_v2_reserve_exit` no tiene mutación ni
  test dedicados (ningún test lo ejerce; solo se menciona en un docstring).
- **`OBS-14.b`** (barrido de arranque sin ventana de gracia) y **`OBS-15`** (techo de 1000 `APPLIED`)
  siguen **abiertas**, sin cambios.
- El artefacto multianual de `v2.86`/`v2.87` sigue **exigiendo RE-EJECUCIÓN**: no es evidencia de
  estrategia ni mueve `P3-2`/`P3-3`.
- `mypy`/`pytest` **no medidos localmente como ejecutables** (Windows Application Control); los mide el CI.

## 7. CI del objeto vigente (`v2.88.3-beta`) — **VERDE, citado POST-TAG**

> **Límite estructural declarado (patrón `OBS-3`/`OBS-4`, no un fallo):** `Release tag CI` **solo corre al
> EMPUJAR** el tag, así que la cita de su resultado **no puede** existir dentro de ese mismo tag. La copia
> de este fichero **dentro** de `v2.88.3-beta` dice literalmente
> «Pendiente de medir: se publica en cuanto el tag `v2.88.3-beta` dispare `Release tag CI`» — un auditor
> que trabaje **estrictamente sobre el objeto sellado** verá eso y **NO** debe concluir «CI no
> acreditado»: la cita acreditada es **esta sección**, en un commit **POST-TAG** de `main`.

`Release tag CI` run [`36558405748`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405748)
(tag anotado **`v2.88.3-beta`** = objeto `66f47cf8e72449dc5bb907ef208abcc7afb0e857` → commit `0038adfc`;
HEAD `0038adfc`, `event=push`, `ref=v2.88.3-beta`, 2026-09-29T10:53:59Z → 11:02:28Z, **8m29s**),
**`conclusion: success` en la PRIMERA pasada** (`attempt 1`):

| Job | Resultado |
| --- | --- |
| shared (build/typecheck/test) | success |
| **python (ruff/imports/mypy/pytest offline)** | **success** ← el job que tumbó `v2.88.2-beta` |
| decision-spine | success |
| frontend (typecheck/lint/test/build + contract:check) | success |
| playwright (mock E2E) | success |
| **lifecycle-pg (Alembic + auth + golden restart)** | **success** ← crash/recovery + 3 sesiones concurrentes |
| dr-verify (battery DB_DR / TCP CI) | success |
| a7-gate (A7 C3 chaos live_a7 · dedicated real-PG) | success |
| security (gitleaks) | success |
| playwright (integrated E2E, opt-in) | skipped (por diseño) |
| certify (aggregate + artifact) | success |

Recuentos **verbatim** del job `python` (la puerta que falló en `v2.88.2`):

```
Ruff            All checks passed!
Import-linter   Contracts: 4 kept, 0 broken.
Mypy            Success: no issues found in 508 source files
Pytest offline  3040 passed, 37 skipped, 6 warnings in 69.72s (0:01:09)
```

**Cuadre con el rojo del objeto anterior:** `3040 passed + 37 skipped = 3077` recogidos = exactamente los
`3034 passed + 6 failed + 37 skipped = 3077` de `v2.88.2-beta`. Los **6** fallos de la costura
**desaparecen** sin mover ni un `skip`: el arreglo no oculta tests, los **enruta**.

Otros jobs (recuentos verbatim de sus logs):

| Job | Recuento |
| --- | --- |
| decision-spine | `604 passed in 5.32s` |
| a7-gate (A7 C3 chaos live_a7 · PG real) | `7 passed in 15.48s` |
| lifecycle-pg | **8 invocaciones `pytest`** (`165`, `45`, `1`, `1`, `3`, `2`, `2`, `1` passed) = **220 passed, 0 failed** |
| dr-verify | success (batería de script, sin líneas `pytest`) |

**Lectura honesta:** los **dos** gates que perseguían los tres RE-SELLOS anteriores quedan verdes en el
**mismo** run — el job `python` (costura offline, lo nuevo de `v2.88.3`) y `lifecycle-pg` (crash/recovery
real + carrera de 3 sesiones + golden day + aislamiento por cuenta, lo heredado de `v2.88.2`). El motor de
este tag es **idéntico** al de `v2.88.2`; lo que cambia es que **la validación ya no miente**.

<!-- COMMIT-QUE-INTRODUJO-ESTA-CITA: a6c44b77e446c1e62d0ad0bdeb9f47441398fc6e (abreviado `a6c44b77`) -->

> **Un commit no puede citar su propio hash.** El hash del commit **POST-TAG** que introdujo esta sección
> se registra en el commit **inmediatamente siguiente** (el SEGUNDO POST-TAG, `docs`-only, que **no**
> cambia ninguna afirmación de este fichero): **`a6c44b77e446c1e62d0ad0bdeb9f47441398fc6e`**, el PRIMER
> commit de `main` POSTERIOR al tag `v2.88.3-beta`. Verifícalo con:
>
> ```
> git log --format=%h:%s -1 --grep "cita POST-TAG del CI del tag v2.88.3-beta"
> ```

### 7.1 El resto de workflows del MISMO commit (`0038adfc`) — todos verdes

Citados para **no dejar el árbol a medias**: el commit sellado no solo pasa `Release tag CI`.

| Workflow | Ref | Run | Resultado |
| --- | --- | --- | --- |
| Python CI | `v2.88.3-beta` | [`36558405715`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405715) | success |
| Frontend CI | `v2.88.3-beta` | [`36558405669`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405669) | success |
| Optimize lab | `v2.88.3-beta` | [`36558405730`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405730) | success |
| Fase 2 scientific | `v2.88.3-beta` | [`36558405668`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405668) | success |
| Python CI | `main` | [`36558402839`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558402839) | success |
| Frontend CI | `main` | [`36558402720`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558402720) | success |
| Optimize lab | `main` | [`36558402895`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558402895) | success |
| Gitleaks | `main` | [`36558402801`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558402801) | success |

Los dos commits **POST-TAG** (`a6c44b77` y el siguiente, `docs`-only, sin tocar `packages/`/`apps/`) **no**
disparan workflows de Python por el trigger por rutas: la cita **no** introduce código nuevo.
