# Audit Pack — V2.39 · Régimen de mercado por trial (incremento 4)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.39** — cuarto incremento de Strategy Intelligence: el **régimen de mercado**
> por trial, derivado de las barras del propio trial (as-of), persistido y agregable.
>
> **Base:** `v2.38.1-beta` (`main == 7c499cfc`).
> **Alembic head:** `039_research_trials_regime` (migración aditiva nueva).
> **Bump:** `1.63.1-beta` → `1.64.0-beta`.
> **Flag:** `AUTO_ORCHESTRATOR_ADAPTIVE_REGIME` **OFF por defecto**; con OFF el ciclo es
> **idéntico** a `v2.38.1-beta`.

---

## 0. Contexto: qué añade V2.39 y qué NO

V2.38 dio granularidad por **región de parámetros** (clave compuesta `familia|region`) y dejó
explícitamente fuera **régimen** e **instrument class** porque no existían como dato
persistido. V2.39 persiste la primera de esas dos dimensiones: el **régimen de mercado**.

- **Sí:** un régimen por trial, derivado de sus barras, con columna nueva nullable, `GROUP BY`
  ampliado en las dos agregaciones y un desglose aditivo en el snapshot.
- **No:** el régimen **no** entra en la clave `familia|region` (sigue intacta), **no** entra en
  `compute_family_weights`, **no** cambia el reparto de cupos y **no** entra en el
  `snapshot_hash`. Es una dimensión **paralela** observable.

### Decisión de fuente (crítica)

El régimen macro cognitivo existente **NO es calculable as-of**:
`bolsa_analytics.cognitive.market_state.build_market_state` se alimenta de
`bolsa_market.macro_snapshot.fetch_macro_snapshot_dict`, que usa valores _live_ de Yahoo
(`date.today()`, `closes[-1]`) y **no persiste serie histórica**. Etiquetar un trial pasado
con el régimen de hoy sería inventar dato. Por eso V2.39 deriva el régimen de las **barras del
propio trial** (corte as-of en la última barra de la ventana): determinista y reproducible.

---

## 1. El clasificador puro (`discovery_market_regime.py`)

- **Versión:** `MATH_VERSION_MARKET_REGIME_V0 = "discovery_market_regime_v0"`.
- **Un solo eje:** `TRIAL_REGIMES = ("trend_up", "trend_down", "range", "high_vol")` +
  `NO_REGIME = ""`.
- **Reglas (en orden):**
  1. **Fail-closed**: `< MIN_REGIME_BARS` (60), NaN/inf, `high`/`low` ausentes, cierres
     degenerados o `math_version` desconocida ⇒ `""`. Nunca se aproxima.
  2. `high_vol` si el rango relativo medio `(high-low)/close` supera el umbral (0.045).
     Prioridad sobre la tendencia: en mercado revuelto la dirección es poco fiable.
  3. `trend_up`/`trend_down` si la pendiente normalizada por volatilidad
     (`(SMA10 - SMA40)/SMA40 / vol`) supera ±0.5.
  4. `range` en cualquier otro caso.
- **Puro:** sin LLM, sin red, sin BD. Imports solo de la stdlib y tipos locales.

---

## 2. Persistencia (migración 039 + write-path)

- **Migración aditiva** `039_research_trials_regime` (clone del patrón 038): columna
  `regime String NULL`, sin backfill, `downgrade()` completo, guards idempotentes.
  `down_revision = "038_research_trials_param_region"`.
- **Cadena completa:** `ResearchTrialRow.regime` · `ResearchTrial.regime` · Protocol
  `insert_trial(regime=)` · repo SQL (mapeo `_map` + constructor de fila).
- **LAB:** campo `OptimizeSmaGridResult.regime`, calculado con `classify_market_regime(...)`
  en los **cuatro** constructores del dataclass: `_finalize`, `_run_cpcv`, `_run_walk_forward`,
  `_run_declarative_partial_on_bars` (cada uno con la ventana real que evaluó; en los casos
  CPCV/WF/declarativo se usa la ventana completa de la corrida por estabilidad).
- **Write-path:** `_regime_for_trial(regime, params, blocks)` con preferencia
  `result.regime` → `params['discovery_regime']` → `blocks['discovery']['regime']` → `None`.

