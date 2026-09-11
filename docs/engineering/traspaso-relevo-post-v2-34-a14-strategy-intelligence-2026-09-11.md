# RELEVO — post V2.34/A14 · Strategy Intelligence (gramática controlada de Discovery) — 2026-09-11

> **Para el agente entrante (con sus subagentes).** Este documento es autocontenido: asume
> **cero contexto previo** más allá de lo que aquí se dice. Léelo entero antes de tocar nada.
> Respeta el estilo del repo: español, fail-closed, sin LLM en hot path, LIVE congelado.
>
> **AsOf:** 2026-09-11 · **Base:** `main` · HEAD local **`114327c3`** (relevo A14) sobre `61e613b1`
> (hardening H1+H2), ancestro `5fcd0224` (cierre A13).
> **Alembic head:** `035_paper_forward_evidence` (SIN migración nueva en A14).
> **Veredicto:** A14 **CERRADA en código y verificada** (working tree **sin commitear**). Pendiente:
> (a) commit, (b) push + tag por parte del owner.

---

## 0. Estado en una frase

Discovery ya no es un catálogo de familias técnicas fijas: es una **gramática controlada**
(`REGIME + TREND FILTER + MOMENTUM + ENTRY TRIGGER + EXIT`, máx. 2–3 opcionales) acotada por
presupuesto determinista, y **la vía declarativa del LAB ya produce gates reales** (antes
`robustness`/`walk_forward` quedaban `NOT_EVALUATED` y ninguna candidata de Discovery podía
promocionar). Sin segundo motor, sin segundo FSM, sin migración.

---

## 1. Contexto mínimo indispensable (verificado en código)

### 1.1 Qué es este proyecto

Monorepo de una plataforma de bolsa. Relevante para esta continuación:

- `packages/py/domain` — dominio puro (entidades del ciclo de vida, promoción, salud).
- `packages/py/application` — fases del orquestador (LAB, shadow, forward, vigilancia), stores,
  Discovery (catálogo + motor + gramática) y `optimize.py`.
- `packages/py/analytics` — motor de reglas/backtest determinista (`rules_grid`, `rules_engine`,
  `indicators/compute.py`).
- `packages/py/infrastructure` — SQLAlchemy + Alembic (PostgreSQL).
- `apps/api-python` — workers de fondo (AUTO), API, y los E2E de certificación PG.

### 1.2 Ciclo estratégico actual (lo que YA existe, no reimplementar)

```
ESTUDIO → DISCOVERY (catálogo + gramática A14) → LAB (CPCV/PBO/DSR/WFE/OOS reales)
        → TOP3 → COACH → FINALISTA
        → SHADOW (hold-out histórico, V2.32/A12, evidencia EJECUTADA)
        → PROMOTION (gate cuantitativo + coach + evidencia shadow)
        → ACTIVE
        → PAPER FORWARD (mercado nuevo post-promoción, V2.33/A13)
        → VIGILANCIA → (degradación) → re-LAB
```

Puntos de anclaje reales (rutas exactas):

- **Único motor declarativo**: `packages/py/analytics/src/bolsa_analytics/optimize/rules_grid.py`
  → `_simulate_rules_strategy(bars, definition, *, initial_cash, trade_from_index,
attach_round_trips, execution_model="next_open")`, y `run_rules_grid_search` (recorre puntos
  del grid con una `template`). Causalidad `index-1 → open(index)`.
- **Evaluador de señales/FSM**: `packages/py/analytics/src/bolsa_analytics/signals/rules_engine.py`
  (`evaluate_rules_signals`, `_series_for_spec` — resolución causal de indicadores).
- **Catálogo de Discovery**: `packages/py/application/src/bolsa_application/discovery_catalog.py`
  (`DiscoveryFamily`, `DISCOVERY_FAMILIES`, `DiscoveryBudget`, `family_by_name`, helpers `_spec`/
  `_cross`/`_compare`/`_price_vs`/`_definition`).
- **Gramática A14 (NUEVO)**: `packages/py/application/src/bolsa_application/discovery_grammar.py`.
- **Motor de Discovery**: `packages/py/application/src/bolsa_application/strategy_discovery_engine.py`
  (`discover_for_instrument` / `discover_candidates` / `discover_from_universe`).
