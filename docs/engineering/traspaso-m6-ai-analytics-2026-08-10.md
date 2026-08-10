# Traspaso M6 — AI / Analytics (`py/ai` + `py/analytics`) · 2026-08-10

> **Este documento es el punto de entrada para el chat/hilo que ejecute M6.**
> Resumen ejecutivo del **estado verificado** del repo tras cerrar M4 (2026-08-10),
> preparado para continuar en un **hilo nuevo** sin perder contexto. No se re-descubre nada:
> cada hecho de abajo está confirmado en el repo/CI.

## 0. Qué es M6 (fuente: `docs/engineering/general-audit-plan-2026-08-10.md` §5)

Fila de la tabla de módulos:

> **M6 — AI / analytics** (`py/ai` doc vs código, motores backtest/indicadores) | `py/ai` (doc vs código), motores backtest/indicadores | Riesgo **Medio** | Prioridad ★★

Orden sugerido del plan 08-10:
1. **M0** (docs) — cerrado
2. **M1 + M2** (reproducibilidad/versiones) — cerrados
3. **M3 / M4 / M6** (backend por capas) → **M3 cerrado** (`db7e5e5`), **M4 cerrado** (`69820c1`), **M6 es el siguiente**
4. **M5** (frontend por features) — lo más grande, dividido
5. **M7** (dev-stack residual F3.7)

> **Decisión de orden:** tras M3/M4 (backend), el siguiente natural es **M6**, que continúa la
> descomposición por capas backend; M5 (frontend) queda para después por ser el más grande y
> requerir un hilo dedicado amplio.

## 1. Protocolo sagrado (leer y respetar — mismo que M1/M2/M3/M4)

1. **Tolerancia cero a fallos.** No asumir: verificar siempre en el repo/CI.
2. **Preservación funcional absoluta.** Un cambio solo si es necesario y probado.
3. **Alcance atómico.** Un módulo por hilo; no tocar nada ajeno a M6 (ni M3 domain/application, ni
   M4 infrastructure, ni M5 frontend).
4. **Flujo en 3 fases:** FASE 1 (diagnóstico, sin cambios) → FASE 2 (plan atómico + aprobación del
   usuario) → FASE 3 (ejecución + batería + commit + push + registro). Sin aprobación explícita
   **no se toca código ni se commitea.**
5. **Docs como fuente de verdad.** Anclar decisiones a ficheros reales.
6. «No romper NADA»: batería completa de tests antes y después.

## 2. Estado del repo al crear este traspaso (2026-08-10, tras M4)

- Rama activa: `stage/estudio-membership-operativa-2026-08-04`.
- HEAD: `69820c1` (cierre M4 — fuente de verdad del modelo + ADR-025 + registro §7.4). **Working tree limpio**,
  sincronizado con `origin/<rama>`.
- Commit M4: `69820c1` "M4: decidir/registrar fuente de verdad del modelo de datos (Prisma dueño DDL ·
  SQLAlchemy runtime · Alembic placeholder) + ADR-025 + registro §7.4" (solo docs: 4 ficheros, +115/−2).

### Commits de módulos anteriores (todos pusheados, CI verde)

| Commit | Módulo / contenido |
| ------ | ----------------- |
| `69820c1` | M4 · Fuente de verdad del modelo (ADR-025) + registro §7.4 |
| `d7b9d99` | docs · Traspaso M4 (entrada) |
| `db7e5e5` | M3 · Cierre capa de dominio + registro §7.3 |
| `b82b48c` | docs · Traspaso M3 (entrada) |
| `0469fa2` | M2 · Registro docs §7.2 |
| `57d81cd` | M2 · Fix CI frontend declarar @types/node |
| `ae79c62` | M2 · Fix CI frontend build shared |
| `20ecad0` | M2 · @types react/react-dom 19.2.18/19.2.4 |

## 3. Hechos de diagnóstico confirmados (relevantes para M6)

- **Batería CI backend (`python-ci.yml`):** `ruff check packages/py apps/api-python --config pyproject.toml`
  (select E/F/I/UP/B) + `mypy ... domain market infrastructure api-python --follow-imports=silent`
  (`continue-on-error: true`) + `pytest market/tests analytics/tests apps/api-python/tests`
  con `--ignore=apps/api-python/tests/integration --ignore=apps/api-python/tests/test_lists.py
  --ignore=apps/api-python/tests/test_workspaces.py`.
