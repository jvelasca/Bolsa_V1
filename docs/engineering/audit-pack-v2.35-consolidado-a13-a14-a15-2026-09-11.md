# Audit Pack — V2.35 / Consolidado A13 · A14 · A15

> **Para el auditor externo.** Punto de entrada único para auditar desde **GitHub**, sin acceso
> al entorno de desarrollo, las tres últimas fases del núcleo de Strategy Intelligence:
> **A13 — Paper Forward**, **A14 — Strategy Intelligence (gramática controlada de Discovery)** y
> **A15 — Observabilidad y gobernanza de la gramática**. Fecha: 2026-09-11. Estado auditado:
> `main` == `f47e0ceb`, tag **`v2.35-beta`**.

## 0. Qué auditar y dónde

| Elemento                     | Referencia                                                                                                                                      |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Estado auditado (HEAD)       | `f47e0ceb` (`main` == `origin/main`), tag anotado **`v2.35-beta`**                                                                              |
| Tag anterior certificado     | `v2.34-beta` → `129f3baa`                                                                                                                       |
| Diff recomendado             | `git diff v2.34-beta..v2.35-beta` (A15) · `git diff v2.32.1-beta..v2.34-beta` (A13+hardening+A14)                                               |
| Relevo A13 (`paper forward`) | [`traspaso-relevo-tag-v2-33-...`](./traspaso-relevo-post-v2-33-a13-hardening-a14-2026-09-11.md)                                                 |
| Relevo A14 (gramática)       | [`traspaso-relevo-post-v2-34-a14-strategy-intelligence-2026-09-11.md`](./traspaso-relevo-post-v2-34-a14-strategy-intelligence-2026-09-11.md)    |
| Relevo A15 (observabilidad)  | [`traspaso-relevo-post-v2-35-a15-grammar-observability-2026-09-11.md`](./traspaso-relevo-post-v2-35-a15-grammar-observability-2026-09-11.md)    |
| Audit-pack de la fase previa | [`audit-pack-v2.33-2026-09-11.md`](./audit-pack-v2.33-2026-09-11.md) · [`audit-pack-v2.32.1-2026-09-11.md`](./audit-pack-v2.32.1-2026-09-11.md) |
| Estado vivo del proyecto     | [`PROJECT_STATE.md`](./PROJECT_STATE.md)                                                                                                        |

> **Nota de honestidad sobre Releases.** El último Release público de GitHub era `v2.11-beta`
> (2026-09-06). Este pack se acompaña de la **publicación de los Releases** de los hitos
> posteriores para que la historia sea navegable. Los tags existen desde mucho antes; los
> Releases se estaban creando por fase y quedaron rezagados. Ver §6 para el inventario completo
> tag → commit → veredicto de CI (incluyendo los dos tags cuyo Release-tag CI **no** quedó verde).

El **diff real a revisar** es:

```bash
git fetch --tags origin
git diff v2.32.1-beta..v2.35-beta     # A13 (paper forward) + hardening H1/H2 + A14 + A15
```

---

## 1. Cómo reproducir la verificación

Requisitos: `uv` + Python 3.12. Postgres 16 **solo** para las suites de certificación.

```bash
git fetch --tags origin
git checkout v2.35-beta

# --- 1) Calidad (no requiere DB) ---
uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml   # All checks passed
uv run lint-imports --config packages/py/.importlinter                  # 4 kept, 0 broken
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent                 # Success

# --- 2) Tests puros (herméticos, sin DB) ---
uv run pytest \
  packages/py/application/tests/test_paper_forward_phase.py \
  packages/py/application/tests/test_discovery_grammar.py \
  packages/py/application/tests/test_strategy_discovery_engine.py \
  packages/py/application/tests/test_auto_orchestrator.py \
  apps/api-python/tests/test_auto_orchestrator_worker.py -q

# --- 3) Certificación PG (skip = fallo) ---
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
PAPER_FORWARD_PG_REQUIRED=1   uv run pytest apps/api-python/tests/test_a13_paper_forward_pg.py -q
AUTO_ORCHESTRATOR_PG_REQUIRED=1 uv run pytest packages/py/application/tests/test_auto_orchestrator.py -q
```

Smoke de la migración (una sola cabeza, `035`):

```bash
cd packages/py/infrastructure
uv run alembic heads          # → 035_paper_forward_evidence (head)
uv run alembic upgrade head
uv run alembic downgrade -1   # → 034_shadow_dataset_fingerprint; downgrade() completo
uv run alembic upgrade head
```

