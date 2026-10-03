# Evidencia cruda — `v2.88.43-beta` (AUTO · **DÍA-D-3b.3**: **BOOTSTRAP DE CICLOS** — la banda TOTAL venue × sampling, sin tocar motor)

> **Objeto:** package **`2.11.43-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** **capacidad del instrumento** sobre **DÍA-D AUTO**, advisory y read-only. Añade la **segunda mitad** de la incertidumbre del instrumento (muestreo de ciclos) a la banda del sorteo del venue de `v2.88.42`, y las compone en la **banda TOTAL** por ley de varianza total. **`Δ decisión motor = 0`**.
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py`) se toca, y el artefacto congelado de `replay-repro` no se mueve.
> **Padre:** [`evidence/v2.88.42/README.md`](../v2.88.42/README.md) (banda del sorteo del venue, punto → banda).
> **Nomenclatura:** `AUTO engineering release = v2.88.43-beta` · `application package = 2.11.43-beta` · `SCHEMA_VERSION = dia-d-multi-sampling-v1` (ledger `dia-d-multi-cycle-ledger-v1`).

---

## 0. Qué añade este sello

| # | Pieza | Qué hace |
|---|---|---|
| **Módulo puro** | `packages/py/application/src/bolsa_application/dia_d_multi_sampling.py` (`SCHEMA_VERSION="dia-d-multi-sampling-v1"`, `KIND="DIA_D_AUTO_MULTI_SAMPLING"`) | `build_cycle_ledger` publica el **ledger de ciclos** de UN sorteo (una fila por ciclo con `realizedR`/MAE/MFE y etiquetas `year`/`regime`/`operationalRegime`). `build_sampling_artifact` pliega los `K` ledgers en la descomposición **venue/sampling/total** por métrica (`expectancyR`/`realizedRTotal`/`hitRate`), la banda TOTAL (percentiles 2.5/97.5 del pool `K × B`), `varianceShare` y citabilidad por eje. PRNG propio determinista (SplitMix64 sobre `sha256`), estable entre versiones. |
| **Ledger** | `dia-d-multi-cycle-ledger-v1` | `v2_93 --cycles-out` escribe el ledger; `v2_94 --cycles` lo propaga por sorteo (`draw-XX/multi-cycles.json`) reutilizando las `K` pasadas que ya ejecuta (coste extra de harness `= 0`). **Sin `--cycles`, la salida de `v2_94` es byte-idéntica a `v2.88.42`.** |
| **CLI** | `apps/api-python/scripts/v2_95_dia_d_multi_bootstrap.py` | Consumidor **puro** de `--out-dir` (no re-ejecuta el harness): reconstruye la banda del venue con `build_band_artifact`, cruza el sorteo 0 contra el sello (`--check-against`) y escribe el JSON combinado (`--resamples`, `--seed`, `--out`). |
| **Fragilidad** | `fragility` por cubo | Declara `fragile` + motivos (`insufficient_draws`, `few_cycles_per_draw`) para que `pointCitable` y `scientifically strong` no se confundan. |
| **Guardián** | `apps/api-python/tests/test_dia_d_bump_guard.py` | Extendido a `v2_95`; `meta.bump` alineado a `2.11.43-beta` en `v2_89/v2_90/v2_91/v2_92/v2_93/v2_94/v2_95`. |
| **Tests que muerden** | `packages/py/application/tests/test_dia_d_multi_sampling.py` | `14` tests: ledger (etiquetas/huecos de excursión); `totalVar = venueVar + samplingVar` y `shares` suman 1; `samplingVar = 0` con sorteos constantes; `realizedRTotal = n·expectancy`; cubo ausente baja `drawsWithCell`; sin sorteos ⇒ `None`/`sin_muestra`; citabilidad por eje (cruza cero / banda estrecha); `K<2` ⇒ `insufficient_draws`; fragilidad; cruce con la banda del venue; determinismo y contrato. |

---