- **Verificado en HEAD `69820c1` (2026-08-10):**
  - `ruff` solo el `B007` conocido (`packages/py/infrastructure/tests/test_daily_ops_digest_pdf.py:54`,
    mini-módulo alternativo/independiente a M6).
  - `mypy` deuda no bloqueante: **454 errores en 99 ficheros** (continue-on-error; sin errores nuevos).
  - `pytest` CI: **434 passed / exit 0** (market + analytics + api-python, con los ignores del workflow).
    El conjunto amplio con domain/application/infrastructure = **663 passed / 2 failed** (`test_list_unsubscribe_index.py`,
    pre-existentes documentados desde §4j/M1).
- **Nota entorno Windows:** `uv` NO está en PATH de PowerShell; usar ruta completa
  `$env:USERPROFILE\.local\bin\uv.exe`. Patrón de commit: `git commit --no-verify` (hook lint-staged
  dispara prettier sobre ficheros legacy con CRLF desincronizado; documentado desde M1).

## 4. Mapeo M6 (inventario confirmado)

### 4.1 `packages/py/ai` — `bolsa_ai` (AI Governance · RFC-007)

- `pyproject.toml`: `bolsa-ai` 0.1.0, `requires-python>=3.12`, **solo `httpx>=0.28`** (dev: `pytest>`);
  tipo `hatchling`, `force-include` de `src/bolsa_ai/prompts`.
- `src/bolsa_ai/`: `adapters/` (base, ollama, openai), `audit_sink.py`, `guardrails.py`, `models.py`,
  `proxy.py`, `registry.py`, `schemas.py`, `__init__.py` (+ dir `prompts/`).
- `tests/`: `test_audit_sink.py`, `test_backtest_coach_schema.py`, `test_golden_and_ollama.py`
  (marker `ollama` = requiere servicio Ollama), `test_proxy_heuristic.py`.
- **Estado (verificado en M0/§6):** `bolsa_ai` está **implementado** (no placeholder). Fue corregido
  `docs/ARCHITECTURE.md` (§8.1/6.4) y `packages/py/README.md` para listarlo.

### 4.2 `packages/py/analytics` — `bolsa_analytics` (análisis determinista / motores)

- `pyproject.toml`: `bolsa-analytics` 0.1.0, deps `bolsa-domain`, `bolsa-ai`, `numpy>=2.0`,
  `pandas>=2.2`, `vectorbt>=0.26`, `optuna>=4.0`; extra `minimal` (solo domain) y `ml` (`lightgbm>=4.0`).
- `src/bolsa_analytics/` (módulos):
  - `cognitive/` (28 ficheros): decision_memory/session/outcome/replay, confidence_lifecycle, edge_report,
    evidence(_engine), effectiveness, gate_decision, investor_profile, macro_facts/inputs, market_events/state,
    observe_profile, order_intent, policy_gate, psr_dsr, recommendation, score_macro, stats_suite,
    suggest_policy, trading_policy(_templates), trials_log, weight_rules, auto_live.
  - `features/` (catalog, compute_bridge, indicator_ids, models, online_adapter, ports).
  - `indicators/` (compute, legacy).
  - `knowledge/` (28 ficheros): assessment, as_of_cut, composite_score, core_r_review_evidence,
    decision_package_ta, decision_runtime, dia_d_session_evidence, evidence_assessment, filing_ask/summary,
    fundamental_assessment/card/copilot/facts/inputs, macro_assessment, news_assessment, opportunity,
    score_fund, score_ta, technical_assessment/facts, models.
  - `optimize/` (15 ficheros): cpcv, engines, grid_is_metrics, holdout, lab_edge_report, macd_grid, metrics,
    optuna_sma, pbo, rsi_grid, sma_grid, vectorbt_sma, walk_forward.
  - `prediction/` (heuristic, lightgbm_direction, models, ports, registry, service).
  - `research/` (11 ficheros): data_snapshot, hybrid_definition, indicator_definition_validator, llm_draft,
    llm_indicator_draft, manifest, prompt_draft, prompt_indicator_draft, scan_manifest, strategy_definition_validator.
  - `signals/` (13 ficheros): data_quality_v1, evaluate, feature_cache, fundamental_gate, fundamental_screener,
    hybrid_scan, pattern_uptrend_v1, preset_catalog, preset_rules, rules_engine, sector_bands, strategy,
    technical_rating_v1.
  - raíz: `backtest.py`, `cost_model_v2.py`, `drawing_replay.py`, `warmup_matrix.py`.
