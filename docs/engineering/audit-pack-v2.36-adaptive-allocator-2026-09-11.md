# Audit Pack — V2.36 · Strategy Intelligence adaptativa (incremento 1: carril `adaptive`)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.36, incremento 1** — activar el carril `adaptive` del `DiscoveryBudgetAllocator`
> con un snapshot de evidencia determinista, versionado y persistido, calculado fuera del hot
> path e inyectado en el worker.
>
> **Estado auditado:** `main == cb147d89` == tag **`v2.36-beta`** (base `5348bee0` == tag `v2.35.1-beta`).
> **Alembic head:** `036_discovery_evidence_snapshots`.
> **Bump:** `1.60.1-beta` → `1.61.0-beta`.
> **Flag de rollout:** `AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR` **OFF por defecto** (con OFF, el
> sistema es byte-idéntico a `v2.35.1-beta`).
>
> **Veredicto de CI:** Release-tag CI **GREEN VERIFICADO** para `v2.36-beta` (run
> [`34604803938`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34604803938), conclusión
> `success`, 2026-09-11). Adicionalmente, verificación **local** de los tres bloques (estático,
> offline y PG con gates).

---

## 0. Qué auditar y dónde

| Artefacto             | Ruta                                                                                                                                                                                                        |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Entidad de dominio    | `packages/py/domain/src/bolsa_domain/entities/discovery_evidence_snapshot.py`                                                                                                                               |
| Contrato de repo      | `packages/py/domain/src/bolsa_domain/repositories/discovery_evidence_snapshot_repository.py`                                                                                                                |
| Lectura agregada      | `packages/py/domain/src/bolsa_domain/repositories/research_trial_repository.py` (Protocol) · `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/research_trial_repository.py` (SQL) |
| Builder determinista  | `packages/py/application/src/bolsa_application/discovery_evidence.py`                                                                                                                                       |
| Modelo de tabla       | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` (`DiscoveryEvidenceSnapshotRow`)                                                                                            |
| Repo SQL del snapshot | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/discovery_evidence_snapshot_repository.py`                                                                                       |
| Migración             | `packages/py/infrastructure/alembic/versions/036_discovery_evidence_snapshots.py`                                                                                                                           |
| Job batch/CLI         | `apps/api-python/scripts/build_discovery_evidence_snapshot.py`                                                                                                                                              |
| Worker (inyección)    | `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`                                                                                                                                      |
| Relevo de fase        | `docs/engineering/traspaso-relevo-v2-36-adaptive-allocator-2026-09-11.md`                                                                                                                                   |

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

Resultado local observado (2026-09-11): ruff OK · lint-imports 4/4 · mypy **474 files Success**
· offline **1518 passed** · PG **10 passed** + snapshot PG **6 passed** + lifecycle **57 passed**
(anti-explosión `len(plans) == 1784` intacto).

Job batch (manual, contra PG):

```bash
uv run --project apps/api-python python apps/api-python/scripts/build_discovery_evidence_snapshot.py --dry-run
uv run --project apps/api-python python apps/api-python/scripts/build_discovery_evidence_snapshot.py
# 2.ª ejecución sobre la misma evidencia: persisted=false (mismo snapshotHash)
```

---

## 2. Matriz afirmación → código → test

