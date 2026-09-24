# Traspaso / relevo — post `v2.61-beta` (`AUTO-19B`) · 2026-09-24

**Para quien toma el relevo.** `AUTO-19B` (calibración del intervalo + walk-forward) está **cerrada**:
instrumento puro, fixture declarado, tests, `M159…M164`, CI y sello `1.86.0-beta` / `v2.61-beta`.
**Sin migración.** **El sello del reparto sigue `auto18-v1`** (fase de solo medición).

## Decisiones tomadas (y por qué)

1. **Solo medición.** El propietario ratificó que la calibración es **evidencia read-only**: no toca el
   reparto, ni el plan, ni el journal, ni el gobernador. `AUTO-19A` ya lo dejó así; `AUTO-19B` lo
   respeta.
2. **Instrumento primero.** El fixture sigue siendo **sintético y declarado**; el material PAPER real
   entra por el JSON de ciclos del CLI (`--walk-forward --cycles ...`). Es la costura ya validada.
3. **Una sola aritmética de celda.** En vez de reimplementar la medición IS/OOS, se extrajo
   `measure_is_oos_row` de `_build_cell`: el replay de `AUTO-19A` y el walk-forward de `AUTO-19B`
   miden con el MISMO código. Los veredictos de shrinkage/`effective_N`/cobertura se **reutilizan**.
4. **Ventanas crecientes (expanding).** Se copia la forma de `optimize/walk_forward.py`
   (`n_folds + 1` segmentos; el último absorbe el resto). Pliegues que no alcanzan los mínimos **no se
   forman**; los huecos se declaran (`skipped_strategy` / `insufficient_folds`).

## Estado medido (local)

- **Ruff:** All checks passed. **Import Linter:** 4 kept, 0 broken. **Mypy:** 499 ficheros, 0 errores.
- **Pytest:** analytics + costura 19A `1190 passed`; aplicación `1941 passed`; la nueva
  `test_auto_adaptive_calibration.py` `19 passed`.
- **Mutaciones:** `M159…M164` `6/6`; **matriz completa `164/164`**, árbol intacto, cero fragmentos
  ausentes.
- **Byte-identidad:** sin `--walk-forward` el CLI de `AUTO-19A` emite el mismo JSON.
- **Sello (CI remoto):** tag `v2.61-beta` (objeto `2f64dc1c` → `f9f64799`), `main` en fast-forward
  (`63a02e34..f9f64799`). `Release tag CI` **GREEN** (job `python` **`2766 passed / 35 skipped`**,
  `certify` en `success`) tras re-ejecutar los jobs fallidos: **flake ajeno PG declarado**
  (`test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once`,
  `AssertionError: RETRY`, verde al reintentar). PR de auditoría **#70**.

## Huecos declarados (el siguiente turno)

- **Datos reales:** correr el instrumento sobre ciclos PAPER reales es el paso operativo siguiente. Sin
  él, los números miden el instrumento.
- **`P(R > 0)`:** no implementado (fuera de alcance).
- **Correlación entre estrategias** y **current-regime gating:** fuera de alcance.
- **Persistencia/UI del reporte de calibración:** no hay; es un instrumento de CLI, no un endpoint.

## Archivos clave

- `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py` — split, seis
  preguntas, `aggregate`, `CalibrationReport`.
- `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_replay.py` — `measure_is_oos_row`.
- `scripts/research/auto_replay_battery.py` — `--walk-forward` / `--folds`.
- `packages/py/analytics/tests/test_auto_adaptive_calibration.py` + fixture
  `auto_calibration_cycles.json`.
- `apps/api-python/scripts/v2_44_mutation_audit.py` — `M159…M164`.

## Cómo re-verificar en frío

```text
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync python -m pytest packages/py/analytics/tests -q
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M159 M160 M161 M162 M163 M164
```
