# `OBS-20` — La retirada declara el motivo con la materialización EXACTA del CICLO (`v2.88.7-beta`, `AUTO-MATERIAL-20`, 2026-09-29)

> **Tipo de entrega:** cambio de **motor** (evidencia del motivo en la regla 2 de la reconciliación) + **2
> funciones de test** (+1 motor hermético, +1 mutación neta ×2: `M266`/`M267`) + re-anclaje de **2 suites PG**
> a la semántica de `OBS-18` + informe + evidencia + registros.
> **Objeto:** tag anotado **`v2.88.7-beta`** · **Versión:** `2.11.6-beta` → **`2.11.7-beta`** ·
> **Alembic head:** `046_fill_reference_mid` (**sin migración**) · **Base del diff:** `032ae7cc`
> (= `v2.88.6-beta`).
> **Origen:** el `Release tag CI` del sello `v2.88.6-beta` salió **ROJO** (`36603391512`) y, al reproducir el
> fallo en local, la suite de concurrencia mostró una **carrera medida** (~**1 de cada 9** corridas) que
> declaraba **`cancel`** —«nunca materializó»— sobre una reserva que **SÍ** había materializado: el ledger
> tenía su fill en `APPLIED` y la fila de la reserva seguía en `released_qty == 0`.

---

## 0. Qué es y qué NO es esta entrega

**Es** el cierre de **`OBS-20`**, con **dos** defectos **medidos** y **distintos**, que el sello anterior dejó
abiertos:

1. **Motor (proveniencia de la retirada):** la decisión de `OBS-18` se toma con la **evidencia de la fila**
   (`released_qty`), pero esa evidencia la escribe **otra sesión** (la que liquida el fill). Si esa sesión
   **no tiene la reserva en su libro**, la liberación **nunca ocurre**: la fila queda en `0` con el fill **ya
   aplicado** en el ledger y el cierre declara **`cancel`** sobre una reserva que **sí** materializó.
2. **CI (el sello `v2.88.6` no era certificable):** el commit sellado (`032ae7cc`) llevaba todavía la
   aserción **antigua** de `test_crash_recovery_day_process_pg.py` (esperaba una **cola viva** al morir el
   proceso), incompatible con el motor de `OBS-18` (que **retira** la cola muerta al cerrar el turno). El
   `Release tag CI` lo midió: **`lifecycle-pg` → `Pytest Crash/Recovery Day` ROJO** con
   `reservas vivas: []`.

**NO es** un cambio de comportamiento de trading: no se toca `TOP_N`, `REGIME`, `RISK`, `SIGNALS`, `A/B`,
ningún umbral, ni el fallback, ni se backdatea nada. **NO** cierra `OBS-15` (techo de 1000 `APPLIED`),
`OBS-16` ni la deuda de datos. **NO** cierra `OBS-19` (la deriva entre las dos listas offline de pytest),
que sigue **abierta**.

---

## 1. El rojo del sello `v2.88.6-beta`: la suite aún exigía una cola VIVA

Cita cruda del run ([`evidencia-ci-tag-v2.88.6-2026-09-29.txt`](./evidencia-ci-tag-v2.88.6-2026-09-29.txt)):

```
job  lifecycle-pg (Alembic + auth + golden restart)   → failure
step Pytest Crash/Recovery Day (proceso scheduler matado en sucio + PG, fail if skipped)
  E  AssertionError: la muerte debe ocurrir con el fill PARCIAL durable (cola de reserva viva);
     reservas vivas: []
  1 failed in 122.20s (0:02:02)
steps Fail on skipped Concurrent AUTO / HardKill recovery / crash injection matrix / multiprocess  → failure
job  certify (aggregate + artifact)  → failure   ("Release tag CI not GREEN", lifecycle-pg=failure)
```

**Lectura.** El `OBS-18` sellado **retira** la cola muerta al cerrar el turno (`tail_dead`,
`remaining_qty = 0`), así que el hecho durable que el test debía exigir **no** era una cola viva sino la
**evidencia de su retirada**. El árbol de trabajo ya llevaba el re-anclaje (no commiteado en `032ae7cc`):
esta entrega lo **sella**, junto con el arreglo de motor que la propia suite PG destapó al repetirse.