## 1. Afirmaciones falsables

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|
| **1** | **La banda del venue no se mueve:** `v2_95` reconstruye la banda `v2.88.42` **byte a byte** (bands + validity + coverage), sin más cambio que `meta.bump`. | Que la reconstrucción difiera del sello del venue. | Comparación de `global`/`byYear`/`byRegime`/`byOperationalRegime`/`byYearByRegime`/`coverage` contra `multi-band-2021_2026.v2.88.42.bak.json` ⇒ **idénticos** (`True`). |
| **2** | **Autochequeo `k=0`:** el sorteo 0 (producción) reproduce el sello `v2.88.41` (`expectancyR=-0.0094`, `93` ciclos, `REFUTED`, `STRONG`) y `venueBandCrossCheck.evidenceDrift=False`. | Que el sorteo 0 mida otra cosa. | `venueBandCrossCheck={available:true, evidenceDrift:false, driftedKeys:[]}`; `venue_cross_check` del sorteo 0 contra `multi-2021_2026.json`. |
| **3** | **Varianza total declarada:** `totalVar = venueVar + samplingVar` y `varianceShare.venue + varianceShare.sampling = 1`. | Una descomposición que no cierre. | `test_total_variance_is_venue_plus_sampling_and_shares_sum_to_one`; GLOBAL `varianceShare = {venue 0.2734, sampling 0.7266}`. |
| **4** | **El bootstrap no inventa ruido:** con sorteos de ciclos constantes, `samplingVar = 0` y la banda no se ensancha. | Un `samplingVar > 0` sin dispersión real. | `test_sampling_variance_is_zero_when_each_draw_is_constant`; celda `2023 × trend_down` (`n=2`, ciclos constantes) ⇒ `samplingVar = 0.0000`. |
| **5** | **Regla del hueco:** celda sin muestra ⇒ `None`/`NOT_MEASURED`, nunca `0`. | Un `0` donde no hay muestra. | `test_no_draws_declares_none_not_zero`, `test_cell_absent_in_a_draw_lowers_draws_with_cell`. |
| **6** | **`Δ motor = 0`:** el ledger se escribe desde `v2_93`; ningún fichero de motor cambia. | Editar motor o el artefacto congelado. | `git status --porcelain` del motor = **vacío**; `git diff --name-only` = módulo/tests/CLIs/docs/bumps. |
| **7** | **Determinismo:** mismo `B` y misma semilla ⇒ payload **byte a byte** idéntico. | Cualquier reloj o azar global. | Dos corridas `v2_95 --resamples 2000` ⇒ `sha256 0AF78E48…` idéntico (`test_artifact_is_deterministic_and_declares_its_contract`). |
| **8** | **El bootstrap no se apoya en `numpy`:** PRNG propio, reproducible entre versiones de Python. | Depender de un PRNG cambiante. | `_mix64` (SplitMix64) sobre `sha256(seed|dim|year|regime|draw)`; `packages/py/application` no depende de `numpy`. |

---

## 2. Medición real (offline, PostgreSQL): bootstrap `B = 2000` sobre `K = 12` sorteos, 2021-2026

Primero se regeneraron los `K = 12` sorteos con su ledger: `python apps/api-python/scripts/v2_94_dia_d_multi_band.py --from-year 2021 --to-year 2026 --universe pit --draws 12 --reuse --cycles --check-against operability_runs/dia-d-auto/multi-2021_2026.json` (`≈ 35 min`). Después el bootstrap (instantáneo, `≈ 5 s`): `python apps/api-python/scripts/v2_95_dia_d_multi_bootstrap.py --out-dir operability_runs/dia-d-auto-band --resamples 2000 --check-against operability_runs/dia-d-auto/multi-2021_2026.json`.

Cada sorteo es una pasada **completa** del harness multirregimen (`v2_93`); `k = 0` es la realización de producción y `k = 1..11` desplazan el ancla del seed.

### 2.1 Cobertura (por año, sobre `12` sorteos)

| Año | Medidos | Vacíos | No medidos | Motivo |
|---|---|---|---|---|
| 2021 | 0/12 | **12/12** | 0/12 | medido sin ciclos en TODOS los sorteos |
| 2022 | **12/12** | 0/12 | 0/12 | — |
| 2023 | **12/12** | 0/12 | 0/12 | — |
| 2024 | **12/12** | 0/12 | 0/12 | — |
| 2025 | **12/12** | 0/12 | 0/12 | — |
| 2026 | 0/12 | 0/12 | **12/12** | `sin_universo_pit` (ancla `2026-12-31` futura) |

### 2.2 Cubo GLOBAL — venue vs sampling vs total

| Eje | `expectancyR` (media) | banda `expectancyR` | banda `realizedRTotal` | var (sobre R total) | SE | `pointCitable` |
|---|---|---|---|---|---|---|
| venue | -0.0283 | `[-0.1813, +0.1248]` | `[-16.859, +10.857]` | 75.060 | 2.501 | **False** (cruza cero) |
| sampling | -0.0283 | — | — | 195.759 | 4.039 | **False** |
| **total** | -0.0283 | `[-0.3784, +0.3401]` | `[-35.065, +28.569]` | **270.819** | **4.751** | **False** (cruza cero) |

