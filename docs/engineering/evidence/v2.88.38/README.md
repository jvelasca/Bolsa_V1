# Evidencia cruda — `v2.88.38-beta` (AUTO · **DÍA-D**: primera **ventana longitudinal OOS** con el universo `PIT` **en uso** — estabilidad del edge + MAE/MFE por ciclo, sin tocar motor)

> **Objeto:** package **`2.11.38-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** **medición** (no capacidad) sobre **DÍA-D AUTO**, advisory y read-only. Cierra el salto pendiente tras `v2.88.37`: el proveedor `Universe(D)` pasa de «capacidad probada» a **usado en una corrida real** que produce un **OOS por día `D`** (expectativa, acierto, estabilidad temporal y excursiones MAE/MFE) sobre una **ventana contigua acotada** (año natural 2022).
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py`) se toca, y **el artefacto congelado de `replay-repro` no se mueve**. `AUTO_ENGINE_SIM_REAL_PRICE` sigue **OFF** en el instrumento.
> **Padre:** [`evidence/v2.88.37/README.md`](../v2.88.37/README.md) (proveedor `Universe(D)` real).
> **Nomenclatura:** `AUTO engineering release = v2.88.38-beta` · `application package = 2.11.38-beta`.

---

## 0. Qué entrega este sello

| # | Pieza | Qué añade |
|---|---|---|
| **1 · Agregado puro** | `packages/py/application/src/bolsa_application/dia_d_longitudinal.py` | `excursions(...)`/`excursion_for_cycle(...)` (**MAE/MFE en R** desde barras D1, normalizado por el riesgo al nacer el ciclo), `bucket_series(...)`/`stability_summary(...)` (series por año/trimestre/mes) y `build_dia_d_longitudinal_artifact(...)` (payload determinista que **reutiliza** `build_value_scorecard`, sin duplicar umbrales ni veredictos). `longest_operable_run(...)` para el plan B declarado. **Capa nueva**: no modifica `score_replay` ni `RoundTrip.to_dict`. |
| **2 · CLI** | `apps/api-python/scripts/v2_91_dia_d_longitudinal.py` | Carga el universo `PIT` (**modo histórico**), fija la ventana (`--year 2022` o `--from/--to`), corre **una** pasada del replay durable y agrega. Publica una **sonda** (`probe`: ventana pedida vs efectiva, días, operables, ciclos, `truncationReason`) y, si la corrida trunca, reintenta **una vez** sobre el **tramo operable más largo** y lo declara (`windowFallback`); **nunca** inventa la muestra. |
| **3 · Modo histórico PIT** | `packages/py/application/src/bolsa_application/universe_point_in_time_catalog.py` | `historical=True` (`--pit-historical`, default ON en `v2_91`) hace que el **suelo** de elegibilidad `active_from` salga de la disponibilidad **REAL** de barras (`availability_from`), porque `instruments.created_at` es el **alta en catálogo** (reciente) y **NO** una fecha de listado: usarlo de suelo dejaba 2022 **sin un solo elegible**. La cota **SUPERIOR** (`active_until`, baja/delistado) **no** cambia: sigue corrigiendo el survivorship. La procedencia se declara en `coverage()` (`historicalMode`, `provenance.active_from`). |
| **4 · Tests** | `packages/py/application/tests/test_dia_d_longitudinal.py` (+ `.../test_universe_point_in_time_catalog.py`) | 14 tests puros del agregado/MAE-MFE + **5 nuevos** del modo histórico (bloqueo original, suelo REAL, techo intacto, procedencia declarada, determinismo). |
| **5 · Sello** | `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md` | Bump `2.11.37-beta` → `2.11.38-beta`; `meta.bump` de `v2_89`/`v2_90`/`v2_91` alineado (guardián `test_dia_d_bump_guard.py`). |

**Procedencia del universo en modo histórico (declarada, no disfrazada):**

| Campo | Fuente | Procedencia |
|---|---|---|
| `availability_from` / `availability_until` | `MIN`/`MAX(timestamp)` de `ohlcv_bars` D1 | **REAL** |
| `active_from` | `availability_from` (**modo histórico**) | **DECLARADO** (≈ fecha de listado; `created_at` no lo es) |
| `active_until` | `is_active` (abierto) / última barra (baja) | **DECLARADO** |
| `sector_at` | `instruments.sector` actual | **DECLARADO** (no point-in-time) |

---

## 1. Afirmaciones falsables

