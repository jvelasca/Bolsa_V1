# Audit Pack — V2.32.1 / A12.1 (Remediación auditoría V2.32)

> **Para el auditor externo.** Este documento es el punto de entrada para auditar la
> remediación de la auditoría V2.32 **desde Git**, sin acceso al entorno de desarrollo.
> Fecha: 2026-09-11.

## 0. Qué auditar y dónde (referencias Git exactas)

| Elemento                      | Referencia                                                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Tag certificado               | **`v2.32.1-beta`** → commit `0d4c39c2`                                                                                   |
| Commit de la remediación      | **`aefbf7eb`** (`fix(v2.32.1/A12.1): remediacion auditoria V2.32 ...`)                                                   |
| Commit del cierre/documento   | `f39a6c10` (`docs(v2.32.1/A12.1): cierre de la remediacion ...`)                                                         |
| Commit del audit pack (este)  | `0d4c39c2` (`docs(v2.32.1): audit pack ...`)                                                                             |
| Base auditada (HEAD anterior) | **`854dc86b`** (`feat(v2.32/A12): shadow validation with executed evidence ...`)                                         |
| Doc de cierre (detalle)       | [`cierre-v2.32.1-a12.1-remediacion-auditoria-2026-09-11.md`](./cierre-v2.32.1-a12.1-remediacion-auditoria-2026-09-11.md) |

El **diff a revisar** es exactamente:

```
git diff 854dc86b..aefbf7eb        # la remediación de código (23 ficheros)
git show f39a6c10                  # el documento de cierre + CHANGELOG
git show 0d4c39c2                  # este audit pack
```

## 1. Cómo reproducir la verificación (sin entorno del autor)

Requisitos: `uv` + Python 3.12. Postgres 16 **solo** para la suite `lifecycle-pg`.

```bash
git fetch --tags origin
git checkout v2.32.1-beta

# --- Calidad (no requiere DB) ---
uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml   # All checks passed
uv run lint-imports --config packages/py/.importlinter                  # 4 kept, 0 broken
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent                 # Success

# --- Suite offline (sin DB) ---
uv run pytest packages/py/domain/tests packages/py/market/tests \
  packages/py/analytics/tests \
  packages/py/application/tests/test_strategy_shadow_phase.py \
  packages/py/application/tests/test_strategy_vigilance_phase.py \
  packages/py/application/tests/test_auto_orchestrator.py \
  packages/py/application/tests/test_lab_discovery_dispatch.py \
  packages/py/domain/tests/test_strategy_lifecycle.py \
  apps/api-python/tests/test_auto_orchestrator_worker.py -q
```

Para la certificación con Postgres real:

```bash
# Postgres 16 en localhost:5432 (bolsa/bolsa_dev/bolsa_v1)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
LIFECYCLE_PG_REQUIRED=1 AUTO_ORCHESTRATOR_PG_REQUIRED=1 \
STRATEGY_LIFECYCLE_PG_REQUIRED=1 \
uv run pytest \
  apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py \
  apps/api-python/tests/test_strategy_lifecycle_pg.py \
  packages/py/application/tests/test_sim_strategy_attribution.py -q
# → 12 passed (sin skips)
```

## 2. Matriz hallazgo → commit → punto de código → test

Cada hallazgo auditado tiene (a) el punto de código que lo cierra y (b) un test que lo
bloquea. Los tests son la evidencia ejecutable; el auditor puede correrlos.

