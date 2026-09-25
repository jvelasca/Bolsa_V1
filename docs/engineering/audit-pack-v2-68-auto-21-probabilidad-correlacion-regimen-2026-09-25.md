# Audit-pack — `v2.68-beta` (`AUTO-21`) · `P(R>0)`, correlación entre estrategias y evidencia del régimen actual

> **AsOf:** 2026-09-25 · **Versión:** `1.93.0-beta` · **Base auditada (diff):** `v2.67-beta`
> **Alcance:** las tres lecturas nuevas de `AUTO-21` — `P(R>0)` por bootstrap, correlación entre
> estrategias por cubo temporal y evidencia del régimen actual. Fase de **medición/evidencia**.
> **SIN migración** (head `046_fill_reference_mid`). **El freeze no se toca.**

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | `P(R>0)` es la fracción de medias bootstrap **estrictamente** `> 0` | `auto_adaptive_uncertainty.py` `_interval_from_episodes` | `test_probability_positive_is_the_share_of_positive_bootstrap_means` + **M183** |
| 2 | Sin bootstrap no hay probabilidad (`None`), nunca un `0` | `ExpectancyInterval.probability_positive` | `test_probability_positive_is_none_without_a_bootstrap` |
| 3 | El sello de la lectura sube a `bootstrap_episodes_v2` | `ADAPTIVE_UNCERTAINTY_METHOD` | `test_auto_v60_auto19_uncertainty_seam.py::...the_plan_carries_the_interval...` + **M182** |
| 4 | La pregunta de calibración exige **ambos** términos y es `inconclusive` sin muestra | `_question_probability_positive` | `test_probability_positive_calibration_is_inconclusive_without_both_terms` + **M185** |
| 5 | El sello de calibración sube a `walk_forward_calibration_v3` | `CALIBRATION_METHOD` | `test_auto_v64_auto20c_artifact.py` + **M184** |
| 6 | `probabilityPositiveOos` es la fracción positiva **realizada** del OOS (por ciclos, no media de celdas) | `_aggregate` | `test_the_aggregate_pools_the_realized_positive_share_by_cycles` |
| 7 | Sin cubos compartidos la correlación es `None` + nota (jamás `0`) | `build_strategy_correlation_report` | `test_without_shared_buckets_the_gap_is_declared` + **M186** |
| 8 | Con menos de `min_buckets` o serie constante ⇒ `None` + nota | `pearson_correlation` / `build_strategy_correlation_report` | `test_too_few_shared_buckets_are_declared_not_faked`, `test_a_constant_series_declares_it_instead_of_zero` |
| 9 | La correlación **no** entra al optimizador ni a la reserva | `git diff` de `portfolio_optimizer.py`/`portfolio_reservation.py` → **vacío** | `git diff v2.67-beta v2.68-beta -- ...` |
| 10 | Una estrategia sin celda del régimen actual declara el hueco (no publica el agregado) | `build_current_regime_evidence` | `test_a_strategy_without_a_cell_for_the_regime_declares_the_gap` + **M187** |
| 11 | El régimen actual sale del flag o del ciclo más reciente **con régimen declarable** (`UNKNOWN` no fija el actual) | `current_regime_from_cycles` | `test_an_unknown_regime_is_not_a_current_regime` |
| 12 | El render publica lo medido y **retira** el stub `AUTO-21 (fuera de alcance)` | `auto_evidence_report.py` | `test_auto_v64_auto20c_artifact.py` |
| 13 | Sin las claves nuevas el artefacto **no gana** ningún bloque (aditividad) | `build_evidence_artifact` (claves aditivas) | `test_the_artifact_omits_the_auto21_keys_when_there_is_no_reading` |
| 14 | El espejo TS **lee** (no recalcula) y trata lo ausente como `NO MEDIDO` | `auto-evidence-report.ts` (+ test) | vitest `auto-evidence-report.test.ts` |
| 15 | El freeze sigue intacto y no hay migración | `git diff` del freeze; Alembic head | verificación git + `046_*` |

## 2. Qué cambia (y qué no)