---

## 3. Agregación y evidencia

- `family_evidence_summary`: `SELECT regime` + `GROUP BY (preset_key, param_region, regime)`
  - `ORDER BY` análogo; publica `"regime": _normalized_regime(row.regime)`.
- `posterior_evidence_summary`: mismo `GROUP BY`; la clave compuesta **no cambia**
  (`familia|region`) y el régimen se publica **aparte** en `regimeCounts`.
- `discovery_evidence.py`: `regime` entra en el `evidence_fingerprint` (orden
  `(presetKey, paramRegion, regime)`) y `regimeGranularity` se publica en el `payload`,
  **fuera** del `snapshot_hash`. **`compute_family_weights` NO se toca.**

---

## 4. Rollout y equivalencia con V2.38.1

- Flag `AUTO_ORCHESTRATOR_ADAPTIVE_REGIME` (**OFF**), `adaptive_regime_enabled()`.
- `LabOptimizeRunner(emit_regime=...)` fijado por el composition root e **impuesto después**
  de los overrides de la candidata (`_merge_params`): una candidata **no puede encender** el
  régimen.
- Con OFF, `_persist_optimize_research_trials(..., emit_regime=False)` escribe `regime=None`
  ⇒ los trials quedan a `NULL` ⇒ la evidencia es **idéntica** a V2.38.1 (misma clave, mismos
  pesos, mismo `snapshot_hash`). La equivalencia se garantiza por la **ausencia de dato**, no
  por un colapso posterior (lección del P2-01 de V2.38.1).
- Log aditivo `log_regime_rollout_state()` (solo observabilidad, no altera decisiones).

---

## 5. Matriz de aserciones → código/tests

| Aserción                                                 | Código                          | Test                                                                                                                                 |
| -------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| El clasificador es determinista                          | `discovery_market_regime.py`    | `test_same_bars_yield_same_regime`, `test_copies_of_same_series_yield_same_regime`                                                   |
| Fail-closed con barras insuficientes                     | `classify_market_regime`        | `test_below_min_bars_has_no_regime`, `test_empty_series_has_no_regime`                                                               |
| Fail-closed con NaN / sin high-low / precios degenerados | idem                            | `test_nan_close_does_not_crash_and_is_fail_closed`, `test_missing_high_low_is_fail_closed`, `test_degenerate_prices_are_fail_closed` |
| Fail-closed con `math_version` desconocida               | idem                            | `test_unknown_math_version_is_fail_closed`                                                                                           |
| Distingue tendencia / rango / volatilidad                | idem                            | `test_uptrend_is_detected`, `test_downtrend_is_detected`, `test_flat_market_is_range`, `test_high_volatility_takes_priority`         |
| El resultado es siempre del conjunto canónico            | idem                            | `test_result_is_always_a_canonical_label`                                                                                            |
| El régimen no entra en la clave de granularidad          | `discovery_evidence.py`         | `test_regime_does_not_enter_the_granularity_key`                                                                                     |
| `regimeGranularity` publicado y aditivo                  | `discovery_evidence.py`         | `test_regime_granularity_payload_is_populated_when_regime_present`, `test_regime_granularity_is_empty_without_regime`                |
| El régimen no cambia el `snapshot_hash`                  | `snapshot_hash`                 | `test_regime_does_not_change_snapshot_hash_vs_no_regime`                                                                             |
| El régimen sí entra en el fingerprint                    | `evidence_fingerprint`          | `test_regime_changes_evidence_fingerprint`                                                                                           |
| Fingerprint determinista ante orden de regímenes         | idem                            | `test_fingerprint_is_order_insensitive_across_regimes`                                                                               |
| Región y régimen conviven sin colisión                   | idem                            | `test_regime_and_region_coexist_without_key_collision`                                                                               |
| Con `emit_regime=False` no se persiste régimen           | `optimization_runs.py`          | `test_emit_regime_false_persists_no_regime`                                                                                          |
| Con `emit_regime=True` llega el régimen del resultado    | idem                            | `test_emit_regime_true_persists_result_regime`                                                                                       |
| `_regime_for_trial` fail-closed + fallback               | idem                            | `test_regime_for_trial_*` (4 tests)                                                                                                  |
| El flag OFF es el default                                | `auto_orchestrator_worker.py`   | `test_adaptive_regime_defaults_off`                                                                                                  |
| La candidata no puede encender el régimen                | `orchestrator_lab_runner.py`    | `test_lab_runner_candidate_cannot_enable_regime`                                                                                     |
| Roundtrip de la columna `regime`                         | repo SQL                        | `test_regime_roundtrips` (PG)                                                                                                        |
| Agregación por régimen                                   | `family_evidence_summary`       | `test_family_evidence_summary_groups_by_regime` (PG)                                                                                 |
| `regimeCounts` en la evidencia posterior                 | `posterior_evidence_summary`    | `test_posterior_evidence_summary_publishes_regime_counts` (PG)                                                                       |
| Migración 039 upgradable/downgradable                    | `039_research_trials_regime.py` | `test_migration_039_roundtrip` (PG)                                                                                                  |

