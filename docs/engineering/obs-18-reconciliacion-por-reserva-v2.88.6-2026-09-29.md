# `OBS-18` — Reconciliación por EVIDENCIA DE LA RESERVA + guardarraíl de estancamiento del replay (`v2.88.6-beta`, `AUTO-MATERIAL-19`, 2026-09-29)

> **Tipo de entrega:** cambio de **motor** (regla 2 de la reconciliación) + cambio de **instrumento** (replay
> OOS: motivo de retirada + guardarraíl de estancamiento) + 25 funciones de test + 9 mutaciones + **2
> workflows** (se cablea el test del instrumento, que nunca corrió en CI: hueco medido) + informe +
> evidencia + registros.
> **Objeto:** tag anotado **`v2.88.6-beta`** · **Versión:** `2.11.5-beta` → **`2.11.6-beta`** ·
> **Alembic head:** `046_fill_reference_mid` (**sin migración**) · **Base del diff:** `27264aab`
> (= `v2.88.5-beta` + cita POST-TAG de su CI).
> **Origen:** el **replay OOS multianual** de `AUTO-MATERIAL-15` (`v2.87`) se declaró viable con el libro
> **sucio**, y su artefacto quedó marcado como **no reproducible con el código sellado**. Al re-ejecutarlo
> sobre `v2.88.5-beta` el replay **volvió a truncarse**: el libro retenía **16 reservas vivas** y
> `$5999.9998 / $6000` de riesgo comprometido, y el horizonte lo publicaba como **`completed: true`**.

---

## 0. Qué es y qué NO es esta entrega

**Es** el cierre de **`OBS-18`**, con dos defectos **medidos** y **distintos**:

1. **Motor (regla 2 de la reconciliación):** la retirada se decidía por el **AGREGADO de fills del
   instrumento+lado** (`filled == 0.0`) en vez de por la **evidencia de la propia reserva**
   (`released_qty`). Consecuencia medida: una reserva que **nunca materializó** sobrevivía **para siempre**
   en cuanto una hermana suya llenaba, y la **COLA** de un fill parcial no la retiraba **nadie** (la regla 1
   solo libera lo materializado).
2. **Instrumento (replay OOS):** el artefacto **no medía el motivo** de la retirada y **no declaraba** el
   estancamiento, así que un replay con el presupuesto agotado se publicaba como **corrida completa**.

**NO es** un cambio de comportamiento de trading: no se toca `TOP_N`, `REGIME`, `RISK`, `SIGNALS`, `A/B`,
ningún umbral, ni el fallback, ni se backdatea nada. **NO** cierra `OBS-15` (techo de 1000 `APPLIED`),
`OBS-16` (costuras manuales de `object.__new__`) ni `P3-2`/`P3-3` (la ventana PAPER real sigue **ABIERTA**:
el replay usa **reloj simulado** y no puede acreditarla).

---

## 1. El defecto de motor: la regla 2 decidía por el AGREGADO

### 1.1 La forma sellada (histórica)

```python
filled = 0.0
for instant, qty in applied.get((instrument, reservation.side), ()):
    if instant >= created:
        filled += qty          # AGREGADO del instrumento+lado posterior al alta de ESTA fila
...
elif (measurable and created is not None and instrument not in (in_flight or frozenset())
      and filled == 0.0):      # ← el agregado decide por ELLA
```

`filled` es un total **ajeno a la fila**: suma los fills de **cualquier** orden del mismo
`(instrumento, lado)` posteriores a su alta. Dos huecos, los dos medidos:

| Caso | Evidencia de la RESERVA | Agregado | Regla 2 sellada | Resultado medido |
| --- | --- | --- | --- | --- |
| **Nunca materializó, hermana llenó** | `released_qty == 0`, sin traza en vuelo | `filled = 4 > 0` | **no retira** | capital retenido **para siempre** |
| **Cola de fill parcial muerta** | `released_qty = 4 > 0`, `remaining_qty = 6 > 0`, sin traza en vuelo | `filled = 4 > 0` | **no retira** | capital retenido **para siempre** |