| ID     | Hallazgo                                                | Punto de código (en `aefbf7eb`)                                                                          | Test que lo bloquea                                                                                                                                                                              |
| ------ | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| P1-01  | Solape LAB/shadow                                       | `strategy_shadow_phase.split_holdout`; `auto_orchestrator._resolve_holdout`/`_candidate_with_lab_cutoff` | `test_strategy_shadow_phase.py::test_shadow_replay_splits_holdout_after_lab_end`, `::test_shadow_replay_fails_closed_without_separation`, `::test_shadow_replay_requires_holdout_when_requested` |
| P1-02  | E2E no certificado por commit                           | `.github/workflows/python-ci.yml` job `lifecycle-pg`                                                     | CI `lifecycle-pg` (skip = fallo)                                                                                                                                                                 |
| P1-02  | E2E determinista sin SKIPPED                            | `test_a11_discovery_to_auto_sim_pg._seed_instrument_with_bars`/`_make_discovery_runner`                  | `test_a11_discovery_to_auto_sim_pg.py` (fill = aserción dura)                                                                                                                                    |
| P2-01  | DD fail-open                                            | `strategy_lifecycle.ShadowPolicy.evaluate`                                                               | `test_strategy_lifecycle.py::test_shadow_policy_fails_closed_when_drawdown_missing`                                                                                                              |
| P2-02  | Override humano en AUTO                                 | `auto_orchestrator_worker.orchestrator_loop`/`_default_orchestrator`                                     | `test_auto_orchestrator_worker.py::test_loop_does_not_pass_shadow_override`, `::test_default_orchestrator_does_not_wire_shadow_override`                                                         |
| P2-03  | Sin fingerprint del dataset                             | `strategy_shadow_phase` (`_fingerprint_kwargs`, `_bars_hash`); migración `034`                           | `test_strategy_shadow_phase.py::test_shadow_replay_fingerprint_is_reproducible`                                                                                                                  |
| P2-04  | `trades` cuenta piernas                                 | `strategy_lifecycle.ShadowPolicy` (`min_closed_round_trips`); `strategy_shadow_phase`                    | `test_strategy_lifecycle.py::test_shadow_policy_round_trips_is_the_sample_guard`                                                                                                                 |
| P2-05  | `run_id` constante                                      | `auto_orchestrator_worker._new_cycle_id`                                                                 | `test_auto_orchestrator_worker.py` (identidad por ciclo)                                                                                                                                         |
| Aud.2a | `can_transition` fail-open sin gates                    | `strategy_lifecycle.can_transition`                                                                      | `test_strategy_lifecycle.py::test_transition_without_gates_is_fail_closed`, `::test_transition_with_not_evaluated_gate_is_fail_closed`                                                           |
| Aud.2b | `HealthThresholds` predictivos `0.0`                    | `strategy_vigilance_phase.HealthThresholds`/`evaluate_active_health`                                     | `test_strategy_vigilance_phase.py::test_predictive_thresholds_default_to_none`, `::test_unconfigured_thresholds_do_not_degrade`, `::test_calibrated_credibility_threshold_degrades`              |
| GATE-1 | Lector de gates (`robustness`/`walk_forward`/`dsr`) mal | `strategy_lab_phase.evaluate_optimize_result` (`edge_report["suite"]`)                                   | `test_a11_discovery_to_auto_sim_pg.py` (promoción alcanza `active`)                                                                                                                              |

## 3. Checklist de auditoría (sugerido)

- [ ] `git checkout v2.32.1-beta` y confirmar que `aefbf7eb` está en la cadena
      (`git merge-base --is-ancestor aefbf7eb f39a6c10`).
- [ ] Revisar `git diff 854dc86b..aefbf7eb` fichero a fichero contra la matriz de §2.
- [ ] Verificar el **fail-closed** en cada punto: sin evidencia shadow ⇒ no promoción;
      sin frontera de LAB ⇒ no evidencia; sin umbral calibrado ⇒ no degrada por un cero
      fabricado; `can_transition(gates=())` ⇒ `allowed=False`.
- [ ] Confirmar que la migración `034` es aditiva/nullable, sin backfill, con
      `down_revision = "033_position_strategy_attr"` y `downgrade()` completo.
- [ ] Correr la verificación de §1 (calidad + offline). Para la suite PG, §1 con DB.
- [ ] Confirmar invariante **LIVE congelado**: 0 caminos nuevos; `AUTO ⇒ SIMULATED`.
- [ ] Revisar que el job `lifecycle-pg` de `python-ci.yml` usa gates `*_PG_REQUIRED=1`
      (un skip es fallo duro).

## 4. Invariantes congelados (no se tocan en esta remediación)

- `AUTO ⇒ SIMULATED`; `LIVE` bloqueado por `LIVE_EXECUTION_AUTHORIZED` +
  `LIVE_EXECUTION_UNLOCKED` (ambas false). **Cero caminos LIVE nuevos.**
- COACH advisory; RiskGate / SimulationGate / Ledger / Reconciliation deterministas.
- Sin LLM en el hot path. Long-only intacto.

## 5. Fuera de alcance / deuda conocida (no imputable a esta remediación)

Fallos **preexistentes** en el baseline (documentados por transparencia, no introducidos
por `aefbf7eb`):

- `test_scheduler_worker::test_event_loop_starters_reunen_todos_los_workers_periodicos`
  (el set esperado es anterior a `start_auto_orchestrator`).
- `test_queue_poll_worker::test_run_con_arq_es_noop`.
- `test_auto_scheduler_real_pg_zero_human_intervention`.
- Par `test_a9_scheduler_process_pg_zero_human` (requiere Postgres local limpio; falla con
  `MultipleResultsFound` sobre una BD sucia).

> Cierre: [`cierre-v2.32.1-a12.1-remediacion-auditoria-2026-09-11.md`](./cierre-v2.32.1-a12.1-remediacion-auditoria-2026-09-11.md)
