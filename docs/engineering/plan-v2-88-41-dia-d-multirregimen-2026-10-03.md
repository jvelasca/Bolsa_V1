# Plan — `v2.88.41-beta` / `AUTO·DÍA-D-3b`: multirregimen 2021-2026 (año × régimen × resultado × excursión), `Δ motor = 0`

> **Estado:** **EJECUTADO** (2026-10-03). Sellado como `2.11.41-beta` / `v2.88.41-beta`. Evidencia: [`evidence/v2.88.41/README.md`](./evidence/v2.88.41/README.md).
> **Plan vivo del chat:** `~/.cursor/plans/dia-d-3b_multirregimen_6323074e.plan.md` (no se edita; esta es la copia sellada).

## 0. Objetivo

Convertir el diagnóstico de un solo año (`2022`, monorégimen `high_vol`) en una **base multirregimen**: correr el MISMO harness hermético **una pasada por año (2021-2026)**, con **universo `PIT` por año**, y agregar la atribución por **año × régimen × resultado (WINNERS/LOSERS) × excursión (MAE/MFE/captura/reversión)**.

Responde la pregunta del dictamen: *¿el `-0.5011 R/ciclo` es fenómeno de régimen, de selección de entradas, de gestión de riesgo o de salida?* — de forma **descriptiva**, sin conclusión causal y **sin tocar AUTO**.