**Los 5 pasos «no skip silencioso» y `certify`** fallan **en cascada**: no son defectos propios, son la
consecuencia de abortar el job en el primer paso rojo (el diseño anti-skip silencioso de `v2.76`).

---

## 2. El defecto de motor (`OBS-20`): quién escribe la evidencia y quién la lee

### 2.1 La ventana medida

`OBS-18` dejó la decisión así:

```python
materialized = float(reservation.released_qty or 0.0)   # evidencia DE LA FILA
...
reason=(RELEASE_REASON_DEAD_TAIL if materialized > 0.0 else RELEASE_REASON_CANCEL)
```

Esa lectura es correcta **si la fila ya registró su fill**. Pero la liberación de lo materializado la ejecuta
el **camino caliente de la sesión que LIQUIDA** el fill (`attribute_fills=True` →
`_v2_release_reservations_for_fill`), y esa operación solo actúa sobre las reservas que esa sesión tiene
**en su libro**. Si la sesión que liquida **no tiene la reserva** (libro de otra sesión, o el barrido de
arranque de un proceso que nace sin memoria), entonces:

| Instante | Ledger (`execution_events`) | Fila (`portfolio_reservations`) |
| --- | --- | --- |
| fill liquidado | **`APPLIED`** | `released_qty = 0` ← **la liberación no ocurrió** |
| cierre de turno de OTRA sesión | `APPLIED` (contradice) | `released_qty = 0` ⇒ **`cancel`** |

Resultado: una retirada que declara **«nunca materializó»** sobre una reserva cuyo fill **sí** está en el
ledger. `OBS-18` lo hizo **visible** (antes el agregado `filled == 0.0` la escondía, ver §1 del informe de
`OBS-18`) pero no lo cerró: con el agregado, la rama **no se ejecutaba**; con la evidencia de la fila,
**se ejecuta y miente**.

Síntoma medido en la suite de concurrencia (`test_concurrent_auto_pg.py[5]`, **~1 de cada 9** corridas):

```
assert 'cancel' == 'tail_dead'
       + cancel
       - tail_dead
```

### 2.2 La corrección: la identidad EXACTA del ciclo, sin heurísticas

`cycle_id` (V2.47) **ya viaja** en las dos partes y **ya está persistido** (migración `042`/`047`): el
**contexto financiero del fill** (`sim_fill_finance_contexts.cycle_id`) y la **reserva**
(`portfolio_reservations.cycle_id`). Es, por tanto, la identidad que ata un fill aplicado a **su** reserva
**sin migración y sin heurísticas**:

```python
# APPLIED_FILLS_READ (applied_fills.py) — el ciclo viaja del contexto al hecho aplicado
cycle_id=getattr(context, "cycle_id", None),

# WORKER (_v2_reconcile_reservations) — materialización EXACTA del ciclo
cycle_fills: dict[tuple[str, str], float] = {}
for fact in facts_read.facts:
    cycle = str(getattr(fact, "cycle_id", None) or "").strip()
    if not cycle:
        continue
    key = (cycle, fact.side)
    cycle_fills[key] = cycle_fills.get(key, 0.0) + float(fact.quantity)
...
cycle = str(getattr(reservation, "cycle_id", None) or "").strip()
if cycle:
    linked = cycle_fills.get((cycle, reservation.side), 0.0)
    if linked > 0.0:
        committed = float(reservation.quantity or 0.0)
        materialized = max(materialized, min(linked, committed) if committed > 0.0 else linked)
```

Propiedades del arreglo, todas **declaradas**:

- **Acotado por LADO** (`(cycle, side)`): un ciclo tiene las **dos** patas (entrada `BUY` y salida `SELL`); la
  pata de compra de un ciclo **no** puede atribuirse a su reserva de venta.
- **Instrumento+lado NO es identidad** y **no** se usa ni para el motivo: dos órdenes del mismo instrumento y
  lado son **ciclos distintos** — es exactamente el defecto que `OBS-18` corrigió y **no** se reintroduce.
