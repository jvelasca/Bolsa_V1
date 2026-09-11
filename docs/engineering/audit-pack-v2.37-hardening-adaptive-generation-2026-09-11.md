# Audit Pack — V2.37 · Hardening de V2.36 (P2-01/02/03) + Adaptive Discovery Generation

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.37** — cerrar los tres P2 de la auditoría de `v2.36-beta` y habilitar la
> **emisión adaptativa real** (el carril `adaptive` deja de ser solo cupo y pasa a decidir
> qué hipótesis se exploran), sin relajar ningún gate.
>
> **Base auditada:** `v2.36-beta` (`main == cb147d89`).
> **Alembic head:** `037_discovery_evidence_freshness`.
> **Bump:** `1.61.0-beta` → `1.62.0-beta`.
> **Elevación:** `main == 13020eeb` == tag **`v2.37-beta`**, Release-tag CI **GREEN verificado**
> (run [`34619419865`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34619419865), `success`).
> **Flags de rollout:** `AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR` y
> `AUTO_ORCHESTRATOR_ADAPTIVE_GENERATION` **OFF por defecto**; con ambos OFF el sistema es
> **byte-idéntico a `v2.36-beta`**. `AUTO_ORCHESTRATOR_ADAPTIVE_MAX_STALENESS_DAYS` default 30.

> **Nota de CI (fix de deuda):** los tests `test_discovery_evidence.py`,
> `test_discovery_search_policy.py` y `test_discovery_evidence_snapshot_pg.py` existían desde
> v2.36 pero **no estaban cableados en ningún job** (los workflows enumeran ficheros, no globs).
> Se han incorporado al job `python-offline` y al `grammar-discovery-pg`/`lifecycle-pg` en el
> commit `13020eeb`, de modo que el tag los certifica.

---

## 0. Qué auditar y dónde

| Artefacto                                  | Ruta                                                                                                                  |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Señal compuesta v1 (P2-01)                 | `packages/py/application/src/bolsa_application/discovery_evidence.py`                                                 |
| Política exploración/explotación (P2-02)   | `packages/py/application/src/bolsa_application/discovery_catalog.py`                                                  |
| Entidad + freshness + fingerprint (P2-03)  | `packages/py/domain/src/bolsa_domain/entities/discovery_evidence_snapshot.py`                                         |
| Search policy (incremento 2)               | `packages/py/application/src/bolsa_application/discovery_search_policy.py`                                            |
| Emisión adaptativa en el motor             | `packages/py/application/src/bolsa_application/strategy_discovery_engine.py`                                          |
| Agregación LAB enriquecida + posterior     | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/research_trial_repository.py`              |
| Repo del snapshot (fingerprint)            | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/discovery_evidence_snapshot_repository.py` |
| Migración                                  | `packages/py/infrastructure/alembic/versions/037_discovery_evidence_freshness.py`                                     |
| Job batch/CLI                              | `apps/api-python/scripts/build_discovery_evidence_snapshot.py`                                                        |
| Worker (freshness + inyección de política) | `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`                                                |

---

## 1. Cómo reproducir la verificación

```bash
# --- 1) Calidad (no requiere DB) ---
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
  packages/py/infrastructure/src packages/py/application/src apps/api-python/src \
  --follow-imports=silent

# --- 2) Tests puros (herméticos, sin DB) ---
uv run pytest packages/py/domain/tests packages/py/application/tests \
  apps/api-python/tests/test_auto_orchestrator_worker.py -q

# --- 3) Certificación PG (skip = fallo) ---
# PowerShell:
$env:A14_GRAMMAR_PG_REQUIRED="1"; $env:LIFECYCLE_PG_REQUIRED="1"; $env:AUTO_ORCHESTRATOR_PG_REQUIRED="1"
uv run pytest apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py \
  apps/api-python/tests/test_a14_grammar_discovery_pg.py \
  apps/api-python/tests/test_discovery_evidence_snapshot_pg.py -q
uv run pytest apps/api-python/tests/test_strategy_lifecycle_pg.py -q
```

Resultado local observado (2026-09-11): ruff OK · lint-imports 4/4 · mypy **475 files Success**
· offline **1547 passed** · PG discovery/snapshot **12 passed** + snapshot detallado
**10 passed** + lifecycle **6 passed**.

Job batch (manual, contra PG):

```bash
uv run --project apps/api-python python apps/api-python/scripts/build_discovery_evidence_snapshot.py --dry-run
# mathVersion = discovery_evidence_v1; evidenceFingerprint presente; fail-closed 0.0 sin evidencia
uv run --project apps/api-python python apps/api-python/scripts/build_discovery_evidence_snapshot.py
# 2.ª ejecución: persisted=false (mismo snapshotHash)
```

---

## 2. Matriz afirmación → código → test

