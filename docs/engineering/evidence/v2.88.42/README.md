# Evidencia cruda — `v2.88.42-beta` (AUTO · **DÍA-D-3b.2**: **DE PUNTO A BANDA** — incertidumbre del sorteo del venue en la atribución multirregimen, sin tocar motor)

> **Objeto:** package **`2.11.42-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** **capacidad del instrumento** sobre **DÍA-D AUTO**, advisory y read-only. Añade la **banda** del sorteo del venue a la atribución multirregimen de `v2.88.41` sin cambiar el motor: **`Δ decisión motor = 0`**.
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py`) se toca, y **el artefacto congelado de `replay-repro` no se mueve**. El `seed` del venue se inyecta y se **restaura byte a byte** tras cada sorteo (misma técnica sellada por `W3.3` en `v2.88.16.3`).
> **Padre:** [`evidence/v2.88.41/README.md`](../v2.88.41/README.md) (atribución multirregimen, punto).
> **Nomenclatura:** `AUTO engineering release = v2.88.42-beta` · `application package = 2.11.42-beta` · `SCHEMA_VERSION = dia-d-multi-band-v1`.

---

## 0. Qué añade este sello

| # | Pieza | Qué hace |
|---|---|---|
| **Módulo puro** | `packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py` (`SCHEMA_VERSION="dia-d-multi-band-v1"`, `KIND="DIA_D_AUTO_MULTI_BAND"`) | `build_band_artifact(draws=…)` pliega `K` artefactos `dia-d-multi-v1` y publica, por cubo (global / año / régimen trial / régimen operativo / año × régimen), `bands` (`min`/`median`/`max`/`mean`/`stdev` de `expectancyR`, `realizedRTotal`, `hitRate`, `meanMaeR`, `meanMfeR`, `captureMean`, `reversedCount`, `cycles`) y `validity` (`crossesZeroR`/`pointCitable`/`se`/`ci95HalfWidth`). Reutiliza la regla del hueco de `dia_d_multi` (sin muestra ⇒ `None`, nunca `0`). |
| **CLI** | `apps/api-python/scripts/v2_94_dia_d_multi_band.py` | Corre el harness de `v2_93` **K veces**; cada sorteo `k>0` desplaza el ancla del seed (`fill_seed(bar_tick_now + k, symbol)`) y **restaura el árbol byte a byte** (verificado); `k=0` es producción. `--draws 12`, `--reuse`, `--check-against` (cross-check tolerante de `v2_92`), `--out-dir`. |
| **Cobertura** | `coverage` de la banda | Por año pedido, en cuántos sorteos se **midió** / quedó **vacío** / **no se midió** (con motivos agregados). Un año nunca medido no se rellena. |
| **Guardián** | `apps/api-python/tests/test_dia_d_bump_guard.py` | Extendido a `v2_94`; `meta.bump` alineado a `2.11.42-beta` en `v2_89/v2_90/v2_91/v2_92/v2_93/v2_94`. |
| **Tests que muerden** | `packages/py/application/tests/test_dia_d_multi_uncertainty.py` | `9` tests: orden-estadísticos y momentos; `meanMfeR` global `None` (hueco) vs por año medido; cubo ausente baja `drawsWithCell`; `pointCitable` falso con banda que cruza cero; verdadero con banda estrecha y alejada; `K<2` ⇒ `insufficient_draws`; sin sorteos ⇒ `None`/`sin_muestra`; cobertura por año; determinismo y contrato. |

---

