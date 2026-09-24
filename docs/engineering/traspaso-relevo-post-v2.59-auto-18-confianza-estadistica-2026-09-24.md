# Traspaso de relevo — `AUTO-18` **CERRADA** (`V2.59` / `1.84.0-beta`)

**Fecha:** 2026-09-24 · **Rama:** `main` en **fast-forward** · **Tag:** `v2.59-beta` ·
**Fase anterior:** `AUTO-17` (tag `v2.58-beta` → `72f6084a`) · **Commit de partida del paquete:** `75913f0c`.

**Documentos de la fase:** [plan](./plan-v2-59-auto-18-confianza-estadistica-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-59-auto-18-confianza-estadistica-2026-09-24.md) ·
[arranque del auditor](./arranque-auditor-v2.59-auto-18-confianza-estadistica-2026-09-24.md).

---

## 0. Qué está ratificado y qué se ejecutó

El propietario ratificó **AUTO-18 completo**: los **8 bloques en una sola fase**, un solo sello
`auto18-v1`; el **reparto CAMBIA** (el encogimiento del peso pasa a usar el `effective_N` **estadístico**
y el factor aplicado se **publica**); la `effective_N` estadística se define por **episodios de régimen**
(rachas) acotada por la muestra medida; la **calibración es descriptiva** (read-only). Core backend,
**sin UI**, **sin tocar el gobernador**, **sin SHORT**, **sin migración** y **sin backfill**.

Los siete pasos del plan se ejecutaron en orden, cada uno con su gate. **Cinco realineos declarados** de
la sonda (`M60`, `M125`, `M128`, `M131`, `M134`), todos publicados (§5).

---

## 1. Estado medido del repo (2026-09-24)