| #   | Afirmación                                                    | Código                                                 | Test                                                                                                                  |
| --- | ------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| 1   | La v1 no satura el score por encima de 1.0                    | `discovery_evidence._normalize_is_score`/`_saturating` | `test_v1_does_not_saturate_above_one`                                                                                 |
| 2   | Una métrica ausente es neutral (no 0, no premio)              | `_family_strength_v1` (shrinkage por cobertura)        | `test_v1_absent_metric_is_neutral_not_penalized`                                                                      |
| 3   | Drawdown, profit factor y evidencia posterior mueven la señal | `_v1_components`                                       | `test_v1_drawdown_and_profit_factor_move_the_signal`, `test_v1_posterior_evidence_raises_strength`                    |
| 4   | La fórmula v0 sigue siendo reproducible                       | `_family_strength_v0`                                  | `test_v0_math_version_is_still_reproducible`                                                                          |
| 5   | La agregación LAB reporta cobertura sin inventar ceros        | `family_evidence_summary`                              | `test_family_evidence_summary_aggregates_rich_metrics`                                                                |
| 6   | La evidencia posterior se agrega por familia y nivel          | `posterior_evidence_summary`                           | `test_posterior_evidence_summary_by_family`                                                                           |
| 7   | El adaptive nunca absorbe el presupuesto de exploración       | `DiscoveryBudgetAllocator.allocate` (floor)            | `test_exploration_floor_guarantees_exploration_under_extreme_adaptive`, `test_adaptive_never_absorbs_all_exploration` |
| 8   | Con ratio 0 el reparto es el histórico                        | `exploration_floor_ratio`                              | `test_exploration_floor_zero_keeps_history`                                                                           |
| 9   | Snapshot stale ⇒ descartado (peso 0)                          | `_refresh_adaptive_snapshot` + `is_fresh`              | `test_stale_snapshot_is_discarded_fail_closed`                                                                        |
| 10  | Staleness 0 desactiva la validación (compat)                  | `adaptive_max_staleness_days`                          | `test_staleness_check_disabled_accepts_old_snapshot`                                                                  |
| 11  | La huella del dataset se persiste y roundtrip                 | tabla + repo                                           | `test_fingerprint_persists_and_roundtrips`                                                                            |
| 12  | Migración 037 aditiva con `up`/`down` limpio                  | `037_discovery_evidence_freshness.py`                  | `test_migration_037_roundtrip`                                                                                        |
| 13  | La search policy es determinista                              | `build_search_policy`                                  | `test_same_snapshot_yields_same_policy_and_hash`                                                                      |
| 14  | La política es fail-closed sin snapshot/cupo/evidencia        | `build_search_policy`                                  | `test_no_snapshot_is_empty_policy`, `test_zero_cap_is_empty_policy`, `test_no_evidence_is_empty_policy`               |
| 15  | La exploración nunca se agota                                 | `_apportion` + tramos                                  | `test_exploitation_never_absorbs_all`                                                                                 |
| 16  | La emisión adaptativa respeta el cupo y el global             | `discover_for_instrument_with_summary`                 | `test_adaptive_emission_emits_within_global_budget`                                                                   |
| 17  | Sin política el carril no emite (v2.36)                       | motor (`search_policy=None`)                           | `test_adaptive_emission_without_policy_keeps_history`                                                                 |
| 18  | La emisión adaptativa es determinista                         | motor                                                  | `test_adaptive_emission_is_deterministic`                                                                             |
| 19  | Flag de generación OFF por defecto                            | `adaptive_generation_enabled`                          | `test_adaptive_generation_defaults_off`                                                                               |

---

## 3. Invariantes congelados (no se tocan en v2.37)

- `AUTO ⇒ SIMULATED`; **LIVE bloqueado**; **sin LLM en hot path**; fail-closed; long-only.
- H1 (`require_holdout=True` inviolable) y H2 (identidad de dataset) intactos.
- Gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar; Adaptive nunca salta shadow ni promotion gate.
- Test anti-explosión `len(plans) == 1784` intacto.
- El aprendizaje no entra en el hot path: el worker lee e inyecta; el motor sigue puro.
- Con ambos flags OFF: salida **byte-idéntica a v2.36**.

---

## 4. Checklist de auditoría (sugerido)

- [ ] La v1 conserva información por encima de `is_score` 1.0 (no satura).
- [ ] Una métrica ausente no se puntúa como 0 ni se premia por ausencia.
- [ ] El carril adaptativo no puede superar su cota ni comerse el suelo de exploración.
- [ ] Un snapshot `stale` no gobierna el reparto (fail-closed) y `MAX_STALENESS_DAYS=0` es compat.
- [ ] `037` es aditiva y su `downgrade()` deja la BD como estaba.
- [ ] La emisión adaptativa nunca supera `adaptive_cap` ni `max_candidates`/`max_trials_total`.
- [ ] Sin política o con flags OFF la salida es la histórica (v2.36).
- [ ] `math_version`/`evidence_fingerprint` presentes en entidad, payload y tabla.

---

## 5. Fuera de alcance (siguiente evolución)

- Bandit online o cualquier aprendizaje no determinista en el hot path.
- Granularidad efectiva `family + regime + parameter region + instrument class` (el payload
  publica el hueco `familyGranularity`; falta que el repo agregue por clave compuesta).
- Persistir `lane`/`grammar_plan`/`search_policy_hash` por trial para ponderar por carril real.
