# Evidencia cruda — retirada con la materialización EXACTA del CICLO (`v2.88.7`, `AUTO-MATERIAL-20`, 2026-09-29)

Resumen **verificable** del cierre de `OBS-20`. Las cifras están **transcritas** de las corridas, sin
edición; los artefactos completos son **gitignoreados** (`.gitignore:102` → `/operability_runs/`) y se
regeneran con los comandos de §6.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-20` (`v2.88.7`) — `OBS-20`: la retirada declara el motivo con la materialización **exacta del ciclo**; re-anclaje de las suites PG a la semántica de `OBS-18` |
| Versión de paquete | `2.11.6-beta` → **`2.11.7-beta`** |
| Tag (lo crea el propietario) | **`v2.88.7-beta`** (anotado) |
| Base del diff | **`032ae7cc`** (= `v2.88.6-beta`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Contenido del sello | motor (evidencia del motivo por `cycle_id`) + 1 test hermético nuevo + 2 mutaciones (`M266`/`M267`) + re-anclaje de 2 suites PG + informe + evidencia + registros |

## 1. El rojo que origina el sello (citado, no heredado)

`Release tag CI` del sello anterior (`36603391512`, ref `v2.88.6-beta`, `032ae7cc`) — **FAILURE**:

```
job lifecycle-pg  ->  step Pytest Crash/Recovery Day
  E  AssertionError: la muerte debe ocurrir con el fill PARCIAL durable (cola de reserva viva);
     reservas vivas: []
  1 failed in 122.20s (0:02:02)
```

La aserción sellada exigía una **cola viva** al morir el proceso; el motor de `OBS-18` —sellado en el mismo
commit— **retira** la cola muerta al cerrar el turno (`tail_dead`, `remaining_qty = 0`). El re-anclaje ya
estaba en el árbol de trabajo y se **sella** aquí. El job `python` de ese run **sí** fue verde y cuadró con
lo declarado: **`3103 passed, 37 skipped`**.

## 2. El defecto (`OBS-20`): quién escribe la evidencia y quién la lee

`OBS-18` decide por la **evidencia de la fila** (`released_qty`), pero esa evidencia la escribe el **camino
caliente de la sesión que LIQUIDA** el fill, y solo sobre las reservas que esa sesión tiene **en su libro**.
Si no la tiene (libro de otra sesión, o barrido de arranque de un proceso sin memoria):

| Instante | Ledger (`execution_events`) | Fila (`portfolio_reservations`) |
| --- | --- | --- |
| fill liquidado | **`APPLIED`** | `released_qty = 0` (la liberación **no ocurrió**) |
| cierre de turno de **otra** sesión | `APPLIED` (contradice) | `released_qty = 0` ⇒ **`cancel`** |

Firma medida en `test_concurrent_auto_pg.py[5]` (**~1 de cada 9** corridas): `assert 'cancel' == 'tail_dead'`.

## 3. La corrección (motor)

`cycle_id` (V2.47) **ya** viaja en las dos partes y **ya** está persistido (migración `042`/`047`): el
contexto financiero del fill y la reserva. Es la identidad **sin heurísticas**:

```python
# applied_fills.py — el ciclo viaja del contexto al hecho aplicado
cycle_id=getattr(context, "cycle_id", None),

# auto_simulation_worker.py — materialización EXACTA del ciclo (acotada por LADO)
cycle_fills[(cycle, fact.side)] += float(fact.quantity)
...
linked = cycle_fills.get((cycle, reservation.side), 0.0)
if linked > 0.0:
    committed = float(reservation.quantity or 0.0)
    materialized = max(materialized, min(linked, committed) if committed > 0.0 else linked)
