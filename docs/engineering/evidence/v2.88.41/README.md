# Evidencia cruda — `v2.88.41-beta` (AUTO · **DÍA-D-3b**: **atribución MULTIRREGIMEN 2021-2026** — año × régimen × resultado × excursión, sin tocar motor)

> **Objeto:** package **`2.11.41-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** **capacidad del instrumento** sobre **DÍA-D AUTO**, advisory y read-only. Convierte el diagnóstico de **un** año (2022, monorégimen) en una **base multirregimen** sin cambiar el motor: **`Δ decisión motor = 0`**.
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py`) se toca, y **el artefacto congelado de `replay-repro` no se mueve**. La muestra OOS de `2022` es **idéntica** a la sellada por `v2.88.40` (`expectancyR=-0.5011`, `hitRate=0.3396`, `53` ciclos).
> **Padre:** [`evidence/v2.88.40/README.md`](../v2.88.40/README.md) (corrección semántica de la atribución).
> **Nomenclatura:** `AUTO engineering release = v2.88.41-beta` · `application package = 2.11.41-beta` · `SCHEMA_VERSION = dia-d-multi-v1`.

---

## 0. Qué añade este sello

| # | Pieza | Qué hace |
|---|---|---|
| **Módulo puro** | `packages/py/application/src/bolsa_application/dia_d_multi.py` (`SCHEMA_VERSION="dia-d-multi-v1"`, `KIND="DIA_D_AUTO_MULTI_ATTRIBUTION"`) | `build_dia_d_multi_artifact(...)` pliega las corridas de varios años y **reutiliza** `payoff_decomposition`/`capture_study`/`mae_severity`/`concentration` de `dia_d_attribution` + `build_value_scorecard`. Publica `byYear`, `byRegime`, `byOperationalRegime` y la matriz `byYearByRegime` (sólo celdas medidas). Cada cubo lleva payoff + excursión media + captura de MFE + severidad de MAE por **población** (ALL/WINNERS/LOSERS). |
| **CLI** | `apps/api-python/scripts/v2_93_dia_d_multi.py` | Una pasada por año (2021-2026) con `CatalogPointInTimeUniverse` anclado al **fin de cada año** (`YYYY-12-31`; fail-closed si vacío, **sin** caer al catálogo), plan B declarado (`--fallback`) y `--check-against` (cross-check tolerante de `v2_92`). |
| **Cobertura** | `coverage` del artefacto | `yearsRequested`/`yearsMeasured`/`yearsEmpty`/`yearsNotMeasured` (con `reason`). Un año MEDIDO sin ciclos se declara `yearsEmpty`; un año sin ventana declarada cae en `sin_ventana_declarada`. |
| **Guardián** | `apps/api-python/tests/test_dia_d_bump_guard.py` | Extendido a `v2_93`; `meta.bump` alineado a `2.11.41-beta` en `v2_89/v2_90/v2_91/v2_92/v2_93`. |

---