### 1.2 La forma nueva: evidencia POR RESERVA + motivo declarado

```python
materialized = float(reservation.released_qty or 0.0)
if attribute_fills and fill_qty > 0:
    ...                                        # regla 1: libera lo MATERIALIZADO
elif measurable and created is not None and instrument not in (in_flight or frozenset()):
    released = await self._v2_release_reservation(
        reservation,
        status=RESERVATION_RELEASED_BY_RESTART if startup else RESERVATION_RELEASED_BY_CANCEL,
        reason=(RELEASE_REASON_RESTART if startup
                else (RELEASE_REASON_DEAD_TAIL if materialized > 0.0 else RELEASE_REASON_CANCEL)),
        released_qty=None,
    )
```

- El discriminador es **lo que el camino caliente liberó de ESTA fila** (`released_qty`), no el total del
  instrumento.
- **Fail-closed intacto:** la guardia de `in_flight` **manda** (una traza sin aplicar del instrumento
  significa que la orden sigue trabajando y su cola **todavía puede** materializar); con lectura
  incompleta (`measurable=False`) o sin fecha legible **no se libera nada**; y la liberación **nunca
  supera** la cantidad viva.
- El **motivo** declara la causa en vez de esconderla: `tail_dead` cuando la fila **sí** registró fill
  parcial (se retira la **cola**, no lo materializado) y `cancel` cuando **no** materializó nada.
- El `outcome` publica la evidencia **de la reserva** (`fill_qty = materialized`), no el chunk del agregado:
  una reserva que no materializó **no** puede «marcar como llenado» el fill de su hermana al sincronizar el
  `INTENT` de salida (lo cerraría como `PARTIAL` con cantidad ajena).

---

## 2. La medida que lo destapó: el replay multianual vuelve a truncarse

Re-ejecutado el instrumento de `AUTO-MATERIAL-15` sobre el árbol de `v2.88.5-beta`, **antes** del fix
(`operability_runs/replay-oos-ciclo-durable-resello-20260929.json`):

| Métrica | Medido |
| --- | --- |
| Ticks recorridos | **1224/1224** (`2021-12-07 → 2026-09-28`) |
| Fills / ciclos | **140** / **16** (todos de **2022**) |
| Reservas vivas al cierre | **16** |
| Riesgo comprometido final | **`5999.9998` / `6000`** |
| `horizon.completed` | **`true`** ← el pseudo-final: un replay agotado publicado como completo |

Es **la misma huella** que `v2.86` midió con otro nombre (`risk_budget_exceeded` **1400** ⇒ truncación tras
`2022-05-06`): el libro de compromisos no se vaciaba. La diferencia es que ahora el instrumento puede
**nombrar** la causa.

---

## 3. El instrumento: `byDeadTail` era un **cero silencioso**

La primera instrumentación del motivo **no llegaba al artefacto**: el log de retiradas del harness
registraba estado, instrumento e instante… **y no la causa**. El artefacto publicaba `byDeadTail: 0` sobre
**64 retiradas**: «no medí el motivo» leído como «ninguna retirada fue una cola muerta».

Corregido el log (la autoridad es la fila que devuelve el libro), la corrida sellada **mide el mecanismo**:

```
releases: {"total": {"RELEASED_BY_FILL": 174, "RELEASED_BY_CANCEL": 64},
           "byFill": 174, "byCancel": 64, "byDeadTail": 36,
           "reasons": {"fill": 174, "tail_dead": 36, "cancel": 28}}
```

**36 de las 64** retiradas por cancelación son **colas de fill parcial** (`tail_dead`) y **28** son reservas
que **nunca** materializaron (`cancel`). Separarlas no es cosmética: son dos mecanismos distintos y el
síntoma (`RELEASED_BY_CANCEL`) los tapaba a los dos.

---

## 4. El guardarraíl de estancamiento: `completed: true` sobre un libro agotado

Un replay que recorre todos sus ticks **puede** ser dos cosas muy distintas: una corrida completa o una
corrida que **se quedó sin gasolina**. El instrumento solo medía la primera. Se añade una condición
**explícita y doble**:

