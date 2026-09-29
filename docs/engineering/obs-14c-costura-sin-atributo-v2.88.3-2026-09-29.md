# RE-SELLO 3 — la costura del journal no declaraba el libro de propiedad (`AUTO-MATERIAL-16c` / `v2.88.3`)

> **AsOf:** 2026-09-29 · **Fase:** corrección de **VALIDACIÓN** (un test de costura) + arnés + docs; el motor **no** cambia.
> **Tipo de entrega:** test de costura (1 línea) + mutación `M252` + informe + evidencia + registros.
> **Bump:** `2.11.2-beta` → `2.11.3-beta` · **SIN migración** (Alembic head sigue en `046_fill_reference_mid`).
> **Sello:** tag anotado **`v2.88.3-beta`** · **tags SUPERADOS:** `v2.88-beta`, `v2.88.1-beta`, `v2.88.2-beta` (los tres con su CI rojo conservado) · **base del diff:** `41e7e679` (= `v2.88.2-beta`).
> **Padres:** [obs-14b](./obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md) → [obs-14](./obs-14-correccion-fail-open-v2.88.1-2026-09-29.md) → [obs-14-cierre-por-turno](./obs-14-cierre-por-turno-v2.88-2026-09-29.md) · **Evidencia:** [evidence/v2.88.3/README.md](./evidence/v2.88.3/README.md) · **Índice:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) · **Deuda:** [deuda-p3-post-auditoria-v2.70-2026-09-26.md](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)

---

## 1. Por qué existe este RE-SELLO

El tag `v2.88.2-beta` (`41e7e679`) se publicó y su `Release tag CI`
([`36553839085`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36553839085)) cayó en el job
**`python (ruff/imports/mypy/pytest offline)`**: `ruff`, `import-linter` y `mypy` verdes; **`Pytest
offline`** con **6 fallos idénticos** (`6 failed, 3034 passed, 37 skipped`):

```
AttributeError: 'AutoSimulationWorker' object has no attribute '_v2_owned_reservations'.
  Did you mean: '_v2_reservations'?
apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:2335
apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py   (los 6 tests del fichero)
```

**Y lo importante: lo que perseguían los dos RE-SELLOS anteriores quedó VERDE.** El job `lifecycle-pg`
—crash/recovery del día real, **3 sesiones concurrentes sobre la misma señal**, golden day, aislamiento de
cuenta— pasó, igual que `a7-gate`, `dr-verify`, `shared`, `frontend`, `spine` y `security`. Es la primera
corrida en la que el cierre de turno pasa **a la vez** el gate de correctitud y el de la carrera. El tercer
rojo es **de otro sitio**, y de otra naturaleza.

## 2. Causa raíz: un defecto de la VALIDACIÓN, no del motor

La costura `test_auto_v51_auto10_cycle_journal_seam.py` construye el worker **sin `__init__`**:

```python
def _worker(*, sink: Any | None = None, regime: str | None = _REGIME) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._reservation_store = InMemoryReservationStore(seed=())
    worker._v2_reservations = ()
    worker._v2_reservation_blocked = frozenset()
    worker._v2_reservation_carryover = frozenset()
    ...
```

Es un patrón deliberado del proyecto (15 ficheros lo usan): el doble declara **a mano** solo el estado que
la ruta ejercitada necesita, para aislar la costura de la aritmética. La ruta de este fichero es
`_v2_persist_tick_reservations` — el **alta** de la reserva — y ahí es donde `v2.88.2` añadió
`self._v2_owned_reservations.add(...)`. El libro de propiedad vive en el `__init__`, que la costura **no
ejecuta**: `AttributeError`.

**El motor NUNCA tuvo este defecto**: en producción `__init__` siempre corre. El defecto es que mi
**validación local no cubrió la puerta real del CI**. Corrí suites vecinas (carrera `7 passed`, ciclo
durable `14`, instrumento `14`, vecinos del motor `49 passed`, pasos saltados `5 passed`) y **no** la
batería offline completa, que es la que GitHub ejecuta y la que recorre las 15 costuras.

> Lección declarada como **`OBS-16`** (proceso, MEDIUM): *«la verificación local puede no cubrir la
> batería offline del CI»*, con dos mecanismos: (a) la batería no se corría entera y (b) las costuras
> `object.__new__` **duplican a mano** el estado del worker, así que **todo atributo nuevo del `__init__`
> puede romperlas sin aviso local**. Ver §7.

## 3. Arreglo (1 línea funcional) y por qué es el sitio correcto