**Cambia.**
- `ExpectancyInterval.probabilityPositive` + sello `bootstrap_episodes_v2`.
- Pregunta `probability_positive_calibration` + `probabilityPositiveOos` + sello `walk_forward_calibration_v3`.
- Módulos nuevos `auto_adaptive_correlation.py` y `auto_adaptive_regime_evidence.py`.
- Claves **aditivas y opcionales** `correlation` / `currentRegime` / `currentEvidence` en el artefacto,
  `--bucket` / `--current-regime` en el battery, render medido y espejo TS.
- Matriz de mutaciones: **M182…M187**.
- `package.json` / `CHANGELOG`: bump a `1.93.0-beta`.

**NO cambia.**
- El esquema del artefacto (`auto20c_evidence_artifact_v1` **se mantiene**), el invariante PAPER=virtual, el
  reparto (`auto18-v1` / `auto15-v1`), el freeze, la migración. Sin las claves nuevas el artefacto es
  **byte-idéntico** al auditado en `v2.67`.
- **La correlación NO se conecta** al optimizador ni a la reserva: se **publica**, no reparte.

## 3. Compuertas re-medidas

| Compuerta | Comando | Resultado |
|---|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` | **1327 passed** (232 ficheros) con `--testTimeout=30000`; con el timeout por defecto (5 s) **flaquea** `backtests/core-r-scheduler.test.ts` bajo la carga de la suite (ver §4) |
| Frontend typecheck | `pnpm --filter @bolsa/web typecheck` | OK |
| Frontend lint | `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes) |
| Frontend build | `pnpm --filter @bolsa/web build` | OK |
| Frontend contrato | `pnpm --filter @bolsa/web contract:check` | OK |
| Python analytics | `uv run pytest packages/py/analytics -q` | **1238 passed** |
| Ruff | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| import-linter | `uv run lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| Mutaciones (tramo) | `uv run python apps/api-python/scripts/v2_44_mutation_audit.py M182 M183 M184 M185 M186 M187` | las **6 muerden** (M182 → seam del plan · M183 → fracción bootstrap · M184 → artefacto · M185 → 5 tests de calibración · M186 → cubos · M187 → 2 tests de régimen) |
| Matriz completa | `uv run python apps/api-python/scripts/v2_44_mutation_audit.py` | **187/187** medidas, **0** sin fragmento, restauración **byte a byte** (`intacto: la sonda no altero el arbol`) |

## 4. Flake declarado (NO es de la fase)

`apps/web/src/features/backtests/core-r-scheduler.test.ts` (`runCoreRSchedulerTick > skips when disabled` /
`> skips when no listId`) da `Error: Test timed out in 5000ms` **solo bajo la carga de la suite completa**
(la suite tarda ~170 s en recolectar y ~57 s en ejecutar en esta máquina). Evidencia de que **no** es de
esta fase:

- El fichero está **sin tocar**: `git status --porcelain apps/web/src/features/backtests` → **vacío**.
- Aislado pasa **siempre** (8 passed, ~1,2 s por test).
- Junto a los tests del perímetro de `AUTO-21` pasa (42 passed): los ficheros de la fase no lo provocan.
- Con `--testTimeout=30000` la suite completa queda **1327 passed / 232 ficheros**, sin rojos.

## 5. Nota de alcance para el auditor

- La **correlación** y la **evidencia del régimen actual** son **evidencia publicada**: no mueven ninguna
  asignación. Que no muevan nada es el **objetivo** de la fase, no un defecto.
- La evidencia del régimen **reutiliza** el bootstrap de `AUTO-19A` (`build_adaptive_uncertainty`): no hay
  una segunda aritmética de celda que pueda divergir. La prueba de la celda es la misma
  (`test_the_regime_cell_reuses_the_bootstrap_and_publishes_probability_positive`).
- La **corrida PAPER real** no se ejecuta (bloqueo por material): el fixture es **sintético y declarado**, y
  mide el **instrumento**, no el mercado.
- La **paridad TS-vs-Python** del contrato de claves es **vitest** (el test lee el `.py`); el espejo Python
  del render entra en la matriz por **M182/M184** (sellos) y por los tests del artefacto.
