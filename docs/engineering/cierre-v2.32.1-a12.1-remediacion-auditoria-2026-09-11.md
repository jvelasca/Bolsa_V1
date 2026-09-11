# Cierre V2.32.1 / A12.1 — Remediación auditoría V2.32 (P1 + hardening P2) (2026-09-11)

Version: `v2.32.1-beta`. Alcance: **todos los hallazgos verificados de la auditoría
V2.32** contra el HEAD `854dc86` (commit `feat(v2.32/A12)`). No hay P0. La arquitectura
no cambia y `LIVE` permanece **congelado**: no se toca `LIVE_EXECUTION_AUTHORIZED` ni
`LIVE_EXECUTION_UNLOCKED`, ni se añade ningún camino LIVE.

Commit de la remediación: `aefbf7eb` (23 ficheros, +1150 / −106). Tag de certificación:
`v2.32.1-beta` (ver §10).

---

## 0. Hallazgos auditados y verificados en código (HEAD `854dc86`)

| ID     | Hallazgo                                                                                     | Evidencia en HEAD                                                 | Estado  |
| ------ | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------- |
| P1-01  | La ventana shadow se solapa con la del LAB (ambas leen las últimas N barras)                 | `orchestrator_lab_runner.py` `bar_limit: 400` + worker shadow 250 | CERRADO |
| P1-02  | El E2E A12 no se certifica por commit (está `--ignore`d en `python-ci.yml`)                  | `python-ci.yml` líneas 104/351                                    | CERRADO |
| P2-01  | DD fail-open: `max_drawdown_pct is None` salta la comprobación (asimétrico con `return_pct`) | `strategy_lifecycle.py`                                           | CERRADO |
| P2-02  | Override humano cableado en la ruta AUTO real                                                | `auto_orchestrator_worker.py`                                     | CERRADO |
| P2-03  | Sin fingerprint del dataset shadow                                                           | tabla de la migración `032`                                       | CERRADO |
| P2-04  | `trades` cuenta piernas, no round-trips                                                      | `rules_grid.py`                                                   | CERRADO |
| P2-05  | `run_id` constante por instrumento                                                           | `auto_orchestrator_worker.py`                                     | CERRADO |
| Aud.2a | `can_transition(gates=())` cae a `allowed=True` (fail-open)                                  | `strategy_lifecycle.py`                                           | CERRADO |
| Aud.2b | `HealthThresholds` predictivos por defecto `0.0` contradice el rationale documentado         | `strategy_vigilance_phase.py`                                     | CERRADO |

**Defecto adicional detectado y corregido durante la remediación** (bloqueaba la
promoción de forma silenciosa):

| ID     | Hallazgo                                                                                                                                                         | Estado  |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| GATE-1 | `evaluate_optimize_result` no leía `walkForwardEfficiency`/`dsr` del `edge_report["suite"]` anidado ⇒ gates `robustness`/`walk_forward`/`dsr` en `NOT_EVALUATED` | CERRADO |

---

## 1. P1-01 — Hold-out estricto LAB / shadow

Antes, LAB y shadow leían ambos "las últimas N barras", así que las últimas 250 se
solapaban: la afirmación "ventana separada del LAB" era solo documentación, sin
aserción.

DESPUÉS: el orquestador conoce la frontera del LAB y el shadow solo ve barras
**estrictamente posteriores**.

- `packages/py/application/src/bolsa_application/auto_orchestrator.py`
  - `_resolve_holdout(...)`: obtiene la serie completa vía `shadow_bars` y calcula
    `lab_end` a partir de `shadow_config.window_bars`.
  - `_candidate_with_lab_cutoff(...)`: inyecta `date_to = lab_end` en los parámetros de
    la candidata **antes** de correr el LAB ⇒ el LAB opera solo con datos anteriores al
    hold-out.
  - `_run_shadow(...)`: recibe la serie completa prefetchada y `lab_end`.
  - `OrchestratorDeps.shadow_require_holdout`: fuerza el modo estricto.
- `packages/py/application/src/bolsa_application/strategy_shadow_phase.py`
  - `split_holdout(bars, lab_end, min_bars)`: parte en LAB vs hold-out, **falla cerrado**
    si no hay separación estricta posible o si el hold-out es más corto que `min_bars`.
  - `ShadowReplayConfig(lab_end, require_holdout)`: contrato de ventana.
  - Motivos explícitos: `shadow_solape_lab`, `shadow_barras_holdout_insuficientes`.
- `packages/py/application/src/bolsa_application/orchestrator_lab_runner.py`
  - `LabOptimizeResult.lab_bars_used`: expone la ventana efectiva del LAB para calcular
    el hold-out.
  - `_LAB_RUN_KEYS` acepta `date_to`; `_STRUCTURAL_LAB_DEFAULTS` aplica `bar_limit` a
    **todas** las familias (incluidas las declarativas del Discovery) para que el corte
    sea coherente.
- `packages/py/application/src/bolsa_application/optimize.py` /
  `optimization_runs.py`: `execute(..., date_to=...)` se propaga a `get_bars` y se
  registra en el payload de auditoría (`labDateTo`).