Verificación consolidada por el CI del tag (9 jobs obligatorios; un rojo no-GREENea el tag):

```bash
gh run list --workflow=release-tag-ci.yml --branch v2.35-beta
# → Release tag CI: success (security · shared · spine · frontend · python ·
#   playwright-mock · lifecycle-pg · dr-verify · a7-gate → certify GREEN)
```

---

## 2. A13 — Paper Forward de la ACTIVE (tag `v2.33.0-beta`)

Se paraleliza/continúa el forward de la estrategia **ACTIVE** sobre barras nuevas
post-promoción, con evidencia persistence aditiva (migración `035`).

| ID     | Afirmación                                             | Punto de código                                                       | Test que lo bloquea                                                                                                            |
| ------ | ------------------------------------------------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| A13-01 | Forward solo sobre barras nuevas post-promoción        | `paper_forward_phase.split_forward`; `PaperForwardConfig.promoted_at` | `test_paper_forward_phase.py::test_split_forward_keeps_only_bars_after_promotion`                                              |
| A13-02 | Sin barras nuevas ⇒ sin evidencia (fail-closed)        | `run_paper_forward` (`forward_sin_barras`)                            | `test_paper_forward_phase.py::test_paper_forward_without_new_bars_is_fail_closed`; E2E `test_a13_forward_requires_new_bars_pg` |
| A13-03 | Señal desde la definición de la ACTIVE (un solo motor) | `extract_active_executable` + `rules_grid._simulate_rules_strategy`   | `test_paper_forward_phase.py::test_extract_active_executable_none_when_missing`                                                |
| A13-04 | Guarda de muestra en round-trips cerrados              | `PaperForwardPolicy.min_closed_round_trips`                           | `test_strategy_lifecycle.py::test_paper_forward_fails_closed_without_sample`                                                   |
| A13-05 | DD fail-closed (métrica ausente ≠ sin riesgo)          | `PaperForwardPolicy.evaluate`                                         | `test_strategy_lifecycle.py::test_paper_forward_fails_closed_when_drawdown_missing`                                            |
| A13-06 | Evidencia reproducible (fingerprint)                   | `paper_forward_phase._fingerprint_kwargs`/`_bars_hash`                | `test_paper_forward_phase.py::test_paper_forward_fingerprint_is_reproducible`                                                  |
| A13-07 | Persistencia aditiva, sin backfill                     | migración `035_paper_forward_evidence`; `PaperForwardResultRow`       | `alembic heads`/`downgrade`; `test_strategy_lifecycle_pg.py::test_paper_forward_result_persistence_pg`                         |
| A13-08 | Evidencia atribuida a la `version_id` de la ACTIVE     | store `save_forward_result`/`list_forward_results`                    | `test_a13_paper_forward_pg.py` (round-trip persistido)                                                                         |
| A13-09 | Wiring AUTO OFF por defecto (reversible)               | `auto_orchestrator_worker.forward_enabled`/`_make_forward_runner`     | `test_auto_orchestrator_worker.py::test_forward_defaults_off`                                                                  |
| A13-10 | Forward tras el ciclo y antes de la vigilancia         | `auto_orchestrator_loop(forward_runner=...)`                          | `test_auto_orchestrator_worker.py::test_loop_runs_forward_between_cycle_and_watch`                                             |
| A13-11 | Certificación PG obligatoria por commit (skip = fallo) | `.github/workflows/python-ci.yml` job `paper-forward-pg`              | CI `paper-forward-pg` (`PAPER_FORWARD_PG_REQUIRED=1`)                                                                          |
| A13-12 | Cero caminos LIVE                                      | `LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`               | `test_a13_paper_forward_pg.py` (0 eventos de venue LIVE)                                                                       |
| A13-13 | El forward no rompe el ciclo ni inventa evidencia      | `_make_forward_runner` (try/except fail-closed)                       | `test_auto_orchestrator_worker.py` (runner opcional)                                                                           |

Detalle completo en [`audit-pack-v2.33-2026-09-11.md`](./audit-pack-v2.33-2026-09-11.md).

---

## 3. Hardening H1+H2 (sin tag propio; commit `61e613b1`)

Salda dos hallazgos de la auditoría V2.32.1, **sin migración**:

| ID  | Afirmación                                                           | Punto de código                                 | Test que lo bloquea                                     |
| --- | -------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------- |
| H1  | El hold-out es **inviolable** en toda ruta de promoción productiva   | `require_holdout=True` cableado en la promoción | tests de promoción (`test_strategy_promotion_phase.py`) |
| H2  | Identidad de dataset ampliada (`instrument_id`/`timeframe`/`source`) | `dataset fingerprint` (`bars_hash` enriquecido) | tests de fingerprint de dataset                         |