| Hecho | Valor medido |
| --- | --- |
| Alembic head | **`046_fill_reference_mid`** (sin cambio: AUTO-18 no migra) |
| Guardia `_ALEMBIC_HEAD` | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` = **`046_fill_reference_mid`** |
| Sello del reparto | `ADAPTIVE_POLICY_VERSION = "auto18-v1"` (`auto_adaptive.py:198`) |
| Sello del gate | `DATA_GATE_POLICY_VERSION = "auto15-v1"` (**intacto**) |
| Compuertas | ruff **`All checks passed!`** · mypy **`Success: no issues found in 499 source files`** · import-linter **`4 kept, 0 broken`** |
| Tramo de la fase | **`311 passed`**, `0` rojos (once suites) |
| Batería pre-tag (selección exacta del CI) | **`2728 passed`**, `0` rojos (sin PG; ver §5) |
| Matriz de mutaciones | **`M1…M148`** (`148/148` muerden) — ver §5 |
| Freeze | `auto_adaptive_journal.py` y `v2_43_governor_evidence.py`: **diff vacío**; `governor.json` sin trackear |
| Flag Adaptive | **OFF** (sin plan, sin lectura, sin encogimiento) |

---

## 2. Lo ya HECHO y verificado (Pasos 1 a 6)

### Paso 1 — Puro de confianza (`auto_adaptive_confidence.py`)

- `measured_n` (ciclos con R medido) + `episodes` (`_episodes`, `:391`) y **`effective_n =
  min(measured_n, episodes)`**; descuento declarado (`ADAPTIVE_CONFIDENCE_EPISODE_DISCOUNT`, `:267`). Los
  ciclos `UNKNOWN` forman/extienden su **propia** racha.
- Cobertura **por régimen** como eje propio (`_coverage_band`, `:416`): `HIGH`/`MEDIUM`/`LOW`/`UNCOVERED`
  desde la muestra **efectiva**; no mueve la banda.
- Calibración **descriptiva** (`ConfidenceCalibration`, `:767`; `_regime_calibration`, `:1026`): por banda
  `n`/`mean_r`/`win_rate`/rango prometido/fiabilidad observada.
- `shrunk_expectancy_r` publicada (`_shrunk`, `:434`) en `RegimeConfidence` (`:634`) y `StrategyConfidence`
  (`:700`).

### Paso 2 — `cost_model_version` aditivo (sin migración)

- `TradingCostModel.cost_model_signature()` (`portfolio_reservation.py:205`) → `cm:<preset|bps>:10/2/5/0`;
  `TradingCost.cost_model_version` (`:263`) y su clave aditiva `costModelVersion` en los dos `to_dict()`
  (`:283`).
- Propaga por `CycleR` (`auto_self_evaluation.py:430`) → `NetRBasisSeries.cost_model_version` (`:746`) →
  `StrategySelfEvaluation`. Sin el campo, el informe es **byte-idéntico**.

### Paso 3 — Transición de modelo de coste

- Clave de agrupación `(basis, cost_model_version)` en `_net_r_series` (`auto_self_evaluation.py:1233`) con
  `_cost_model_key`/`_cost_model_of` (`:1270`/`:1275`): dos metros ⇒ **dos series**, nunca una media.
- `BasisTransition` gana `COST_MODEL_TRANSITION` (`auto_adaptive_confidence.py:210`); `_basis_transition`
  (`:514`) lo detecta; `_decay` (`:577`) bloquea ante `TRANSITION`/`MIXED`/`COST_MODEL_TRANSITION`; el eje
  del neto exige población homogénea (`_net_basis_comparable`, `auto_adaptive.py:1030`).

### Paso 4 — Reparto ajustado y sello `auto18-v1`

- `_confidence_factor` (`auto_adaptive.py:1188`) usa el `effective_n` **estadístico**; el factor aplicado se
  publica en `AllocationPlan.shrink_factors` (`:615`, `:1308`) y la evidencia lleva los seis campos
  (`measuredN`/`episodes`/`effectiveN`/`coverage`/`shrunkExpectancyR`/`shrinkFactor`, `evidence_for` `:830`).
- Sello `ADAPTIVE_POLICY_VERSION = "auto18-v1"` (`:198`). **Aquí SÍ cambia la regla** del reparto.

### Paso 5 — Sonda de mutaciones `M139…M148`

- 10 nuevas + realineos de `M60`, `M125`, `M128`, `M131`, `M134`. Matriz completa `M1…M148` con
  restauración **byte a byte** y huella `git status` idéntica.

### Paso 6 — Deudas P2 (§16–19) en el mismo sello

- Enums cerrados `NetRBasis` (`auto_self_evaluation.py:131`) y `BasisTransition`
  (`auto_adaptive_confidence.py:210`), con los **mismos valores** de string (JSON byte-idéntico).
- Invariante de dominio `affirms_declared_net_r_basis` (`auto_self_evaluation.py:1307`) + guarda en
  `_strategy_row` (`:1424`): un neto **publicado** declara su base (`undeclared` si nadie la firmó).
- `DATA_DEGRADED` (`:253`) para «neto sin base»: **baja la banda** (`_band` `:494`) y añade nota; distinto
  del `UNKNOWN` inocuo.
- Documentado que `MIXED` (heterogeneidad interna) y `TRANSITION` (cambio temporal) son **dos ejes**.

### Paso 7 — Cierre: docs, verificación, bump y sello

- Compuertas con el comando de CI, delta simétrico fichero a fichero con los rojos declarados de antemano,
  paquete de docs, bump `1.84.0-beta`, tag `v2.59-beta`, `main` en fast-forward y PR de auditoría.

---

## 3. Anclas de código (verificadas sobre el árbol que se sella)

| Qué | Dónde |
| --- | --- |
| `_episodes` / `_coverage_band` / `_shrunk` | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_confidence.py:391` / `:416` / `:434` |
| `BasisTransition` (enum) / `_basis_transition` / `_decay` | `.../auto_adaptive_confidence.py:210` / `:514` / `:577` |
| `ConfidenceCalibration` / `AdaptiveConfidence.calibration` | `.../auto_adaptive_confidence.py:767` / `:813` |
| `NetRBasis` (enum) / `NetRBasisSeries` | `.../auto_self_evaluation.py:131` / `:746` |
| `_net_r_series` / `_cost_model_key` / `_cost_model_of` | `.../auto_self_evaluation.py:1233` / `:1270` / `:1275` |
| `affirms_declared_net_r_basis` / guarda | `.../auto_self_evaluation.py:1307` / `:1424` |
| `cost_model_signature` / `TradingCost.cost_model_version` | `.../portfolio_reservation.py:205` / `:263` |
| `_net_basis_comparable` / `_confidence_factor` | `.../auto_adaptive.py:1030` / `:1188` |
| `AllocationPlan.shrink_factors` / `evidence_for` | `.../auto_adaptive.py:615` / `:830` |
| Sello del reparto | `.../auto_adaptive.py:198` |
| Guardia de head de Alembic | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Bloque de la sonda (`M139…M148`) | `apps/api-python/scripts/v2_44_mutation_audit.py` (`MUTATIONS`) |