- `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`:
  `_make_shadow_bars_provider()` lee `LAB_BAR_LIMIT_DEFAULT + shadow_window` barras para
  que exista un hold-out real posterior.

Sin frontera de LAB determinable ⇒ no hay evidencia ⇒ no hay promoción (fail-closed).

---

## 2. P1-02 — Certificación PostgreSQL por commit

`.github/workflows/python-ci.yml` gana el job **`lifecycle-pg`** (per-commit, no solo en
el tag):

- Servicio `postgres:16-alpine`.
- `alembic upgrade head` (cadena 032 → 033 → **034**).
- Suite A12 crítica: `test_a11_discovery_to_auto_sim_pg.py`,
  `test_strategy_lifecycle_pg.py`, `test_sim_strategy_attribution.py`, con
  `LIFECYCLE_PG_REQUIRED=1`, `AUTO_ORCHESTRATOR_PG_REQUIRED=1`,
  `STRATEGY_LIFECYCLE_PG_REQUIRED=1` ⇒ **un skip es un fallo duro**.
- El `--ignore` del E2E A11 se mantiene en el job offline (sin Postgres), pero el E2E sí
  se ejecuta y certifica en `lifecycle-pg`.

`release-tag-ci.yml` conserva su `lifecycle-pg`; el nuevo job duplica solo el subconjunto
A12-crítico.

---

## 3. P1-02 — E2E determinista (sin SKIPPED)

`apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py`:

- `_seed_instrument_with_bars`: 700 barras con oscilación (bloques de 20) + deriva suave,
  un declive moderado en las ~25 barras previas a la última y un **salto vertical en la
  última barra** que fuerza un cruce SMA al alza (`prev_fast <= prev_slow and fast >
slow`) exactamente ahí ⇒ `entry_long` de la ACTIVE para cualquier par
  (rápida, lenta) del campeón.
- Se elimina el `pytest.skip` por no-fill: un no-fill es **fallo** en la certificación.
- `_make_discovery_runner()`: candidatas H0 `sma_crossover` con rejilla completa
  (`fast_periods`/`slow_periods` múltiples) y `cpcv_groups`/`walk_forward_folds`/
  `max_trials` explícitos. Necesario porque el CPCV/CSCV requiere varias estrategias para
  estimar PBO; una rejilla de un solo punto no produce `robustness`/`dsr`. El wiring
  (`discovery=...`) sigue siendo el real.
- Asserts nuevos: evidencia shadow real persistida, `lab_end`, `shadow_start`,
  `bars_hash`, `round_trips`.

---

## 4. P2-01 — Drawdown fail-closed

`packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py`
`ShadowPolicy.evaluate`: si `self.max_drawdown_pct is not None` y la métrica del replay es
`None`, se añade `shadow_drawdown_ausente` ⇒ falla cerrado. Simétrico con `return_pct`.

---

## 5. P2-02 — Sin override en la ruta AUTO

`apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`: la ruta AUTO real
deja de pasar `shadow_validated`/`shadow_override`. AUTO promociona **solo por
evidencia**, nunca por flag humano. El parámetro se mantiene en `evaluate_promotion` para
callers manuales/admin/test (no se elimina la API).

---

## 6. P2-03 — Fingerprint del dataset shadow

- `ShadowValidationResult` gana: `round_trips`, `data_snapshot_id`, `shadow_start`,
  `shadow_end`, `bars_hash`, `strategy_definition_hash`, `engine_version`, `config_hash`,
  `lab_end`.
- `run_shadow_replay` calcula `bars_hash` de forma determinista sobre el hold-out exacto
  (timestamps + OHLCV) y reutiliza el `definition_hash` del finalista
  (`ENGINE_VERSION = "shadow-replay/2.32.1"`).
- **Migración `034_shadow_dataset_fingerprint`** (`down_revision =
"033_position_strategy_attr"`): añade esas columnas (nullable; `round_trips` con
  `server_default "0"`) a `strategy_shadow_validations`. **Sin backfill**: la ausencia de
  evidencia es información, no un dato falso.
- `StrategyShadowValidationRow` + `save_shadow_result`/`list_shadow_results` actualizados.

---

## 7. P2-04 — Semántica de round-trips

La guarda de muestra de `ShadowPolicy` pasa a `min_closed_round_trips` (operaciones
cerradas). `trades` se conserva como piernas ejecutadas para contabilidad. El resultado
expone ambos.

---

## 8. P2-05 — Identidad por ciclo

`auto_orchestrator_worker.py`: `_new_cycle_id()` genera
`orchestrator:{instrument}:{UTC timestamp}-{short random}` en vez del constante
`orchestrator:{instrument}`, para distinguir retries / re-LAB / ciclos shadow en `as_of` y
filas de shadow.

---

## 9. Auditorías 2a / 2b

- **2a — `can_transition` fail-closed**: con `gates` vacío se devuelve
  `allowed=False` con motivo `gates_no_evaluados` (antes caía a `allowed=True`). Con
  gates presentes, un fallo sigue devolviendo `gates_fallidos:<...>`.