---

## 4. A14 — Strategy Intelligence (gramática controlada de Discovery) — tag `v2.34-beta`

Discovery pasa de un **catálogo** de familias técnicas a una **gramática controlada** que compone
bloques funcionales (`REGIME + TREND FILTER + MOMENTUM + ENTRY TRIGGER + EXIT`), con `TRIGGER`/`EXIT`
obligatorios y máx. 3 opcionales. Enumeración **determinista** y presupuesto único (`GrammarBudget`),
con techo fijado por test anti-explosión (**1784 planes**). **Sin segundo motor ni segundo FSM.**

Cierra el **gap bloqueante de promoción**: la vía declarativa del LAB (`_run_cpcv`/`_run_walk_forward`)
gana una rama que reutiliza `split_cpcv_paths` + `_simulate_rules_strategy` y produce
**CPCV/PBO/DSR/WFE reales** (antes quedaban `NOT_EVALUATED` y ninguna candidata de Discovery podía
promocionar). Sana además familias inertes del catálogo previamente cableadas sin señal.

| ID     | Afirmación                                                  | Punto de código                                                      | Test que lo bloquea                                                     |
| ------ | ----------------------------------------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| A14-01 | Gramática compone bloques con obligatorios fijos            | `discovery_grammar.GRAMMAR_COMPONENT_ORDER`/`GRAMMAR_VARIANTS`       | `test_discovery_grammar.py` (composición)                               |
| A14-02 | Enumeración determinista (sin aleatoriedad)                 | `enumerate_grammar_plans`                                            | `test_discovery_grammar.py` (orden estable, mismo input→mismo output)   |
| A14-03 | Techo combinatorio acotado (**1784 planes**)                | `enumerate_grammar_plans` + `GrammarBudget`                          | `test_discovery_grammar.py` (anti-explosión `len(plans) == 1784`)       |
| A14-04 | Presupuesto único compartido (catálogo + gramática)         | `GrammarBudget` / `DiscoveryBudget`                                  | `test_strategy_discovery_engine.py` (cupos)                             |
| A14-05 | La vía declarativa produce CPCV/PBO/DSR/WFE reales          | `_run_cpcv`/`_run_walk_forward` + `split_cpcv_paths`                 | `test_lab_discovery_dispatch.py`; PG `test_a14_grammar_discovery_pg.py` |
| A14-06 | Sin segundo motor de trading / sin segundo FSM              | reutiliza `rules_grid._simulate_rules_strategy`                      | (invariante) revisión de imports + import-linter                        |
| A14-07 | Gramática **OFF por defecto** (`AUTO_ORCHESTRATOR_GRAMMAR`) | `auto_orchestrator_worker.grammar_enabled`/`_grammar_budget`         | `test_auto_orchestrator_worker.py` (`defaults_off`, `enabled_truthy`)   |
| A14-08 | Familias inertes del catálogo saneadas                      | `_simulate_rules_strategy` (ramas de familia)                        | `test_strategy_discovery_engine.py` (familias producen señal)           |
| A14-09 | Cero caminos LIVE                                           | (invariante) `LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` | (invariante) revisión de imports                                        |

---

## 5. A15 — Observabilidad y gobernanza de la gramática — tag `v2.35-beta`

Hace **gobernable el rollout** de la gramática de A14 con **observabilidad de solo lectura**, sin
cambiar decisiones, presupuestos, gates ni migración. Nuevo `DiscoveryEmissionSummary` + API aditiva
`discover_for_instrument_with_summary(...)`; `OrchestratorResult` gana conteos aditivos; el worker
AUTO emite logs estructurados y acumula contadores de proceso.