- **Lo registrado en la fila nunca se rebaja**: la evidencia del ciclo **completa** (`max`), no sustituye.
- **Cota por lo COMPROMETIDO**: `min(linked, quantity)`; la evidencia no puede declarar más de lo que esa
  reserva se comprometió a consumir.
- **`None` = no declara ciclo** (fila anterior a `2.47` o lectura sin contexto): **no** se afirma vínculo, y
  el comportamiento es el de `OBS-18` (la fila decide).
- **Fail-closed intacto**: la guardia de `in_flight` **manda** (traza sin aplicar ⇒ la orden sigue
  trabajando), con lectura incompleta (`measurable=False`) o sin fecha legible **no se libera nada**, y la
  liberación **nunca** supera la cantidad viva.
- **`AppliedFillFact.cycle_id` NO se publica en `to_dict()`**: es evidencia **interna** de reconciliación; el
  contrato serializado de los libros **no cambia**.

---

## 3. La medida que lo separa de «un fallo de test»: 4 retiradas del replay multianual

Re-ejecutado el instrumento de `AUTO-MATERIAL-15` con el motor corregido (ciclo durable, `1225/1225` ticks,
`2021-12-07 → 2026-09-29`), el artefacto **cambia exactamente en los motivos**, y solo ahí:

| Motivo | Sellado `v2.88.6` | **Sellado `v2.88.7`** |
| --- | --- | --- |
| `fill` | **174** | **174** |
| `tail_dead` | **36** | **40** |
| `cancel` | **28** | **24** |

Y el cambio está **localizado** en **4 días, una retirada cada uno** (medido comparando `book.perDay`
campo a campo; **ningún otro día cambia**):

| Día | `(tail_dead, cancel, fill)` `v2.88.6` | `v2.88.7` |
| --- | --- | --- |
| `2022-03-14` | `(0, 1, 1)` | `(1, 0, 1)` |
| `2022-03-16` | `(1, 1, 2)` | `(2, 0, 2)` |
| `2022-06-09` | `(0, 1, 0)` | `(1, 0, 0)` |
| `2022-06-13` | `(0, 1, 2)` | `(1, 0, 2)` |

Lectura: **4** de las **64** cancelaciones del ciclo durable eran **proveniencia falsa** (`cancel` sobre
reservas cuyo fill **estaba** en el ledger). El **puntaje no se mueve** (mismos **62** ciclos, mismo
`R` total **−18.3660**): lo que cambia es **qué declara el libro**, no lo que el motor opera.

**Libro limpio y reproducible (la medición se conserva):** `liveMax **0**`,
`finalReservedRisk **0.0**`, `finalReservedCash **0.0**`, `stall.declared = false` (**36** días operables sin
actividad, umbral `20`), `cancelReleaseDays 57`; artefacto de **`3 393 187` B** con SHA-256
**`7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461`**, **byte-idéntico** en dos corridas
independientes.

> **Nota de comparabilidad (declarada).** El censo del `v2.88.6` terminaba en `2026-09-28` (`1224` ticks) y
> éste en `2026-09-29` (`1225`): el día nuevo **no** añade fills ni retiradas (mismos `752`/`210`/`238`), así
> que las **cuatro** reatribuciones medidas son del motor, no del calendario.

---

## 4. El re-anclaje de las suites PG a la semántica de `OBS-18`

### 4.1 `test_concurrent_auto_pg.py` (3 casos, `[2]`/`[3]`/`[5]`)

| | Sello `v2.88.6` (antiguo) | **`v2.88.7`** |
| --- | --- | --- |
| Contabilidad | `released == held`, `remaining == requested − held` | **`released == requested`**, **`remaining == 0`** |
| Escenario | `remaining > 0` (exige cola viva) | `0 < aplicado < pedido` y **`applied == held`** |
| Motivo | no se miraba | **`tail_dead`** y estado **≠ `OPEN`** |
| Capital | `Σ reserved_cash` vivo ≤ tope de **una** reserva | **`retained == 0.0`** |
| Riesgo | — | **`reserved_risk > 0`** (denominador de `R`, asimetría deliberada del store) |

### 4.2 `test_crash_recovery_day_process_pg.py` (1 caso, proceso real + muerte sucia)