## 1. Afirmaciones falsables

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|
| **1** | **Autochequeo `k=0`:** el sorteo 0 (producción, sin parchear) reproduce el sello `v2.88.41` (`expectancyR=-0.0094`, `93` ciclos, `hitRate=0.4839`, `REFUTED`, `STRONG`). | Que el sorteo 0 mida otra cosa (instrumento distinto del sello). | `crossCheck.evidenceDrift=False`, `driftedKeys=[]` comparando el `summary` del sorteo 0 contra `operability_runs/dia-d-auto/multi-2021_2026.json` (sello `v2.88.41-beta`). |
| **2** | **Banda declarada:** cada cubo publica `draws`/`drawsWithCell` y `min`/`median`/`max`/`mean`/`stdev`; `validity` se **evalúa**, no se narra. | Un cubo sin banda o un `pointCitable` fijado a mano. | `K=12` en todos los cubos global/año/régimen; `GLOBAL` `realizedRTotal` `[-16.859, +10.857]`, `se=2.501`, `ci95HalfWidth=4.902`, `crossesZeroR=True`, `pointCitable=False`. |
| **3** | **`point_citable` reproducible:** el criterio es el de `W3.3` (`no cruza cero` ∧ `|mean|>1.96·SE`, `K>=2`). | Un criterio distinto o un `K<2` que cite un punto. | `test_point_citable_is_false_when_the_band_crosses_zero`, `…_is_true_when_the_band_is_away_from_zero_and_narrow`, `test_insufficient_draws_blocks_citability`. |
| **4** | **Regla del hueco:** celda sin muestra ⇒ `None`/`NOT_MEASURED`, nunca `0`; `meanMfeR` global no se inventa. | Un `0` donde no hay muestra. | `test_band_of_a_missing_metric_is_none_never_zero`, `test_no_draws_declares_none_not_zero`; `meanMfeR` global `=None`. |
| **5** | **`Δ motor = 0`:** tras cada sorteo el árbol se restaura byte a byte; `git diff` sin ficheros de motor; `replay-repro` intacto. | Editar motor o el artefacto congelado. | `git status --porcelain -- apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` = **vacío**; `git diff --name-only` = sólo `v2_89…v2_93` (`meta.bump`), `test_dia_d_bump_guard.py`, `package.json`. |
| **6** | **Determinismo:** mismas `K` semillas ⇒ payload **byte a byte** idéntico (sin reloj/ULID). | Cualquier reloj o azar en el payload. | Dos reconstrucciones `--reuse` idénticas: `sha256 4e87a3e6318a208ae6f601f538f98d74a253e725214701ca6e42e3caff28e6e4` (`45 983 B`); `test_artifact_is_deterministic_and_declares_its_contract`. |

---

## 2. Medición real (offline, PostgreSQL): banda del sorteo del venue, `K = 12`, 2021-2026

Comando: `python apps/api-python/scripts/v2_94_dia_d_multi_band.py --from-year 2021 --to-year 2026 --universe pit --draws 12 --reuse --check-against operability_runs/dia-d-auto/multi-2021_2026.json --out operability_runs/dia-d-auto/multi-band-2021_2026.json`

Cada sorteo es una pasada **completa** del harness multirregimen (`v2_93`); `k = 0` es la realización de producción y `k = 1..11` desplazan el ancla del seed. Duración de la corrida real: `≈ 30 min` (12 pasadas).

### 2.1 Cobertura de la banda (por año, sobre `12` sorteos)

| Año | Medidos | Vacíos | No medidos | Motivo |
|---|---|---|---|---|
| 2021 | 0/12 | **12/12** | 0/12 | medido sin ciclos en TODOS los sorteos |
| 2022 | **12/12** | 0/12 | 0/12 | — |
| 2023 | **12/12** | 0/12 | 0/12 | — |
| 2024 | **12/12** | 0/12 | 0/12 | — |
| 2025 | **12/12** | 0/12 | 0/12 | — |
| 2026 | 0/12 | 0/12 | **12/12** | `sin_universo_pit` (ancla `2026-12-31` futura) |

### 2.2 Cubo GLOBAL (banda de `12` sorteos)

| Métrica | `min` | `median` | `max` | `mean` | `stdev` |
|---|---|---|---|---|---|
| `cycles` | 70 | 92.5 | 104 | 89.5 | 8.3516 |
| `expectancyR` | **-0.1813** | -0.0181 | **+0.1248** | **-0.0283** | 0.09675 |
| `realizedRTotal` | **-16.859** | -1.652 | **+10.857** | **-2.946** | 8.6637 |
| `hitRate` | 0.4086 | 0.4825 | 0.5402 | 0.4758 | 0.03706 |
| `meanMaeR` | -1.2925 | -1.1645 | -1.0632 | -1.1757 | 0.06303 |
| `captureMean` | 0.1661 | 0.2000 | 0.2146 | 0.1956 | 0.01566 |
| `reversedCount` | 4 | 8 | 11 | 8.0 | 2.2730 |

