# Evidencia cruda — `v2.88.37-beta` (AUTO · **DÍA-D**: `Universe(D)` deja de ser solo contrato — **`PointInTimeUniverseProvider` real**)

> **Objeto:** package **`2.11.37-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** capacidad **operativa nueva** (advisory, read-only) sobre **DÍA-D AUTO**. Cierra la única deuda naranja de `v2.88.36` (D35-01): el contrato `Universe(D)` pasa a tener **fuente real** (disponibilidad desde **barras**) + **aproximaciones DECLARADAS** (alta/baja/sector del catálogo), cableada al replay tras un flag.
> **`Δ decisión motor = 0`:** **ningún** fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`) se toca. `AUTO_ENGINE_SIM_REAL_PRICE` sigue **OFF** en el instrumento.
> **Padre:** [`evidence/v2.88.36/README.md`](../v2.88.36/README.md) (consolidación del instrumento: PIT demostrable + robustez).
> **Nomenclatura:** `AUTO engineering release = v2.88.37-beta` · `application package = 2.11.37-beta`.

---

## 0. Qué entrega este sello

| # | Pieza | Qué añade |
|---|---|---|
| **1 · Proveedor** | `packages/py/application/src/bolsa_application/universe_point_in_time_catalog.py` (`CatalogPointInTimeUniverse`) | **D35-01 como capacidad**: la implementación REAL del protocolo `PointInTimeUniverse`. Lee `ohlcv_bars` (D1) + `instruments` en una sesión read-only; `load(...)` (BD) y `from_catalog_rows(...)` (puro); `members(day)`/`ids(day)` filtran por `eligible_at` (fail-closed), deduplican y ordenan. Separa **REAL** (`availability_from/until` = `MIN`/`MAX` de barras) de **DECLARADO** (`active_from` = `created_at`, `active_until` = `is_active`/última barra, `sector_at` = sector actual) y lo expone en `coverage()`. Un instrumento **sin barras** es inelegible (no se inventa fecha). |
| **2 · Wiring** | `apps/api-python/scripts/v2_89_dia_d_auto_replay.py` | Nuevo flag **`--universe {catalog,pit}`** (default `catalog`, comportamiento intacto). Con `pit` y sin `--watch`, el watch sale de `universe_ids(provider, D)` (fail-closed si vacío: **no** cae al catálogo). `meta.watchSource` gana `"pit"`, `survivorBiasRisk=false` cuando `pit`, + `meta.universeCoverage`/`meta.universeExcludedNoBars`, y un `limit` declarado. |
| **3 · Tests** | `packages/py/application/tests/test_universe_point_in_time_catalog.py` | 8 tests puros (sin BD) de la procedencia real-vs-declarado, fail-closed y determinismo. |
| **4 · Sello** | `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md` | Bump `2.11.36-beta` → `2.11.37-beta`; `meta.bump` de `v2_89`/`v2_90` alineado (guardián `test_dia_d_bump_guard.py`). |

**Procedencia de datos del proveedor (declarada, no disfrazada):**

| Campo | Fuente | Procedencia |
|---|---|---|
| `availability_from` / `availability_until` | `MIN`/`MAX(timestamp)` de `ohlcv_bars` D1 | **REAL** |
| `active_from` | `instruments.created_at` | **DECLARADO** (alta en catálogo, NO fecha de listado) |
| `active_until` | `is_active` (abierto) / última barra (baja) | **DECLARADO** |
| `sector_at` | `instruments.sector` actual | **DECLARADO** (no point-in-time) |

---

## 1. Afirmaciones falsables

| # | Hallazgo | Afirmación | Cómo se rompe (falsación) | Evidencia |
|---|---|---|---|---|
| **D35-01** 🟢 | Capacidad PIT | La disponibilidad de un `UniverseMember` sale de las **barras** (REAL) y el resto es **DECLARADO**; sin barras ⇒ inelegible (fail-closed). | Inventar `availability_from` sin barras; tratar `active_*`/`sector_at` como PIT genuino; no filtrar por `eligible_at`. | `test_universe_point_in_time_catalog.py` (disponibilidad real, delistado, sin barras, inicio desconocido, `require_sector`) |
| **Wiring** 🟢 | `--universe pit` | Con `pit`, `meta.watchSource="pit"` y `survivorBiasRisk=false`; sin elegibles ⇒ error (no cae al catálogo). | Fallback silencioso al catálogo; dejar `survivorBiasRisk=true`. | smoke read-only (abajo) |
| **Procedencia** 🟢 | Honestidad | `coverage()` declara `REAL` vs `DECLARADO` por campo y cuenta excluidos. | Ocultar la procedencia o el conteo de excluidos. | `test_coverage_declares_real_and_declared_provenance`, smoke |
| **C4** | `None ≠ 0` | Un hueco no se rellena con `0`; sin barras no hay fecha inventada. | Rellenar con `0`/fecha por defecto. | tests del proveedor |
| **C6** | Determinismo | `members`/`ids` ordenan y deduplican (mismo estado ⇒ mismo universo). | Iteración no ordenada / sin dedupe. | `test_members_and_ids_are_deterministic_sorted_and_deduplicated` |
| **Δ motor** | No regresión | Ningún fichero de motor tocado; el default (`catalog`) no cambia. | Editar motor o el default. | `git diff` de alcance + smoke `catalog` |

