# Evidencia cruda — ventana de gracia por EDAD del barrido de reservas (`v2.88.5`, `AUTO-MATERIAL-18`, 2026-09-29)

Resumen **verificable** del cierre de `OBS-14.b`: la reconciliación de reservas retira una candidata solo
si es **de esta sesión** (`only_ids`) **o** si **ya envejeció** la ventana de gracia; una reserva **ajena y
joven** se **conserva** (fail-closed). Las cifras están transcritas de las corridas, sin edición.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-18` (`v2.88.5`) — ventana de gracia por EDAD (`OBS-14.b`) + tests + mutaciones + docs |
| Versión de paquete | `2.11.4-beta` → **`2.11.5-beta`** |
| Tag (lo crea el propietario) | **`v2.88.5-beta`** (anotado) |
| Base del diff | **`a4d32c0d`** (= `v2.88.4-beta` + cita POST-TAG de su CI) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Diff del motor | **`+91 / −20`** en `auto_simulation_worker.py` (**5 hunks**) — **SÍ se toca el motor** |
| Contenido del sello | motor (ventana de gracia) + 8 funciones de test (7 netas) + 4 mutaciones (`M250` re-anclada, `M254`/`M255`/`M256`) + `CHANGELOG` + `package.json` + docs |

## 1. El hueco que se cierra

`v2.88.2` acotó el **cierre de turno** por **propiedad** (`only_ids = _v2_owned_reservations`) y dejó el
**barrido de ARRANQUE** global. La regla 2 decide «esta orden murió sin llenarse» con la **misma** evidencia
durable (sin `APPLIED`, sin traza en vuelo, lecturas medibles), que **no puede** distinguir:

| Caso | Qué es | Qué debe hacer la reconciliación |
| --- | --- | --- |
| **Huérfana** | reserva que dejó un proceso **muerto** | retirarla (liberar el capital) |
| **Viva ajena** | reserva que **otra sesión** acaba de dar de alta y **aún no ha emitido** | **no tocarla** |

En un **reinicio rodante**, el arranque de B retiraba la reserva **viva de A** y devolvía al mercado un
capital que **A sí materializa** (capital reservado ≠ materializado): el **mismo fail-OPEN** de `v2.88.1`,
por la pata que el CI **no** ejercitaba (en el arranque simultáneo la ventana es nula). **Ya existía en
`v2.85.2`**: no es una regresión de `v2.88`.

## 2. El mecanismo (PROPIEDAD *o* EDAD)

```python
V2_RESERVATION_GRACE_TURNS = 1

def reservation_grace_window(interval_seconds: float | None = None) -> timedelta:
    seconds = _sim_interval_seconds() if interval_seconds is None else interval_seconds
    return timedelta(seconds=V2_RESERVATION_GRACE_TURNS * seconds)
```

Derivada de la **cadencia REAL del loop** (`AUTO_ENGINE_SIM_INTERVAL_SECONDS`, default **`60 s`**) ⇒ ventana
de **60 s**, **no** un número mágico. Regla 2 (`_v2_reconcile_reservations`):

```python
mine = only_ids is not None and reservation.reservation_id in only_ids
if not mine and not self._v2_reservation_is_aged(created):
    resolved.append(reservation)
    continue
```

Predicado (`_v2_reservation_is_aged`):

```python
if created is None:
    return False