**`validity` GLOBAL:** `crossesZeroR=`**`True`** · `se=2.501` · `ci95HalfWidth=4.902` · `pointCitable=`**`False`**.

### 2.3 Por AÑO (banda de `realizedRTotal` y citabilidad)

| Año | `expectancyR` media | `expectancyR` banda | `realizedRTotal` banda | `drawsWithCell` | `pointCitable` |
|---|---|---|---|---|---|
| 2022 | **-0.4363** | `[-0.6406, -0.1391]` | `[-35.872, -7.927]` | 12 | **True** |
| 2023 | +0.3658 | `[-0.5040, +0.9151]` | `[-5.544, +11.983]` | 12 | False (cruza cero) |
| 2024 | **+1.2856** | `[+0.8425, +1.6662]` | `[+6.740, +12.392]` | 12 | **True** |
| 2025 | +0.2477 | `[-0.0107, +0.6120]` | `[-0.215, +10.404]` | 12 | False (cruza cero) |

### 2.4 Por RÉGIMEN (trial y operativo)

| Régimen (trial) | Operativo | `expectancyR` media | `realizedRTotal` banda | `pointCitable` |
|---|---|---|---|---|
| `high_vol` | `HIGH_VOLATILITY` | **-0.1556** | `[-23.319, -1.114]` | **True** |
| `range` | `SIDEWAYS` | **+1.1017** | `[+1.124, +8.284]` | **True** |
| `trend_down` | `BEAR_TREND` | +0.5234 | `[-0.154, +7.556]` | False (cruza cero) |

### 2.5 Matriz AÑO × RÉGIMEN (banda y citabilidad)

| Año | Régimen | `drawsWithCell` | `expectancyR` media | `realizedRTotal` banda | `pointCitable` |
|---|---|---|---|---|---|
| 2022 | `high_vol` | 12 | -0.4363 | `[-35.872, -7.927]` | True |
| 2023 | `high_vol` | 12 | +0.3820 | `[-5.544, +11.983]` | False |
| 2023 | `trend_down` | **2** | -1.2010 | `[-1.263, -1.139]` | True (n=2, frágil) |
| 2024 | `high_vol` | 12 | +1.3920 | `[+2.033, +8.305]` | True |
| 2024 | `trend_down` | 12 | +1.2030 | `[+0.049, +5.356]` | True |
| 2025 | `high_vol` | 12 | -0.0390 | `[-5.632, +5.399]` | False |
| 2025 | `range` | 12 | +1.1020 | `[+1.124, +8.284]` | True |
| 2025 | `trend_down` | 12 | -0.1100 | `[-3.279, +2.724]` | False |

### 2.6 Veredicto por sorteo (el dato que `v2.88.41` citaba como punto)

`REFUTED` ×7 · `OOS_SUPPORTED` ×3 · `MIXED` ×2 (de `12`). El **signo** del edge global **cambia entre sorteos** (`expectancyR` de `-0.1813` a `+0.1248`).

**Lectura honesta.**

1. **El hallazgo es el resultado, no un fallo:** el punto global de `v2.88.41` (`-0.0094`) **no es citable**. La banda de R total cruza cero (`[-16.859, +10.857]`, `SE=2.501`, `IC95 ±4.902`) y el veredicto alterna entre `REFUTED`/`OOS_SUPPORTED`/`MIXED` según el sorteo. Citar `-0.0094` sin banda era citar un dado.
2. **Determinismo ≠ validez:** `k=0` reproduce el sello byte a byte (autochequeo) **porque es el mismo dado**, no porque el resultado sea estable.
3. **Hay celdas estrechas y repetibles:** `2022` (negativo), `2024` (positivo), `range` (positivo) y `high_vol` (negativo) **no** cruzan cero y su `|media|>1.96·SE`. Son las únicas afirmaciones que la banda permite sostener a `K=12`.
4. **`trend_down` y `2023`/`2025` no son citables:** su banda cruza cero; el signo medio es un artefacto del sorteo.
5. **Cuidado con `n` pequeño:** la celda `2023 × trend_down` sólo aparece en `2/12` sorteos (`drawsWithCell=2`); su banda `[-1.263, -1.139]` pasa el criterio pero es **frágil** y así se declara.

