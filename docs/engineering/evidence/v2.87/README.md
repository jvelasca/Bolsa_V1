# Evidencia cruda — Replay OOS del ciclo durable reserva→fill→liberación (`v2.87`, 2026-09-29)

Resumen **verificable** del artefacto del replay. El JSON completo (3 165 540 B) es
**gitignoreado** (`.gitignore:102` → `/operability_runs/`), así que no viaja en un clon del
repositorio; se regenera con el comando de abajo. Estas cifras son las que el JSON contiene,
transcritas sin edición.

> **[NOTA DE CONTEXTO POSTERIOR — 2026-09-29.]** Esta evidencia viaja dentro del tag **`v2.88-beta`** del
> **sello conjunto** (`AUTO-MATERIAL-14` + `AUTO-MATERIAL-15` + cierre de `OBS-14` / `AUTO-MATERIAL-16`).
> Los `2.10.2-beta`/«SIN tag» de abajo describen el **estado al autorarla**, no el estado final. El texto
> sellado se conserva **verbatim**.

## Artefacto

| | |
| --- | --- |
| Fichero | `operability_runs/replay-oos-ciclo-durable-20260929.json` |
| Tamaño | `3 165 540` B |
| SHA-256 | `DC61B3B912C6C7CE6455837BF8E6E6BDD6C03CE6B900D6B73D7925B203C6C54F` |
| Fecha de corrida | 2026-09-29 (UTC) |

**Control A/B (`--no-durable-cycle`)** — mismo harness, misma ventana, **solo** con la
reconciliación de cierre apagada. Se conserva como contraprueba de que el desbloqueo no es
narración:

| | |
| --- | --- |
| Fichero | `operability_runs/replay-oos-ciclo-durable-20260929-control.json` |
| Tamaño | `2 949 320` B |
| SHA-256 | `FE4CBF79E221A27E2A517A10976664FB6149BB4AAB8635851B5558A28378CCD1` |

Regeneración:

```powershell
# Corrida con ciclo durable (la del informe)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --json `
  --out operability_runs/replay-oos-ciclo-durable-20260929.json

# Contraprueba A/B (reconciliación de cierre APAGADA)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --no-durable-cycle --json `
  --out operability_runs/replay-oos-ciclo-durable-20260929-control.json
```

## Cabecera de identidad

```
bump          2.10.2-beta
account       1484e253d2d54645945a6b1d7
venue         paper
versionA      v283-window-a
watchSize     20
sectorsKnown  20
nature        INVESTIGACION
phase         V2.87 AUTO-MATERIAL-15 REPLAY OOS CICLO DURABLE
reconcilesAtTickClose  true
```

## Paso 0 — censo (`census`)

```
totalDays            1284
operableDays          318
maxOperableStreak     205
operableByOperational {"HIGH_VOLATILITY": 310, "SIDEWAYS": 8}
aggregateCounts       {"trend_down": 907, "high_vol": 310, "sin_regimen": 59, "range": 8}
```

Días operables por año (operables / total):

```
2021:   0 /  77      2024:   4 / 254
2022: 218 / 257      2025:  23 / 253
2023:  36 / 255      2026:  37 / 188
```

## Paso 2b — replay (`replay`)

```
startDay            2021-12-07
endDay              2026-09-28
ticks               1224
daysWithFills        141
totals              {"decided": 24480, "proposals": 238, "orders": 210, "fills": 752, "vetoes": 24283}
regimeCounts        {"BEAR_TREND": 906, "HIGH_VOLATILITY": 310, "SIDEWAYS": 8}
```

Motivos de veto por familia (`journalReasons`):

```
{"approved": 86, "concentration_exceeded": 33, "regime_invalid": 878,
 "risk_budget_exceeded": 11, "risk_measurement_partial": 227, "top_n_excluded": 292}
