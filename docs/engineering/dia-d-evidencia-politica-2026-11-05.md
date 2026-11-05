# DÍA D contra la política de evidencia por cuenta — medición 2021-2026 (2026-11-05)

> **Estado:** **NO ACREDITA** la política de evidencia con los umbrales por defecto. La corrida
> mide y declara; **no** toca el motor, ni la allocation, ni ningún umbral. **AUTO sigue OFF** y
> **PAPER sigue INCONCLUSIVE**.
>
> **Artefacto:** `operability_runs/dia-d-auto/v2_93_policy_defaults_2026-11-05.json` (+ `.log`,
> no versionados, `2.11.183-beta`). Reproducible con:
>
> ```bash
> python apps/api-python/scripts/v2_93_dia_d_multi.py \
>   --from-year 2021 --to-year 2026 --universe pit --json \
>   --out operability_runs/dia-d-auto/v2_93_policy_defaults_2026-11-05.json
> ```

## 1. Qué se corrió

Barrido multi-día **read-only** (`v2_93`) sobre el harness hermético `v2.86`/`v2.87` vía `v2_91`,
universo **PIT por día** (`CatalogPointInTimeUniverse` sobre 181 instrumentos del catálogo local,
barras D1 durables 2021-10-27 → 2026-11-05), `--venue paper`, edge declarado `0.9`, `topK 5` y
`AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` (sin geometría sintética). Atribución **por `entryDay`**.

Lo que la corrida mide: **R por ciclo** (unidad de riesgo), hit rate, MAE/MFE y captura.
Lo que la corrida **no** mide se declara abajo; ningún hueco se rellena con `0`.

### Cobertura

| año | ventana solicitada | fechas D con barras | ciclos medidos |
|---|---|---|---|
| 2021 | 2021-10-29 → 2021-12-31 | 46 | 0 |
| 2022 | 2022-01-03 → 2022-12-30 | 258 | 54 |
| 2023 | 2023-01-02 → 2023-12-29 | 258 | 22 |
| 2024 | 2024-01-02 → 2024-12-31 | 259 | 48 |
| 2025 | 2025-01-02 → 2025-12-31 | 258 | 38 |
| 2026 | 2026-01-02 → 2026-11-05 | 255 | 30 |
| **total** | | **1 334** | **192** |

`2021` figura en `coverage.yearsEmpty` (ventana operable sin ciclos): se declara, no se rellena.
Equivalencia declarada: **«ventana» = fecha D** (día hábil con barras en la ventana solicitada);
no es una ventana móvil de equity.

## 2. Resultado medido

| métrica | valor |
|---|---|
| ciclos medidos | **192** |
| expectativa | **−0,2037 R/ciclo** |
| hit rate | **41,7 %** (80 ganadores / 112 perdedores) |
| R realizado total | **−39,11 R** |
| ganancia media / pérdida media | +1,3248 R / −1,2955 R (payoff 1,0226) |
| captura de MFE (media / mediana) | 0,171 / 0,000 (0 ciclos > 1,0) |
| R dejados en la mesa (media) | 1,006 R |
| reversiones con MFE ≥ 1 R | 20 de 189 medidos |
| calidad de evidencia del artefacto | `STRONG` |
| veredicto del artefacto | **`REFUTED` — `negative_expectancy`** |

Por año (la pérdida se concentra en 2022 y 2026):

| año | ciclos | R/ciclo | hit | R total |
|---|---|---|---|---|
| 2022 | 54 | −0,5480 | 37,0 % | −29,59 |
| 2023 | 22 | +0,0267 | 45,5 % | +0,59 |
| 2024 | 48 | −0,1082 | 47,9 % | −5,19 |
| 2025 | 38 | +0,0655 | 42,1 % | +2,49 |
| 2026 | 30 | −0,2468 | 36,7 % | −7,40 |