## 1. Afirmaciones falsables

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|
| **1** | **Cobertura declarada:** `yearsMeasured ∪ yearsNotMeasured = yearsRequested`; cada año no medido lleva `reason`; ningún año se rellena con `0`. | Un año pedido ausente de ambas listas o un relleno con `0`. | `yearsRequested=['2021'..'2026']`; `yearsMeasured=['2021'..'2025']`; `yearsNotMeasured=[{year:'2026',reason:'sin_universo_pit'}]`; `yearsEmpty=['2021']`. Unión = `yearsRequested` (test `test_coverage_fails_closed_when_a_requested_year_has_no_window`). |
| **2** | **Consistencia de la matriz:** para cada año, `Σ cycles` de sus celdas `byYearByRegime` == `byYear[año].cycles`. | Una celda huérfana o un año descolgado. | `2022`=`53`, `2023`=`10`, `2024`=`8`, `2025`=`22` (celdas y filas coinciden; `test_by_year_by_regime_and_matrix_are_consistent`). |
| **3** | **Separación por población:** `LOSERS` y `WINNERS` de un régimen tienen `meanMaeR` divergentes; en `2022`/`high_vol` se reproduce `LOSERS` `< -1R` ≈ `94.29 %` y `WINNERS` ≈ `11.11 %`. | Que la fracción de TODOS se presente como "perdedores". | `2022/high_vol`: `LOSERS` `< -1R` `33/35` (**94.29 %**) vs `WINNERS` `2/18` (**11.11 %**). Global `high_vol`: `LOSERS` `42/45` (**93.33 %**) vs `WINNERS` `3/35` (**8.57 %**). |
| **4** | **Excursión acotada:** todo `captureRatio` en `[0, +inf)`, `aboveOneCount` declarado, `reversedCount` estable. | Un `captureRatio` negativo o una explosión por MFE diminuto. | `captureRatio`: media `0.2022`, mediana `0.0`, máx `0.6237`, `aboveOneCount=0`; `reversedCount=11`; `captureStudy.measuredCycles=91`, `notMeasuredCycles=2`. |
| **5** | **Determinismo:** dos corridas ⇒ payload **byte a byte** idéntico (sin reloj/ULID). | Cualquier reloj o aleatorio en el payload. | Dos corridas `2021-2026` `identical=True`; `sha256 6ec29bfdbba904f059e6d2959367c584abba8230a5685404a5ff52f952ecdfdc`; `90 473 B` (`test_artifact_is_deterministic`). |
| **6** | **Instrumento congelado intacto:** `replay-repro` byte a byte y `git diff` sin ficheros de motor. | Editar motor o el artefacto congelado. | `git diff --name-only HEAD -- apps packages` = sólo `dia_d_multi.py`, `test_dia_d_multi.py`, `v2_93_…py`, `meta.bump` de `v2_89/90/91/92`, `test_dia_d_bump_guard.py`, `package.json` ⇒ **`Δ motor = 0`**. |
| **7** | **Sin contrato:** `contract:check` sin cambios (la atribución es Python puro, no viaja por OpenAPI). | DTO/OpenAPI regenerado. | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |

---

## 2. Medición multirregimen 2021-2026 (corrida **real**, PostgreSQL)

Comando: `uv run --no-sync python apps/api-python/scripts/v2_93_dia_d_multi.py --from-year 2021 --to-year 2026 --universe pit --out operability_runs/dia-d-auto/multi-2021_2026.json`

### 2.1 Cobertura y ventanas

| Año | Medido | Ventana efectiva | Ciclos | `truncationReason` | `windowFallback` |
|---|---|---|---|---|---|
| 2021 | sí (**`yearsEmpty`**) | `2021-09-15 → 2022-01-28` | **0** | `null` | `null` |
| 2022 | sí | `2021-09-15 → 2023-01-27` | **53** | `null` | `null` |
| 2023 | sí | `2022-08-26 → 2024-01-29` | **10** | `null` | `null` |
| 2024 | sí | `2023-08-24 → 2025-01-29` | **8** | `null` | `null` |
| 2025 | sí | `2024-08-22 → 2026-01-29` | **22** | `null` | `null` |
| 2026 | **no** | — | — | — | motivo `sin_universo_pit` |

**Por qué `2026` no se mide (declarado, no inventado).** El watch `PIT` se ancla al **fin de año** (`2026-12-31`) y `availability_until` es el **MAX real de barras durables** (la última barra es anterior a `2026-12-31`); `eligible_at` es fail-closed, así que el ancla futura **no** aporta miembros (`eligible_at('2026-12-31') = 0`). Membresías elegibles por ancla: `2021=74`, `2022=74`, `2023=74`, `2024=75`, `2025=75`, **`2026=0`**. `2026` es, además, **año parcial** a `2026-10-03`.

**`2021` medido pero vacío.** La corrida se ejecutó (ventana efectiva `2021-09-15 → 2022-01-28`) y **no** aportó ningún ciclo medible (`cyclesMeasured=0`); se declara en `coverage.yearsEmpty` y **no** aparece como fila en `byYear` (un vacío no se rellena con `0`).

### 2.2 Resumen global

| Bloque | Valor |
|---|---|
| Veredicto | **`REFUTED`** (`negative_expectancy`) · `evidenceQuality=`**`STRONG`** |
| Muestra | **`93`** ciclos · `wins=45` / `losses=48` |
| Expectativa | `expectancyR=`**`-0.0094`** · `hitRate=0.4839` · `realizedRTotal=-0.8752` |
| Payoff | `avgWinR=+1.4123` · `avgLossR=-1.3423` · `payoffRatio=1.0522` · `identityGap=7.46e-17` |
| Concentración | **`concentrated`** · `expectancyWithoutWorstR=+0.0199` · `signFlipsWithoutWorst=true` · peor `5`=`-12.0241` · mejor `5`=`+15.9728` |

