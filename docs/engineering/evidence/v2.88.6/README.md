# Evidencia cruda — reconciliación por EVIDENCIA DE LA RESERVA + guardarraíl de estancamiento (`v2.88.6`, `AUTO-MATERIAL-19`, 2026-09-29)

Resumen **verificable** del cierre de `OBS-18`. Las cifras están **transcritas** de las corridas, sin
edición; los artefactos completos son **gitignoreados** (`.gitignore:102` → `/operability_runs/`) y se
regeneran con los comandos de §6.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-19` (`v2.88.6`) — `OBS-18`: regla 2 por evidencia de la reserva + motivo declarado + guardarraíl de estancamiento |
| Versión de paquete | `2.11.5-beta` → **`2.11.6-beta`** |
| Tag (lo crea el propietario) | **`v2.88.6-beta`** (anotado) |
| Base del diff | **`27264aab`** (= `v2.88.5-beta` + cita POST-TAG de su CI) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Contenido del sello | motor (regla 2) + instrumento (motivo + guardarraíl) + 25 funciones de test + 9 mutaciones (`M257`–`M265`) + informe + evidencia + registros |

## 1. El defecto (por qué se re-ejecutó el instrumento)

El replay OOS multianual de `AUTO-MATERIAL-15` (`v2.87`) quedó marcado **NO reproducible con el código
sellado** y **exigía re-ejecución**. Al re-ejecutarlo sobre `v2.88.5-beta` **antes** del fix:

```
ticks 1224/1224 · endDay 2026-09-28 · fills 140 · ciclos 16 (solo 2022)
book  liveMax 16 · finalReservedRisk 5999.9998
horizon {"completed": true, "truncationReason": null}      ← pseudo-final
```

Causa medida (**motor**, regla 2 de `_v2_reconcile_reservations`): la retirada se decidía por el **agregado
de fills del instrumento+lado** (`filled == 0.0`), no por la evidencia de la fila (`released_qty`). Una
reserva que **nunca** materializó sobrevivía mientras una hermana suya llenara, y la **cola** de un fill
parcial no la retiraba **nadie**.

## 2. La corrección (motor)

```python
materialized = float(reservation.released_qty or 0.0)
if attribute_fills and fill_qty > 0:
    ...                                       # regla 1: libera lo MATERIALIZADO
elif measurable and created is not None and instrument not in (in_flight or frozenset()):
    released = await self._v2_release_reservation(
        reservation,
        status=RESERVATION_RELEASED_BY_RESTART if startup else RESERVATION_RELEASED_BY_CANCEL,
        reason=(RELEASE_REASON_RESTART if startup
                else (RELEASE_REASON_DEAD_TAIL if materialized > 0.0 else RELEASE_REASON_CANCEL)),
        released_qty=None,
    )
    fill_qty = materialized                  # el outcome declara la EVIDENCIA DE LA RESERVA
```

Nuevo motivo en el contrato: `portfolio_reservation.RELEASE_REASON_DEAD_TAIL = "tail_dead"`.

## 3. La corrección (instrumento)

1. **El motivo llega al artefacto.** El log de retiradas del harness registra ahora `reason` y
   `releasedQty` (la autoridad es la fila que devuelve el libro). Sin él, `byDeadTail` era un **cero
   silencioso**: `0` sobre **64** retiradas.
2. **Guardarraíl de estancamiento.** `declare_stall(...)` declara `truncationReason = "stalled_book"` si el
   libro conserva capital comprometido (`live_reservations > 0` o riesgo `> 0` o riesgo **ilegible**) y
   pasaron **`STALL_OPERABLE_DAYS = 20`** días **operables** sin una sola orden ni fill. Su aritmética es
   pura (`operable_days_without_activity`): un índice **fuera del censo** no cuenta como operable, y sin
   actividad **ninguna** se cuenta desde el principio.
3. **El artefacto lo publica:** `replay.book.stall` (`declared`, `thresholdOperableDays`,
   `operableDaysWithoutActivity`, `lastActiveDay`) y `replay.releases.reasons` / `byDeadTail`.

## 4. Corrida sellada — ciclo durable

| | |
| --- | --- |
| Fichero | `operability_runs/replay-oos-durable-obs18-fix-20260929.json` |
| Tamaño | `3 390 659` B |
| SHA-256 | **`9AF077A0B4A4F59F88FB4B50E5E2C1A34B103D7386F6F7CEC2C29534F9928E4A`** |
| Reproducibilidad | **byte-idéntica** en una segunda corrida independiente (`...-fix-repro.json`, mismo SHA-256) |

```
startDay            2021-12-07
endDay              2026-09-28
ticks               1224        (completed=true, truncationReason=null)
totals              {"decided": 24480, "proposals": 238, "orders": 210, "fills": 752, "vetoes": 24283}
daysWithFills       141
regimeCounts        {"BEAR_TREND": 906, "HIGH_VOLATILITY": 310, "SIDEWAYS": 8}
journalReasons      {"approved": 86, "concentration_exceeded": 33, "regime_invalid": 878,
                     "risk_budget_exceeded": 11, "risk_measurement_partial": 227, "top_n_excluded": 292}