Por régimen: `trend_down` 121 ciclos · −0,0666 R/ciclo · hit 45,5 %; `high_vol` 68 ciclos ·
−0,3993 R/ciclo · hit 36,8 %; `range` 3 ciclos · −1,3013 R/ciclo (muestra insuficiente).

Lectura descriptiva: la mediana del R por año ronda **−1 R** salvo 2024, la pérdida media
(−1,2955 R) supera a la ganancia media (+1,3248 R) en módulo-relación porque el **hit rate**
(41,7 %) queda por debajo del punto de equilibrio del payoff (~49,4 %). No es una conclusión
causal: es la forma de la muestra.

## 3. Veredicto contra cada umbral de la política (defaults)

| umbral (default) | valor de la política | medido | veredicto |
|---|---|---|---|
| ventanas / fechas D | ≥ 30 | 1 334 | **CUMPLE** (con la equivalencia declarada) |
| operaciones totales | ≥ 100 | 192 | **CUMPLE** |
| % ventanas positivas | ≥ 60 % | **NOT_MEASURED** (no hay equity por fecha D) · proxy por año: 2 de 5 medidos con R total > 0 = 40 % | **NO ACREDITADO** |
| retorno neto | ≥ 0 % | **NOT_MEASURED** (la unidad es R, no %) · R total −39,11 R y expectativa −0,2037 R | **NO ACREDITADO** |
| drawdown máximo | ≤ 15 % | **NOT_MEASURED** (el artefacto agrega por año y no publica curva de equity) | **NO ACREDITADO** |
| exceso vs comprar y mantener | ≥ 0 % | **NOT_MEASURED** (sin benchmark buy-and-hold en el artefacto) | **NO ACREDITADO** |
| reserva fuera de muestra | 30 % | **NOT_MEASURED** (la corrida usa la ventana completa; no hay holdout reservado) | **NO ACREDITADO** |
| coste mínimo ida+vuelta | ≥ 22 bps | **32 bps** del modelo de coste de la casa (10 bps comisión + 5 bps slippage por lado, 2 bps de spread) | **CUMPLE** como configuración; el coste **realizado** es `NOT_MEASURED` |

### Veredicto global

**NO ACREDITA.** Cuatro umbrales económicos de la política (ventanas positivas, retorno neto,
drawdown, exceso vs buy-and-hold) y la reserva fuera de muestra **no son medibles con este
artefacto**; los dos que sí se miden (tamaño de muestra y coste mínimo configurado) se cumplen,
pero el signo de la evidencia es **negativo** y el propio artefacto emite `REFUTED`. No se
relaja ningún umbral para «hacer pasar» la corrida, ni se convierte un `NOT_MEASURED` en 0.

## 4. Lo que falta para poder acreditar (sin tocar umbrales)

1. **Curva de equity** del replay (PnL monetario por ciclo y por fecha D) para poder medir
   retorno neto %, drawdown % y % de ventanas positivas con el denominador que la política pide.
2. **Benchmark buy-and-hold** del mismo universo PIT y ventana, para el exceso.
3. **Holdout reservado** (30 % de las fechas D) medido *después* de fijar los umbrales; la
   política ya está fijada por defecto, así que basta con declarar y respetar el corte.
4. **Coste realizado**: emitir las filas de coste (`--cycle-detail`) o conciliar los fills del
   replay con el modelo aplicado.
5. **Ventana PAPER real** (P3-2/P3-3): el replay no la sustituye.

## 5. Invariantes de esta medición

- `Δ motor = 0`: no se tocó `auto_v2_entry.py`, `auto_simulation_worker.py`, la allocation, `TOP_N`
  ni ningún umbral de la política.
- **AUTO OFF** y **PAPER INCONCLUSIVE** sin cambios.
- Un hueco es `None`/`NOT_MEASURED`; nunca `0`. `2021` se declara vacío y no se promedia.
- Read-only: la corrida no escribe en PostgreSQL ni toca el sello de `replay-repro`.