- `tests/` (~70 ficheros): backtest, cognitive (D1/D3…), composite_score, cost_model, cpcv, decision_*,
  evidence_*, feature_*, filing_*, fundamental_*, gate_*, holdout, hybrid_scan, indicators, knowledge,
  lab_edge_report, _grid, _warmup, metrics, multi_assessment, news, _presets, oos, opportunity, pattern,
  pbo, prediction, prompt_*, recommendation, research_manifest, rules_engine, scan_manifest, sector_bands,
  signal_*, sma_grid, strategy_*, technical_*, vectorbt_optuna, walk_forward, warmup_matrix.

## 5. Frentes a resolver (para el chat M6 — heredados, no consensuados)

Esto **no** es un plan consensuado, es el diagnóstico heredado + elaboración. El chat M6 debe, en FASE 1
(diagnóstico, **sin cambios**):

1. **`py/ai` doc vs código**: confirmar que la documentación (ARCHITECTURE, README, ADR-003 §10 orden IA)
   refleja el `bolsa_ai` implementado (Proxy, Prompt Registry, adapters LLM, audit/guardrails). Auditar
   coherencia RFC-007 ↔ implementación.
2. **Motores backtest/indicadores (`py/analytics`)**: coherencia entre `backtest.py`, `optimize/metrics.py`,
   `indicators/`, `signals/`. Especial atención al **hallazgo M3 §7.3**: `optimize.py:209` (application)
   re-implementa la fórmula `trial_score` de analytics inline con inconsistencia interna `round 6` vs
   `round 4` → requiere decisión de salida numérica (NO tocar sin aprobación explícita; solo documentar en M6).
3. **Herencia `vectorbt==1.1.0`**: fijado en M1 (mantenimiento parado). Auditar los motores de optimización
   que lo usan (`vectorbt_sma`, `vectorbt_optuna`) — preservar, no perseguir upgrades.
4. **ML optional (`lightgbm`)**: extra `ml` en analytics; `prediction/lightgbm_direction.py`. Verificar que
   los tests que lo requieren no bloqueen CI (lightgbm podría no estar instalado en el venv CI).
5. **Batería aplicable de M6**: `ruff` + `mypy` + `pytest` (referencia cierre M4: ruff solo `B007`, pytest
   **434 passed / exit 0** en CI, conjunto amplio 663/2 pre-existentes, mypy 454 continue-on-error).
6. **No tocar** ni el frontend web (M5) ni M3/M4 (aunque `analytics` → `application` es un flujo legítimo,
   los cambios de salida numérica son riesgo y requieren batería + aprobación).

## 6. Documentos fuente de verdad / índices

- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/general-audit-plan-2026-08-10.md` (§4 hallazgos, §5 módulos, §7 registros M0)
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.1 M1, §7.2 M2, §7.3 M3, §7.4 M4)
- `docs/engineering/traspaso-m4-infraestructura-datos-2026-08-10.md` (precedente más reciente del patrón)
- `docs/engineering/traspaso-m3-dominio-2026-08-10.md`
- `docs/ARCHITECTURE.md` · `docs/PROJECT_PREMISES.md` · `docs/DATA_MODEL.md` · `docs/adr/*` (especialmente
  ADR-003 §10 orden IA · ADR-005 IA strategy · RFC-007 AI Governance)
- `packages/py/ai/pyproject.toml` · `packages/py/analytics/pyproject.toml`
- `docs/engineering/code-documentation-standard-2026-08-03.md` (docstrings forward-only)

> Al cierre de M6 (FASE 3), actualizar `dev-continuation-plan-2026-08-09.md` con una sección **7.5**
> nueva (patrón §7.1–7.4) y añadir/confirmar este fichero en el índice engineering (bajo Product/Ops,
> junto a los traspasos).
