# Cierre V2.31 / A11 — Intelligent Strategy Discovery (2026-09-10)

Version: `v2.31-beta`. Alcance: **los dos P1 de la auditoría V2.30**.

1. **P1-01 — `StrategyDiscoveryEngine`**: el LAB solo optimizaba 3 familias
   (`SUPPORTED_FAMILIES` = SMA crossover / RSI mean-reversion / MACD signal cross),
   mientras el motor de indicadores ofrece 33 `definitionId`. No había selector que los
   conectara al ciclo AUTO.
2. **P1-02 — ACTIVE fail-closed**: con `AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL=1`, si la
   ACTIVE no podía evaluar su señal, el decisor **heredaba la ACCIÓN del spine**
   (otra estrategia). La procedencia real era invisible: el AUTO podía operar con una
   lógica distinta a la que él mismo había promocionado.

Fuera de alcance (diferido a V2.32, ver §6): **shadow real** (evidencia ejecutada, no
el flag `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`) y **atribución de versión tras crash**
en posiciones readoptadas.

---

## 1. Pipeline (antes → después)

```
ANTES
  ESTUDIO ──▶ LAB (3 familias fijas) ──▶ TOP3 ──▶ COACH ──▶ FINALISTA ──▶ VALIDACION ──▶ ACTIVE
                                  ▲                                                     │
                                  └── una candidata por instrumento, familia fija        │
                                                                                        ▼
                                       ACTIVE sin señal ──▶ hereda ACCIÓN del spine (otra estrategia)

AHORA
  ESTUDIO ──▶ DISCOVERY ENGINE ──▶ LAB (reglas declarativas) ──▶ TOP3 ──▶ COACH ──▶ FINALISTA ──▶ ACTIVE
              (search space curado)                                                              │
                                                                                                  ▼
                                       ACTIVE sin señal ──▶ NO TRADE (HOLD, fail-closed)
```

---

## 2. Parte A — Discovery Engine (P1-01)

### 2.1 Catálogo curado (`discovery_catalog.py`)

Nuevo `packages/py/application/src/bolsa_application/discovery_catalog.py`, **puro**
(sin red/IA/DB). Declara 14 plantillas agrupadas en tres ramas, con un espacio de
parámetros **pequeño y justificado** (anti-explosión: multiple testing / PBO / coste):

| Rama           | Familias                                                                                                                   | Indicadores (`definitionId`)                   |
| -------------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **Trend**      | `ema_crossover`, `donchian_breakout`, `supertrend_follow`, `adx_di_trend`, `sar_flip`, `ichimoku_tk_cross`                 | `ema`, `dc`, `st`+`atr`, `adx`, `sar`, `ich`   |
| **Momentum**   | `rsi_mean_reversion`, `macd_signal_cross`, `stoch_oversold`, `stoch_rsi_reversion`, `williams_r_reversion`, `roc_momentum` | `rsi`, `macd`, `stoch`, `srsi`, `willr`, `roc` |
| **Volatility** | `bb_reversion`, `bb_breakout`                                                                                              | `bb`                                           |

Cada plantilla es una **regla declarativa determinista** en el esquema
`StrategyDefinitionV1` (el mismo que consume `evaluate_strategy_last_bar` /
`evaluate_rules_signals`), con `indicator_cross` / `indicator_compare` /
`price_vs_indicator`. `template(params) -> definition | None`: si faltan parámetros,
devuelve `None` y el punto **no** se convierte en candidata (fail-closed).

### 2.2 Motor (`strategy_discovery_engine.py`)

`discover_for_instrument(...)` (alias `discover_candidates`) es una **función pura**:

- emite `StrategyCandidate(origin="discovery")` con `params = {definition, discovery_family,
discovery_parent, discovery_params}`;
- respeta el **presupuesto global** `DiscoveryBudget(max_trials_total, max_per_family,
max_candidates, min_bars)`;
- es **determinista** (producto cartesiano estable ⇒ ids reproducibles);
- filtro opcional de warm-up por `bar_count` (evita candidatas condenadas a "sin trials");
- sin familias ⇒ tupla vacía; plantilla que no materializa ⇒ no emite.

### 2.3 LAB declarativo (`rules_grid.py` + `RunSmaGridOptimize._run_rules`)

Los grids H0 (`sma_grid`/`rsi_grid`/`macd_grid`) tienen features cableadas. Para las
plantillas del catálogo se añade `run_rules_grid_search`, que materializa cada punto con
la plantilla de la familia y simula con el **motor real de reglas**
(`evaluate_rules_signals` en modo `gated`), reutilizando la misma contabilidad de
equity/drawdown/score y la causalidad `index-1 → open(index)` (sin look-ahead).

- `RunSmaGridOptimize.execute(..., definition=...)`: si llega una definición declarativa,
  despacha a `_run_rules` (engine `rules_grid_h0`) y **preserva el nombre de familia** del
  catálogo (no lo colapsa a SMA/RSI/MACD).
- `RunSmaGridOptimizeAndSave` y `LabOptimizeRunner` propagan `definition`; el adaptador
  deja de exigir que el nombre sea uno de los tres H0.