```

- Acotado por **LADO** (`(cycle, side)`): un ciclo tiene las dos patas (entrada `BUY` y salida `SELL`).
- **Instrumento+lado NO** se usa como identidad (dos órdenes del mismo instrumento y lado son **ciclos
  distintos**: es el defecto que `OBS-18` corrigió).
- **`max`**: lo registrado en la fila **nunca** se rebaja; la evidencia del ciclo **completa**.
- **Cota por lo COMPROMETIDO** (`min(linked, quantity)`).
- **`None` = no declara ciclo** ⇒ comportamiento de `OBS-18` (decide la fila).
- **Fail-closed intacto**: `in_flight` manda, `measurable` manda, y nunca se libera más que la cantidad viva.
- `AppliedFillFact.cycle_id` **no** se publica en `to_dict()`: el contrato serializado **no cambia**.

## 4. La medida que lo separa de «un fallo de test»: 4 retiradas del replay multianual

Ciclo durable, **`1225/1225`** ticks, `2021-12-07 → 2026-09-29`:

| Motivo | `v2.88.6` | **`v2.88.7`** |
| --- | --- | --- |
| `fill` | 174 | **174** |
| `tail_dead` | 36 | **40** |
| `cancel` | 28 | **24** |

El cambio está **localizado** en **4 días, una retirada cada uno** (comparación campo a campo de
`book.perDay`; **ningún otro día cambia**):

| Día | `(tail_dead, cancel, fill)` `v2.88.6` | `v2.88.7` |
| --- | --- | --- |
| `2022-03-14` | `(0, 1, 1)` | `(1, 0, 1)` |
| `2022-03-16` | `(1, 1, 2)` | `(2, 0, 2)` |
| `2022-06-09` | `(0, 1, 0)` | `(1, 0, 0)` |
| `2022-06-13` | `(0, 1, 2)` | `(1, 0, 2)` |

**4** de las **64** cancelaciones eran **proveniencia falsa**. El **puntaje no se mueve** (mismos `62`
ciclos, mismo `R` total **−18.3660**).

> **Comparabilidad (declarada).** El censo de `v2.88.6` terminaba en `2026-09-28` (`1224` ticks) y el de
> `v2.88.7` en `2026-09-29` (`1225`): el día nuevo **no** añade fills ni retiradas (mismos
> `752`/`210`/`238`), así que las cuatro reatribuciones son del motor, no del calendario.

## 5. Corrida sellada — ciclo durable

| | |
| --- | --- |
| Fichero | `operability_runs/replay-oos-durable-obs20-fix-20260929.json` |
| Tamaño | `3 393 187` B |
| SHA-256 | **`7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461`** |
| Reproducibilidad | **byte-idéntica** en una segunda corrida independiente (`...-fix-repro-20260929.json`, mismo tamaño y mismo SHA-256) |

```
startDay            2021-12-07
endDay              2026-09-29
ticks               1225        (completed=true, truncationReason=null)
totals              {"decided": 24500, "proposals": 238, "orders": 210, "fills": 752, "vetoes": 24303}
daysWithFills       141
regimeCounts        {"BEAR_TREND": 907, "HIGH_VOLATILITY": 310, "SIDEWAYS": 8}
journalReasons      {"approved": 86, "concentration_exceeded": 33, "regime_invalid": 878,
                     "risk_budget_exceeded": 11, "risk_measurement_partial": 227, "top_n_excluded": 292}
```

**Libro de compromisos** (la medición que cierra `OBS-20`):

```
liveMax               0            finalReservedRisk 0.0        finalReservedCash 0.0
partialDays           0            measuredUnknownDays []
cancelReleaseDays     57
releases            {"total": {"RELEASED_BY_FILL": 174, "RELEASED_BY_CANCEL": 64},
                     "byFill": 174, "byCancel": 64, "byDeadTail": 40,
                     "reasons": {"fill": 174, "tail_dead": 40, "cancel": 24}}
stall               {"declared": false, "thresholdOperableDays": 20,
                     "operableDaysWithoutActivity": 36, "lastActiveDay": "2026-01-27"}
retention           {"appliedRetention": 900, "appliedPeak": 752, "appliedArchived": 0,
                     "engineReadLimit": 1000}
finalBook           {"inFlight": [], "liveReservations": [], "pendingTraceCount": 0,
                     "pendingTraces": [], "unappliedMeasurement": "COMPLETE",
                     "unappliedRows": [], "ownedReservationIds": []}