return (self._time - created) > self._v2_reservation_grace
```

- **Estricto (`>`):** en el borde exacto (`age == grace == 1 turno`) **no** está caducada ⇒ **conserva**.
- **Sin fecha legible** (`created is None`) ⇒ **conserva**.
- **Fecha FUTURA** (relojes no comparables; `self._time - created < 0`) ⇒ **conserva** (fail-closed).
- Reloj de referencia: `self._time` (la **misma** autoridad con la que esta sesión fecha sus altas).

**Por qué 1 turno es correcto aquí:** el motor AUTO opera **solo** `paper`/`simulated` (sin bridge LIVE),
así que la orden **liquida dentro del tick**; una reserva que superó **un turno completo** sin fill ni traza
en vuelo está muerta **por construcción** (su dueño, sea quien sea, ya cerró su turno). La EDAD es el
discriminador y **no** requiere identidad de sesión (que el esquema no tiene).

**Consecuencia declarada:** la huérfana que **aún no envejeció** sobrevive al barrido de arranque y se
retira en el **primer cierre de turno posterior a la ventana** (`RELEASED_BY_CANCEL`) — a lo sumo **un turno
más tarde** — o en el arranque siguiente (`RELEASED_BY_RESTART`). Retención **acotada**, no fuga.

## 3. Tests (8 funciones nuevas ⇒ **7 netas**)

`apps/api-python/tests/test_auto_v2_durable_cycle.py` — **16 → 22** (7 nuevas, **1 sustituida**; +6 netos):

```
### test_closing_reconcile_does_not_touch_a_young_foreign_reservation
  - cierre: la ajena JOVEN se CONSERVA (sigue is_live, released_qty == 0), su capital sigue comprometido
    y conservarla NO la adopta (no entra en _v2_owned_reservations); las SUYAS sí se retiran
### test_closing_reconcile_retires_a_foreign_reservation_once_it_aged
  - cierre: la ajena ENVEJECIDA (2 ventanas) se retira RELEASED_BY_CANCEL / cancel
### test_startup_sweep_retains_a_young_foreign_reservation
  - ARRANQUE: la ajena JOVEN (edad 0) SOBREVIVE al barrido (el fail-OPEN de OBS-14.b)
### test_startup_sweep_retires_an_aged_foreign_reservation
  - ARRANQUE: la ajena ENVEJECIDA se retira RELEASED_BY_RESTART / restart
### test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future
  - RELOJES NO COMPARABLES: fecha 2 ventanas ADELANTADA => se conserva (no se afirma edad)
### test_grace_window_boundary_is_strict_at_exactly_one_turn
  - BORDE: edad == 1 turno CONSERVA; edad == 1 turno + 1 s RETIRA (dos reservas, un segundo de diferencia)
### test_closing_reconcile_does_not_abandon_a_young_foreign_exit_intent
  - PATA DE SALIDA: la ajena conservada no deja el ExitOrder del dueño en ABANDONED
```

`apps/api-python/tests/test_auto_v44_exit_crash_matrix.py` — **8 → 9** (1 nueva; +1 neto):

```
### test_c2b_restart_inside_the_grace_window_retains_and_then_converges
  - crash tras reservar + reinicio DENTRO de la ventana => la reserva se CONSERVA
  - el reinicio siguiente, ya ENVEJECIDA, la retira y el libro CONVERGE a plano (retención acotada)
```

Corrida de las cuatro suites afectadas:

```
$ uv run --no-sync python -m pytest \
    apps/api-python/tests/test_auto_v2_durable_cycle.py \
    apps/api-python/tests/test_auto_v44_exit_crash_matrix.py \
    apps/api-python/tests/test_auto_v44_exit_governance.py \
    apps/api-python/tests/test_auto_v46_crash_recovery.py -q -p no:cacheprovider
..........................................                                 [100%]
42 passed in 1.31s
```

Re-anclados a la semántica de edad explícita (sin tests nuevos): `test_auto_v44_exit_crash_matrix.py`
(`C2`/`C4` reinician en el minuto +2), `test_auto_v44_exit_governance.py` (9 tests, reinicio a `09:02` con
alta en `09:01`) y `test_auto_v46_crash_recovery.py` (2 tests, `minute=4`).

## 4. Mutaciones (matriz `253` → `256`)

Rotuladas por el run (`> ###`, verbatim de `logs/dev/mutmatrix-v2.88.5.txt`):

