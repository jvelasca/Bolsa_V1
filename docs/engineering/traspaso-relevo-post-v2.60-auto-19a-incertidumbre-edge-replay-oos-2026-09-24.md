# Traspaso de relevo — `AUTO-19A` **CERRADA** (`V2.60` / `1.85.0-beta`)

**Fecha:** 2026-09-24 · **Rama:** `main` en **fast-forward** · **Tag:** `v2.60-beta` ·
**PR de auditoría de la fase:** [#69](https://github.com/jvelasca/Bolsa_V1/pull/69) ·
**Fase anterior:** `AUTO-18` (tag `v2.59-beta` → `1.84.0-beta`, PR de auditoría
[#68](https://github.com/jvelasca/Bolsa_V1/pull/68)).

**Documentos de la fase:** [plan](./plan-v2-60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[arranque del auditor](./arranque-auditor-v2.60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[arranque del agente siguiente](./arranque-agente-post-v2.60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md).

---

## 0. Qué está ratificado y qué se ejecutó

El propietario ratificó **dos decisiones** para esta fase: (1) **solo medición/validación** — el sello del
reparto se queda en **`auto18-v1`** y la asignación **no** cambia; (2) el replay es **estadístico** —
motor puro + fixture grabado + script/reporte, **sin Postgres**. La correlación entre estrategias (bloque 5
del acta) queda para **AUTO-20**.

Los cinco pasos del plan se ejecutaron en orden, cada uno con su gate. **Cero realineos** de la sonda.

---

## 1. Estado medido del repo (2026-09-24)

| Hecho | Valor medido |
| --- | --- |
| Alembic head | **`046_fill_reference_mid`** (sin cambio: AUTO-19A no migra) |
| Guardia `_ALEMBIC_HEAD` | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` = **`046_fill_reference_mid`** |
| Sello del reparto | `ADAPTIVE_POLICY_VERSION = "auto18-v1"` (`auto_adaptive.py:203`) — **NO se mueve** |
| Sello del gate | `DATA_GATE_POLICY_VERSION = "auto15-v1"` (**intacto**) |
| Compuertas | ruff **`All checks passed!`** · mypy **`Success: no issues found in 499 source files`** · import-linter **`4 kept, 0 broken`** |
| Tramo de la fase | **`271 passed`**, `0` rojos (doce suites) |
| Batería pre-tag (selección exacta del CI) | **`2774 passed`**, `0` rojos, `94.98 s` (**+46** sobre `v2.59`) |
| Delta simétrico (versiones de `HEAD` vs árbol de la fase) | **`144 passed`, `0` rojos** (fase puramente aditiva) |
| Matriz de mutaciones | **`M1…M158`** (`158/158` muerden, `0` realineos) — ver §5 |
| Freeze | `auto_adaptive_journal.py` y `v2_43_governor_evidence.py`: **diff vacío**; `governor.json` sin trackear |
| Flag Adaptive | **OFF** (sin plan, sin lectura, sin encogimiento) |

---

## 2. Lo ya HECHO y verificado (Pasos 1 a 4)

### Paso 1 — Puro de incertidumbre (`auto_adaptive_uncertainty.py`, nuevo)

- `ExpectancyInterval` por **bootstrap de EPISODIOS** (`ADAPTIVE_UNCERTAINTY_METHOD = "bootstrap_episodes_v1"`,
  `:94`): percentil sobre **rachas de régimen** remuestreadas **con reemplazo**, con `seed` declarada
  (`:107`) y `resamples` (`:103`); `level` por defecto `0.90` con clamp `[0.5, 0.99]` (`:99`).
- **Honestidad**: sin ciclos medidos ⇒ `point=None` + `no_cycles`; con menos de `min_episodes`
  (`:111`) rachas ⇒ solo el punto + `insufficient_episodes` y edge `UNKNOWN`.
- **`lower ≤ point ≤ upper` por construcción** (`:357-358`, se ensancha si hace falta); `dispersion_r`
  (`:360`) como lectura mínima de estabilidad.
- **`edgeConfidence`** (`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`, `:119-131`) derivado del **signo del intervalo**
  frente a cero, degradado a la baja (suelo `LOW`) por cobertura/deterioro/base, con notas declaradas
  (`:135-141`); `_edge_confidence` (`:375`).
- `AdaptiveUncertainty` por `strategyVersion` **y por celda `strategy × regime`** (`:438`, `:477`, `:554`).
- **Lectores promovidos a público** en `auto_adaptive_confidence.py` (`measured_r` `:407`, `regime_of`
  `:417`, `order_cycles_by_instant` `:422`, `regime_episodes` `:434`, `coverage_band` `:503`): un solo
  productor de la semántica de episodios.

### Paso 2 — Puro de replay OOS (`auto_adaptive_replay.py`, nuevo)

- `REPLAY_METHOD = "statistical_oos_v1"` (`:91`); split **cronológico** IS/OOS con clamp de la fracción
  (`0.10–0.40`, `:95`) y mínimos declarados (`is=8`, `oos=4`, `cells=2`, `:101-107`).
- `_build_cell` (`:290`) mide en el IS la expectancy cruda/encogida, `effective_N`, `episodes`, banda,
  `coverage`, el intervalo y el edge, y en el OOS la expectancy **realizada**; calcula errores y acierto de
  signo; el régimen que **dominó** el OOS (`_majority_regime`, `:267`) decide la celda de cobertura.
- Las **cuatro preguntas** (`:401`, `:436`, `:468`, `:501`) con veredicto
  `supported`/`not_supported`/`inconclusive`, `sample` y métricas; `build_replay_report` (`:539`).
- **CLI sin PG** `scripts/research/auto_replay_battery.py` + **fixture determinista**
  `packages/py/analytics/tests/fixtures/auto_replay_cycles.json` (7 estrategias, una sin material ⇒ 6
  celdas; veredictos medidos: `supported`/`supported`/`not_supported`/`inconclusive`).

### Paso 3 — Cableado aditivo (sin cambiar la regla)

- `auto_adaptive.py`: `StrategyHealth.expectancy_interval`/`edge_confidence` (`:460`/`:464`),
  `uncertainty` en `StrategyHealth`/`AdaptivePlan` (`:537`/`:791`), claves nuevas en `evidence_for`
  (`:873`) y frame `uncertainty` en `as_dict()` (`:913`). **Sin `uncertainty` el plan es byte-idéntico.**
- `auto_self_evaluation_feed.py`: `build_adaptive_uncertainty_from_fills` (`:326`, mismo material, sin
  segundo FIFO).
- `auto_simulation_worker.py`: `_v2_build_adaptive_plan` construye la incertidumbre (`:3104`), registra los
  huecos y la pasa al plan (`:3165`).

### Paso 4 — Sonda de mutaciones `M149…M158`

- 10 etiquetas nuevas + corrida **COMPLETA** `M1…M158` con restauración **byte a byte** y huella `git status`
  idéntica. **Cero realineos** (los fragmentos de `M1…M148` siguen anclados).

---

## 3. Anclas de código (verificadas sobre el árbol que se sella)

| Qué | Dónde |
| --- | --- |
| `bootstrap_episodes_v1` / nivel / semilla / `min_episodes` | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_uncertainty.py:94` / `:99` / `:107` / `:111` |
| Bandas + notas de EDGE / `_edge_confidence` | `.../auto_adaptive_uncertainty.py:119-141` / `:375` |
| `_interval_from_episodes` / `ExpectancyInterval` / `percentile` | `.../auto_adaptive_uncertainty.py:295` / `:175` / `:155` |
| `_cell_uncertainty` / `_strategy_uncertainty` / fachada | `.../auto_adaptive_uncertainty.py:438` / `:477` / `:554` |
| `statistical_oos_v1` / fracción OOS / mínimos | `.../auto_adaptive_replay.py:91` / `:95` / `:101` |
| `_build_cell` / las cuatro preguntas / fachada | `.../auto_adaptive_replay.py:290` / `:401`…`:501` / `:539` |
| Lectores promovidos a público (AUTO-18) | `.../auto_adaptive_confidence.py:407` / `:417` / `:422` / `:434` / `:503` |
| `StrategyHealth.expectancy_interval` / `edge_confidence` | `.../auto_adaptive.py:460` / `:464` |
| `evidence_for` (dos claves nuevas) / frame `uncertainty` | `.../auto_adaptive.py:873` / `:913` |
| Sello del reparto | `.../auto_adaptive.py:203` |
| `build_adaptive_uncertainty_from_fills` | `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py:326` |
| Consumo en el worker | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:3104` / `:3165` |
| Guardia de head de Alembic | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Bloque de la sonda (`M149…M158`) | `apps/api-python/scripts/v2_44_mutation_audit.py` (`MUTATIONS`) |

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
- **Tramo de la fase:** `test_auto_adaptive_uncertainty.py` + `test_auto_adaptive_replay.py` +
  `test_auto_adaptive.py` + `test_auto_adaptive_confidence.py` + `test_auto_self_evaluation_feed.py` +
  `test_auto_v60_auto19_uncertainty_seam.py` + `test_auto_v59_auto18_confidence_seam.py` +
  `test_auto_v53_auto12_confidence_seam.py` + `test_auto_v54_auto13_recovery_seam.py` +
  `test_auto_v54_auto13_data_gate_wiring_seam.py` + `test_auto_v55_auto14_regime_cell_allocation_seam.py` +
  `test_auto_v57_auto16_applied_cost_seam.py` ⇒ **`271 passed`**, `0` rojos.
- **Batería COMPLETA pre-tag con la selección EXACTA del CI** (la lista literal de `python-ci.yml` sobre
  `uv run --no-sync python -m pytest`, incluidos `apps/api-python/tests` con sus `--ignore`): **`2774
  passed`**, `0` rojos, **`94.98 s`**. Solo queda fuera lo que exige PostgreSQL real.
- **Delta simétrico:** las versiones de `HEAD` de los **dos** ficheros de test modificados contra el árbol
  de la fase ⇒ **`144 passed`, `0` rojos**: **no hay un solo rojo que declarar** (fase aditiva).
- **Matriz COMPLETA `M1…M158`:** corrida entera (`158/158` muerden, `0` en `NADA`, `0` fragmentos ausentes,
  restauración byte a byte, huella idéntica). **Cero realineos.**
- **Sello `v2.60-beta`:** medido. El `Release tag CI`
  [`35999631671`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999631671) salió **GREEN a la
  primera** (`10 success` + `1 skipped`, `certify` en `success`) **sin rojos y sin flakes** — nada que
  declarar ni que re-ejecutar (contraste con el flake ajeno que obligó a un re-run en `v2.59`) —, con el job
  `python` del tag en **`2747 passed / 35 skipped`** (**+46** sobre `v2.59`, `0` skips nuevos) y los dos
  `Python CI` per-commit (tag y `main`) **`5/5` verdes**. El PR de auditoría se abre post-sello, mismo
  patrón que `AUTO-13`…`AUTO-18`; las cifras completas viven en el pack §11.

---

## 6. Límites declarados y freeze

- **El intervalo es un bootstrap por episodios**: cota conservadora declarada, no varianza muestral.
- **El replay es estadístico**: no re-simula órdenes; sus veredictos se declaran `inconclusive` sin material.
- **El fixture por defecto es sintético**: mide el instrumento, no la estrategia real.
- **`confidence` no se renombra**: el eje nuevo (`edgeConfidence`) va en campos nuevos.
- **Freeze:** `auto_adaptive_journal.py` y el gobernador **intactos** (diff vacío); sello del reparto
  **`auto18-v1`**; sin UI, sin SHORT, sin backfill; `*.md` sin `prettier`; `governor.json` sigue sin trackear.

---

## 7. Punto de entrada para el siguiente agente

La fase está **cerrada**: lo que falta es la decisión del propietario sobre **`AUTO-20`**, no trabajo
pendiente. Candidatos declarados (**no decididos**): **correlación entre estrategias** (el bloque que
`AUTO-19A` dejó fuera a propósito), **validar la degradación del `edgeConfidence`** en el propio replay,
la **caducidad** de la racha durable de `AUTO-15`, el bootstrap por **bloques de tamaño fijo** si las
rachas son muy desiguales, y la **primera toma de decisión con el flag ON**.