```

**Puntuación** (`replay.score`; la unidad es el **ciclo**, los fills parciales se agregan por símbolo):

```
realizedCount       62            realizedRTotal  -18.365980744109294
meanR               -0.296225…    medianR         -1.053446…
positiveShare       0.370967…    (23/62)          unmeasuredCount 0

byYear  2022: {"count": 50, "meanR": -0.504255…, "positiveShare": 0.3000}
        2023: {"count":  7, "meanR":  0.227441…, "positiveShare": 0.5714}
        2024: {"count":  2, "meanR":  1.876265…, "positiveShare": 1.0000}
        2025: {"count":  3, "meanR":  0.500718…, "positiveShare": 0.6667}
```

**Muestra MULTIANUAL** (4 temporadas). `stall.declared = false` con **36** días operables sin actividad: el
libro está **limpio**, así que el motor **eligió** no operar.

## 6. Regeneración

```powershell
# Corrida durable (la del informe; byte-reproducible en DOS corridas)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --json `
  --out operability_runs/replay-oos-durable-obs20-fix-20260929.json
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --json `
  --out operability_runs/replay-oos-durable-obs20-fix-repro-20260929.json

# Suites del motor y del instrumento
uv run --no-sync python -m pytest `
  apps/api-python/tests/test_auto_v2_durable_cycle.py `
  packages/py/application/tests/test_replay_oos.py `
  packages/py/application/tests/test_replay_oos_durable_cycle.py `
  apps/api-python/tests/test_v2_87_release_log.py `
  apps/api-python/tests/test_replay_oos_cli_renderers.py -q

# Mutaciones del fix (matriz completa: 267)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py

# Suites PG del sello (las del job `lifecycle-pg` que salió rojo)
uv run --no-sync python -m pytest apps/api-python/tests/test_crash_recovery_day_process_pg.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_concurrent_auto_pg.py -q
```

**Requisito medido:** PostgreSQL arriba y alcanzable en `127.0.0.1:5432` (Docker Desktop iniciado) para las
suites PG y para la batería offline con el comando EXACTO del CI (el rojo local PG-gated necesita BD).

## 7. Verificación del sello

```
apps/api-python/tests/test_auto_v2_durable_cycle.py              27 passed   (era 26 → +1)
packages/py/application/tests/test_replay_oos.py                 18 passed
packages/py/application/tests/test_replay_oos_durable_cycle.py   45 passed
apps/api-python/tests/test_v2_87_release_log.py                   5 passed
apps/api-python/tests/test_replay_oos_cli_renderers.py            3 passed
  -> corrida conjunta de las cinco suites                       98 passed   (era 97)

suites PG (locales, PG real):
  test_golden_day_v2_process_pg.py                                1 passed
  test_crash_recovery_day_process_pg.py                           1 passed   (el rojo del tag de v2.88.6)
  test_concurrent_auto_pg.py                                      3 passed × 12 corridas (12/12)
  test_auto_v46_hardkill_recovery_pg.py                           2 passed
  test_auto_v46_crash_injection_pg.py                             2 passed
  test_auto_v46_multiprocess_pg.py                                1 passed (113.46 s)