```
### M250 (barrido sin EDAD, ventana NULA): toda reserva 'envejece' al instante -> el barrido vuelve a
         retirar la AJENA y JOVEN (fail-OPEN). Su forma historica (`only_ids=frozenset()`) dejo de medir
         al entrar la EDAD: se re-ancla aqui
    rojo en: test_closing_reconcile_does_not_abandon_a_young_foreign_exit_intent,
             test_closing_reconcile_does_not_touch_a_young_foreign_reservation,
             test_grace_window_boundary_is_strict_at_exactly_one_turn,
             test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it,
             test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future,
             test_startup_sweep_retains_a_young_foreign_reservation          (6 tests)
    restaurado byte a byte: si

### M254 (ventana INFINITA): ninguna reserva envejece -> la retirada diferida no llega nunca y el crash
         deja de converger
    rojo en: test_c2_crash_after_reserving_before_emit_releases_dead_and_exits_once,
             test_c2b_restart_inside_the_grace_window_retains_and_then_converges,
             test_c4_crash_after_partial_fill_carries_the_intent_and_converges,
             test_closing_reconcile_retires_a_foreign_reservation_once_it_aged,
             test_grace_window_boundary_is_strict_at_exactly_one_turn,
             test_startup_sweep_retires_an_aged_foreign_reservation           (6 tests)
    restaurado byte a byte: si

### M255 (edad sin signo): la distancia ABSOLUTA cuenta como edad -> una reserva con el reloj ADELANTADO
         se retira (skew = fail-OPEN)
    rojo en: test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future    (1 test)
    restaurado byte a byte: si

### M256 (borde no estricto): edad == ventana ya autoriza a retirar -> se retira en el instante en que el
         dueno puede estar cerrando
    rojo en: test_grace_window_boundary_is_strict_at_exactly_one_turn,
             test_reserve_exit_ownership_is_scoped_to_the_session_that_created_it  (2 tests)
    restaurado byte a byte: si

=== huella del arbol ===
estado git de esos ficheros (despues): M apps/api-python/src/bolsa_api/background/auto_simulation_worker.py
  intacto: la sonda no altero el arbol
  medidas: 256/256 (ninguna se quedo sin fragmento)
--- exit_code: 0   elapsed_ms: 770282 (~12m50s)
```

| Mutación | Detectada | Tests que la cazan |
| --- | --- | --- |
| `M250` (ventana NULA, re-anclada) | ✅ | **6** (retenciones joven + borde) |
| **`M254` (ventana INFINITA)** | ✅ | **6** (retiradas + `C2`/`C2b`/`C4` convergencia) |
| **`M255` (edad sin signo)** | ✅ | **1** (`test_startup_sweep_retains_a_foreign_reservation_dated_in_the_future`) |
| **`M256` (borde no estricto)** | ✅ | **2** (`test_grace_window_boundary_is_strict_at_exactly_one_turn` + simetría de salida) |
| **Matriz COMPLETA** | **`256/256`** medidas · árbol **intacto** · `exit 0` · ~12m50s | — |

Las cuatro direcciones de la ventana tienen su mutación: **propiedad** (`M250`/`M252`/`M253`), **edad**
(`M250` vs `M254`), **borde** (`M256`) y **relojes no comparables** (`M255`). `M250`/`M255` atacan el
fail-closed (retirar de más) y `M254`/`M256` la **terminación** (conservar de más).

## 5. Compuertas

```
$ uv run ruff check packages/py apps/api-python --config pyproject.toml
All checks passed!

$ uv run --no-sync python -m pytest <115 args EXACTOS del job `Pytest offline` del workflow> -p no:cacheprovider
...
FAILED apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it
1 failed, 3085 passed, 4 warnings in 73.77s (0:01:12)
```

El único `failed` es **pre-existente y ajeno** (`AssertionError: assert 17 == 26`): necesita **material
`paper_real` real sembrado en PostgreSQL local** y la BD de desarrollo tiene **17** ciclos de los **26**
que el test exige. En el job `python` del CI ese test **se salta** (no hay PG en ese job; forma parte de
los `37` skips) — es el **mismo** fallo de entorno ya declarado en la evidencia de `v2.88.3`. Los
recuentos **cuadran**: `3085 + 1 = 3086` recogidos = los **`3079`** que recogía el job `python` de
`v2.88.4` (`3042 passed + 37 skipped`) **+ 7** netos ⇒ esperado del CI **`3049 passed, 37 skipped`**.

## 6. Límites declarados

