# Audit Pack — V2.38.1 · Hotfix de los 2 P2 de la auditoría de V2.38

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.38.1** — hotfix que cierra los dos P2 conceptuales detectados en la
> **auditoría externa de `v2.38-beta`** (commit `41b96a41`, Release-tag CI GREEN,
> [run 34625070951](https://github.com/jvelasca/Bolsa_V1/actions/runs/34625070951)).
>
> **Base auditada:** `v2.38-beta` (`main == 41b96a41`).
> **Alembic head:** `038_research_trials_param_region` (el hotfix **no** añade migración).
> **Bump:** `1.63.0-beta` → `1.63.1-beta`.
> **Flag:** `AUTO_ORCHESTRATOR_ADAPTIVE_PARAM_REGION` sigue **OFF por defecto**.

---

## 0. Contexto: qué encontró la auditoría de V2.38

La auditoría de `v2.38-beta` emitió **8,9 / 10** con **P0 = 0, P1 = 0, P2 = 2**:

| ID        | Hallazgo                                                                                         | Severidad |
| --------- | ------------------------------------------------------------------------------------------------ | --------- |
| **P2-01** | El claim "byte-idéntico a V2.37 con flag OFF" **no se cumple** numéricamente.                    | P2        |
| **P2-02** | `evidence_fingerprint` no ordenaba por clave compuesta (fragilidad latente de determinismo).     | P2        |
| **P3**    | `MATH_VERSION_SEARCH_POLICY_V0` reescrito in-place (irreproducibilidad de políticas históricas). | P3        |
| **P3**    | `test_granularity_does_not_change_snapshot_hash_vs_plain_family` era tautológico.                | P3        |

---

## 1. P2-01 — La equivalencia con V2.37 no era real

**Diagnóstico.** El write-path (`strategy_discovery_engine`) etiquetaba
`discovery_param_region` **siempre, sin consultar el flag**. Consecuencia: con OFF los
trials igualmente llevaban región → el snapshot contenía claves compuestas →
`_collapse_regions` **sí se ejecutaba** y colapsaba con `max(peso)`, criterio conservador
pero **no equivalente** a la fuerza que V2.37 calcularía sobre la familia agregada. El
snapshot solo persiste `family_weights`/`sample_sizes`, por lo que `_collapse_regions`
**no puede** recomputar la fuerza sobre el agregado familiar.

**Divergencia medida** (mismo trial set: 3 trials en `sma|r00:aaa` + 4 en `sma|r01:bbb`):

```
V2.37 real       : {'sma': 0.747045}   samples {'sma': 7}
V2.38 colapsado  : {'sma': 0.802329}   samples {'sma': 7}   ← max(0.528, 0.802)
DIVERGE peso? True    DIVERGE samples? False
```

≈ **7,4 %** de desviación en el peso adaptativo (el `sample_sizes` coincidía).

**Fix aplicado (equivalencia real, no aproximada).**

- El motor recibe la decisión como **dependencia inyectada**, sin romper su pureza:
  `discover_for_instrument_with_summary(..., emit_param_region: bool = True)`.
- Con `emit_param_region=False` las candidatas **no** llevan `discovery_param_region`; el
  dict de `params` es byte-idéntico al histórico de V2.37.
- El worker pasa `emit_param_region=adaptive_param_region_enabled()`: con OFF **no se
  genera región**, la evidencia nueva es idéntica a V2.37 y el colapso es un no-op.
- `_collapse_regions` se **conserva**, pero reencuadrado como puente para **evidencia
  histórica** ya persistida con región (transición ON→OFF), con docstring corregido para
  no prometer equivalencia numérica.

**Artefactos:** `strategy_discovery_engine.py` (firma + dos construcciones de candidata),
`auto_orchestrator_worker.py` (pasa el flag; docstrings de `_collapse_regions` y
`adaptive_param_region_enabled`).

**Tests nuevos:** `test_emit_param_region_false_omits_region_key`,
`test_emit_param_region_true_labels_region`,
`test_emit_param_region_false_is_byte_identical_to_v237_params` (application);
`test_runner_passes_emit_param_region_false_when_flag_off`,
`test_runner_passes_emit_param_region_true_when_flag_on` (worker).

---

## 2. P2-02 — Orden incompleto en `evidence_fingerprint`

**Diagnóstico.** `compute_family_weights` ordenaba por `(presetKey, paramRegion)` pero
`evidence_fingerprint` solo por `presetKey`. Con varias regiones de una misma familia el
orden relativo dependía del orden de entrada (`sorted` es estable), lo que hacía frágil un
valor que es **identidad del dataset**.

**Fix.** Orden canónico por clave compuesta en el fingerprint. **Tests nuevos:**
`test_fingerprint_is_order_insensitive_across_regions`,
`test_fingerprint_is_order_insensitive_across_families_and_regions`.

---

## 3. P3 — Versionado y test tautológico

- **`MATH_VERSION_SEARCH_POLICY`.** Coexisten `_V0 = "discovery_search_policy_v0"` y
  `_V1 = "discovery_search_policy_v1"`, con alias `MATH_VERSION_SEARCH_POLICY` = vigente.
  Antes `_V0` valía `..._v1` (reescrito in-place) y una política histórica no era
  distinguible. **Tests:** `test_math_versions_are_distinct_and_reproducible`,
  `test_region_policy_uses_v1_math_version`.
- **Test del hash.** Se documenta la naturaleza tautológica del test original y se añade la
  comprobación real: recalcular `snapshot_hash` sobre los componentes declarados reproduce
  el hash almacenado ⇒ el payload (granularidad y fingerprint) no participa.

---

## 4. Qué auditar

| Artefacto                                   | Ruta                                                                         |
| ------------------------------------------- | ---------------------------------------------------------------------------- |
| Inyección del flag en el motor              | `packages/py/application/src/bolsa_application/strategy_discovery_engine.py` |
| Orden canónico del fingerprint              | `packages/py/application/src/bolsa_application/discovery_evidence.py`        |
| Versionado de la search policy              | `packages/py/application/src/bolsa_application/discovery_search_policy.py`   |
| Worker (pasa el flag + colapso documentado) | `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`       |

---

## 5. Cómo reproducir la verificación

```bash
# --- Calidad (invocación EXACTA de CI: el root afecta a la clasificación de imports) ---
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/application/src/bolsa_application/discovery_evidence.py \
             packages/py/application/src/bolsa_application/discovery_search_policy.py \
             packages/py/application/src/bolsa_application/strategy_discovery_engine.py \
             apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py

# --- Tests puros (herméticos, sin DB) ---
uv run pytest packages/py/application/tests \
              apps/api-python/tests/test_auto_orchestrator_worker.py -q
```

---

## 6. Matriz de aserciones → código/tests

| Aserción                                                       | Código                                                     | Test                                                                    |
| -------------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------- |
| Con OFF, la candidata no lleva región                          | `strategy_discovery_engine.py` (`emit_param_region=False`) | `test_emit_param_region_false_omits_region_key`                         |
| Con OFF, `params` es byte-idéntico a V2.37                     | idem                                                       | `test_emit_param_region_false_is_byte_identical_to_v237_params`         |
| El worker inyecta el flag                                      | `auto_orchestrator_worker.py` (`_discover`)                | `test_runner_passes_emit_param_region_false_when_flag_off` (+ `_true_`) |
| El fingerprint es determinista ante orden adverso              | `discovery_evidence.py` (`evidence_fingerprint`)           | `test_fingerprint_is_order_insensitive_across_regions` (+ familias)     |
| `familyGranularity` fuera del `snapshot_hash`                  | `discovery_evidence.py` (`snapshot_hash`)                  | `test_granularity_does_not_change_snapshot_hash_vs_plain_family`        |
| v0 y v1 de la search policy coexisten                          | `discovery_search_policy.py`                               | `test_math_versions_are_distinct_and_reproducible`                      |
| El colapso sigue actuando sobre evidencia histórica con región | `auto_orchestrator_worker.py` (`_collapse_regions`)        | `test_collapse_regions_merges_composite_keys`                           |
| Sin región, el colapso es no-op                                | idem                                                       | `test_collapse_regions_noop_without_regions`                            |

---

## 7. Invariantes intactas

`AUTO ⇒ SIMULATED` · LIVE bloqueado · sin LLM en hot path · fail-closed · H1/H2 · long-only ·
gates CPCV/PBO/DSR/WFE/OOS sin relajar · anti-explosión `len(plans) == 1784` · Alembic head
`038_research_trials_param_region`.

---

## 8. Verificación local ejecutada

```
ruff (--config pyproject.toml)        → All checks passed
mypy (4 módulos tocados)              → Success: no issues found
pytest (application + worker + PG)    → 1497 passed
```