- **2b — `HealthThresholds` predictivos**: `min_edge`/`min_wfe`/`min_dsr`/
  `min_credibility` pasan a `float | None = None`; `as_dict()` omite `None`;
  `evaluate_active_health` **no compara** cuando el umbral es `None` (no fabrica un
  0.0). El worker AUTO pasa umbrales calibrados configurables por env
  (`AUTO_ORCHESTRATOR_HEALTH_*`).

---

## 10. GATE-1 — Corrección del lector de gates (fallo preexistente)

`packages/py/application/src/bolsa_application/strategy_lab_phase.py`
`evaluate_optimize_result` leía `walkForwardEfficiency`/`dsr` solo del nivel superior de
`edge_report`, pero `build_lab_edge_report_lite` los anida en `edge_report["suite"]`.
Consecuencia: `robustness`/`walk_forward`/`dsr` quedaban `NOT_EVALUATED` aunque el LAB
**sí** hubiera medido esos valores ⇒ ninguna candidata podía promocionar. Ahora se leen
también del `suite` (y de `result.cpcv` para el WFE).

---

## 11. Migración y cadena

- Nueva: `packages/py/infrastructure/alembic/versions/034_shadow_dataset_fingerprint.py`
  (`down_revision = "033_position_strategy_attr"`), aditiva/nullable con `downgrade()`
  completo y guards idempotentes offline-safe.
- `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`:
  `StrategyShadowValidationRow` con las columnas nuevas.

---

## 12. Invariantes que NO se tocan

- `AUTO ⇒ SIMULATED`; LIVE bloqueado por `LIVE_EXECUTION_AUTHORIZED` +
  `LIVE_EXECUTION_UNLOCKED` (ambas false). **Cero caminos LIVE nuevos.**
- COACH sigue advisory; RiskGate / SimulationGate / Ledger / Reconciliation
  deterministas.
- Sin LLM en el hot path. Long-only intacto.
- Fail-closed: sin evidencia shadow ⇒ no promoción; sin frontera de LAB ⇒ no evidencia;
  sin umbral calibrado ⇒ la vigilancia no degrada por un cero fabricado.

---

## 13. Verificación (reproducible desde Git)

```
uv run ruff check packages/py apps/api-python --config pyproject.toml   → All checks passed
uv run lint-imports --config packages/py/.importlinter                  → 4 kept, 0 broken
uv run mypy <11 ficheros fuente modificados>                            → Success, sin issues
uv run pytest <suite offline CI>                                        → 920 passed (foco remediación)
```

Suite de certificación PG (`lifecycle-pg`), local contra Postgres:

```
LIFECYCLE_PG_REQUIRED=1 AUTO_ORCHESTRATOR_PG_REQUIRED=1 \
STRATEGY_LIFECYCLE_PG_REQUIRED=1 \
uv run pytest \
  apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py \
  apps/api-python/tests/test_strategy_lifecycle_pg.py \
  packages/py/application/tests/test_sim_strategy_attribution.py -q
→ 12 passed (sin skips)
```

Tests de la remediación (puros, sin DB):

- `packages/py/domain/tests/test_strategy_lifecycle.py`:
  `test_transition_without_gates_is_fail_closed`,
  `test_transition_with_not_evaluated_gate_is_fail_closed`,
  `test_shadow_policy_fails_closed_when_drawdown_missing`,
  `test_shadow_policy_round_trips_is_the_sample_guard`.
- `packages/py/application/tests/test_strategy_shadow_phase.py`:
  `test_shadow_replay_requires_holdout_when_requested`,
  `test_shadow_replay_splits_holdout_after_lab_end`,
  `test_shadow_replay_fails_closed_without_separation`,
  `test_shadow_replay_fingerprint_is_reproducible`.
- `packages/py/application/tests/test_strategy_vigilance_phase.py`:
  `test_predictive_thresholds_default_to_none`,
  `test_unconfigured_thresholds_do_not_degrade`,
  `test_calibrated_credibility_threshold_degrades`.
- `apps/api-python/tests/test_auto_orchestrator_worker.py`:
  `test_loop_does_not_pass_shadow_override`,
  `test_default_orchestrator_does_not_wire_shadow_override`,
  `test_health_thresholds_are_calibrated`.

---

## 14. Por qué esto cierra la auditoría V2.32

Antes: la "ventana separada" del shadow era un solapamiento real sin aserción; la
promoción podía autorizarse con un flag humano en AUTO; el DD era fail-open; la guarda de
muestra contaba piernas; el fingerprint del dataset no existía; y el E2E que certifica el
camino crítico no corría por commit. Ahora: el hold-out es **estricto y verificable**
(`lab_end` + `shadow_start` + `bars_hash` persistidos), la promoción AUTO es **solo por
evidencia**, las políticas **fallan cerradas**, la muestra se mide en round-trips, y el
camino `DISCOVERY → SHADOW → SIM → VIGILANCIA` se certifica en cada push con Postgres
real y **sin skips**. El sistema sigue SIM-only, con LIVE intacto.