```python
def declare_stall(*, operable_days_without_activity, live_reservations, reserved_risk, threshold=20):
    if days < max(1, threshold):
        return None
    committed = live_reservations > 0 or risk is None or risk > 0.0   # risk ilegible = fail-CLOSED
    return HORIZON_STALLED_BOOK if committed else None
```

- **Cuándo se declara:** el libro sigue **comprometido** (`live_reservations > 0` **o** riesgo `> 0` **o**
  riesgo **ilegible**, que no se lee como «limpio») **y** pasaron **`STALL_OPERABLE_DAYS = 20`** días
  **operables** sin una sola orden ni fill. El umbral es de **DECLARACIÓN**, no un gate: la corrida **nunca**
  se corta por él, solo deja de publicarse como completa.
- **Cuándo NO:** un libro **limpio** con una temporada sin señales **no** es un estancamiento (el motor
  **eligió** no operar). Ese es el caso de la corrida buena: `36` días operables sin actividad, libro limpio
  ⇒ **no se declara**.
- La aritmética («días operables posteriores al último día con actividad») es una función **pura**
  (`operable_days_without_activity`) con 5 tests: un índice **fuera del censo** **no** se cuenta como
  operable («no se puede afirmar»), y sin actividad **ninguna** se cuenta desde el principio (la ausencia es
  **total**, no «desconocida»).

Efecto medido sobre la **contraprueba A/B** (control sin ciclo durable):

```
horizon: {"completed": false, "ticks": 1224, "totalTicks": 1224, "truncationReason": "stalled_book"}
stall:   {"declared": true, "lastActiveDay": "2022-05-06", "operableDaysWithoutActivity": 266}
```

El guardarraíl **nombra** la fecha que `v2.86` había tenido que descubrir a mano (`2022-05-06`) y convierte
un «completo» falso en una **truncación declarada**.

---

## 5. Tests (`+25` funciones netas)

`packages/py/application/tests/test_replay_oos_durable_cycle.py` — **29 → 45** (**+16**):

```
### motivos de retirada (OBS-18)
  - test_count_release_reasons_separates_dead_tail_from_orphan_cancel
  - test_by_dead_tail_counts_only_the_declared_tail_reason
  - test_tally_releases_tracks_the_reasons_of_the_new_events_only
  - test_release_motives_are_normalized_and_absent_is_not_a_reason
### guardarraíl de estancamiento
  - test_declare_stall_stays_silent_below_the_threshold
  - test_declare_stall_declares_a_committed_book_without_activity
  - test_declare_stall_does_not_confuse_a_quiet_season_with_a_stall
  - test_declare_stall_treats_an_unreadable_risk_as_committed            (parametrizado ×2)
  - test_declare_stall_reason_makes_the_horizon_incomplete
### aritmética del guardarraíl (pura)
  - test_operable_days_without_activity_counts_only_operable_days_after_the_last_one
  - test_operable_days_without_activity_counts_from_the_start_without_any_activity
  - test_operable_days_without_activity_is_zero_when_every_operable_day_had_activity
  - test_operable_days_without_activity_does_not_invent_operability_outside_the_census
  - test_operable_days_without_activity_clamps_hostile_indexes
  - test_operable_days_feeds_declare_stall_end_to_end
```

`apps/api-python/tests/test_auto_v2_durable_cycle.py` — **22 → 26** (**+4**, los cuatro del motor):

```
  - test_never_materialized_reservation_is_retired_even_if_a_sibling_filled
  - test_dead_tail_of_a_partially_filled_reservation_is_cancelled
  - test_a_tail_with_capital_in_flight_is_conserved
  - test_closing_reconcile_retires_a_dead_order_whose_release_was_lost
```

`apps/api-python/tests/test_v2_87_release_log.py` — **NUEVA** (**5**): el contrato del log que impide el
cero silencioso (`reason` en la fila; un chunk **parcial** sigue **vivo** pero con su motivo anotado; una
liberación idempotente **no** entra al log; sin motivo declarado la fila publica vacío, **no** `cancel`).