| ID     | Afirmación                                                        | Punto de código                                                                                                                          | Test que lo bloquea                                                                                                |
| ------ | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| A15-01 | La observabilidad **no** cambia la emisión con gramática OFF      | `discover_for_instrument` (wrapper delega en `_with_summary`, descarta summary)                                                          | `test_discovery_grammar.py::test_summary_grammar_disabled_is_byte_identical_to_wrapper`                            |
| A15-02 | Resumen reporta procedencia catálogo vs gramática y suma al total | `DiscoveryEmissionSummary`; `discover_for_instrument_with_summary`                                                                       | `test_discovery_grammar.py::test_summary_counts_catalog_and_grammar_and_sums_to_total`                             |
| A15-03 | Con gramática OFF, gramática = 0                                  | `DiscoveryEmissionSummary.grammar_candidates`                                                                                            | `test_discovery_grammar.py::test_summary_grammar_disabled_reports_zero_grammar_candidates`                         |
| A15-04 | Warm-up (`bar_count_ok`) reportado, no impuesto                   | `DiscoveryEmissionSummary.bar_count_ok`                                                                                                  | `test_discovery_grammar.py::test_summary_grammar_warmup_flag_is_false_when_bar_count_is_low`                       |
| A15-05 | Resumen determinista                                              | `discover_for_instrument_with_summary`                                                                                                   | `test_discovery_grammar.py::test_summary_is_deterministic`                                                         |
| A15-06 | `OrchestratorResult` agrega conteos de LAB/SHADOW por procedencia | `auto_orchestrator.py` (`catalog_candidates`, `grammar_candidates`, `lab_grammar_evaluated`, `shadow_started`, `shadow_grammar_started`) | `test_auto_orchestrator.py::test_orchestrator_reports_grammar_provenance_and_lab_shadow`                           |
| A15-07 | Shadow fail-closed: sin provider de barras ⇒ `shadow_started=0`   | `_run_shadow` (ausencia de evidencia ≠ aprobación)                                                                                       | `test_auto_orchestrator.py::test_orchestrator_reports_grammar_provenance_and_lab_shadow`                           |
| A15-08 | Con provider, `shadow_started` cuenta el replay real              | `auto_orchestrator.py` (shadow con barras)                                                                                               | `test_auto_orchestrator.py::test_orchestrator_counts_shadow_started_with_provider`                                 |
| A15-09 | El worker acumula contadores y emite `cycle_summary`              | `auto_orchestrator_worker` (`GrammarObservabilityCounters`, `_record_discovery_summary`)                                                 | `test_auto_orchestrator_worker.py::test_grammar_runner_records_enabled_counters`, `::test_loop_logs_cycle_summary` |
| A15-10 | Contadores monótonos entre ciclos                                 | `_GRAMMAR_COUNTERS`                                                                                                                      | `test_auto_orchestrator_worker.py::test_grammar_counters_are_monotonic_across_calls`                               |
| A15-11 | Sin persistencia en DB (sin migración A15)                        | —                                                                                                                                        | `alembic heads` sigue `035`; (ausencia de migración 036)                                                           |
| A15-12 | Cero caminos LIVE; sin LLM en hot path                            | (invariante) freeze                                                                                                                      | (invariante) revisión de imports                                                                                   |

> **Deuda declarada (no imputable a A15):** los contadores de A15 son de **proceso** (logs +
> memoria), no persistidos. Convertir la procedencia en consultable desde la BD (sin migración,
> vía `strategy_candidates.strategy_family LIKE 'grammar:%'`) es el objeto de una fase posterior
> (A16, aparcada a fecha de este pack).

---

## 6. Inventario tag → commit → veredicto de CI (desde `v2.11-beta`)

Veredicto = resultado de la **última** ejecución de `release-tag-ci` disparada por el tag (run
`push`). Esta columna es deliberadamente honesta: **no todos los tags están verdes**.