- **LAB**: `packages/py/application/src/bolsa_application/optimize.py`
  (`RunSmaGridOptimize.execute`, `_run_rules`, `_run_cpcv`, `_run_walk_forward`,
  `_run_declarative_partial_on_bars` (NUEVO), `_rules_grid_for`, `_rules_to_grid`).
- **Runner del LAB del AUTO**: `packages/py/application/src/bolsa_application/orchestrator_lab_runner.py`
  (`LabOptimizeRunner`, `_STRUCTURAL_LAB_DEFAULTS`, `_DECLARATIVE_LAB_DEFAULTS` (NUEVO)).
- **Orquestador**: `packages/py/application/src/bolsa_application/auto_orchestrator.py`
  (`OrchestratorDeps`, `_champion_definition`).
- **Worker AUTO**: `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`
  (`auto_orchestrator_loop`, `_make_discovery_runner`, `_discovery_budget`, `_grammar_budget`,
  `grammar_enabled`, env-gates).
- **Shadow**: `strategy_shadow_phase.py` (`split_holdout`, `ShadowReplayConfig`, `run_shadow_replay`).
- **Forward**: `paper_forward_phase.py` (`split_forward`, `PaperForwardConfig`, `run_paper_forward`).
- **Store del ciclo**: `strategy_lifecycle_store.py` (Protocol + InMemory + `PostgresStrategyLifecycleStore`).
- **Tablas**: `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`.

### 1.3 Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado por `LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`
  (ambas false). **Cero caminos LIVE nuevos.**
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en el hot path**.
- **Fail-closed**: ausencia de evidencia ≠ aprobación.
- **H1 — `require_holdout=True` inviolable** en la ruta de promoción; sin `lab_end` no hay replay.
- **H2 — identidad de dataset en `bars_hash`** (`instrument_id`/`timeframe`/`source`/`adjusted`).
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo.
- Long-only intacto. `PAPER_D_EXECUTE` off por defecto.
- Gates intactos: **CPCV, PBO, DSR, WFE, OOS** + coach. No se relaja ningún umbral.

---

## 2. Qué se acaba de hacer (V2.34/A14) — working tree sin commitear

**Ficheros modificados (10):** `.github/workflows/python-ci.yml`, `CHANGELOG.md`,
`apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`,
`apps/api-python/tests/test_auto_orchestrator_worker.py`,
`packages/py/analytics/src/bolsa_analytics/signals/rules_engine.py`,
`packages/py/application/src/bolsa_application/auto_orchestrator.py`,
`packages/py/application/src/bolsa_application/optimize.py`,
`packages/py/application/src/bolsa_application/orchestrator_lab_runner.py`,
`packages/py/application/src/bolsa_application/strategy_discovery_engine.py`,
`packages/py/application/tests/test_lab_discovery_dispatch.py`.

**Ficheros nuevos (4):**
`packages/py/application/src/bolsa_application/discovery_grammar.py`,
`packages/py/application/tests/test_discovery_grammar.py`,
`packages/py/analytics/tests/test_rules_engine_series_wiring.py`,
`apps/api-python/tests/test_a14_grammar_discovery_pg.py`.

### 2.1 Hallazgo bloqueante que A14 cierra (dirigió todo el diseño)

Antes de A14, la vía declarativa del LAB **no podía promocionar nada**:

- `_run_rules` construía `OptimizeSmaGridResult(..., walk_forward=None, cpcv=None)`.
- `orchestrator_lab_runner._STRUCTURAL_LAB_DEFAULTS` **excluía a propósito**
  `cpcv_groups`/`walk_forward_folds` para familias declarativas.
- `_run_h0_partial_on_bars` solo despachaba a `_run_rsi`/`_run_macd`/`_run_sma`.

Consecuencia: `robustness` → `NOT_EVALUATED` (`pbo_ausente`) y `walk_forward` → `NOT_EVALUATED`
para toda familia no-H0. Como `StrategyValidation.passed` exige los 6 gates PASS, **ninguna
candidata de Discovery podía promocionar**. Una gramática nueva habría sido decorativa.