Corrida conjunta de las cinco suites afectadas (invocación **tipo CI**, con `packages/` y `apps/` a la vez —
el caso que descubrió que un test `async` sin marcador no corre en ese `rootdir`):

```
$ uv run --no-sync python -m pytest \
    packages/py/application/tests/test_replay_oos.py \
    packages/py/application/tests/test_replay_oos_durable_cycle.py \
    apps/api-python/tests/test_v2_87_release_log.py \
    apps/api-python/tests/test_auto_v2_durable_cycle.py \
    apps/api-python/tests/test_replay_oos_cli_renderers.py -q -p no:cacheprovider
97 passed in 1.16s
```

---

## 6. Mutaciones (matriz `256` → `265`)

Nueve direcciones nuevas, todas **medidas** (no «esperadas»): el fragmento existe y el árbol queda
**restaurado byte a byte**.

| Mutación | Ataca | Tests que la cazan |
| --- | --- | --- |
| **`M257` (regla 2 por AGREGADO)** | la decisión por evidencia **de la fila** | **3** (`never_materialized`, `dead_tail`, `dead_order_whose_release_was_lost`) |
| **`M258` (cola muerta conservada)** | la **cola** del fill parcial | **2** (`dead_tail`, `never_materialized`) |
| **`M259` (motivo mudo)** | el **motivo** `tail_dead` | **1** (`dead_tail`) |
| **`M260` (estancamiento mudo)** | el **umbral** del guardarraíl | **4** |
| **`M261` (estancamiento fail-OPEN)** | riesgo **ilegible** ⇒ «limpio» | **1** (`unreadable_risk`) |
| **`M262` (log sin motivo)** | el log del instrumento | **3** (`test_v2_87_release_log.py`) |
| **`M263` (motivo por ESTADO)** | el conteo por **causa** | **4** |
| **`M264` (delta de motivos inflado)** | el delta del **tick** | **1** (`tracks_the_reasons_of_the_new_events_only`) |
| **`M265` (operabilidad inventada)** | el **censo recortado** | **2** |

Las cuatro direcciones del defecto tienen su mutación: **decisión** (`M257`), **cola** (`M258`),
**motivo** (`M259`, `M262`, `M263`, `M264`) y **declaración** (`M260`, `M261`, `M265`). Matriz **COMPLETA**
`265/265` medida en **una sola pasada limpia**, con el árbol **intacto** (`exit 0`); log crudo **versionado**
dentro del sello: [`evidence/v2.88.6/mutation-matrix-265.log`](./evidence/v2.88.6/mutation-matrix-265.log).

**Hazard medido al remedir la matriz (declarado, no ocultado).** Dos sondas de mutación **concurrentes**
sobre el mismo árbol **se abortan mutuamente**: la sonda comprueba, antes de cada mutación, que el fichero
sigue **byte a byte** igual al que leyó al arrancar, y aborta declarándolo si no —lo que ocurre en cuanto
**otra** sonda tiene un mutante aplicado en ese fichero. Medido en esta fase: una sonda **vieja** (de una
sesión anterior, con la salida en `.mutation_matrix_v2886_full.log`) seguía **viva** y su log creció durante
la corrida nueva; la nueva abortó en **`M60`** (`auto_adaptive_confidence.py`) y la vieja en **`M241`**
(`auto_simulation_worker.py`). **Ninguna de las dos** mide la matriz: el aborto es la **protección**
correcta (jamás deja el árbol mutado), pero un log **parcial** no acredita una matriz completa. La cifra
`265/265` de este informe procede de la **re-ejecución en solitario** con el árbol verificado limpio
(`git diff` de `src` = solo los tres ficheros de la fase) y **las dos sondas zombis apagadas**.

---

## 7. Las corridas selladas y la relectura de `v2.87`

### 7.1 Ciclo durable (la corrida del informe)