| # | Hallazgo | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|---|
| **D35-02** 🟢 | El `Universe(D)` **se usa** | Con `--universe pit` el watch sale del proveedor (`meta.watchSource="pit"`, `survivorBiasRisk=false`) y alimenta una corrida **medida** (no un `NOT_MEASURED`). | Volver a `catalog`; dejar `survivorBiasRisk=true`; rellenar el watch a mano. | smoke 2022 (abajo), `meta.watchSource` |
| **Histórico** 🟢 | El suelo no bloquea la historia | En **modo histórico** el suelo `active_from` = `availability_from` (REAL) **sin** relajar el techo: un delistado sigue cerrando. | Usar `created_at` de suelo ⇒ **0 elegibles** en 2022. | `test_historical_mode_uses_real_bar_availability_as_floor`, `test_historical_mode_does_not_relax_the_upper_bound` |
| **Honestidad** 🟢 | Procedencia | `coverage()` declara `historicalMode` y el `active_from` usado; nunca disfraza `created_at` de PIT genuino. | Ocultar el modo o la procedencia. | `test_historical_mode_is_declared_in_coverage_provenance`, `test_default_mode_floor_is_created_at_and_blocks_history_before_catalog` |
| **MAE/MFE** | La excursión es medible | MAE/MFE = extremos **entre días (D1)** normalizados por el riesgo del ciclo, con la **dirección inferida** de la geometría `stop` vs `entry` (long: `stop < entry`). Geometría imposible ⇒ **hueco** (`None`), no `0`. | Presentarlos como intradía; rellenar un hueco con `0`; inventar la dirección. | `test_dia_d_longitudinal.py` (long/short, geometría imposible, hueco declarado) |
| **C4** | `None ≠ 0` | Un hueco se declara (`None`/`NOT_MEASURED`); la media de una muestra vacía es `None`. | Rellenar con `0`. | tests del agregado |
| **Estabilidad** | Sin fingir cubos | La dispersión intra-ventana es sobre los **cubos** reales; `0` ciclos ⇒ `expectancyR=None`, no `0`. | Contar como `0`. | `stability_summary` + asserciones |
| **Δ motor** | No regresión | Ningún fichero de motor tocado; el default (`historical=False`) no cambia; el artefacto congelado de `replay-repro` no se mueve. | Editar motor o el artefacto. | `git diff` de alcance (abajo) |

---

## 2. Corrida longitudinal 2022 (smoke **medido**, PostgreSQL real)

Comando: `uv run --no-sync python apps/api-python/scripts/v2_91_dia_d_longitudinal.py --year 2022 --json --out operability_runs/dia-d-auto/longitudinal-2022-01-03_2022-12-30.json`

| Bloque | Valor |
|---|---|
| Universo (`PIT`, histórico) | `instrumentsConsidered=303`, `membersMaterialized=76`, `excludedNoBars=227`, `excludedInsufficientBars=0`, `excludedNoSector=0`, `historicalMode=true` |
| Watch | `watchSource="pit"`, `survivorBiasRisk=false`, `watchSize=20` |
| Ventana | pedida `2022-01-03 → 2022-12-30` (257 días); efectiva `2021-09-15 → 2023-01-27` (`history=90d`, `horizon=20d`); **`operableDays=218`** |
| Replay | `353` ticks, `horizon.completed=true`, `truncationReason=null`, **`windowFallback=null`** (sin plan B) |
| Muestra | `measuredCycles=53`, `openPositions=7`, `unmeasuredCount=0` |
| **Veredicto** | **`REFUTED`** (`negative_expectancy`) · `evidenceQuality=STRONG` |
| Expectativa / acierto | `expectancyR=-0.5011`, `hitRate=0.3396`, `realizedRTotal=-26.5604` |
| Estabilidad (9 cubos mes) | `negativeBuckets=7`, `positiveBuckets=2`, `flatBuckets=0`, `meanBucketR=-0.2616`, `min=-1.3925`, `max=2.0710` |
| Excursiones (MAE/MFE, R) | `measured=53`, `meanMaeR=-1.3880`, `minMaeR=-3.1945`, `meanMfeR=1.2408`, `maxMfeR=5.5513`, `unmeasured=0` |

**Lectura honesta:** en el **año natural 2022**, el edge medido por este instrumento está **refutado** (expectativa negativa, acierto ~34 %, 7 de 9 meses negativos). El instrumento **no** maquilla el resultado: la ventana completa se midió, sin truncar, sin plan B y con evidencia `STRONG`. Artefacto en `operability_runs/dia-d-auto/` (**gitignoreado**, no viaja en el repo).