| #   | Afirmación                                                                                                            | Código                                                                           | Test                                                                                                                                                                     |
| --- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | El discovery es una función pura de `(instrument_id, snapshot)`; el aprendizaje se inyecta, no se calcula en el motor | `auto_orchestrator_worker._make_discovery_runner` + `_refresh_adaptive_snapshot` | `test_loop_reads_adaptive_snapshot_once_per_cycle`                                                                                                                       |
| 2   | Misma evidencia ⇒ mismo `snapshot_hash` y mismos pesos                                                                | `discovery_evidence.snapshot_hash`                                               | `test_same_evidence_yields_same_hash_and_weights`                                                                                                                        |
| 3   | El hash es orden-insensible                                                                                           | `compute_family_weights` (orden canónico)                                        | `test_family_order_does_not_change_hash`, `test_snapshot_hash_is_stable_across_equivalent_dicts`                                                                         |
| 4   | Fail-closed: sin evidencia ⇒ `adaptive_weight = 0.0`                                                                  | `compute_lane_weights`                                                           | `test_no_evidence_yields_zero_adaptive_weight`, `test_families_below_min_samples_do_not_enable_lane`, `test_compute_lane_weights_fail_closed_when_total_below_threshold` |
| 5   | Cota anti-multiple-testing del prior                                                                                  | `compute_lane_weights` (clamp)                                                   | `test_adaptive_weight_is_bounded_by_max`, `test_adaptive_weight_never_exceeds_one_even_with_high_scores`                                                                 |
| 6   | El carril adaptativo recibe cupo real sin romper el presupuesto global                                                | `DiscoveryBudgetAllocator.allocate`                                              | `test_allocator_gives_adaptive_lane_a_real_quota_without_breaking_global`, `test_zero_weight_adaptive_lane_keeps_history`                                                |
| 7   | Flag nuevo OFF por defecto                                                                                            | `adaptive_allocator_enabled`                                                     | `test_adaptive_allocator_defaults_off`, `test_start_does_not_wire_adaptive_provider_when_disabled`                                                                       |
| 8   | El snapshot manda sobre el env; sin clave adaptativa ⇒ 0                                                              | `_discovery_allocator`                                                           | `test_allocator_snapshot_overrides_env_weight`, `test_allocator_snapshot_without_adaptive_key_is_fail_closed`                                                            |
| 9   | Una lectura de snapshot por ciclo (no por instrumento)                                                                | bucle + `_refresh_adaptive_snapshot`                                             | `test_loop_reads_adaptive_snapshot_once_per_cycle`                                                                                                                       |
| 10  | Con el flag OFF no se toca la BD (byte-idéntico a v2.35.1)                                                            | `start_auto_orchestrator`                                                        | `test_loop_without_provider_does_not_touch_snapshot`                                                                                                                     |
| 11  | Provider que falla ⇒ fail-closed, no tumba el ciclo                                                                   | `_refresh_adaptive_snapshot`                                                     | `test_refresh_adaptive_snapshot_fail_closed_on_provider_error`                                                                                                           |
| 12  | Migración aditiva con `up`/`down` limpio                                                                              | `036_discovery_evidence_snapshots.py`                                            | `test_migration_036_roundtrip`                                                                                                                                           |
| 13  | `save` idempotente por hash (snapshots inmutables)                                                                    | repo SQL                                                                         | `test_save_is_idempotent_by_hash`, `test_batch_job_is_idempotent_by_hash`                                                                                                |
| 14  | `get_latest`/`get_by_hash` devuelven el snapshot correcto                                                             | repo SQL                                                                         | `test_get_by_hash_and_latest`                                                                                                                                            |
| 15  | Agregación por familia H0 determinista y ordenada                                                                     | `family_evidence_summary`                                                        | `test_family_evidence_summary_aggregates_by_preset`                                                                                                                      |
| 16  | El job es idempotente de verdad (corte dato-dependiente)                                                              | `build_discovery_evidence_snapshot.py`                                           | `test_batch_job_is_idempotent_by_hash` + ejecución manual (2.ª = `persisted=false`)                                                                                      |

---

## 3. Invariantes congelados (no se tocan en v2.36 incremento 1)

- `AUTO ⇒ SIMULATED`; **LIVE bloqueado**; **sin LLM en hot path**; fail-closed; long-only.
- H1 (`require_holdout=True` inviolable) y H2 (identidad de dataset) intactos.
- Gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar.
- Sin backfill; migración aditiva con `downgrade()`.
- Test anti-explosión `len(plans) == 1784` intacto (sin cambios).
- Con `AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR` OFF: salida **byte-idéntica a v2.35.1**.

---

## 4. Checklist de auditoría (sugerido)

- [ ] `036` es aditiva y su `downgrade()` deja la BD como estaba (`test_migration_036_roundtrip`).
- [ ] Ningún camino del motor consulta la BD por evidencia: el snapshot entra solo por el seam del worker.
- [ ] Con el flag OFF no hay lectura de `discovery_evidence_snapshots` en el ciclo.
- [ ] El peso adaptativo es 0.0 sin snapshot / sin evidencia (fail-closed honesto).
- [ ] El reparto del allocator nunca supera `max_candidates` ni `max_trials_total`.
- [ ] El corte temporal del snapshot es dato-dependiente (idempotencia real del job).
- [ ] `math_version` presente en entidad, payload y tabla.

---

## 5. Fuera de alcance (incremento 2)

- **Emisión adaptativa real** de candidatas nuevas en el carril con cupo (hoy solo se asigna
  cupo observable).
- Cualquier forma de bandit online o aprendizaje no determinista en el hot path.
- Persistir `lane`/`grammar_plan` por trial (habilitaría ponderación por carril real; hoy la
  ponderación es por familia H0 ya persistida).