| Métrica | Sellado |
| --- | --- |
| Ticks | **1224/1224** (`2021-12-07 → 2026-09-28`) |
| Fills / órdenes / decisiones | **752** / **210** / **24480** |
| Ciclos cerrados | **62** (`2022`: 50 · `2023`: 7 · `2024`: 2 · `2025`: 3) |
| R realizado total / medio / mediano | **−18.3660** / **−0.2962** / **−1.0534** |
| Signo positivo | **37.10 %** (23/62) |
| Reservas vivas (máx.) / riesgo final | **0** / **`0.0`** |
| Retiradas | `fill 174` · `cancel 64` (de ellas **`tail_dead` 36**) |
| Horizonte | **`completed: true`**, sin truncación; `stall.declared = false` |
| Tamaño / SHA-256 | `3 390 659` B / **`9AF077A0…F9928E4A`** |
| **Reproducibilidad** | **byte-idéntica** en una segunda corrida independiente (`9AF077A0…` otra vez) |

### 7.2 Contraprueba A/B (control, `--no-durable-cycle`)

| Métrica | Ciclo durable | Control |
| --- | --- | --- |
| Órdenes | **210** | 31 |
| Fills | **752** | 118 |
| Ciclos cerrados | **62** | 13 (solo 2022) |
| Reservas vivas (máx.) | **0** | **15** |
| Riesgo comprometido final | **`0.0`** | **`5999.9998`** |
| Retiradas | `fill 174` / `cancel 64` (**36 `tail_dead`**) | `fill 29` / `cancel 0` |
| Días con fills | **141** | 16 |
| `risk_budget_exceeded` | **11** | **1400** |
| Horizonte | `1224/1224 · completed=true` | `1224/1224 · **completed=false · stalled_book**` |
| R por año | 2022/2023/2024/2025 | solo 2022 |

Lectura: con el ciclo durable el libro **no gotea** (pico 0, final 0) y el motor opera las **4 temporadas**;
sin él, 15 reservas huérfanas comprometen **todo** el presupuesto y el guardarraíl **declara** el
estancamiento (`2022-05-06`, 266 días operables sin actividad).

**Reproducibilidad del control (declarada, no asumida):** una segunda corrida reproduce **todas** las
mediciones, pero su SHA-256 **difiere** en **23** rutas, **todas** dentro de `replay.finalBook`
(`liveReservations[*].reservationId` / `ownedReservationIds[*]`): son los identificadores `exit:<ULID>` de las
**15 reservas que sobreviven**, y un ULID lleva el **reloj de pared**. El control **no** es byte-reproducible
por construcción; sus cifras **sí**. La corrida durable, que cierra con el libro **limpio**, **no** tiene
esas rutas y es **byte-idéntica**.

### 7.3 Relectura de `v2.87` (evidencia antigua)

El artefacto de `v2.87` quedó marcado **NO reproducible con el código sellado** (`v2.88.1-beta` cambió la
costura) y **exigía re-ejecución**. Con el motor corregido:

| | `v2.87` (artefacto antiguo) | **Sellado `v2.88.6`** |
| --- | --- | --- |
| `byFill` / `byCancel` | 237 / **1** | 174 / **64** (**36 `tail_dead`**) |
| Ciclos / R total | 62 / −18.3660 | **62 / −18.3660** |
| Reservas vivas (máx.) / riesgo final | 1 / 0.0 | **0 / 0.0** |
| Horizonte | `completed=true` | `completed=true` |
| Reproducible byte a byte | **no** | **sí** |

El **puntaje no se mueve** (mismos 62 ciclos, mismo R): lo que cambia es la **contabilidad del libro**, que
en `v2.87` sobre-liberaba (`237` fills liberados sobre `174` reales, por la costura anterior a la guarda de
`v2.88.1`). La cifra antigua **no debe citarse**; la de este sello **sí**, y su hash es **verificable**.

---

## 8. Compuertas

```
$ uv run ruff check packages/py apps/api-python --config pyproject.toml
All checks passed!
```