```python
    worker._v2_reservation_carryover = frozenset()
    # OBS-14.b — el alta de la reserva registra la PROPIEDAD de la sesión (quién la puede
    # retirar al cerrar su turno). Esta costura construye el worker con ``object.__new__``
    # (sin ``__init__``), así que el libro de propiedad se declara aquí, como el resto del
    # estado del libro de reservas que la costura ya declara.
    worker._v2_owned_reservations = set()
```

Por qué **aquí** y no relajando el motor con `getattr`: la convención del proyecto es que el doble de
costura **declare** el estado que usa (ya declara `_v2_reservations`, `_v2_reservation_blocked`,
`_v2_reservation_carryover`, `_v2_tunables`, …). Un `getattr(self, "_v2_owned_reservations", set())` en el
camino de producción convertiría un fallo de inicialización en un **silencio**: el cierre de turno
retiraría "lo suyo" sin dueño y volvería justo al fail-**OPEN** que costó dos RE-SELLOS. **El motor no se
toca.**

**Alcance verificado:** de las **15** costuras con `object.__new__(AutoSimulationWorker)`, esta es la
**única** que ejerce `_v2_persist_tick_reservations` / `_v2_reserve_exit` / `_v2_reconcile_reservations`
(grep exhaustivo sobre `apps/api-python/tests`; las demás solo mencionan los métodos en docstrings, como
`test_auto_v74_producer_seam.py`). Por eso el CI falló en **un** fichero y no en los 15.

## 4. Verificación NUEVA: la batería offline del CI, entera y en local

Lo que faltaba, ahora medido: se **extrae del propio workflow** (`release-tag-ci.yml`, step
`Pytest offline`) el comando completo y se corre **entero** en local.

- Windows Application Control bloquea los ejecutables `pytest` y `mypy` (`os error 4551`, *«Una directiva de
  Control de aplicaciones bloqueó este archivo»*), así que la batería se corre con el sustituto
  `uv run --no-sync python -m pytest <mismos argumentos>`.
- Resultado: **3076 passed, 1 failed** (74,23 s).
- El **único** fallo es el de **entorno ya declarado** en este proyecto:
  `test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it`
  → `AssertionError: assert 17 == 26` (material sembrado de la BD de **desarrollo**; en CI ese job no tiene
  Postgres y el test se salta). Coincidencia exacta de recuentos con el CI: 3077 recolectados en ambos
  lados (allí `3034 + 37 skipped + 6 failed`; aquí `3076 passed + 1 failed`).
- Los **6** fallos de la costura **desaparecen**.

## 5. Validación y mutación