```

**Libro de compromisos** (la medición que cierra `OBS-18`):

```
liveMax               0            finalReservedRisk 0.0        finalReservedCash 0.0
partialDays           0            measuredUnknownDays []
cancelReleaseDays     57
releases            {"total": {"RELEASED_BY_FILL": 174, "RELEASED_BY_CANCEL": 64},
                     "byFill": 174, "byCancel": 64, "byDeadTail": 36,
                     "reasons": {"fill": 174, "tail_dead": 36, "cancel": 28}}
stall               {"declared": false, "thresholdOperableDays": 20,
                     "operableDaysWithoutActivity": 36, "lastActiveDay": "2026-01-27"}
retention           {"appliedRetention": 900, "appliedPeak": 752, "appliedArchived": 0,
                     "engineReadLimit": 1000}
finalBook           {"liveReservations": 0, "inFlight": 0, "unappliedRows": 0,
                     "unappliedMeasurement": "COMPLETE", "ownedReservationIds": 0}
```

**36 de las 64** cancelaciones son **colas de fill parcial** (`tail_dead`) y **28** reservas que **nunca**
materializaron (`cancel`). El libro **no gotea**: pico **0**.

**Puntuación** (`replay.score`; la unidad es el **ciclo**, los fills parciales se agregan por símbolo):

```
realizedCount       62            realizedRTotal  -18.365980744109294
meanR               -0.296225…    medianR         -1.053446…
positiveShare        0.370967…    (23/62)          unmeasuredCount 0

byYear  2022: {"count": 50, "meanR": -0.504255…, "positiveShare": 0.3000}
        2023: {"count":  7, "meanR":  0.227441…, "positiveShare": 0.5714}
        2024: {"count":  2, "meanR":  1.876265…, "positiveShare": 1.0000}
        2025: {"count":  3, "meanR":  0.500718…, "positiveShare": 0.6667}
```

**Muestra MULTIANUAL** (4 temporadas). `stall.declared = false` con **36** días operables sin actividad: el
libro está **limpio**, así que el motor **eligió** no operar — exactamente el caso que el guardarraíl **no**
debe declarar.

## 5. Corrida sellada — contraprueba A/B (`--no-durable-cycle`)

| | |
| --- | --- |
| Fichero | `operability_runs/replay-oos-durable-obs18-fix-20260929-control.json` |
| Tamaño | `3 105 456` B |
| SHA-256 | **`3531AE6B453A6371B103A05B6289598C3E53910C3F43AEAA31A6C831DB848FCD`** |
| Reproducibilidad | **NO byte-reproducible** (declarado, ver abajo); las cifras **sí** se reproducen |

```
totals              {"decided": 24480, "proposals": 35, "orders": 31, "fills": 118, "vetoes": 24449}
daysWithFills       16
book                liveMax 15 · finalReservedRisk 5999.9998 · finalReservedCash 93622.5185
releases            {"total": {"RELEASED_BY_FILL": 29}, "byDeadTail": 0,
                     "reasons": {"fill": 29}}
journalReasons      {"approved": 24, "concentration_exceeded": 2, "regime_invalid": 4530,
                     "risk_budget_exceeded": 1400, "risk_measurement_partial": 160, "top_n_excluded": 4827}
score               {"realizedCount": 13, "realizedRTotal": -11.816269…, "meanR": -0.908944…,
                     "medianR": -1.239013…, "positiveShare": 0.153846…}