**Lo que NO dice:** ni el futuro ni el PAPER real. La banda mide el **ruido del sorteo del venue** (mismo dato, misma estrategia), no la incertidumbre de muestreo del ciclo. `2021` se midió **vacío** en todos los sorteos; `2026` **no se midió** (ancla PIT futura). `CONFIRMED` sigue reservado a la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**).

Artefacto en `operability_runs/dia-d-auto/multi-band-2021_2026.json` (**gitignoreado**, no viaja en el repo); sorteos en `operability_runs/dia-d-auto-band/draw-XX/multi.json`.

---

## 3. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `uv run pytest … test_dia_d_multi_uncertainty.py test_dia_d_multi.py … test_dia_d_bump_guard.py -q` | **131 passed** (`v2.88.41` = `122`; **+9** del nuevo test) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (655 ficheros, 3580 dependencias) |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 527 source files** |
| `pnpm --filter @bolsa/web contract:check` | **`contract:check OK`** |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |
| corrida real `v2_94 --draws 12 --check-against <sello>` | **`crossCheck.evidenceDrift=False`**; `GLOBAL pointCitable=False` |
| determinismo `v2_94 --reuse` ×2 | **idéntico** (`sha256 4e87a3e6…`, `45 983 B`) |
| `git status --porcelain -- auto_simulation_worker.py` · `git diff --name-only` | **vacío** en motor ⇒ **`Δ motor = 0`** |

---

## 4. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B), allocation ni migración cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **La banda mide el ruido del SORTEO del venue**, no la incertidumbre de muestreo del ciclo (esa, bootstrap, es un eje separado) ni el futuro.
4. **REPLAY/OOS ≠ PAPER:** `CONFIRMED` sigue reservado; `P3-2`/`P3-3` siguen **ABIERTAS**.
5. **`K = 12` es la resolución de la banda:** con otro `K` la banda cambia; `K<2` no cita un punto (`insufficient_draws`).
6. **Cubos con `n` pequeño son frágiles** (`drawsWithCell` es el `n` efectivo; p. ej. `2023 × trend_down`, `n=2`).
7. **`2026` parcial/no medido** y **`2021` medido vacío** se heredan declarados de `v2.88.41`.
8. **MAE/MFE entre días (D1);** régimen = agregado trial por día; sector del catálogo **actual** (no PIT).
9. **Muchas celdas pueden dar `pointCitable=False`:** ese es el **hallazgo**, no un fallo.

---

## 5. Comandos (reproducir)

```bash
# Tests puros + rutas + guardián
uv run pytest packages/py/application/tests/test_dia_d_multi_uncertainty.py \
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

# Banda del sorteo del venue, K=12, 2021-2026 (requiere PostgreSQL; artefacto gitignoreado)
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --from-year 2021 --to-year 2026 --universe pit --draws 12 --reuse \
  --check-against operability_runs/dia-d-auto/multi-2021_2026.json \
  --out operability_runs/dia-d-auto/multi-band-2021_2026.json
```

---

## 6. Sello

- **Versión:** `2.11.42-beta` (base `2.11.41-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py`, `packages/py/application/tests/test_dia_d_multi_uncertainty.py`, `apps/api-python/scripts/v2_94_dia_d_multi_band.py`, `docs/engineering/evidence/v2.88.42/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.42-2026-10-03.md`.
- **Ficheros modificados:** `apps/api-python/scripts/v2_89|v2_90|v2_91|v2_92|v2_93…` (sólo `meta.bump`), `apps/api-python/tests/test_dia_d_bump_guard.py` (+`v2_94`), `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Freeze del runner (re-anclado):** el sello mueve `apps`/`packages`; `WINDOW_CONFIG` (`scripts/lib/window-forward.mjs`) se **re-ancló** al árbol del commit funcional de este sello. El pin vive en `scripts/`, así que editarlo **no** mueve a su vez el árbol congelado; `git rev-parse "HEAD:apps" "HEAD:packages"` coincide con el pin y el dry-run declara `freeze OK`.
- **Tag / CI de tag:** **PENDIENTE (se cita POST-TAG)** — este sello es local; el tag anotado y el `Release tag CI` se emiten al empujar. `replay-repro` esperado `REPRODUCIDO` `1E3ADAC2…` (el artefacto congelado **no** se toca).