**Segundo hallazgo (saneado en A14):** las plantillas `roc_momentum`, `stoch_rsi_reversion` y
`sar_flip` usaban ids `roc`/`srsi`/`sar` que `_series_for_spec` **no cableaba** ⇒ regla inerte ⇒
familia muda en silencio (fail-closed a 0 señales).

### 2.2 Cambios, por pieza

**a) Wiring causal de indicadores** (`packages/py/analytics/.../signals/rules_engine.py`)
Cableados en `_series_for_spec`: `wma`, `mom`, `sd`, `roc`, `obv`, `mfi`, `bears`, `bulls`,
`aroon` (líneas up/down), `sar` (vía `compute_psar` con `maxAf`, aceptando el alias histórico
`maxStep`) y `srsi` (líneas k/signal). Las guardias de causalidad siguen vetando `fr` y
`ich:chikou` (devuelven `None`). Sana de paso las tres familias inertes del catálogo.

**b) Gramática controlada (NUEVO `discovery_grammar.py`)**

- Vocabulario: `REGIME`, `TREND_FILTER`, `MOMENTUM`, `ENTRY_TRIGGER`, `EXIT`. `TRIGGER`/`EXIT`
  obligatorios; **máx. 3 opcionales** (`MAX_OPTIONAL_COMPONENTS = 3`).
- Variantes declaradas por bloque (`GRAMMAR_VARIANTS`), cada una aporta `build_specs()` y
  `build_rules()` puras.
- **Composición = conjunción plana** de reglas (`operator: "all"`), exactamente el esquema
  `StrategyDefinitionV1` que el motor ya evalúa. **Sin sintaxis nueva, sin nesting.**
- **Vetos**: `_plan_is_coherent` rechaza reglas _idénticas_ repetidas en dos bloques (la
  redundancia real). Compartir _specs_ es legítimo y se deduplica al materializar.
- `GrammarPlan.materialize()` → `StrategyDefinitionV1` (fail-closed: sin trigger/exit ⇒ `None`).
- `GrammarBudget` envuelve `DiscoveryBudget` (`base`), acota `max_components ∈ [1,3]` y
  `max_per_component_variant`, con `normalized()`.
- `enumerate_grammar_plans()` determinista (orden total: nº de componentes → combinación de
  bloques → producto de variantes). **1784 planes** con el presupuesto por defecto (fijado por test).
- `grammar_variants_for_plan()` — **grid de variantes hermanas** del plan (permuta una variante de
  un bloque) para que el LAB re-optimice de verdad y el PBO CSCV tenga columnas que rankear.

**c) Integración en el motor de Discovery** (`strategy_discovery_engine.py`)

- `discover_for_instrument(..., grammar_budget=None)`: con `None` (default) la salida es
  **idéntica** a la de A13 (test de regresión).
- Con gramática: catálogo primero, gramática después, **mismo presupuesto global**. Se **reserva**
  presupuesto (`_grammar_reserve`) para que un catálogo grande no deje a la gramática sin
  candidatas, sin comerse el presupuesto del catálogo.
- Cada candidata gramatical: `strategy_family="grammar:<presetKey>"`, `params["definition"]` =
  definición materializada, `discovery_parent="grammar"` y `params["grammar_variants"]` (grid).

**d) Worker AUTO** (`auto_orchestrator_worker.py`)

- Nuevos env-gates **OFF por defecto**: `AUTO_ORCHESTRATOR_GRAMMAR`,
  `AUTO_ORCHESTRATOR_GRAMMAR_MAX_COMPONENTS` (default 3), `AUTO_ORCHESTRATOR_GRAMMAR_MAX_VARIANTS`
  (default 4). `_make_discovery_runner` pasa `grammar_budget` solo si `grammar_enabled()`.

**e) Gates declarativos reales** (`optimize.py`)

- Nuevo `_run_declarative_partial_on_bars` (análogo a `_run_h0_partial_on_bars`), reutiliza
  `split_cpcv_paths` + `run_rules_grid_search` ⇒ **el único motor**.
- `_run_cpcv` y `_run_walk_forward` ganan `definition`/`grammar_variants` y despachan a la rama
  declarativa cuando hay `definition`. El resto del pipeline (PBO CSCV, agregación, edge report)
  es idéntico al de H0.
- `_rules_grid_for(definition, family_name, candidate_params)`: usa el grid gramatical
  (`grammar_variants`) si la candidata lo trae; si no, el `param_space` del catálogo; si no, el
  punto único (huérfana).