---

## 4. El método de verificación del repo (no improvisar)

1. **Compuertas con el comando de CI** (no rutas sueltas): `ruff check packages/py apps/api-python
   --config pyproject.toml`, el `mypy` exacto del YAML y `lint-imports --config packages/py/.importlinter`.
2. **pytest con `uv run --no-sync python -m pytest`**: en esta máquina `uv run pytest` lo bloquea la
   directiva de Control de aplicaciones (`os error 4551`).
3. **Sonda de mutaciones**: mide, restaura **byte a byte** y verifica la huella `git status`. Filtro por
   etiqueta para verificar un tramo.
4. **Delta simétrico fichero a fichero**: se corre **la versión de `HEAD`** de cada test modificado contra
   el árbol de la fase (nunca se restan totales).
5. **Los tests PG exigen PostgreSQL real** levantado (compose local); con el puerto cerrado la sonda usa un
   DSN *fast-fail*.

---

## 5. El cierre, hecho y medido

- **Compuertas:** `ruff` **`All checks passed!`**, el `mypy` exacto del YAML **`Success: no issues found in
  499 source files`** e `import-linter` **`4 kept, 0 broken`** (pack §7).
- **Tramo de la fase:** `test_auto_adaptive_confidence.py` + `test_auto_adaptive.py` +
  `test_auto_self_evaluation.py` + `test_cycle_risk.py` + `test_auto_self_evaluation_feed.py` +
  `test_auto_v59_auto18_confidence_seam.py` + `test_auto_v53_auto12_confidence_seam.py` +
  `test_auto_v54_auto13_recovery_seam.py` + `test_auto_v54_auto13_data_gate_wiring_seam.py` +
  `test_auto_v55_auto14_regime_cell_allocation_seam.py` + `test_auto_v57_auto16_applied_cost_seam.py` ⇒
  **`311 passed`**, `0` rojos.
- **Batería completa de analytics+application:** **`3066 passed`**.
- **Batería COMPLETA pre-tag con la selección EXACTA del CI** (la lista literal de `python-ci.yml` sobre
  `uv run --no-sync python -m pytest`, incluidos `apps/api-python/tests` con sus `--ignore`): **`2728
  passed`**, `0` rojos, **`94.07 s`**. Solo queda fuera lo que exige PostgreSQL real (suites PG
  `--ignore`adas, `integration` y `chaos/live_a7`), que corre en los jobs dedicados del tag (§5 y pack §7).
- **Delta simétrico:** ver pack §7 (fichero a fichero, con los rojos declarados de antemano y solo ésos).
- **Matriz COMPLETA `M1…M148`:** corrida entera (`148/148` muerden, `0` fragmentos ausentes, restauración
  byte a byte, huella idéntica). **Cinco realineos declarados** (`M60`, `M125`, `M128`, `M131`, `M134`).
- **Sello `v2.59-beta`:** ver pack §11 (se mide **después** de sellar; el PR de auditoría se abre
  post-sello, mismo patrón que `AUTO-13`…`AUTO-17`).

---

## 6. Límites declarados y freeze

- **La calibración es descriptiva**: publica la fiabilidad observada por banda; no mueve banda ni reparto.
- **El `effective_N` por episodios es una cota conservadora declarada**, no una varianza muestral.
- **`cost_model_version` no se reconstruye hacia atrás**: el histórico queda `None`/`undeclared`.
- **Freeze:** `auto_adaptive_journal.py` y el gobernador **intactos** (diff vacío); sin UI, sin SHORT,
  `*.md` sin `prettier`; `governor.json` sigue sin trackear.

---

## 7. Punto de entrada para el siguiente agente

La fase está **cerrada**: lo que falta es la decisión del propietario sobre `AUTO-19`, no trabajo
pendiente. Candidatos declarados (**no decididos**): ejecución real del `effective_N` sobre varianza
muestral (hoy es cota), caducidad de la racha durable de `AUTO-15`, y la primera toma de decisión con el
flag ON.