- **SÍ** se toca el motor (a diferencia de `v2.88.4`): la ventana de gracia **es** lógica de producción.
- **La ventana es 1 turno con la cadencia nominal (60 s)**: decisión **declarada**, no medida en
  producción. El techo de retención de una huérfana es esa ventana. Si la cadencia configurada
  (`AUTO_ENGINE_SIM_INTERVAL_SECONDS`) fuese muy superior al turno real, la ventana sería más **laxa**
  (nunca menos laxa: la propiedad sigue acotando el cierre).
- **NO** sustituye la prueba real de concurrencia: eso es el job `lifecycle-pg` (crash/recovery + **3
  sesiones concurrentes** + golden day + aislamiento de cuenta) del CI del tag.
- **NO** cierra `OBS-15` (techo de 1000 `APPLIED`), `OBS-16` (costuras manuales de `object.__new__`) ni
  `P3-2`/`P3-3`.

## 7. CI del tag — POST-TAG (patrón `OBS-3`/`OBS-4`)

`Release tag CI` solo corre **al empujar**, así que su cita **no puede** vivir dentro del tag. La
instancia **dentro del tag** de este fichero declaraba lo **esperado**; aquí queda la cita **REAL**, medida
sobre el objeto empujado. **Se cita el run, no se hereda.**

### 7.1 Esperado (escrito DENTRO del tag, antes del push)

Job `python`: **`3049 passed, 37 skipped`** (los `3042` de `v2.88.4` + **7** netos) y los **mismos `37`
skips**. **Matriz completa `256/256`** con el árbol intacto.

### 7.2 Observado (`Release tag CI`, run [`36581692155`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36581692155))

```
HEAD d16e3ade · event=push · ref=v2.88.5-beta
conclusion: SUCCESS   (GREEN en la PRIMERA pasada; attempt 1; 14:18:33Z -> 14:27:33Z, ~9m00s)
10 jobs success + `certify` success; `playwright (integrated E2E, opt-in)` SKIPPED por diseño
```

| Job | Resultado |
| --- | --- |
| `shared (build/typecheck/test)` | success |
| `python (ruff/imports/mypy/pytest offline)` | success |
| `decision-spine` | success |
| `lifecycle-pg (Alembic + auth + golden restart)` | success |
| `frontend (typecheck/lint/test/build + contract:check)` | success |
| `dr-verify (battery DB_DR / TCP CI)` | success |
| `security (gitleaks)` | success |
| `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` | success |
| `playwright (mock E2E)` | success |
| `playwright (integrated E2E, opt-in)` | skipped (por diseño) |
| `certify (aggregate + artifact)` | success |

Job `python` del tag (**verbatim**):

```
ruff    : All checks passed!
imports : Contracts: 4 kept, 0 broken.
mypy    : Success: no issues found in 508 source files
pytest  : 3049 passed, 37 skipped, 6 warnings in 63.71s (0:01:03)
```

**ESPERADO `3049/37` → OBSERVADO `3049/37` → COINCIDE.** El falso rojo de la costura (`v2.88.2`) **no
reaparece** y los **7** tests netos de `OBS-14.b` corren en CI con los **mismos `37` skips**.

Además: `decision-spine 604 passed in 5.72s`; `a7-gate 7 passed in 14.67s`; y `lifecycle-pg` **GREEN** con
**`220 passed`** en sus **8** invocaciones (**0 failed / 0 skipped**; guardas `fail if skipped` verdes:
crash/recovery, **3 sesiones concurrentes**, golden day, aislamiento de cuenta, HardKill, crash injection
matrix y multiprocess).

Companion sobre el mismo commit/ref: `Python CI 36581692059`, `Frontend CI 36581691966`,
`Optimize lab 36581692245`, `Fase 2 scientific 36581692285` → **`success`** las cuatro; en `main` (push
`d16e3ade`) `Python CI 36581687611` `quality` **`3038 passed, 40 skipped`** (= `3031 + 7`) con los cuatro
jobs PG per-commit verdes.

Cita completa, cruda y verbatim: `docs/engineering/evidencia-ci-tag-v2.88.5-2026-09-29.txt`.