### 2.3 Por AÑO (resultado × excursión)

| Año | Ciclos | `expectancyR` | `hitRate` | `meanMaeR` | Captura media | `reversed` | `WINNERS` `< -1R` | `LOSERS` `< -1R` |
|---|---|---|---|---|---|---|---|---|
| 2022 | 53 | **-0.5011** | 0.3396 | -1.3880 | 0.1429 | 7 | `2/18` (11.11 %) | `33/35` (94.29 %) |
| 2023 | 10 | +0.9151 | 0.7000 | -0.9817 | 0.3441 | 2 | `1/7` (14.29 %) | `2/3` (66.67 %) |
| 2024 | 8 | +1.5490 | 0.8750 | -0.4329 | 0.3619 | 0 | `0/7` (0.00 %) | `1/1` (100.00 %) |
| 2025 | 22 | +0.1883 | 0.5909 | -1.2039 | 0.2172 | 2 | `3/13` (23.08 %) | `9/9` (100.00 %) |

### 2.4 Por RÉGIMEN (agregado trial) y OPERATIVO

| Régimen (trial) | Operativo | Ciclos | `expectancyR` | `hitRate` | `meanMaeR` | `WINNERS` `< -1R` | `LOSERS` `< -1R` |
|---|---|---|---|---|---|---|---|
| `high_vol` | `HIGH_VOLATILITY` | **80** | **-0.1492** | 0.4375 | -1.2683 | `3/35` (8.57 %) | `42/45` (93.33 %) |
| `trend_down` | `BEAR_TREND` | 8 | +0.4576 | 0.6250 | -1.2547 | `2/5` (40.00 %) | `3/3` (100.00 %) |
| `range` | `SIDEWAYS` | 5 | +1.4795 | 1.0000 | -0.3648 | `1/5` (20.00 %) | `0/0` (n/d) |

### 2.5 Matriz AÑO × RÉGIMEN (celdas medidas)

| Año | Régimen | Ciclos | `expectancyR` | `hitRate` | `meanMaeR` | `meanMfeR` | Captura media |
|---|---|---|---|---|---|---|---|
| 2022 | `high_vol` | 53 | -0.5011 | 0.3396 | -1.3880 | 1.2408 | 0.1429 |
| 2023 | `high_vol` | 10 | +0.9151 | 0.7000 | -0.9817 | 2.6828 | 0.3441 |
| 2024 | `high_vol` | 4 | +1.7590 | 1.0000 | -0.2879 | 3.9670 | 0.3808 |
| 2024 | `trend_down` | 4 | +1.3390 | 0.7500 | -0.5778 | 3.2547 | 0.3431 |
| 2025 | `high_vol` | 13 | -0.1200 | 0.4615 | -1.3028 | 1.8074 | 0.1880 |
| 2025 | `range` | 5 | +1.4795 | 1.0000 | -0.3648 | 3.4673 | 0.4212 |
| 2025 | `trend_down` | 4 | -0.4239 | 0.5000 | -1.9315 | 1.4689 | 0.0575 |

### 2.6 Severidad de MAE (población global `ALL`)

`cycles=93` · `meanMaeR=-1.2186` · `minMaeR=-4.1436` · `< -1R` **51** (`54.84 %`) · `< -1.25R` **41** (`44.09 %`) · `< -1.5R` **35** (`37.63 %`).

**Lectura honesta (descriptiva, no causal).**

1. **La pérdida de `2022` es una mala racha de régimen, no un sesgo permanente del motor.** Con `2022` incluido el global queda `REFUTED` por un margen mínimo (`-0.0094 R/ciclo`, prácticamente plano); `2023` (`+0.9151`), `2024` (`+1.5490`) y `2025` (`+0.1883`) son **positivos**.
2. **`high_vol` no es uniformemente negativo:** agrega `-0.1492` sobre `80` ciclos, pero la matriz lo descompone en `2022 -0.5011` (53), `2023 +0.9151` (10), `2024 +1.7590` (4) y `2025 -0.1200` (13). La etiqueta de régimen **sola** no separa ganancia de pérdida.
3. **El edge global es frágil (concentración `concentrated`):** quitar **un** ciclo (el peor, `-12.02 R`) voltea el signo (`+0.0199`). La muestra no permite afirmar un edge positivo sostenido.
4. **La severidad de MAE se explica sobre todo por los perdedores:** en `high_vol`, `93.33 %` de los perdedores atraviesa `-1R` frente a `8.57 %` de los ganadores. En `range` no hay perdedores (`n=5`, `hitRate=1.0`).
5. **Premio dejado en la mesa:** captura media `0.2022` (mediana `0.0`) y `leftOnTableR` medio `1.15 R`, con `11` reversiones (llegar a `>= +1R` y cerrar en pérdida). Medido sin ratios negativos.

