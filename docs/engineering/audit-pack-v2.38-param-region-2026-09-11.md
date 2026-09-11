# Audit Pack — V2.38 · Granularidad por región de parámetros (incremento 3)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.38** — la evidencia adaptativa deja de agregarse solo por familia H0
> (`preset_key`) y pasa a granularidad por **región de parámetros**, con bucket
> determinista y versionado, columna nueva nullable (migración aditiva) y consumo en la
> search policy. Régimen e **instrument class quedan explícitamente fuera** (no existen
> hoy como dato persistido; ver §6).
>
> **Base auditada:** `v2.37-beta` (`main == 13020eeb`).
> **Alembic head:** `038_research_trials_param_region`.
> **Bump:** `1.62.0-beta` → `1.63.0-beta`.
> **Flag de rollout:** `AUTO_ORCHESTRATOR_ADAPTIVE_PARAM_REGION` **OFF por defecto**; con
> OFF el sistema es **byte-idéntico a `v2.37-beta`**.

---

## 0. Qué auditar y dónde

| Artefacto                                    | Ruta                                                                                                              |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Bucket determinista de región (núcleo)       | `packages/py/application/src/bolsa_application/discovery_param_region.py`                                         |
| Señal / snapshot con clave compuesta         | `packages/py/application/src/bolsa_application/discovery_evidence.py`                                             |
| Search policy `v1` + `granularityKeyVersion` | `packages/py/application/src/bolsa_application/discovery_search_policy.py`                                        |
| Emisión adaptativa filtrada por región       | `packages/py/application/src/bolsa_application/strategy_discovery_engine.py`                                      |
| Write-path (runner propaga la región)        | `packages/py/application/src/bolsa_application/orchestrator_lab_runner.py`                                        |
| Write-path (persistencia del trial)          | `packages/py/application/src/bolsa_application/optimization_runs.py`                                              |
| Entidad / Protocol                           | `packages/py/domain/src/bolsa_domain/entities/research_trial.py`, `.../repositories/research_trial_repository.py` |
| Agregación por clave compuesta               | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/research_trial_repository.py`          |
| Modelo de tabla                              | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`                                   |
| Migración                                    | `packages/py/infrastructure/alembic/versions/038_research_trials_param_region.py`                                 |
| Job batch/CLI (merge por clave compuesta)    | `apps/api-python/scripts/build_discovery_evidence_snapshot.py`                                                    |
| Worker (flag + colapso + contadores)         | `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`                                            |

---

## 1. Cómo reproducir la verificación

```bash
# --- 1) Calidad (no requiere DB) ---
uv run ruff check <ficheros tocados>          # el repo tiene deuda ruff preexistente fuera de alcance
uv run lint-imports --config packages/py/.importlinter
uv run mypy <módulos tocados>

# --- 2) Tests puros (herméticos, sin DB) ---
uv run pytest packages/py/domain/tests packages/py/application/tests \
  apps/api-python/tests/test_auto_orchestrator_worker.py -q

# --- 3) Certificación PG (skip = fallo) ---
# PowerShell:
$env:A14_GRAMMAR_PG_REQUIRED="1"
uv run pytest apps/api-python/tests/test_discovery_evidence_snapshot_pg.py -q
```

Resultado local observado (2026-09-11): ruff OK (ficheros tocados) · mypy Success en los
módulos tocados · offline **1703 passed** · PG con gates **14 passed** · anti-explosión
`1784` intacto · `--dry-run` OK · sin región, `snapshot_hash` idéntico a v2.37.

> **Nota de entorno:** `uv run lint-imports` no pudo ejecutarse en esta máquina
> (Windows Application Control bloquea el binario, `os error 4551`). Los cuatro contratos
> se han revisado manualmente contra `.importlinter`: `bolsa_domain` **no** gana ninguna
> importación nueva hacia `infrastructure`/`application`/`analytics`/`bolsa_ai` (solo se
> añade un campo a la entidad `ResearchTrial`), y `bolsa_ai` no entra en `domain`.

---

## 2. Matriz afirmación → código → test