byYear              {"2022": {"count": 13, …}}
stall               {"declared": true, "thresholdOperableDays": 20,
                     "operableDaysWithoutActivity": 266, "lastActiveDay": "2022-05-06"}
horizon             {"completed": false, "ticks": 1224, "totalTicks": 1224,
                     "truncationReason": "stalled_book"}
```

**Por qué el control no es byte-reproducible (medido, no supuesto):** una segunda corrida
(`...-fix-control-repro.json`, SHA-256 `5116C23A…1D4AF2`) reproduce **todas** las mediciones y difiere en
**23** rutas, **todas** dentro de `replay.finalBook`: `liveReservations[*].reservationId` y
`ownedReservationIds[*]` son identificadores `exit:<ULID>` de las **15 reservas que sobreviven**, y un ULID
lleva el **reloj de pared**. La corrida durable cierra con el libro **limpio** y **no** tiene esas rutas, por
eso **sí** es byte-idéntica.

**A/B frente a la corrida durable:**

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
| Horizonte | `completed=true` | **`completed=false · stalled_book`** |

## 6. Regeneración

```powershell
# Corrida durable (la del informe; byte-reproducible)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --json `
  --out operability_runs/replay-oos-durable-obs18-fix-20260929.json

# Contraprueba A/B (reconciliación de cierre APAGADA)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --no-durable-cycle --json `
  --out operability_runs/replay-oos-durable-obs18-fix-20260929-control.json

# Suites del motor y del instrumento
uv run --no-sync python -m pytest `
  packages/py/application/tests/test_replay_oos.py `
  packages/py/application/tests/test_replay_oos_durable_cycle.py `
  apps/api-python/tests/test_v2_87_release_log.py `
  apps/api-python/tests/test_auto_v2_durable_cycle.py `
  apps/api-python/tests/test_replay_oos_cli_renderers.py -q

# Mutaciones del fix (matriz completa: 265)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
```

**Requisito medido:** PostgreSQL arriba y alcanzable en `127.0.0.1:5432` (Docker Desktop iniciado). Una
caída de Docker mata el paso read-only con `psycopg.errors.ConnectionTimeout`.

## 7. Relectura de `v2.87` (el artefacto antiguo)

| | `v2.87` (artefacto antiguo) | **Sellado `v2.88.6`** |
| --- | --- | --- |
| `byFill` / `byCancel` | 237 / **1** | 174 / **64** (**36 `tail_dead`**) |
| Ciclos / R total | 62 / −18.3660 | **62 / −18.3660** |
| Reservas vivas (máx.) / riesgo final | 1 / 0.0 | **0 / 0.0** |
| Horizonte | `completed=true` | `completed=true` |
| Reproducible byte a byte | **no** | **sí** |

El **puntaje no se mueve** (mismos 62 ciclos, mismo R): cambia la **contabilidad del libro**, que en `v2.87`
sobre-liberaba (`237` liberaciones por fill sobre `174` reales, por la costura anterior a la guarda de
`v2.88.1`). La cifra antigua **no debe citarse**; la de este sello **sí**, con hash verificable.

## 8. Verificación del instrumento

```
packages/py/application/tests/test_replay_oos.py                 18 passed
packages/py/application/tests/test_replay_oos_durable_cycle.py   45 passed   (era 29 → +16)
apps/api-python/tests/test_v2_87_release_log.py                   5 passed   (NUEVA)
apps/api-python/tests/test_auto_v2_durable_cycle.py              26 passed   (era 22 → +4)
apps/api-python/tests/test_replay_oos_cli_renderers.py            3 passed
ruff check (packages/py + apps/api-python, config raíz)         All checks passed
matriz de mutaciones `M257`–`M265`                              9/9 muerden (matriz 256 → 265)
matriz COMPLETA (una sola pasada limpia)                        265/265, árbol intacto, exit 0
```

Log crudo de la matriz completa, **versionado dentro del sello** (una sola pasada sobre un árbol limpio,
`exit 0`): [`mutation-matrix-265.log`](./mutation-matrix-265.log).