**Lo que NO dice:** ni que el motor pierda siempre, ni que otra ventana dé lo mismo, ni que el PAPER real coincida. `2026` está **parcial** y **no medido** (ancla PIT futura); `2021` se midió **vacío**. La muestra de años positivos es **pequeña** (`10`/`8`/`22` ciclos). `CONFIRMED` sigue reservado a la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**).

Artefacto en `operability_runs/dia-d-auto/multi-2021_2026.json` (**gitignoreado**, no viaja en el repo).

---

## 3. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest test_dia_d_auto.py test_dia_d_auto_feedback.py test_universe_point_in_time.py test_universe_point_in_time_catalog.py test_dia_d_longitudinal.py test_dia_d_attribution.py test_dia_d_multi.py test_auto_dia_d_route.py test_auto_dia_d_feedback_route.py test_dia_d_bump_guard.py -q` | **122 passed** (`v2.88.40` = `112`; **+10** de `test_dia_d_multi.py`) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (654 ficheros, 3575 dependencias) |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 526 source files** |
| `pnpm --filter @bolsa/web contract:check` | **`contract:check OK`** |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |
| smoke `v2_93 --years 2022 --universe pit` | **OK**; reproduce `-0.5011` / `53` ciclos / `33/35` perdedores `< -1R` |
| determinismo `v2_93 --from-year 2021 --to-year 2026` ×2 | **idéntico** (`sha256 6ec29bfd…`, `90 473 B`) |
| `git diff --name-only HEAD -- apps packages` | sin ficheros de motor ⇒ **`Δ motor = 0`** |

---

## 4. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **La atribución es DESCRIPTIVA, no causal:** descompone la muestra medida; no explica el mercado ni el futuro.
4. **`2026` parcial y no medido:** el ancla PIT `2026-12-31` excede la última barra durable (fail-closed); se declara.
5. **`2021` medido vacío:** corrió sin ciclos medibles; se declara `yearsEmpty`.
6. **MAE/MFE entre días (D1):** el día de entrada puede incluir excursión previa al fill.
7. **Régimen = agregado trial por día;** el sector es el del catálogo **actual**, no point-in-time (aquí no se atribuye por sector).
8. **Muestras por año pequeñas** (`10`/`8`/`22` ciclos en `2023`/`2024`/`2025`): la lectura por celda es indicativa, no concluyente.
9. **`CONFIRMED` sigue reservado** a evidencia PAPER real: el veredicto de esta ventana es `REFUTED`.
10. **No sustituye la ventana PAPER real:** `P3-2`/`P3-3` siguen **ABIERTAS**.

---

## 5. Comandos (reproducir)

```bash
# Tests puros + rutas + guardián
python -m pytest packages/py/application/tests/test_dia_d_multi.py \
  packages/py/application/tests/test_dia_d_attribution.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# Gates de CI (comandos EXACTOS)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor
pnpm window:test

# Atribución multirregimen 2021-2026 (requiere PostgreSQL; artefacto gitignoreado)
uv run --no-sync python apps/api-python/scripts/v2_93_dia_d_multi.py --from-year 2021 --to-year 2026 \
  --universe pit --json --out operability_runs/dia-d-auto/multi-2021_2026.json
```

---

## 6. Sello

- **Versión:** `2.11.41-beta` (base `2.11.40-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros modificados:** `apps/api-python/scripts/v2_89|v2_90|v2_91|v2_92…` (sólo `meta.bump`), `apps/api-python/tests/test_dia_d_bump_guard.py` (+`v2_93`), `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/dia_d_multi.py`, `packages/py/application/tests/test_dia_d_multi.py`, `apps/api-python/scripts/v2_93_dia_d_multi.py`, `docs/engineering/evidence/v2.88.41/README.md`, `docs/engineering/plan-v2-88-41-dia-d-multirregimen-2026-10-03.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Freeze del runner (re-anclado):** pendiente de commit funcional (se cita abajo).
- **Tag:** `v2.88.41-beta` (anotado) — **PENDIENTE de push**.
- **CI DE TAG:** **PENDIENTE de push**.