**`varianceShare` GLOBAL = venue `0.2734` / sampling `0.7266`.** La **varianza del muestreo de ciclos domina** (~73 %) sobre la del sorteo del venue (~27 %): la pregunta de la fase («¿cuánto venue y cuánto sampling?») queda **medida**, no narrada. La banda TOTAL de `expectancyR` cruza cero con holgura (`[-0.3784, +0.3401]`).

### 2.3 Por AÑO (banda del venue → banda TOTAL y citabilidad)

| Año | `expectancyR` media | venue `R total` | total `R total` | `share` (venue/samp) | venue | sampling | **total** |
|---|---|---|---|---|---|---|---|
| 2022 | **-0.4363** | `[-35.872, -7.927]` | `[-45.185, +3.533]` | 0.356 / 0.644 | True | True | **False** |
| 2023 | +0.3658 | `[-5.544, +11.983]` | `[-8.035, +16.689]` | 0.458 / 0.542 | False | False | False |
| 2024 | **+1.2856** | `[+6.740, +12.392]` | `[+0.805, +18.517]` | 0.189 / 0.811 | True | True | **True** |
| 2025 | +0.2477 | `[-0.215, +10.404]` | `[-8.512, +18.594]` | 0.165 / 0.835 | False | False | False |

**Hallazgo central:** `2022` era **citable** en `v2.88.42` (banda del venue `[-0.6406, -0.1391]`, `pointCitable=True`). Con la incertidumbre de muestreo, su banda **TOTAL** de R total pasa a `[-45.185, +3.533]` y **cruza cero** ⇒ **deja de ser citable**. Lo mismo ocurre con `range` y `high_vol` (véase 2.4). **Sólo `2024` sobrevive la citabilidad en los tres ejes.**

### 2.4 Por RÉGIMEN (trial)

| Régimen | `expectancyR` media | venue `R total` | total `R total` | `share` (venue/samp) | venue | sampling | **total** | fragilidad |
|---|---|---|---|---|---|---|---|---|
| `high_vol` | **-0.1556** | `[-23.319, -1.114]` | `[-40.211, +16.420]` | 0.236 / 0.764 | True | False | **False** | — |
| `range` | **+1.1017** | `[+1.124, +8.284]` | `[-0.025, +12.134]` | 0.277 / 0.723 | True | True | **False** | `few_cycles_per_draw` |
| `trend_down` | +0.5234 | `[-0.154, +7.556]` | `[-5.523, +12.507]` | 0.259 / 0.741 | False | False | False | `few_cycles_per_draw` |

`range` y `high_vol` eran **citables** en `v2.88.42`; su banda **TOTAL** cruza cero ⇒ dejan de serlo. El eje **sampling** domina en todos los cubos salvo donde el `n` es minúsculo.

### 2.5 Matriz AÑO × RÉGIMEN (citabilidad por eje)

| Año | Régimen | `drawsWithCell` | venue | sampling | **total** | fragilidad |
|---|---|---|---|---|---|---|
| 2022 | `high_vol` | 12 | True | True | **False** | — |
| 2023 | `high_vol` | 12 | False | False | False | — |
| 2023 | `trend_down` | **2** | True | True | True | `few_cycles_per_draw` |
| 2024 | `high_vol` | 12 | True | True | True | `few_cycles_per_draw` |
| 2024 | `trend_down` | 12 | True | False | False | `few_cycles_per_draw` |
| 2025 | `high_vol` | 12 | False | False | False | — |
| 2025 | `range` | 12 | True | True | **False** | `few_cycles_per_draw` |
| 2025 | `trend_down` | 12 | False | False | False | `few_cycles_per_draw` |

`2023 × trend_down` (`n=2`) sigue siendo el caso que **pasa el criterio pero es frágil**: su `samplingVar = 0.0000` (los pocos ciclos son constantes) produce una banda **engañosamente estrecha** (`[-1.263, -1.139]`), y el sistema lo declara (`fragility.reasons=["few_cycles_per_draw"]`). Es exactamente la deuda metodológica que la auditoría de `v2.88.42` señaló.

### 2.6 La respuesta de la fase

> ¿Cuánto de la variabilidad restante procede del **sorteo del venue** y cuánto de **qué operaciones entran en la muestra**?

**A `K = 12`, el muestreo de ciclos aporta ≈ 73 % de la varianza total** (GLOBAL `sampling 0.7266` vs `venue 0.2734`), y en los cubos con `n` suficiente oscila entre `0.54` y `0.84`. La consecuencia práctica es dura: **la banda TOTAL elimina la citabilidad que `v2.88.42` concedía a `2022`, `range` y `high_vol`**, y sólo `2024` permanece citable. El `-0.0094` global de `v2.88.41` no sólo era un punto no citable por el venue (`v2.88.42`); tampoco lo es cuando se añade el muestreo.