- El baseline declarativo se evalúa con la propia definición; si no genera operaciones,
  baseline neutro (no se aborta el grid).

### 2.4 Orquestación y rollout

- `OrchestratorDeps.discovery: DiscoveryRunner | None` (V2.31). Cableado ⇒ `run_cycle`
  usa sus candidatas; vacío ⇒ `OrchestratorResult(status="sin_candidatas_discovery")`
  (fail-closed, **no** se sintetiza la candidata única). No cableado ⇒ comportamiento
  previo (V2.29), sin romper herméticos.
- `_champion_definition` usa la definición ejecutable de la propia candidata cuando la
  familia no es una de las tres H0 (`build_executable_definition` devuelve `None`).
- Composition root (`auto_orchestrator_worker.py`): flag **`AUTO_ORCHESTRATOR_DISCOVERY`
  (default OFF)** + presupuesto por env (`AUTO_ORCHESTRATOR_DISCOVERY_MAX_TRIALS`,
  `_MAX_PER_FAMILY`, `_MAX_CANDIDATES`). Rollout explícito y reversible.

---

## 3. Parte B — ACTIVE fail-closed (P1-02)

`active_strategy_signal_evaluator.py` reescrito:

- **Se elimina el parámetro `fallback`** del decisor: es imposible que otra estrategia
  aporte la ACCIÓN.
- Sin `executable`, sin barras, sin snapshot, fuera de `watch`, o ante **cualquier error
  de evaluación** ⇒ `DecisionPackage(action="HOLD", quantity=0)`.
- El único camino a BUY/SELL es la **señal propia** de la ACTIVE (`entry_long` ⇒ BUY,
  `exit` ⇒ SELL), con lote acotado (`lot_qty` de la estrategia).
- `exit` tiene prioridad sobre `entry_long` en la misma barra (cerrar es lo conservador).

Worker (`auto_simulation_worker.py`):

- `_build_signal_decider` ya no recibe `fallback=base_decider`.
- `load_active_strategy_decider` ya no propaga fallback; el decider clásico (señal OFF)
  se compone con `fallback=None`.
- `AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL` sigue **OFF por defecto** (rollout seguro);
  con ON el contrato es "estrategia promocionada o nada". Docstrings actualizados
  (se retira la afirmación "cae al spine (fail-open seguro)").

---

## 4. Barreras que NO se tocan

- AUTO ⇒ **SIMULATED** únicamente. LIVE real sigue doblemente bloqueado
  (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`, ambas false).
- Sin LLM en el hot path. RiskGate / SimulationGate / Ledger / Reconciliation siguen
  deterministas.
- El COACH sigue siendo advisory: no reordena ni eleva gates.
- Sin migraciones nuevas: el catálogo y el motor son puros; las candidatas del discovery
  reutilizan `strategy_candidates` (no se toca el esquema).

---

## 5. Verificación

- `uv run ruff check packages/py apps/api-python --config pyproject.toml` → limpio.
- `uv run lint-imports --config packages/py/.importlinter` → **4 contratos KEPT**.
- `uv run mypy` sobre los módulos tocados → sin issues (los errores preexistentes de
  `analytics/knowledge`, `analytics/cognitive` y `warmup_matrix` pertenecen a ficheros no
  tocados por V2.31).
- Suite `application` + `analytics` → **1888 passed**.
- Tests nuevos: `test_discovery_catalog.py`, `test_strategy_discovery_engine.py`,
  `test_lab_discovery_dispatch.py`, `test_rules_grid.py`; actualizados
  `test_active_strategy_signal_evaluator.py`, `test_auto_sim_active_strategy_seam.py`,
  `test_auto_orchestrator.py`, `test_orchestrator_lab_runner.py`.
- CI (`.github/workflows/release-tag-ci.yml`): los nuevos ficheros de test del discovery
  se enumeran en el job `python` (patrón V2.29).

---

## 6. Deuda diferida a V2.32 (documentada, no implementada)

- **Shadow real**: `AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1` sigue certificando un flag, no
  una ejecución shadow con evidencia. Falta entidad/store de evidencia (`ShadowValidation`;
  `StrategyValidation` solo lleva gates). V2.31 hace que la ACTIVE no invente señal, pero
  **no** convierte el flag en evidencia.
- **Atribución de versión tras crash**: los cierres de posiciones readoptadas siguen sin
  versión de estrategia (límite documentado en V2.28). El discovery no lo aborda.
- **Endurecer el rollout del discovery**: con el flag ON el presupuesto ya está acotado,
  pero la selección de ramas por régimen (usar `regimes`/`tags` del catálogo para podar
  el search space) es trabajo posterior.

---

## 7. Por qué esto cierra los dos P1

Antes: el AUTO solo podía optimizar 3 familias fijas y, con la señal de la ACTIVE ON,
podía ejecutar la ACCIÓN del spine mientras decía operar la estrategia promocionada.
Ahora: el AUTO descubre entre un search space **curado y acotado** sobre los indicadores
reales (con presupuesto global), y la ACTIVE **solo** opera su propia señal — si no puede,
**no trade**. La procedencia de cada decisión es la estrategia promocionada o nada.