ruff check (packages/py + apps/api-python, config raíz)           All checks passed
batería offline (comando EXACTO del CI: 121 tokens = 81 rutas + 39 `--ignore` + `-q`)  1 failed, 3140 passed (3141 recogidos)
mutaciones M266 / M267 (filtradas)                                2/2 muerden, árbol intacto
matriz COMPLETA (una sola pasada limpia)                          267/267, árbol intacto, exit 0
```

Log crudo de la matriz completa, **versionado dentro del sello**:
[`mutation-matrix-267.log`](./mutation-matrix-267.log).

**El recuento del job `python` del tag que este sello espera:** **`3104 passed, 37 skipped`**
(identidad `recogidos local − 37 skips`: `3141 − 37`). El único rojo local
(`test_auto_v70_auto23_evidence_validation.py`, `assert 17 == 26`) **exige PostgreSQL** y el job offline lo
**skippea**: forma parte de los `37`.

## 9. Cita real del CI del tag (POST-TAG, 2026-09-29)

`Release tag CI` run **[`36614230366`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36614230366)**
(HEAD `5cbe84b0`, `ref=v2.88.7-beta`) → **`SUCCESS` en la PRIMERA pasada** (`attempt 1`;
`18:44:34Z → 18:53:13Z`, **~8m39s**), **10 jobs reales verdes + `certify` verde** y
`playwright (integrated E2E, opt-in)` `skipped` por diseño.

Job `python` **verbatim**: `ruff All checks passed!` · `Contracts: 4 kept, 0 broken` ·
`mypy no issues found in 508 source files` · **`3104 passed, 37 skipped, 6 warnings in 55.36s`**
⇒ **ESPERADO `3104/37` = OBSERVADO `3104/37` → COINCIDE**.

`lifecycle-pg` **GREEN con `220 passed`** en sus **8** invocaciones (**0 failed / 0 skipped**), todas con
guarda `fail if skipped`:

| Paso | Resultado |
| --- | --- |
| Alembic + auth + golden V1.88–V1.97 + integridad | `165 passed in 98.45 s` |
| Aislamiento de cuenta V2.15.4 | `45 passed in 15.02 s` |
| Golden Day 2.0 | `1 passed in 10.64 s` |
| **Crash/Recovery Day** | **`1 passed in 9.34 s`** ← **el rojo del tag de `v2.88.6`** |
| Concurrent AUTO (3 sesiones) | `3 passed in 2.30 s` |
| HardKill recovery | `2 passed in 1.76 s` |
| Crash injection (exactly-once) | `2 passed in 0.92 s` |
| Multiprocess AUTO (N procesos reales) | `1 passed in 113.13 s` |

Companion sobre el mismo commit/ref (`Python CI 36614230218`, `Frontend CI 36614230417`,
`Optimize lab 36614230409`, `Fase 2 scientific 36614230180`) → **`success`** las cuatro; en `main`
(push `5cbe84b0`) `Python CI 36614223164` `quality` **`3093 passed, 40 skipped`** con sus **4** jobs PG
per-commit verdes, y `Frontend CI 36614223183` / `Optimize lab 36614223230` /
`Fase 2 scientific 36614223235` / `Gitleaks 36614223332` **`success`**. Cita cruda:
[`evidencia-ci-tag-v2.88.7-2026-09-29.txt`](../evidencia-ci-tag-v2.88.7-2026-09-29.txt).

**Cola de la cita** (push en `main` del commit que **transporta** esta cita, `190e4e3a`, solo documentación):
`Gitleaks 36625625987` **`success`**, y **nada más corre**: los workflows de código llevan **filtro de
ruta** y no se disparan con un push de solo-docs, así que su ausencia **no** es un hueco de CI. El
certificado del sello vive en el run **`36614230366` del tag** (commit `5cbe84b0`), **no** en el commit de
cita. Integridad de esta evidencia **re-medida** tras el sello: los dos artefactos del replay siguen
**byte-idénticos** (`3 393 187` B, `7D998E4D…C804A0461`).

## 10. Límite de esta evidencia

**NO** acredita `P3-2`/`P3-3`: el replay usa **reloj simulado** (una cuenta/versión/watch,
`pairActive=false`) y **no** sustituye la ventana PAPER real. **NO** cierra `OBS-15` (techo de **1000
`APPLIED`**), `OBS-16` ni la deuda de datos; **NO** cierra **`OBS-19`** (la deriva entre las dos listas
offline de pytest, que sigue **abierta**). El replay **no** escribe en PostgreSQL (cuarentena en memoria,
por construcción). El tag `v2.88.6-beta` **no** se borra: queda como **rojo citado**.

## 11. Reproducibilidad del artefacto (POST-SELLO, 2026-09-29)

**El artefacto de esta tabla ya NO es una promesa sin verificar.** Cuando se selló `v2.88.7-beta`, el
`7D998E4D…C804A0461` **no era auditable**: el fichero vive fuera del repo (`operability_runs/` está en
`.gitignore`) y el CI **no podía regenerarlo** (el script del replay lee barras D1 **reales** de
PostgreSQL y el `db:seed` del repo **solo siembra instrumentos**: las barras vienen de un sync externo,
así que un runner arrancaba con la tabla vacía y el censo daba **0 días operables** → **ningún**
artefacto).

Se cierra con una **entrada congelada** versionada en este mismo directorio
([`replay-input-fixture.ndjson`](./replay-input-fixture.ndjson), `7 482 989` B, SHA-256
`857C9F7D3F2CD43713080736B2C20E7CAE5C94E590A1B4626201D159A1C8279C`: 20 instrumentos + **25 700** barras)
y un job de tag que **regenera** el artefacto con el **mismo** script del sello y **asserta** su
SHA-256 y su tamaño: `replay-repro`, cableado en `certify` (un rojo ahí **no-GREENea** el tag).
Herramienta: [`replay_oos_input_fixture.py`](../../../apps/api-python/scripts/replay_oos_input_fixture.py).

**Medido, no prometido** — sembrando el fixture en una base **distinta** (`bolsa_v1_replay_fixture`,
creada y migrada desde cero) y regenerando con el script intacto:

```
artefacto        /tmp/replay.json
render           CRLF (modo texto de Windows)
bytes            3393187  (sello 3393187 · mismo contenido en LF 3290062)
sha256           7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461
sha256 LF        A4DA036C9AC198EAF88037EBB5D66D0A76CEA95141E03B046CECE1BCBC5B13CB
VEREDICTO        REPRODUCIDO (render del sello, byte a byte)
```

### 11.1 El primer rojo del job fue un hallazgo, no un fallo del motor (`36636706369`)

El `workflow_dispatch` **`36627838819`** puso `replay-repro` en **rojo** con `3 290 062` B /
`A4DA036C…13CB`. El job se instrumentó (huella del runner + **digest por secciones** + **2ª corrida**
idéntica, con [`replay_artifact_digest.py`](../../../apps/api-python/scripts/replay_artifact_digest.py))
y la corrida **`36636706369`** publicó que **todas las secciones coinciden byte a byte** con el sello
(`census` `1237098`/`45E4CC80CFBA6E5C`, `replay` `891272`/`EE81E76CEE0995AA`, `totals` con
`fills=752`, `watch` `561`/`40230635349BF2A0`) y que el runner es **determinista consigo mismo**.

Lo único distinto es el **salto de línea**: el sello se escribió en Windows en modo texto, así que sus
`103 125` líneas llevan `\r\n` (`3 393 187` B); el runner escribe `\n` (`3 290 062` B). Diferencia =
`103 125` B = **una `\r` por línea**, y la comprobación cruzada lo cierra: `sha256(sello CRLF→LF)` =
`A4DA036C…` (el del runner) y `sha256(runner LF→CRLF)` = `7D998E4D…` (el del sello). Por tanto el
`sha256` del fichero identificaba **el render de Windows**, no la evidencia.

Arreglo: `assert-artifact` declara **los dos renders** y acepta ambos diciendo cuál ha visto (un
fichero manipulado sigue dando **`NO reproducido`**); el manifiesto del fixture publica los dos pares
(`expectedArtifactSha256(Lf)`/`expectedArtifactBytes(Lf)`). **Deuda declarada para el siguiente sello:**
fijar `newline="\n"` en el escritor del replay (el del fixture ya lo hace) para que el mismo contenido
tenga **un** hash en cualquier SO.


Límites declarados: el job se añade **después** del sello, así que `v2.88.7-beta` se selló **sin** él
(la primera certificación del job es la del **siguiente** tag o de un `workflow_dispatch`); reproduce
**el mismo artefacto**, luego acredita **reproducibilidad**, **no** la corrección de la semántica de
`OBS-20`. Informe completo:
[`reproducibilidad-replay-oos-v2.88.7-2026-09-29.md`](../reproducibilidad-replay-oos-v2.88.7-2026-09-29.md).