---

## 2. Verificación (ejecutada)

| Comando | Resultado |
|---|---|
| `python -m pytest .../test_dia_d_auto.py .../test_dia_d_auto_feedback.py .../test_universe_point_in_time.py .../test_universe_point_in_time_catalog.py apps/api-python/tests/test_auto_dia_d_route.py apps/api-python/tests/test_auto_dia_d_feedback_route.py apps/api-python/tests/test_dia_d_bump_guard.py -q` | **77 passed** |
| `uv run ruff check ...universe_point_in_time_catalog.py ...test_universe_point_in_time_catalog.py apps/api-python/scripts/v2_89_dia_d_auto_replay.py --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **Contracts: 4 kept, 0 broken** (651 ficheros, 3554 dependencias) |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 523 source files** |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK` |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **4 ficheros / 14 tests passed** |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** |

**Smoke read-only (requiere PostgreSQL), `D = 2026-09-30`:**

| Run | `meta.watchSource` | `survivorBiasRisk` | `watchSize` | Cobertura |
|---|---|---|---|---|
| `--universe pit` | **`pit`** | **`false`** | 20 | `instrumentsConsidered=303`, `membersMaterialized=76`, `excludedNoBars=227`, `excludedInsufficientBars=0`, `excludedNoSector=0` |
| default (`catalog`) | `catalog` | `true` | 20 | `universeCoverage=null` |

Ambos runs: veredicto `NOT_MEASURED` (sin hechos durables de `D`), `Δ motor = 0`. Artefactos en `operability_runs/dia-d-auto/` (gitignoreado).

---

## 3. Límites declarados (lo que este sello **NO** cierra)

1. **`Δ motor = 0`.** El instrumento **observa y mide**; no decide. Ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) cambia.
2. **Sin migración:** Alembic head sigue `048_journal_entry_dedupe_key`.
3. **No hay historial real de listado/baja ni de sector:** `active_from`/`active_until`/`sector_at` son **aproximaciones DECLARADAS** (no PIT genuino). El artefacto lo declara (`meta.universeCoverage` + `limits`).
4. **No se ejecuta la ventana longitudinal DÍA-D** ni se mide la estabilidad del edge: se difiere a `v2.88.38`.
5. **`CONFIRMED` sigue reservado** a evidencia PAPER real; hoy **no** se emite.
6. **Freeze del runner:** sin re-anclar en este slice. El pin vigente (`WINDOW_CONFIG.commit=e9af4ada`, `apps=5cdd0666…`, `packages=eb2242ea…`) sigue casando con `HEAD`; el re-anclaje al commit funcional de `v2.88.37` corresponde al **commit de sello**.

---

## 4. Comandos (reproducir)

```bash
# Tests puros + rutas + guardián
python -m pytest packages/py/application/tests/test_dia_d_auto.py packages/py/application/tests/test_dia_d_auto_feedback.py \
  packages/py/application/tests/test_universe_point_in_time.py packages/py/application/tests/test_universe_point_in_time_catalog.py \
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

# Smoke read-only del proveedor PIT (requiere PostgreSQL)
uv run --no-sync python apps/api-python/scripts/v2_89_dia_d_auto_replay.py --at 2026-09-30 --universe pit --json
```

---

## 5. Sello

- **Versión:** `2.11.37-beta` (base `2.11.36-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/universe_point_in_time_catalog.py`, `packages/py/application/tests/test_universe_point_in_time_catalog.py`, `docs/engineering/evidence/v2.88.37/README.md`.
- **Ficheros modificados:** `apps/api-python/scripts/v2_89_dia_d_auto_replay.py`, `apps/api-python/scripts/v2_90_dia_d_feedback.py`, `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **CI de tag:** **PENDIENTE** (se cita tras el push/tag de `v2.88.37-beta`).