**Hazard declarado (medido al remedir la matriz).** Dos sondas **concurrentes** se abortan mutuamente: la
sonda aborta si el fichero que va a mutar ya no es byte a byte el que leyó al arrancar, que es exactamente
lo que ocurre mientras **otra** sonda tiene un mutante aplicado. En esta fase una sonda **vieja** seguía
viva: la nueva abortó en `M60` y la vieja en `M241`, y **ningún** log parcial acredita la matriz. La cifra
`265/265` es de la re-ejecución **en solitario** (sondas zombis apagadas, árbol verificado).

**Deriva de compuerta detectada y corregida al cerrar (declarado).** La repetición de `ruff` antes de sellar
encontró **5 `I001`** (bloques de import con `bolsa_api` colocado después de `bolsa_application` en
`auto_simulation_worker.py` y en `v2_87_replay_oos_durable_cycle.py`, y dos ficheros de test sin la línea en
blanco de rigor) y **9 colapsos de formato** (multilínea → una línea) **ajenos al cambio semántico**
(`auto_simulation_worker.py`, `portfolio_reservation.py`). Los `I001` habrían tumbado el step `Ruff` del job
`python` del tag. Corregido (`ruff check --fix` + reversión de los 9 colapsos): el diff del motor queda en
**`+47 / −8`** (antes `+63 / −38`) y el de `portfolio_reservation.py` en **`+5 / −0`**. **Por qué importa
(medido):** un colapso **desarmaba una mutación en silencio** — `M116` anclaba el `bool(...)` multilínea y la
sonda lo declaró «fragmento ausente»; con el formato revertido `M116` vuelve a **morder** (`1` test) y
**`M241`** (anclada a la condición *antigua* de la regla 2, justo lo que `OBS-18` elimina) se **re-ancló sin
cambiar su semántica** ⇒ **13** tests rojos.

Recuento esperado del job `python` del CI: **`3103 passed, 37 skipped`** (con los **mismos `37` skips**),
derivado de la identidad que cuadró con los runs reales de `v2.88.4` (`3079 − 37 = 3042`) y `v2.88.5`
(`3086 − 37 = 3049`): **recogidos local − 37**. Medida local de esta fase: **`3140` recogidos**
(`1 failed, 3139 passed`; el `1 failed` es el test PG-gated ya conocido de `v2.88.5`, que en CI se
skippea). El salto `3049 → 3103` = **`+54`** = **`+9`** (tests nuevos de ficheros que ya estaban en la lista)
**`+ 45`** (el fichero del instrumento cableado; `16` nuevos + `29` de `v2.87`).

**HUECO DE COBERTURA DE CI, medido y cerrado (declarado).** La primera medida dio `1 failed, 3094 passed`
(Δ `+9` contra `v2.88.5`) cuando la fase añade **`+25`** funciones de test. Causa: **el fichero del
instrumento** `packages/py/application/tests/test_replay_oos_durable_cycle.py` (**45 tests herméticos**,
`0.33 s`, sin PG ni red) **no estaba en la lista de NINGÚN workflow** — se creó en `v2.88` (`564240d2`) y
`git log -S` confirma que nunca se añadió (ese directorio se lista fichero a fichero). Sin cerrarlo, el job
del tag habría dado **`3058`** y **los 16 tests que protegen la regla 2 por evidencia, la cola muerta y el
guardarraíl no habrían corrido en CI**. Se cablea en `release-tag-ci.yml` (**`115 → 116` argumentos**) y en
`python-ci.yml` con la nota de procedencia (patrón «HUECO DECLARADO» de `v2.76`) y se **re-mide**:
`3094 → 3139 passed` = **`+45`**, el tamaño exacto del fichero. Queda **abierta** la deriva estructural
entre las dos listas (`OBS-19`).

## 9. Límite de esta evidencia

**NO** acredita `P3-2`/`P3-3`: el replay usa **reloj simulado** (los cubos de calendario del forward se
construyen con `datetime.now(UTC)`) y la ventana real exige **días de pared con material durable**. La
muestra ya es **multianual** (62 ciclos, 4 temporadas), pero sigue siendo **un** instrumento con **una sola
cuenta/versión/watch** y `pairActive=false` (una sola versión puntuada): **no** mide edge ni cierra deuda de
datos. **NO** cierra `OBS-15` (techo de 1000 `APPLIED`), `OBS-16` ni la deuda de datos; **deja abierta**
`OBS-19` (la deriva entre las dos listas offline de pytest de los workflows). El replay **no**
escribe en PostgreSQL (cuarentena en memoria, por construcción).