---

## 6. Qué auditar

| Artefacto                   | Ruta                                                                                                     |
| --------------------------- | -------------------------------------------------------------------------------------------------------- |
| Clasificador puro           | `packages/py/application/src/bolsa_application/discovery_market_regime.py`                               |
| Migración 039               | `packages/py/infrastructure/alembic/versions/039_research_trials_regime.py`                              |
| Cálculo en el LAB           | `packages/py/application/src/bolsa_application/optimize.py`                                              |
| Write-path                  | `packages/py/application/src/bolsa_application/optimization_runs.py`                                     |
| Runner (fija `emit_regime`) | `packages/py/application/src/bolsa_application/orchestrator_lab_runner.py`                               |
| Evidencia                   | `packages/py/application/src/bolsa_application/discovery_evidence.py`                                    |
| Agregación                  | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/research_trial_repository.py` |
| Rollout                     | `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`                                   |

---

## 7. Cómo reproducir la verificación

```bash
# --- Calidad (invocación EXACTA de CI: el root afecta a la clasificación de imports) ---
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/application/src/bolsa_application/discovery_market_regime.py \
             packages/py/application/src/bolsa_application/optimize.py \
             packages/py/application/src/bolsa_application/optimization_runs.py \
             packages/py/application/src/bolsa_application/orchestrator_lab_runner.py \
             packages/py/application/src/bolsa_application/discovery_evidence.py \
             apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py

# --- Tests puros (herméticos, sin DB) ---
uv run pytest packages/py/application/tests/test_discovery_market_regime.py \
              packages/py/application/tests/test_discovery_evidence.py \
              packages/py/application/tests/test_optimization_runs.py \
              apps/api-python/tests/test_auto_orchestrator_worker.py -q

# --- Certificación PG (skip = fallo); requiere migrate a head antes ---
cd packages/py/infrastructure && uv run alembic upgrade head && cd ../../..
uv run pytest apps/api-python/tests/test_discovery_evidence_snapshot_pg.py -q
```

---

## 8. Invariantes intactas

`AUTO ⇒ SIMULATED` · LIVE bloqueado · sin LLM en hot path · fail-closed · H1/H2 · long-only ·
gates CPCV/PBO/DSR/WFE/OOS sin relajar · anti-explosión `len(plans) == 1784` · la clave
compuesta `familia|region` y `_collapse_regions` **sin modificar** · con el flag de régimen
OFF, comportamiento idéntico a V2.38.1 · Alembic head `039_research_trials_regime`.

---

## 9. Verificación local ejecutada

```
ruff (--config pyproject.toml)              → All checks passed
mypy (8 módulos tocados)                    → Success: no issues found
pytest V2.39 (offline, herméticos)          → 212 passed
pytest PG (test_discovery_evidence_snapshot_pg.py) → 18 passed
```

> Nota de honestidad (patrón del repo): este documento **no afirmaba CI de un tag aún no
> creado**. El sellado se ejecutó después: `v2.39-beta` == `main == e94f2632`, Release-tag CI
> **GREEN verificado** (run `34727468861`, `success`, 10/10 jobs requeridos verdes + `certify`
> aggregate). Queda pendiente la auditoría externa sobre el tag sellado.