---

## 3. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest .../test_dia_d_auto.py .../test_dia_d_auto_feedback.py .../test_universe_point_in_time.py .../test_universe_point_in_time_catalog.py .../test_dia_d_longitudinal.py apps/api-python/tests/test_auto_dia_d_route.py apps/api-python/tests/test_auto_dia_d_feedback_route.py apps/api-python/tests/test_dia_d_bump_guard.py -q` | **96 passed** (incl. `13` del proveedor PIT —**+5**— y `14` del agregado longitudinal) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (652 ficheros, 3562 dependencias) |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 524 source files** |
| `pnpm --filter @bolsa/web contract:check` | **`contract:check OK`** |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |
| `git diff --name-only <freeze-anterior> -- apps packages` | Sólo `universe_point_in_time_catalog.py`, `dia_d_longitudinal.py`, `v2_91_dia_d_longitudinal.py` (`scripts/`) y `test_dia_d_bump_guard.py` ⇒ **`Δ motor = 0`** |

**Nota sobre `replay-repro` local:** regenerar el artefacto **contra el PostgreSQL local** **no** reproduce el SHA del sello **porque la BD local ha seguido sincronizando barras** después del freeze (dato observado: el `.json` local actual ≠ el sellado). El job `replay-repro` del CI **siembra la entrada congelada** (`replay-input-fixture.ndjson`) y regenera con el **mismo** script (`v2_87_replay_oos_durable_cycle.py`, **no tocado**): ahí sí es byte a byte. Aquí se certifica **`Δ motor = 0`** por **alcance de ficheros** (ningún módulo de motor modificado ni importado por el replay).

---

## 4. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **`active_from`/`active_until`/`sector_at` son aproximaciones DECLARADAS** (no hay historial real de listado/baja ni de sector). El artefacto lo declara (`meta.universeCoverage` + `limits`).
4. **MAE/MFE son extremos ENTRE DÍAS (D1):** el día de entrada puede incluir excursión **previa al fill**; **no** se presentan como intradía.
5. **La estabilidad intra-2022 NO mide multirregimen** (una sola ventana): es dispersión entre cubos, no una prueba de regímenes.
6. **`CONFIRMED` sigue reservado** a evidencia PAPER real: el veredicto de esta ventana es **`REFUTED`**; con otra semilla/ventana favorable **no** se promociona a `CONFIRMED` (no se emite aquí).
7. **No sustituye la ventana PAPER real:** `P3-2`/`P3-3` siguen **ABIERTAS**.

---

## 5. Comandos (reproducir)

```bash
# Tests puros + rutas + guardián
python -m pytest packages/py/application/tests/test_dia_d_auto.py packages/py/application/tests/test_dia_d_auto_feedback.py \
  packages/py/application/tests/test_universe_point_in_time.py packages/py/application/tests/test_universe_point_in_time_catalog.py \
  packages/py/application/tests/test_dia_d_longitudinal.py \
  apps/api-python/tests/test_auto_dia_d_route.py apps/api-python/tests/test_auto_dia_d_feedback_route.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# Gates de CI (comandos EXACTOS)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent

# Contrato + UI
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor

# Runner de la ventana (sin regresión)
pnpm window:test

# Ventana longitudinal OOS 2022 (requiere PostgreSQL; artefacto gitignoreado)
uv run --no-sync python apps/api-python/scripts/v2_91_dia_d_longitudinal.py --year 2022 --json \
  --out operability_runs/dia-d-auto/longitudinal-2022-01-03_2022-12-30.json
```

---

## 6. Sello

- **Versión:** `2.11.38-beta` (base `2.11.37-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/dia_d_longitudinal.py`, `packages/py/application/tests/test_dia_d_longitudinal.py`, `apps/api-python/scripts/v2_91_dia_d_longitudinal.py`, `docs/engineering/plan-v2-88-38-dia-d-ventana-longitudinal-oos-2026-10-03.md`, `docs/engineering/evidence/v2.88.38/README.md`.
- **Ficheros modificados:** `packages/py/application/src/bolsa_application/universe_point_in_time_catalog.py`, `packages/py/application/tests/test_universe_point_in_time_catalog.py`, `apps/api-python/tests/test_dia_d_bump_guard.py`, `apps/api-python/scripts/v2_89_dia_d_auto_replay.py`, `apps/api-python/scripts/v2_90_dia_d_feedback.py`, `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **CI DE TAG:** PENDIENTE (se cita tras el push del tag).
