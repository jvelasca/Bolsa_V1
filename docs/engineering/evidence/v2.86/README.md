# Evidencia cruda — Replay OOS de viabilidad del motor AUTO (`v2.86`, 2026-09-29)

Resumen **verificable** del artefacto del replay. El JSON completo (2 054 030 B) es
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
| Fichero | `operability_runs/replay-oos-viability-20260929.json` |
| Tamaño | `2 054 030` B |
| SHA-256 | `91A871FBD5B43335C1197DA74D5D91663730A12FD0929FB8A3CB3F4C35143A90` |
| Fecha de corrida | 2026-09-29 (UTC) |

Regeneración:

```powershell
uv run --no-sync python apps/api-python/scripts/v2_86_replay_oos_viability.py --json `
  --out operability_runs/replay-oos-viability-20260929.json
```

## Cabecera de identidad

```
bump        2.10.2-beta
account     1484e253d2d54645945a6b1d7
venue       paper
versionA    v283-window-a
watchSize   20
sectorsKnown 20
```

## Paso 0 — censo (`census`)

```
totalDays           1284
operableDays        318
maxOperableStreak   205
operableByOperational  {"HIGH_VOLATILITY": 310, "SIDEWAYS": 8}
aggregateCounts        {"trend_down": 907, "high_vol": 310, "sin_regimen": 59, "range": 8}
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
daysWithFills         16
totals              {"decided": 24480, "proposals": 35, "orders": 31, "fills": 118, "vetoes": 24449}
regimeCounts        {"BEAR_TREND": 906, "HIGH_VOLATILITY": 310, "SIDEWAYS": 8}
lastFillDay         2022-05-06
```

Motivos de veto por familia (`journalReasons`):

```
{"approved": 24, "concentration_exceeded": 2, "regime_invalid": 4530,
 "risk_budget_exceeded": 1400, "risk_measurement_partial": 160, "top_n_excluded": 4827}
```

## Paso 3 — puntuación (`replay.score`)

La unidad es el **ciclo** (los fills parciales del motor se agregan por símbolo; ver el informe §2.3).

```
realizedCount       13
realizedRTotal      -11.8163
meanR               -0.9089
medianR             -1.2390
positiveShare        0.1538   (2/13)
unmeasuredCount      0
openPositions        1       (R no realizado, marcado)
byVersion           {"v283-window-a": {"count": 13, "meanR": -0.9089, "medianR": -1.2390, "positiveShare": 0.1538}}
```

Distribución de R realizado: `≤ −1R` **11** · `(−1, 0)` **0** · `[0, 1)` **1** · `≥ +1R` **1**.

Ciclos cerrados por mes de salida: `2022-02`: 1 · `2022-03`: 8 · `2022-04`: 3 · `2022-05`: 1.

## Verificación del instrumento

```
packages/py/application/tests/test_replay_oos.py                          18 passed
guardarraíles vecinos (replay_oos + forward_deciders + partial_fills + worker)  71 passed
ruff check (módulo + tests + CLI + matriz)                                All checks passed
matriz de mutaciones M234..M239                                          6/6 muerden (árbol restaurado byte a byte)
```

## Límite de esta evidencia

**NO** acredita `P3-2`/`P3-3` ni sustituye una ventana PAPER real: el replay usa un **reloj simulado** y
la ventana real exige **días de pared con material durable**. La muestra (13 ciclos, un solo episodio)
**no es concluyente** sobre el edge del motor.