- `RunSmaGridOptimize.execute` gana `grammar_variants` (se propaga a `_run_rules`/CPCV/WF).
- `_rules_to_grid(trial, definition, template)`: **re-materializa la definición con los parámetros
  ganadores** del trial (cierra el bug de propagación del campeón).

**f) Runner del LAB** (`orchestrator_lab_runner.py`)

- Nuevo `_DECLARATIVE_LAB_DEFAULTS = {"cpcv_groups": 4, "walk_forward_folds": 3}` aplicado a
  familias no-H0 (declarativas), de modo que `robustness`/`walk_forward` **se miden**. El candidato
  puede sobreescribirlos.
- `grammar_variants` añadido a `_GRID_KEYS` para que fluya hasta el optimizador.

**g) Propagación del campeón** (`auto_orchestrator.py`)

- `_champion_definition` prefiere la definición re-materializada del campeón
  (`champion_trial.params["definition"]`) sobre la de la candidata, y `champion_params` ya no anida
  la definición. Verificado: candidata `ema(20,100)` ⇒ `executable` campeón `ema(10,50)`.

### 2.3 Verificación reproducible (ya pasada en esta sesión)

```bash
# Bloque 1: estático (verde)
uv run ruff check packages/py apps/api-python --config pyproject.toml   # All checks passed
uv run lint-imports --config packages/py/.importlinter                  # 4 kept, 0 broken
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent                 # Success (470 files)

# Bloque 2: quality offline (2 ficheros nuevos añadidos a la lista del job `quality`)
#   → 1232 passed
# Copia el comando `uv run pytest ...` del job `quality` de python-ci.yml
#   (ahora con --ignore=apps/api-python/tests/test_a14_grammar_discovery_pg.py).

# Bloque 3: PG de certificación (Postgres 16 en localhost:5432)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
A14_GRAMMAR_PG_REQUIRED=1 PAPER_FORWARD_PG_REQUIRED=1 AUTO_ORCHESTRATOR_PG_REQUIRED=1 \
uv run pytest apps/api-python/tests/test_a14_grammar_discovery_pg.py \
  apps/api-python/tests/test_a13_paper_forward_pg.py \
  apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py -q
# → 6 passed (sin skips)

# Bloque 4 (paquete completo):
uv run pytest packages/py -q
# → 2304 passed + fallos preexistentes de chaos (§3)
```

**Evidencia destacada del E2E A14:** un plan gramatical real produce CPCV `pathCount=6`, PBO `0.0`
y WFE `0.0329`; sin evidencia shadow la promoción es fail-closed
(`shadow_validation_requerida`); `ExecutionEventRow` live == 0.

### 2.4 Tests y CI

- Herméticos: `packages/py/application/tests/test_discovery_grammar.py` (17),
  `packages/py/analytics/tests/test_rules_engine_series_wiring.py`,
  `packages/py/application/tests/test_lab_discovery_dispatch.py` (ampliado: CPCV/WF declarativos,
  gates medidos, propagación del campeón) y `apps/api-python/tests/test_auto_orchestrator_worker.py`
  (env-gates de la gramática).
- E2E PG: `apps/api-python/tests/test_a14_grammar_discovery_pg.py` (2 tests; gate
  `A14_GRAMMAR_PG_REQUIRED`, skip = fallo).
- CI: job nuevo **`grammar-discovery-pg`** en `.github/workflows/python-ci.yml` (patrón de
  `paper-forward-pg`), y `--ignore` de ese fichero en el job `quality`.
- CHANGELOG: entrada `1.59.0-beta` (V2.34/A14).

---

## 3. Deuda conocida (NO introducida por A14 — no confundir)

Fallos **preexistentes** del baseline, ruido de entorno de alta concurrencia:

- `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py` — **2 fallos** en el
  baseline (verificado con `git stash`: el mismo fichero falla igual sin los cambios de A14). En
  una corrida completa bajo carga puede aparecer un **tercer** fallo intermitente
  (`test_load_custody_and_buy_concurrent_no_double_charge`): es flaky de carga, no una regresión.
  **No se toca** (deuda explícitamente fuera de alcance).

---