- Bump: `2.11.40-beta → 2.11.41-beta`. **SIN migración** (Alembic head `048_journal_entry_dedupe_key`).
- **`Δ motor = 0`**: no se toca ningún fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`, `v2_87_replay_oos_durable_cycle.py`) ni el artefacto congelado de `replay-repro`.
- **CLI-only** (sin DTO/OpenAPI/UI): el artefacto vive en `operability_runs/dia-d-auto/*.json` (gitignored) y se regenera, no se hereda.

## 1. Precedente y reutilización (no duplicar)

Se sigue el patrón de `v2.88.39`/`v2.88.40`: **módulo puro nuevo + CLI nuevo**, sin extender el runner ni el artefacto sellado.

- Harness: `apps/api-python/scripts/v2_91_dia_d_longitudinal.py` → `_resolve_window`, `_run_pass` (conduce `v87._run_durable_replay` con stores en memoria).
- Cross-check tolerante: `_load_cross_check` / `_cross_check_summary` de `apps/api-python/scripts/v2_92_dia_d_attribution.py`.
- Régimen: `bolsa_application.replay_oos.census_operable_days` (`aggregate` trial y `operational`).
- Universo PIT: `CatalogPointInTimeUniverse.load(...)` + `universe_ids(provider, anchor)`.
- Módulo puro: `bolsa_application.dia_d_attribution` → `payoff_decomposition`, `capture_study`, `mae_severity`, `concentration`, `index_excursions`, `Excursion`.
- Excursiones: `bolsa_application.dia_d_longitudinal.excursions`.

## 2. Diseño

### 2.1 Módulo puro nuevo `packages/py/application/src/bolsa_application/dia_d_multi.py`

- `SCHEMA_VERSION = "dia-d-multi-v1"`, `KIND = "DIA_D_AUTO_MULTI_ATTRIBUTION"`, `readOnly = True`, `basis = "entryDay"`.
- `build_dia_d_multi_artifact(*, years, windows, round_trips, excursions_rows, regime_by_day, operational_regime_by_day, meta, top_k, limits)`.
- Reutiliza `payoff_decomposition` / `capture_study` / `mae_severity` / `concentration` de `dia_d_attribution` (no se reimplementan umbrales `-1R/-1.25R/-1.5R`).
- Por cada cubo (año, régimen, régimen operativo) publica: `cycles`, `expectancyR`, `hitRate`, `medianR`, `realizedRTotal`, `meanMaeR`, `meanMfeR`, `capture`, `maeSeverity.populations` (ALL/WINNERS/LOSERS).
- `byYearByRegime`: matriz **solo con celdas medidas**; una celda vacía **no se emite** (nunca `0`).
- `coverage`: `yearsRequested` / `yearsMeasured` / `yearsEmpty` / `yearsNotMeasured` con `reason` por año.
- `windows`: lista por año con `requestedFrom/To`, `effectiveFrom/To`, `cyclesMeasured`, `truncationReason`, `windowFallback`, `universeCoverage`, `watchSource`.
- Regla del hueco heredada: `None`/`NOT_MEASURED`, **nunca** `0`; cubo sin ciclos medibles no aparece.
- Límites declarados en `DEFAULT_LIMITS`: descriptivo no causal; REPLAY/OOS (no sustituye PAPER); MAE/MFE entre días (D1); sector = catálogo actual; régimen = agregado trial por día; `CONFIRMED` reservado a PAPER; multirregimen depende de la disponibilidad real de barras por año.

### 2.2 CLI nuevo `apps/api-python/scripts/v2_93_dia_d_multi.py`

- Args: `--from-year 2021 --to-year 2026` (o `--years 2021,2022,...`), `--universe pit` (default), `--watch`, `--watch-size`, `--min-bars`, `--history-days`, `--horizon-days`, `--edge`, `--attribution-top-k`, `--version-a`, `--venue`, `--account-id`, `--check-against`, `--fallback/--no-fallback`, `--json`, `--out`.
- Por año: `universe_ids(provider, <año>-12-31)` (fail-closed si vacío) → `_run_pass` → fallback declarado si trunca → recoge `round_trips` (atribuidos por `entryDay`), `excursions`, `regime_by_day` (aggregate) y `operational_regime_by_day`.
- Un año sin barras suficientes **se declara** en `coverage.yearsNotMeasured` (no se inventa).
- `meta.bump = "2.11.41-beta"` (coincide con `package.json`).
- Salida por defecto `operability_runs/dia-d-auto/multi-<from>_<to>.json` (gitignored) + `_print_text` con tabla año × régimen y poblaciones W/L.

## 3. Afirmaciones falsables

1. **Cobertura declarada:** `yearsMeasured ∪ yearsNotMeasured = yearsRequested`; cada año no medido lleva `reason`; ningún año se rellena con `0`.
2. **Consistencia de la matriz:** para cada año, la suma de `cycles` de sus celdas `byYearByRegime` == `byYear[año].cycles`.
3. **Separación por población:** `LOSERS` y `WINNERS` de un régimen tienen `meanMaeR` divergentes (en `2022`/`high_vol` se reproduce `LOSERS` `< -1R` ≈ `94.29 %` y `WINNERS` ≈ `11.11 %`).
4. **Excursión acotada:** todo `captureRatio` en `[0, +inf)`, `aboveOneCount` declarado, `reversedCount` estable.
5. **Determinismo:** dos corridas ⇒ payload byte a byte idéntico (sin reloj/ULID).
6. **Instrumento congelado intacto:** `replay-repro` byte a byte y `git diff` sin ficheros de motor.
7. **Sin contrato:** `contract:check` sin cambios (la atribución es Python puro, no viaja por OpenAPI).

## 4. Sello, docs y freeze

- Bump `2.11.40-beta → 2.11.41-beta` en `package.json` + `meta.bump` de `v2_89`/`v2_90`/`v2_91`/`v2_92` + nuevo `v2_93`; extender `apps/api-python/tests/test_dia_d_bump_guard.py` con `v2_93`.
- `CHANGELOG.md` (entrada `2.11.41-beta`), `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- Nueva evidencia `docs/engineering/evidence/v2.88.41/README.md` y este plan en `docs/engineering/plan-v2-88-41-dia-d-multirregimen-2026-10-03.md`.
- **Re-anclaje del freeze** en `scripts/lib/window-forward.mjs` (`WINDOW_CONFIG` al commit funcional; editar `scripts/` no mueve el árbol, dry-run `freeze OK`).
- Tag anotado `v2.88.41-beta` + push + cita del `Release tag CI`. **A39-04** (CI del tag `v2.88.40`) ya está evidenciado VERDE en el repo (run [`37132550660`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37132550660)); se re-cita en la respuesta al auditor, no bloquea esta fase.

## 5. Verificación y gates

- `pytest` DÍA-D (`122 passed`) · `ruff` · `lint-imports` (`4 kept, 0 broken`) · `mypy` (`526 source files`) · `contract:check` · `tsc -b --noEmit` · vitest `auto-monitor` (`14`) · `pnpm window:test` (`25/25`).
- Smoke real (PostgreSQL): `uv run --no-sync python apps/api-python/scripts/v2_93_dia_d_multi.py --from-year 2021 --to-year 2026 --universe pit`.
- Medición efectiva: corrida 2021-2026, artefacto sellado (gitignored) y tabla resultado en la evidencia.

## 6. Límites declarados (van en el artefacto y el README)

- Evidencia **REPLAY/OOS**; **no** sustituye la ventana PAPER real (`P3-2`/`P3-3` siguen **ABIERTAS**).
- Atribución **descriptiva, no causal**.
- `2026` es año **parcial** y **no medido** (ancla PIT futura, fail-closed); se declara.
- MAE/MFE **entre días** (D1); sector = catálogo **actual** (no PIT); régimen = agregado trial por día.
- La disponibilidad de barras por año (PIT) se **declara** (considerados / materializados / excluidos sin barras); un año hueco no se inventa.
- `Δ motor = 0`; sin migración; `CONFIRMED` reservado a evidencia PAPER.

## 7. Fuera de alcance (deliberado)

- **No** se modifica el motor AUTO, umbrales (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) ni la allocation.
- **No** se añade endpoint/DTO/UI (evita regenerar contrato y mantener el sello lean).
- **No** se cierra la ventana PAPER real ni se decide aún H1-H4 (entrada/riesgo/gestión/salida): eso requiere la evidencia multirregimen y su cruce posterior con `P3-2`/`P3-3`.