**La compuerta se MIDIÓ sobre el árbol final, y la verificación de cierre encontró deriva (declarado).** Al
repetirla antes de sellar aparecieron **5 `I001`** (bloques de import desordenados: el `bolsa_api` de
`auto_simulation_worker.py` y de `v2_87_replay_oos_durable_cycle.py` colocado *después* de
`bolsa_application`, y dos ficheros de test sin la línea en blanco de rigor) y **9
colapsos de formato** (multilínea → una línea) **ajenos al cambio semántico**, en
`auto_simulation_worker.py` y `portfolio_reservation.py`. Los `I001` habrían tumbado el step `Ruff` del job
`python` del tag. **Corregido**: `ruff check --fix` para los imports y **reversión** de los 9 colapsos, que
dejan el diff de motor en **`+47 / −8`** (antes `+63 / −38`) y el de `portfolio_reservation.py` en **`+5 / −0`**
(solo la constante, su docstring y `__all__`). **Por qué importa (medido):** uno de esos colapsos
**desarmaba silenciosamente una mutación** — `M116` anclaba el `bool(...)` multilínea y la sonda lo declaró
«fragmento ausente» ⇒ **la matriz no puede afirmar cobertura sobre un fragmento que ya no existe**. Con el
formato revertido, `M116` vuelve a **morder** (`1` test) y **`M241`**, cuya ancla era la condición
*antigua* de la regla 2 (`and filled == 0.0`, justamente lo que `OBS-18` elimina), se **re-ancló a la
condición vigente sin cambiar su semántica** ⇒ **`13`** tests rojos. La lección es la de la casa: **una
mutación que no encuentra su fragmento no mide nada, y un formateo ajeno al cambio la desarma en silencio.**

Batería offline con el **comando EXACTO** del job `Pytest offline` (**116 argumentos**, tras el cableado
de abajo): medida local **`1 failed, 3139 passed`** (**3140 recogidos**). El **único** rojo es
`apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it`,
que **exige PostgreSQL** y que el job offline **skippea**; es el mismo rojo local que en `v2.88.5`
(`logs/dev/battery-v2.88.5.txt`: `1 failed, 3085 passed`). De ahí la identidad que fija el esperado —
**`recogidos local − 37 skips`** — que cuadró con los runs reales de `v2.88.4` (`3079 − 37 = 3042`) y
`v2.88.5` (`3086 − 37 = 3049`):

| | recogidos local | skips CI | **esperado job `python`** |
| --- | --- | --- | --- |
| `v2.88.4` (observado) | `3079` | `37` | `3042 passed, 37 skipped` |
| `v2.88.5` (observado) | `3086` | `37` | `3049 passed, 37 skipped` |
| **`v2.88.6`** | **`3140`** | `37` | **`3103 passed, 37 skipped`** |

Los `37` skips son los mismos de siempre (tests PG que el job no corre por diseño). El salto de `3049` a
`3103` es **`+54`** = **`+9`** (los tests nuevos de los dos ficheros que ya estaban en la lista, `+4` del
motor y `+5` del log) **`+ 45`** (el fichero del instrumento que se cablea aquí — ver el hueco medido
abajo, del que **16** son nuevos de esta fase y **29** eran del instrumento de `v2.87`).

**HUECO DE COBERTURA DE CI: medido y cerrado (y por eso el esperado NO es `3074`).** La primera medida de
esta batería dio `1 failed, 3094 passed` ⇒ delta **`+9`** contra `v2.88.5`, cuando la fase añade **`+25`**
funciones de test. Causa medida: `packages/py/application/tests/test_replay_oos_durable_cycle.py`
(**`45` tests, herméticos** — memoria, sin PG ni red, **`0.33 s`**) **no estaba en la lista de NINGÚN
workflow**. `git log -S` lo confirma: el fichero se creó en el sello `v2.88` (`564240d2`) y nunca se añadió,
porque `packages/py/application/tests` se lista **fichero a fichero** (los PG-gated obligan) y éste se quedó
fuera. Consecuencia real: **los 16 tests que protegen la regla 2 por evidencia, la cola muerta y el
guardarraíl NUNCA habrían corrido en el job del tag** (ni los 29 del instrumento de `v2.87`). Se **cablea**
en `release-tag-ci.yml` (`115 → 116` argumentos) y en `python-ci.yml`, con la nota de procedencia en ambos
(patrón «HUECO DECLARADO» de `v2.76`), y se **re-mide**: `3094 → 3139 passed` = `+45`, exactamente el
tamaño del fichero. **Riesgo medido del cableado: nulo en coste (`0.33 s`) y nulo en hermetismo (los 45
pasan en local, sin PG).**