| Tag            | Commit     | Fecha      | Release-tag CI |
| -------------- | ---------- | ---------- | -------------- |
| `v2.12-beta`   | `b9b35ec2` | 2026-09-07 | ⚠️ failure     |
| `v2.13-beta`   | `6e279e2d` | 2026-09-07 | ✅ success     |
| `v2.14-beta`   | `78dd3f9a` | 2026-09-08 | ✅ success     |
| `v2.14.1-beta` | `99f049a6` | 2026-09-08 | ✅ success     |
| `v2.14.2-beta` | `2a98886c` | 2026-09-08 | ✅ success     |
| `v2.15-beta`   | `7c6d624e` | 2026-09-08 | ✅ success     |
| `v2.15.1-beta` | `2f967fa6` | 2026-09-08 | ✅ success     |
| `v2.15.2-beta` | `f2e37d93` | 2026-09-08 | ✅ success     |
| `v2.15.3-beta` | `5ef9016b` | 2026-09-08 | ✅ success     |
| `v2.16-beta`   | `39b16f4a` | 2026-09-09 | ✅ success     |
| `v2.16.1-beta` | `1596f4ad` | 2026-09-09 | ✅ success     |
| `v2.17-beta`   | `79df594c` | 2026-09-09 | ✅ success     |
| `v2.18-beta`   | `bd2bd163` | 2026-09-09 | ✅ success     |
| `v2.19-beta`   | `1bca9bab` | 2026-09-09 | ✅ success     |
| `v2.20-beta`   | `2a62873a` | 2026-09-09 | ✅ success     |
| `v2.21-beta`   | `ca98a39e` | 2026-09-09 | ✅ success     |
| `v2.22-beta`   | `88d129e7` | 2026-09-10 | ⚠️ failure     |
| `v2.23-beta`   | `738d0eff` | 2026-09-10 | ✅ success     |
| `v2.24-beta`   | `b2ee67ed` | 2026-09-10 | ✅ success     |
| `v2.24.2-beta` | `a970f053` | 2026-09-10 | ✅ success     |
| `v2.25-beta`   | `a970f053` | 2026-09-10 | ✅ success     |
| `v2.26-beta`   | `a970f053` | 2026-09-10 | ✅ success     |
| `v2.29-beta`   | `99c4a9d3` | 2026-09-10 | ✅ success     |
| `v2.30-beta`   | `0d111b41` | 2026-09-10 | ✅ success     |
| `v2.31-beta`   | `740d54c0` | 2026-09-11 | ✅ success     |
| `v2.32.1-beta` | `f552716e` | 2026-09-11 | ✅ success     |
| `v2.34-beta`   | `129f3baa` | 2026-09-11 | ✅ success     |
| `v2.35-beta`   | `f47e0ceb` | 2026-09-11 | ✅ success     |

> Los tags `v2.24-beta`/`v2.25-beta`/`v2.26-beta` apuntan al **mismo commit** (`a970f053`,
> fix de head-guard `029→030`): son re-tags de la misma elevación, no fases distintas.

---

## 7. Invariantes congelados (no se tocan en A13/A14/A15)

- `AUTO ⇒ SIMULATED`; **LIVE bloqueado** por `LIVE_EXECUTION_AUTHORIZED` +
  `LIVE_EXECUTION_UNLOCKED` (ambas false). **Cero caminos LIVE nuevos.**
- `PAPER_D_EXECUTE` off. Sin LLM en el hot path. Long-only intacto.
- COACH advisory; RiskGate / SimulationGate / Ledger / Reconciliation deterministas.
- Fail-closed: ausencia de evidencia ≠ aprobación.
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo.
  Alembic head único: **`035_paper_forward_evidence`**.
- Gramática A14 tras `AUTO_ORCHESTRATOR_GRAMMAR` (**OFF por defecto**).
- A15 es **solo lectura**: no cambia ninguna decisión.

---

## 8. Checklist de auditoría (sugerido)

- [ ] `git checkout v2.35-beta` y confirmar la cadena `v2.32.1-beta → v2.34-beta → v2.35-beta`.
- [ ] Revisar `git diff v2.32.1-beta..v2.35-beta` fichero a fichero contra §2–§5.
- [ ] Confirmar el **fail-closed** de A13 (barras nuevas) y de A15 (shadow sin provider ⇒ 0).
- [ ] Confirmar que la gramática A14 es **determinista** y el techo anti-explosión (1784 planes) sigue.
- [ ] Confirmar que A15 **no** cambia la emisión con gramática OFF (test de regresión byte-idéntico).
- [ ] Confirmar migración única `035`, aditiva/nullable, `downgrade()` completo, sin migración en A14/A15.
- [ ] Confirmar **OFF por defecto** de `AUTO_ORCHESTRATOR_GRAMMAR` y wiring reversible.
- [ ] Confirmar invariante **LIVE congelado**: 0 caminos nuevos; `AUTO ⇒ SIMULATED`.
- [ ] Correr la verificación de §1 (calidad + puros + PG).
- [ ] Revisar §6 y aceptar/rebatir los dos tags en ⚠️ (`v2.12-beta`, `v2.22-beta`).

---

## 9. Fuera de alcance (no imputable a A13/A14/A15)

- **A16 — Gobernanza del rollout con datos reales**: convertir la procedencia de A15 en consultable
  desde la BD (sin migración) y fijar la política de producción (allowlist de bloques/variantes y
  presupuesto). **Aparcada** a fecha de este pack.
- Contadores de A15 no persistidos (deuda declarada, §5).
- Fases LIVE (thaw) y sus gates: ver `roadmap-live-execution-core-2026-09-07.md`.

---

> Cierres por fase: [`cierre-v2.33-a13-paper-forward-2026-09-11.md`](./cierre-v2.33-a13-paper-forward-2026-09-11.md) ·
> relevos A14/A15 enlazados en §0.