```

## Libro de compromisos (`replay.book` y `replay.releases`)

```
reservas vivas (máx.)      1          (finalReservedRisk 0.0 · finalReservedCash 0.0)
días con medición parcial  0          (measuredUnknownDays [])
días con retirada CANCEL   1          (2022-02-28)
retiradas acumuladas       {"RELEASED_BY_FILL": 237, "RELEASED_BY_CANCEL": 1}
retención APPLIED          900 (archivadas 0, pico 752, tope de lectura del motor 1000)
```

`replay.horizon`:

```
{"completed": true, "lastDay": "2026-09-28", "ticks": 1224, "totalTicks": 1224, "truncationReason": null}
```

## Paso 3 — puntuación (`replay.score`)

La unidad es el **ciclo** (los fills parciales del motor se agregan por símbolo; ver el informe §2.3).

```
realizedCount       62
realizedRTotal      -18.3660
meanR               -0.2962
medianR             -1.0534
positiveShare        0.3710   (23/62)
unmeasuredCount      0
unmeasuredReasons    {}
byVersion           {"v283-window-a": {"count": 62, "meanR": -0.2962, "medianR": -1.0534, "positiveShare": 0.3710}}
```

`byYear` (bucket nuevo de `v2.87`):

```
2022: {"count": 50, "meanR": -0.5043, "medianR": -1.1236, "positiveShare": 0.3000}
2023: {"count":  7, "meanR":  0.2274, "medianR":  0.0924, "positiveShare": 0.5714}
2024: {"count":  2, "meanR":  1.8763, "medianR":  1.8763, "positiveShare": 1.0000}
2025: {"count":  3, "meanR":  0.5007, "medianR":  1.4746, "positiveShare": 0.6667}
```

## Contraprueba A/B — el control reproduce el goteo de `v2.86`

Mismo harness y misma ventana; **única** diferencia: `--no-durable-cycle` (la reconciliación de
cierre no se ejecuta).

| Métrica | Ciclo durable (1224 ticks) | Control (`--no-durable-cycle`) |
| --- | --- | --- |
| Órdenes | **210** | 31 |
| Fills | **752** | 118 |
| Ciclos cerrados | **62** | 13 |
| Reservas vivas (máx.) | **1** | **15** |
| Riesgo comprometido final | **0.0** | **5 999.9998** |
| Retiradas `RELEASED_BY_FILL` / `_BY_CANCEL` | **237 / 1** | 29 / **0** |
| Días con fills | **141** | 16 |
| `risk_budget_exceeded` | **11** | **1 400** |
| Horizonte | 1224/1224 · `completed=true` | 1224/1224 · `completed=true` |
| R por año | 2022/2023/2024/2025 | solo 2022 |

Lectura: el control **congela toda la actividad tras ~2022-05** con **15 reservas huérfanas vivas**
que comprometen **todo** el presupuesto (`$6000`) ⇒ `risk_budget_exceeded` **1 400**; la
reconciliación de cierre mantiene el libro limpio (pico **1**, final **0**) y el motor opera las 4
temporadas. Ninguna compuerta se degradó: los vetos estructurales (`top_n_excluded`,
`regime_invalid`) siguen ahí, solo dejan de estar dominados por el goteo.

## Verificación del instrumento

```
packages/py/application/tests/test_replay_oos.py                 18 passed
packages/py/application/tests/test_replay_oos_durable_cycle.py   29 passed
apps/api-python/tests/test_auto_v2_durable_cycle.py               7 passed
guardarraíles vecinos (replay_oos + forward_deciders + partial_fills + worker)  71 passed
ruff check (módulo + tests + CLI + matriz)                       All checks passed
matriz de mutaciones M240..M244                                  5/5 muerden, 5/5 medidas (matriz 244)
```

## Límite de esta evidencia

**NO** acredita `P3-2`/`P3-3` ni sustituye una ventana PAPER real: el replay usa un **reloj
simulado** y la ventana real exige **días de pared con material durable**. La muestra ya es
multi-anual (**62 ciclos**, 4 temporadas), pero sigue siendo un **único instrumento de reloj
simulado** con **una sola cuenta/versión/watch** y **`pairActive=false`** (una sola versión
puntuada), así que **no** mide edge ni cierra deuda de datos. El `book` declara su medición
(`COMPLETE`/`PARTIAL`/`UNKNOWN`) y el horizonte su `truncationReason`; en esta corrida **no hubo
truncación** (`completed=true`, `measuredUnknownDays=[]`).