---

## 9. Límites declarados

- **SÍ se toca el motor**: la regla 2 de `_v2_reconcile_reservations` es lógica de producción.
- **Nuevo motivo en el contrato** (`RELEASE_REASON_DEAD_TAIL = "tail_dead"`): una fila con ese motivo es
  **nueva información** para cualquier consumidor del libro; `count_release_reasons` la separa de `cancel`
  por eso mismo.
- **El guardarraíl NO cierra la truncación**: la **declara**. Un replay estancado sigue siendo un replay
  estancado; lo que se elimina es la opción de presentarlo como completo.
- **SÍ se tocan 2 workflows** (`release-tag-ci.yml`, `python-ci.yml`): es el cierre del hueco medido — el
  test del instrumento (45 tests herméticos, 16 de ellos nuevos) **nunca había corrido en CI**. Sin ese
  cableado el job del tag habría dado `3058`; con él da **`3103`**. No altera el motor, el instrumento ni
  el artefacto: solo **qué batería** lo juzga. Queda **abierta** la deriva estructural de las dos listas
  (ver `OBS-19` en la deuda).
- **El control no es byte-reproducible** (IDs con reloj de pared), y se declara en vez de esconderse.
- **NO** acredita `P3-2`/`P3-3`: el replay usa **reloj simulado**, una sola cuenta/versión/watch y
  `pairActive=false`. La muestra es **multianual** (62 ciclos, 4 temporadas) pero sigue siendo **un**
  instrumento.
- **NO** cierra `OBS-15` (techo de 1000 `APPLIED`), `OBS-16` ni la deuda de datos.
- El replay **no** escribe en PostgreSQL (cuarentena en memoria, por construcción).

---

## 10. CI del tag (POST-TAG por construcción)

`Release tag CI` solo corre **al empujar**, así que su cita **no puede** vivir dentro del tag: la instancia
dentro del tag declara lo **esperado** (`3103 passed, 37 skipped`, matriz `265/265`) y la cita **real** se
añade después, sobre el objeto empujado. **Se cita el run, no se hereda.**

---

## 11. Evidencia y registros

- Evidencia cruda y verificable: [`evidence/v2.88.6/README.md`](./evidence/v2.88.6/README.md).
- Relectura del artefacto antiguo (nota POSTERIOR):
  [`evidence/v2.87/README.md`](./evidence/v2.87/README.md).
- Deuda: [`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
  (`OBS-18` **cerrada**; `OBS-19` **abierta**: la deriva entre las dos listas offline de pytest).
- Listas de CI tocadas (cierre del hueco medido): `.github/workflows/release-tag-ci.yml` (job `python`,
  step `Pytest offline`: `115 → 116` argumentos) y `.github/workflows/python-ci.yml` (job `quality`, step
  `Pytest`), con la nota de procedencia en ambos.
- Índice: [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) ·
  Estado: [`PROJECT_STATE.md`](./PROJECT_STATE.md) · [`CHANGELOG.md`](../../CHANGELOG.md).
- Artefactos (gitignoreados, `.gitignore:102` → `/operability_runs/`):
  `replay-oos-durable-obs18-fix-20260929.json`, `...-control.json`, `...-fix-repro.json`,
  `...-fix-control-repro.json`.
- Matriz completa cruda (una sola pasada limpia, `265/265`, árbol intacto, `exit 0`):
  [`evidence/v2.88.6/mutation-matrix-265.log`](./evidence/v2.88.6/mutation-matrix-265.log).