- **Fase 1** espera el hecho durable **nuevo**: posición materializada **y** fila con
  `release_reason == 'tail_dead'` (`status = RELEASED_BY_CANCEL`, `remaining_qty == 0`,
  `released_qty > 0`) **sin cola viva** del instrumento; y lo comprueba explícitamente
  (`_retired_dead_tails`, `_live_tail`).
- **Fase 2 (reinicio)** añade la **idempotencia de la retirada**: el conjunto de colas retiradas **no
  cambia** (`antes == después`), `released_qty` **no** se re-libera y el motivo **sigue** siendo
  `tail_dead` (el reinicio **no** resucita ni duplica).

---

## 5. Tests y mutaciones

`apps/api-python/tests/test_auto_v2_durable_cycle.py` — **26 → 27** (**+1**, el motor):

```
  - test_a_cancel_is_never_declared_while_an_applied_fill_waits_in_the_ledger
```

Es la **reproducción hermética de la carrera**: fill **ya** `APPLIED` (por eso la guardia de `in_flight` no
lo ve en vuelo) y fila **todavía** en `released_qty = 0`. El test **no** prescribe la forma del arreglo —
acepta **conservar** la reserva (fail-closed) **o** retirarla declarando **`tail_dead`**— y **solo** prohíbe
una cosa: **`cancel`**. Las **cuatro** funciones de `OBS-18` conservan sus dientes: la fixture de hermanas
declara ahora **un ciclo por reserva** (`cyc-…`), como el motor real, y el fill se ata al ciclo de la
**nueva** (la que el camino caliente acredita).

**Mutaciones (matriz `265` → `267`):** dos direcciones nuevas, **ambas muerden** y el árbol queda
**intacto**:

| Mutación | Ataca | Test que la caza |
| --- | --- | --- |
| **`M266` (atribución por ciclo MUDA)** | que el reconciliador **complete** la evidencia con el fill de **su** ciclo | `test_a_cancel_is_never_declared_while_an_applied_fill_waits_in_the_ledger` |
| **`M267` (ciclo no viaja)** | que la lectura del libro **propague** el ciclo del contexto financiero | `test_a_cancel_is_never_declared_while_an_applied_fill_waits_in_the_ledger` |

**A/B de la mutación (medido, la prueba de que el test tiene dientes).** Con la evidencia del ciclo
**apagada** (`M266`), la reproducción hermética falla **con la firma exacta de la suite PG**:

```
E  AssertionError: la fila tiene un fill aplicado en el ledger: la retirada no puede declarar
   'cancel' (motivo='cancel', released=10.0)
E  assert 'cancel' == 'tail_dead'
```

…mientras `test_never_materialized_reservation_is_retired_even_if_a_sibling_filled` **sigue verde**: el
arreglo de `OBS-20` **no** desarma el de `OBS-18` (la hermana que nunca materializó se retira con
**`cancel`**, que es lo correcto).

Corrida conjunta de las cinco suites del motor y del instrumento (**98** tests, era `97`):

```
$ python -m pytest apps/api-python/tests/test_auto_v2_durable_cycle.py \
    packages/py/application/tests/test_replay_oos.py \
    packages/py/application/tests/test_replay_oos_durable_cycle.py \
    apps/api-python/tests/test_v2_87_release_log.py \
    apps/api-python/tests/test_replay_oos_cli_renderers.py -q -p no:randomly
98 passed in 1.03s
```

---

## 6. Compuertas

```
$ python -m ruff check packages/py apps/api-python --config pyproject.toml
All checks passed!
```

**Batería offline con el comando EXACTO del job `python` del tag** (**`121` tokens: `81` rutas + `39`
`--ignore` + `-q`, extraídos de `release-tag-ci.yml` → `Pytest offline`):
`1 failed, 3140 passed` (**3141** recogidos). El **único** rojo es
`apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py::test_the_validation_reads_real_postgres_material_and_seals_it`
(**`assert 17 == 26`**), que **exige PostgreSQL** y que el job offline **skippea**: es el mismo rojo local
que en `v2.88.5`/`v2.88.6` (`local − 37 skips`). Identidad que fija el esperado:

| | recogidos local | skips CI | **esperado job `python`** |
| --- | --- | --- | --- |
| `v2.88.6` (esperado, no observado: el tag salió ROJO) | `3140` | `37` | `3103 passed, 37 skipped` |
| **`v2.88.7`** | **`3141`** | `37` | **`3104 passed, 37 skipped`** |

**Suites PG (locales, PG real en `127.0.0.1:5432`)** — todas **verdes**:

| Suite | Resultado |
| --- | --- |
| `test_golden_day_v2_process_pg.py` | `1 passed` |
| `test_crash_recovery_day_process_pg.py` | `1 passed` (**el que salió rojo en el tag de `v2.88.6`**) |
| `test_concurrent_auto_pg.py` | `3 passed` × **12** corridas seguidas (**12/12**; antes ~**1/9** roja) |
| `test_auto_v46_hardkill_recovery_pg.py` | `2 passed` |
| `test_auto_v46_crash_injection_pg.py` | `2 passed` |
| `test_auto_v46_multiprocess_pg.py` | `1 passed` (`113.46 s`) |

---

## 7. Límites declarados

- **SÍ se toca el motor**: es la evidencia con la que la regla 2 declara el **motivo** de una retirada (y con
  la que alimenta el `outcome` del `INTENT`), no un cambio de política de trading.
- **`cycle_id` es la identidad**, y solo existe desde `2.47`: un fill **sin** ciclo (`None`) **no** aporta
  vínculo y la decisión vuelve a ser la de `OBS-18` (la fila). No se heurística **nunca** por
  instrumento+lado — sería reintroducir el defecto de `OBS-18`.
- **El alcance del arreglo es demostrable en el replay**: **4** de **64** cancelaciones multianuales eran
  proveniencia falsa; el resto de las cifras (fills, órdenes, ciclos, `R`) **no** se mueve.
- **NO** acredita `P3-2`/`P3-3`: el replay sigue usando **reloj simulado** (una cuenta/versión/watch,
  `pairActive=false`) y **no** sustituye la ventana PAPER real.
- **NO** cierra `OBS-15` (techo de **1000 `APPLIED`**), `OBS-16` ni la deuda de datos; **NO** cierra
  **`OBS-19`** (la deriva entre las dos listas offline de pytest, que sigue **abierta**).
- El **re-anclaje** de las suites cambia **qué** se exige al motor (`tail_dead` durable en vez de cola viva),
  no la cobertura: las suites **no** se relajaron — se les añadió la comprobación del **motivo**, la
  **ausencia de cola viva**, el **capital retenido `0`** y la **idempotencia** del reinicio.
- El **tag `v2.88.6-beta` NO se borra**: queda como **rojo citado** (precedente de `v2.88`/`v2.88.1`) y esta
  entrega **cita su run** en vez de heredarlo.

---

## 8. CI del tag (POST-TAG por construcción)

`Release tag CI` solo corre **al empujar**, así que su cita **no puede** vivir dentro del tag: la instancia
dentro del tag declara lo **esperado** (`3104 passed, 37 skipped`, matriz `267/267`) y la cita **real** se
añade después, sobre el objeto empujado. **Se cita el run, no se hereda.**

---

## 9. Evidencia y registros

- Evidencia cruda y verificable: [`evidence/v2.88.7/README.md`](./evidence/v2.88.7/README.md).
- Cita del rojo que motiva esta entrega:
  [`evidencia-ci-tag-v2.88.6-2026-09-29.txt`](./evidencia-ci-tag-v2.88.6-2026-09-29.txt) (run `36603391512`).
- Deuda: [`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
  (`OBS-20` **cerrada**; `OBS-19` **abierta**).
- Índice: [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) ·
  Estado: [`PROJECT_STATE.md`](./PROJECT_STATE.md) · [`CHANGELOG.md`](../../CHANGELOG.md).
- Matriz completa cruda (una sola pasada limpia, `267/267`, árbol intacto, `exit 0`):
  [`evidence/v2.88.7/mutation-matrix-267.log`](./evidence/v2.88.7/mutation-matrix-267.log).
- Artefactos (gitignoreados, `.gitignore:102` → `/operability_runs/`):
  `replay-oos-durable-obs20-fix-20260929.json`, `...-fix-repro-20260929.json`.