**Lo que NO dice:** ni el futuro ni el PAPER real. La banda TOTAL mide **dos ejes de ruido del mismo experimento histórico** (mismo dato, misma estrategia), no la validez de la estrategia ni la independencia de mercado. `2021` se midió **vacío** en todos los sorteos; `2026` **no se midió** (ancla PIT futura). `CONFIRMED` sigue reservado a la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**).

Artefacto en `operability_runs/dia-d-auto/multi-sampling-2021_2026.json` (`91 360 B`, `sha256 58303073…`; **gitignoreado**); ledgers en `operability_runs/dia-d-auto-band/draw-XX/multi-cycles.json`.

---

## 3. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run pytest … test_dia_d_multi_sampling.py test_dia_d_multi_uncertainty.py test_dia_d_multi.py test_dia_d_attribution.py test_dia_d_longitudinal.py test_dia_d_auto.py test_dia_d_auto_feedback.py test_dia_d_bump_guard.py -q` | **110 passed** (**+14** del nuevo `test_dia_d_multi_sampling.py`) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (656 ficheros, 3590 dependencias) |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 528 source files** |
| `pnpm --filter @bolsa/web contract:check` | **`contract:check OK`** |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |
| corrida real `v2_94 --draws 12 --cycles` + `v2_95 --resamples 2000 --check-against <sello>` | **`venueBandCrossCheck.evidenceDrift=False`**; banda del venue reconstruida **byte a byte** |
| determinismo `v2_95 --resamples 2000` ×2 | **idéntico** (`sha256 0AF78E48…`) |
| `git status --porcelain -- <motor>` | **vacío** ⇒ **`Δ motor = 0`** |

---

## 4. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B), allocation ni migración cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **El bootstrap mide el MUESTREO DE CICLOS** (con reemplazo, `n` fijo), no la independencia de mercado ni el futuro.
4. **Los dos ejes se tratan como ortogonales** (ley de varianza total); la interacción real venue×sampling se aproxima por el pool `K × B`, no por un modelo explícito.
5. **`K` sorteos no son `K` muestras independientes de mercado:** son `K` realizaciones del MISMO experimento histórico con distinto sorteo del venue.
6. **REPLAY/OOS ≠ PAPER:** `CONFIRMED` sigue reservado; `P3-2`/`P3-3` siguen **ABIERTAS**.
7. **`B` es la resolución del bootstrap:** con otro `B`/semilla la banda numérica cambia (la estructura no).
8. **Cubos con `n` pequeño son frágiles** (`fragility` lo declara; p. ej. `2023 × trend_down`, `n=2`, `samplingVar=0`).
9. **`2026` no medido** y **`2021` medido vacío** se heredan declarados de `v2.88.41`/`v2.88.42`.
10. **MAE/MFE entre días (D1);** régimen = agregado trial por día; sector del catálogo **actual** (no PIT).

---

## 5. Comandos (reproducir)

```bash
# Tests puros + guardián
uv run pytest packages/py/application/tests/test_dia_d_multi_sampling.py \
  packages/py/application/tests/test_dia_d_multi_uncertainty.py \
  packages/py/application/tests/test_dia_d_multi.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# Gates de CI (comandos EXACTOS)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor
pnpm window:test

# Sorteos con ledger + bootstrap (requiere PostgreSQL; artefactos gitignoreados)
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --from-year 2021 --to-year 2026 --universe pit --draws 12 --reuse --cycles \
  --check-against operability_runs/dia-d-auto/multi-2021_2026.json
uv run --no-sync python apps/api-python/scripts/v2_95_dia_d_multi_bootstrap.py \
  --out-dir operability_runs/dia-d-auto-band --resamples 2000 \
  --check-against operability_runs/dia-d-auto/multi-2021_2026.json \
  --out operability_runs/dia-d-auto/multi-sampling-2021_2026.json
```

---

## 6. Sello

- **Versión:** `2.11.43-beta` (base `2.11.42-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/dia_d_multi_sampling.py`, `packages/py/application/tests/test_dia_d_multi_sampling.py`, `apps/api-python/scripts/v2_95_dia_d_multi_bootstrap.py`, `docs/engineering/evidence/v2.88.43/README.md`.
- **Ficheros modificados:** `apps/api-python/scripts/v2_89|v2_90|v2_91|v2_92|v2_93|v2_94…` (`meta.bump`; `v2_93` +`--cycles-out`; `v2_94` +`--cycles`), `apps/api-python/tests/test_dia_d_bump_guard.py` (+`v2_95`), `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Commits locales:** `<PENDIENTE>` (se publican en la cita del sello).
- **Tag:** `v2.88.43-beta` **PENDIENTE** de push (se cita tras el CI de tag).