## 4. TRABAJO PENDIENTE — en orden

### Tarea 0 (owner, no agente): commit + push + tag de A14

- Commitear el working tree de A14 (recomendado: **un** commit de fase, con CHANGELOG + tests +
  CI, sin migración).
- Push de `main` y tag de la release. `main` va **3 commits por delante** de `origin/main`
  (`5fcd0224`, `61e613b1`, `114327c3`), sin push.
- Verificar CI del tag: como mínimo `quality`, `lifecycle-pg`, `paper-forward-pg`,
  `grammar-discovery-pg` (skip = fallo).
- **No** hacer esto el agente salvo que el owner lo pida explícitamente.

### Tarea 1 — Observabilidad de la gramática (opcional, pequeño)

Si el owner quiere gobernar el rollout de la gramática en producción:

- Métricas/contadores de candidatas gramaticales emitidas vs. catálogo, y de planes que pasan a
  LAB/SHADOW (con el flag OFF/ON).
- Posible refinamiento del vocabulario (más variantes por bloque) — **ojo**: cada variante nueva
  sube el techo combinatorio; el test anti-explosión (`len(plans) == 1784`) obliga a revisar el
  coste de multiple testing de forma consciente.

### Tarea 2 — Próxima fase (a decidir por el owner)

A14 deja el Discovery saneado y promocionable. Candidatos naturales: gobernanza de la gramática
(qué bloques/variantes entran en producción y con qué presupuesto), o la siguiente fase de
Strategy Intelligence (p. ej. selección adaptativa de planes por régimen). **Empezar por PLAN**, no
por código.

---

## 5. Cómo verificar SIEMPRE antes de decir «hecho»

Orden mínimo (paridad con CI):

```bash
# 1) Calidad
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Offline (usa EXACTAMENTE los --ignore del job `quality` de python-ci.yml;
#    si te los saltas, verás fallos falsos de tests que necesitan PG).

# 3) PG de certificación (Postgres 16 local)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
#    Copia los comandos de los jobs `lifecycle-pg`, `paper-forward-pg` y `grammar-discovery-pg`.
```

Reglas de honestidad del repo:

- No declares verde sin haber corrido los tres bloques.
- Distingue fallos **preexistentes** (§3) de regresiones tuyas.
- No certifiques `main`/HEAD como si fuera un tag.

---

## 6. Uso sugerido de subagentes

- **explore** (medium/very thorough): mapear `rules_grid`/`rules_engine`, `optimize.py` y el
  dispatch del LAB antes de tocar la gramática o los gates.
- **generalPurpose**: cambios que cruzan varios módulos manteniendo semántica (p. ej. grid
  gramatical, propagación del campeón).
- **best-of-n-runner**: solo si hace falta comparar dos diseños de gramática en paralelo.
- **bugbot** / **security-review**: **solo** si el owner los pide explícitamente.
- **ci-investigator**: si un check del tag A14 falla y hay que diagnosticarlo.

---

## 7. Checklist de arranque (haz esto primero)

- [ ] `git log --oneline -3` → `114327c3` (relevo A14) debe ser HEAD.
- [ ] `git status --short` → el working tree de A14 (10 M + 4 nuevos) o ya commiteado, según avance.
      Hay caches/`__pycache__`/logs que **no** son tuyos; no los metas en commits.
- [ ] Leer `docs/engineering/PROJECT_STATE.md` (columna viva).
- [ ] `cd packages/py/infrastructure && uv run alembic heads` → debe salir
      `035_paper_forward_evidence (head)`.
- [ ] Preguntar al owner: ¿commit/push de A14 ahora? ¿Tarea 1 (observabilidad) o Tarea 2 (nueva fase)?

---

## 8. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed (ausencia de evidencia ≠ aprobación) ·
migraciones aditivas sin backfill · long-only · Alembic head `035_paper_forward_evidence` ·
gramática A14 tras `AUTO_ORCHESTRATOR_GRAMMAR` (OFF por defecto) ·
A14 en `114327c3` (local, **working tree sin commitear**).

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM · certificar sin
correr los tres bloques de verificación · mezclar A13/hardening/A14 en un commit · editar el fichero
de plan `a14_strategy_intelligence_grammar_3396fd0a.plan.md`.