| Medición | Comando (resumen) | Resultado |
| --- | --- | --- |
| **Batería offline del CI (completa)** | comando extraído del workflow, vía `python -m pytest` | **3076 passed, 1 failed** (solo el de entorno `17 == 26`) |
| Los 6 de la costura | `pytest apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py` | incluidos en la batería, **verdes** |
| Estilo | `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| Mutación nueva `M252` | `v2_44_mutation_audit.py --only M252` | **1/1 detectada** (matriz `251` → **`252`**) |
| Matriz COMPLETA | `v2_44_mutation_audit.py` | **`252/252`** medidas, árbol **intacto**, `exit 0` |

Mutación nueva:

- **`M252` (alta sin propiedad):** el tick persiste la reserva pero **no** registra su dueño ⇒ lo cazan
  **6** tests del ciclo durable (`test_book_does_not_drip_over_n_ticks_when_the_cycle_is_durable`,
  `test_closing_reconcile_does_not_touch_another_sessions_reservation`,
  `test_closing_reconcile_keeps_captured_unapplied_capital_in_flight`,
  `test_orphan_reservation_is_released_as_cancel_at_tick_close`,
  `test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn`,
  `test_two_real_turns_do_not_drip_the_book_between_them`).

## 6. Qué NO cambia

- El **motor es byte a byte** el de `v2.88.2`: no se toca ninguna compuerta, régimen, umbral, ni la lógica
  de propiedad (`only_ids` / `_v2_owned_reservations`).
- **SIN migración**: Alembic head sigue en `046_fill_reference_mid`.
- La **reconciliación de ARRANQUE** mantiene su comportamiento exacto (alcance total).
- Los números del instrumento `v2.87` **no** se mueven por este sello (no toca el instrumento); la
  RE-EJECUCIÓN declarada en `v2.88.1` **se mantiene** (por la guarda `attribute_fills`, no por esto).

## 7. Límites declarados (no se maquillan)

- **`OBS-16` (MEDIUM, proceso) — ABIERTA.** «La verificación local puede no cubrir la batería offline del
  CI». Mecanismos: (a) la batería no se corría entera; (b) **15 costuras `object.__new__` duplican a mano
  el estado del worker**, de modo que cualquier atributo nuevo del `__init__` que una ruta de costura use
  rompe el job offline sin aviso local. **Mitigación adoptada y medida:** extraer el comando del step
  `Pytest offline` del workflow y correrlo entero con `python -m pytest` (el ejecutable `pytest` está
  bloqueado por Windows Application Control). **Mejora posible, NO implementada:** una fábrica de costura
  compartida que derive el estado del `__init__` en vez de duplicarlo a mano.
- **Sin cobertura de mutación para la pata de SALIDA.** La mutación nueva acota la pata de **entrada**
  (`_v2_persist_tick_reservations`). El registro de propiedad de la reserva de **salida**
  (`_v2_reserve_exit`) no tiene mutación ni test dedicados (no hay ningún test que ejerza `_v2_reserve_exit`
  — solo se menciona en un docstring). Se declara: la línea está en el mismo mecanismo, pero **no** está
  fijada por una medición.
- El artefacto multianual de `v2.86`/`v2.87` sigue **exigiendo RE-EJECUCIÓN** (no es evidencia de
  estrategia ni sirve para mover `P3-2`/`P3-3`).
- `mypy` y `pytest` **NO MEDIDOS localmente como ejecutables** (Windows Application Control); los mide el
  job `python (ruff/imports/mypy/pytest offline)` del CI del tag — ya verdes en `ruff`/`imports`/`mypy`
  para el objeto anterior.

## 8. Relevo

- **Estado:** `OBS-14` cerrada (con el alcance correcto desde `v2.88.2`); `OBS-14.b` abierta (barrido de
  arranque sin ventana de gracia); `OBS-15` abierta (techo de 1000 `APPLIED`); **`OBS-16` abierta** (nueva,
  proceso).
- **Objeto de auditoría vigente:** tag `v2.88.3-beta` (versión `2.11.3-beta`). Superados con su CI rojo
  **conservado**: `v2.88-beta` (crash/recovery), `v2.88.1-beta` (carrera concurrente), `v2.88.2-beta`
  (costura del journal) — las tres citas están en `evidence/v2.88/`, `evidence/v2.88.1/` y
  `evidence/v2.88.2/`.

## 9. CI del objeto vigente: **VERDE**, citado POST-TAG

> Sección **POST-TAG**: `Release tag CI` solo corre al empujar el tag, así que este resultado **no puede**
> viajar dentro de `v2.88.3-beta`. La copia sellada de este informe y de
> [`evidence/v2.88.3/README.md`](./evidence/v2.88.3/README.md) declaran ese límite **antes** del push.

`Release tag CI` [`36558405748`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405748)
(tag `v2.88.3-beta` → commit `0038adfc`): **SUCCESS en la primera pasada** (`attempt 1`, 8m29s,
2026-09-29T10:53:59Z → 11:02:28Z). **Los 10 jobs reales en verde** (`playwright` integrado `skipped` por
diseño) + `certify` en verde.

Lo que mide, contra lo que perseguía este RE-SELLO:

| Gate | `v2.88.2-beta` (rojo) | `v2.88.3-beta` |
| --- | --- | --- |
| `python` · **Pytest offline** | `6 failed, 3034 passed, 37 skipped` | **`3040 passed, 37 skipped`** (0 fallos) |
| `python` · `ruff` / `imports` / `mypy` | verdes | verdes (`All checks passed!` · `Contracts: 4 kept, 0 broken.` · `508` ficheros) |
| `lifecycle-pg` (crash/recovery + 3 sesiones concurrentes + golden day) | success | **success** (8 invocaciones `pytest`, **220 passed**, 0 failed) |
| `decision-spine` | success | success (`604 passed`) |
| `a7-gate` (chaos live_a7 · PG real) | success | success (`7 passed`) |
| `dr-verify` / `shared` / `frontend` / `playwright (mock)` / `security` | success | success |

**Cuadre declarado, sin maquillar:** `3040 + 37 = 3077` recogidos = los mismos `3077` del objeto anterior
(`3034 + 6 + 37`). El arreglo **no** oculta tests ni mueve un `skip`: los **6** que fallaban pasan.
`mypy` pasa de `507` a `508` ficheros, y el **único** `.py` de `src` añadido desde `v2.85.2` (`983b0eac`)
es `packages/py/application/src/bolsa_application/replay_oos.py` (instrumento de `v2.86`) — **ningún**
fichero nuevo de este sello.