| #   | Afirmación                                                     | Código                                                          | Test                                                                                           |
| --- | -------------------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 1   | El bucket es determinista (mismo grid+punto ⇒ misma región)    | `discovery_param_region.param_region_for_point`                 | `test_same_point_yields_same_region`                                                           |
| 2   | Estable ante reordenación del mapping                          | `_canonical_point` + `iter_param_points`                        | `test_region_is_stable_under_mapping_reordering`                                               |
| 3   | Fail-closed: punto fuera del grid ⇒ sin región                 | `param_region_for_point`                                        | `test_point_outside_grid_has_no_region`, `test_unknown_key_has_no_region`                      |
| 4   | Clave compuesta: sin región == familia (compatibilidad)        | `compose_granularity_key`                                       | `test_compose_without_region_is_exactly_family`                                                |
| 5   | Ida y vuelta `compose`/`split`                                 | `compose_granularity_key`/`split_granularity_key`               | `test_compose_and_split_roundtrip`                                                             |
| 6   | Etiquetar no añade espacio de búsqueda                         | `param_region_for_point` sobre el catálogo                      | `test_param_region_does_not_change_search_space`                                               |
| 7   | El motor etiqueta las candidatas con la región                 | `strategy_discovery_engine` (catálogo y adaptive)               | `test_adaptive_emission_filters_to_requested_region`                                           |
| 8   | El runner propaga la región al trial                           | `orchestrator_lab_runner._REGION_KEYS`                          | (write-path cubierto por PG/`optimization_runs`)                                               |
| 9   | La columna existe y roundtrip (com/sin región)                 | tabla + repo SQL `insert_trial`/`_map`                          | `test_param_region_roundtrips`                                                                 |
| 10  | La agregación distingue regiones dentro de la familia          | `family_evidence_summary` (`GROUP BY preset_key, param_region`) | `test_family_evidence_summary_groups_by_composite_key`                                         |
| 11  | El posterior se agrega por clave compuesta                     | `posterior_evidence_summary` + `compose_granularity_key`        | `test_posterior_evidence_summary_keyed_by_composite`                                           |
| 12  | Sin región la clave es la familia (hash idéntico a v2.37)      | `compute_family_weights`                                        | `test_without_region_keys_remain_plain_families`                                               |
| 13  | Dos regiones se agregan por separado                           | `compute_family_weights`                                        | `test_composite_key_isolates_regions`                                                          |
| 14  | El hash es estable y sensible a la región                      | `snapshot_hash` + `compute_family_weights`                      | `test_composite_key_hash_is_stable_and_sensitive_to_region`                                    |
| 15  | `familyGranularity` se puebla (y queda vacío sin región)       | `build_discovery_evidence_snapshot`                             | `test_family_granularity_payload_is_populated_when_region_present`, `..._empty_without_region` |
| 16  | La granularidad es aditiva y NO toca el `snapshot_hash`        | payload + `snapshot_hash`                                       | `test_granularity_does_not_change_snapshot_hash_vs_plain_family`                               |
| 17  | Histórico (sin región) y nuevo (con región) coexisten          | `compute_family_weights`                                        | `test_mixed_region_and_plain_family_coexist`                                                   |
| 18  | La política expone `granularityKeyVersion` y claves compuestas | `discovery_search_policy` `v1`                                  | `test_region_policy_keys_are_composite_and_hash_versioned`                                     |
| 19  | Una región desconocida no emite (fail-closed)                  | motor `_points_for_region`                                      | `test_unknown_region_is_fail_closed`                                                           |
| 20  | Migración 038 aditiva con `up`/`down` limpio                   | `038_research_trials_param_region.py`                           | `test_migration_038_roundtrip`                                                                 |
| 21  | Flag de región OFF por defecto                                 | `adaptive_param_region_enabled`                                 | `test_adaptive_param_region_defaults_off`                                                      |
| 22  | Con OFF las claves compuestas colapsan a familia               | `auto_orchestrator_worker._collapse_regions`                    | `test_collapse_regions_merges_composite_keys`, `test_collapse_regions_noop_without_regions`    |

---

## 3. Invariantes congelados (no se tocan en v2.38)

- `AUTO ⇒ SIMULATED`; **LIVE bloqueado**; **sin LLM en hot path**; fail-closed; long-only.
- H1 (`require_holdout=True` inviolable) y H2 (identidad de dataset) intactos.
- Gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar; Adaptive nunca salta shadow ni promotion gate.
- Test anti-explosión `len(plans) == 1784` intacto (solo se **etiqueta**, no se añade espacio).
- El aprendizaje no entra en el hot path: el worker lee e inyecta; el motor sigue puro.
- Con el flag OFF: salida y `snapshot_hash` **byte-idénticos a v2.37**.

---

## 4. Checklist de auditoría (sugerido)

- [ ] El bucket de región es determinista, versionado y fail-closed (sin invención).
- [ ] Sin región, la clave compuesta es la familia y el `snapshot_hash` no cambia.
- [ ] `038` es aditiva, nullable, sin backfill, y su `downgrade()` deja la BD como estaba.
- [ ] La agregación por región es retrocompatible (todo `NULL` ⇒ agregación por familia).
- [ ] El motor filtra `param_points()` a la región y no emite si la región no existe.
- [ ] El flag OFF deja la salida byte-idéntica a v2.37 (colapso a familia).
- [ ] `familyGranularity` está fuera del `snapshot_hash` y dentro de `evidence_fingerprint`.
- [ ] Régimen e instrument class **no** se inventan (no hay dato persistido).

---

## 5. Fuera de alcance (siguiente evolución)

- Granularidad por **régimen**: requiere persistir el régimen (hoy solo existe como
  clasificación en memoria en `bolsa_analytics.cognitive.market_state`) como fuente de
  verdad en el ledger de research.
- Granularidad por **clase de instrumento**: requiere poblar `instruments.type`/`sector`
  con valores reales (hoy `type` es un enum de un valor y `sector` es texto libre vacío).
- Bandit online o cualquier aprendizaje no determinista en el hot path.
- Persistir `lane`/`grammar_plan`/`search_policy_hash`/`param_region` por trial para
  ponderar por carril real (hoy `param_region` ya se persiste; el resto no).

---

## 6. Por qué régimen e instrument class quedan fuera (decisión explícita)

Investigación previa verificada en código (no en docs):

- **Régimen**: solo vive en la capa cognitiva en memoria
  (`packages/py/analytics/src/bolsa_analytics/cognitive/market_state.py`); **jamás** se
  escribe en `research_trials` ni en `research_evidence`. Etiquetar los trials con un
  régimen calculado _a posteriori_ sería inventar el dato (no es el régimen que el motor
  vio al decidir).
- **Instrument class**: `InstrumentRow.type` usa `INSTRUMENT_TYPE_ENUM = ENUM("stock")`
  con **un solo valor** y `sector` es texto libre sin poblar. El concepto real
  ("equities") solo existe en Trading Policy, sin join a research.

Incorporarlos exige **primero persistirlos como fuente de verdad**; la clave compuesta
`compose_granularity_key` está diseñada para admitir nuevos componentes sin romper el
contrato ni el hash histórico.
