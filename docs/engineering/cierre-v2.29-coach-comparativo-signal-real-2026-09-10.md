# Cierre V2.29 / A10 — COACH Comparativo + SignalEvaluator Real

**Fecha:** 2026-09-10
**Alcance:** AUTO **estrictamente SIMULATED**. **LIVE real intacto.**
**Motivo:** cerrar los dos P2 de la auditoría que tocaban el **núcleo de decisión** del
A10 — el COACH solo evaluaba el primer candidato del TOP3 y la estrategia ACTIVE no
evaluaba su propia señal (delegaba en el spine determinista).

> Continúa a `cierre-v2.28-vigilancia-real-2026-09-10.md`.
> V2.27 cerró el **cableado** (universo ESTUDIO + LAB reales); V2.28 la **señal de
> vigilancia** (fills SIM atribuidos); V2.29 la **señal de decisión** y el **COACH
> comparativo**.

---

## 1. Punto de partida

| P2                                | Síntoma                                                                                                               | Ubicación                           |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| COACH no comparativo              | Solo se dictaminaba `selection.top.candidate_ids[0]`; el 2º y 3º del TOP3 nunca se evaluaban                          | `auto_orchestrator.py:240`          |
| SignalEvaluator ausente           | `active_strategy_decider` hacía `proposal = fallback(symbol)` y solo reescalaba el lote: la ACTIVE no calculaba señal | `auto_orchestrator.py:411-460`      |
| Params del campeón no persistidos | `strategy_versions.definition` guardaba la **rejilla** (`candidate.params`), no los parámetros ganadores              | `strategy_promotion_phase.py:48-71` |
| Sin datos en el hot path          | El decisor es **síncrono** y el `OhlcvRepository` es **async**; el worker SIM usa `_price_script`, no barras          | `auto_simulation_worker.py`         |

Los dos últimos eran **prerrequisitos** del primero: sin parámetros del campeón y sin
barras no hay señal que evaluar.

## 2. Decisiones de diseño (acordadas)

1. **Persistir el campeón en la definición** al promocionar, usando el hook existente
   `build_strategy_version(definition=...)`, de forma **aditiva**.
2. **Precargar barras (async) y cerrarlas sobre el decisor síncrono**, sin cambiar la
   firma del seam `DecisionProvider`.
3. **Rollout con flag OFF por defecto**: el spine sigue siendo el default.
4. **Fail-closed / fail-open seguro**: sin campeón no hay definición ejecutable; sin
   snapshot o ante error de evaluación se delega en el spine (nunca se inventa orden).

## 3. Cambios

### 3.1 COACH comparativo

- `strategy_top3_coach_phase.py`: nuevo `assess_top3_with_coach` + `Top3CoachVerdict`.
  Recorre el TOP3 **en el orden de ranking por evidencia** (`select_top3`) y devuelve un
  `CoachAssessment` por candidato. **No reordena**: elige el **primer candidato sin
  veto**. Si todos vetados, `all_vetoed` ⇒ `coach_veto` con las contradicciones agregadas.
  Un candidato del TOP3 sin evaluación asociada se registra como vetado (no se inventa).
- `auto_orchestrator.py`: `run_cycle` usa el veredicto comparativo; persiste **todos** los
  dictámenes y corta en fail-closed si no hay ninguno aprobado.
- `strategy_lifecycle_store.py`: nuevo `save_coach_assessment` / `list_coach_assessments`
  (Protocol + InMemory + Postgres). Se persiste en `strategy_evaluations` con id
  determinista `coach-<candidate_id>` (idempotente) y el dictamen serializado en
  `metrics["coach"]` — **sin migración nueva**.

### 3.2 Parámetros del campeón + definición ejecutable

- `strategy_executable_definition.py` (nuevo):
  - `champion_params_from_result(result)`: parámetros del trial de mayor `score`.
  - `build_executable_definition(family, champion_params)`: traduce
    `(familia, params)` al esquema declarativo `StrategyDefinitionV1`
    (`presetKey` + `indicatorSpecs` + `entries`/`exits`) que consume el motor de señales.
    Cubre `sma_crossover`, `rsi_mean_reversion` y `macd_signal_cross`, y **normaliza
    alias** de familia (`ema_crossover` → SMA, etc.). Fail-closed: sin params o sin
    periodos devuelve `None` (no se inventan valores).
- `auto_orchestrator.py`: `run_cycle` conserva el resultado crudo por candidata y pasa
  `definition={"champion_params": ..., "executable": ...}` a `build_strategy_version`.
  Es **aditivo**: los gates no dependen del hash previo.
- Resultado en `strategy_versions.definition`:

```json
{
  "family": "sma_crossover",
  "params": {"fast_periods": [5, 10], "slow_periods": [20, 30]},
  "instrument_id": "AAA",
  "champion_params": {"fastPeriod": 10, "slowPeriod": 30},
  "executable": {"presetKey": "sma_crossover", "indicatorSpecs": [...], "entries": {...}, "exits": {...}}
}
```

### 3.3 SignalEvaluator real

- `active_strategy_signal_evaluator.py` (nuevo):
  - `make_bar_snapshot_loader(ohlcv, symbols, limit)`: `refresh()` async que precarga
    `{symbol: [bars]}`; un fallo por símbolo se ignora (ese símbolo usará el spine).
  - `make_active_strategy_decider(active, fallback, watch, bars_by_symbol, lot_qty)`:
    evalúa `definition["executable"]` con `evaluate_strategy_last_bar` (motor declarativo
    real, `mode="gated"`) y traduce `entry_long` → BUY, `exit` → SELL, con el lote acotado
    al de la ACTIVE. Sin señal en la última barra, sin barras, sin `executable` o ante
    error ⇒ **fallback al spine**.
- `auto_simulation_worker.py`:
  - Nuevo flag `AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL` (`active_strategy_signal_enabled()`,
    default **OFF**) y `AUTO_ENGINE_SIM_SIGNAL_BARS` (default 120).
  - `load_active_strategy_decider(..., signal_enabled=, ohlcv=)`: con el flag ON compone
    el repo OHLCV **dentro de una sesión viva**, carga el snapshot (async) y lo cierra
    sobre el decisor síncrono. El repo nunca queda apuntando a una sesión cerrada.
  - `_refresh_active_decider` pasa `signal_enabled=active_strategy_signal_enabled()`.

## 4. Variables de entorno nuevas

| Variable                                 | Default | Efecto                                                            |
| ---------------------------------------- | ------- | ----------------------------------------------------------------- |
| `AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL` | OFF     | La ACTIVE evalúa su propia señal; si OFF, solo lote/watch (V2.26) |
| `AUTO_ENGINE_SIM_SIGNAL_BARS`            | 120     | Nº de barras precargadas para la evaluación                       |

## 5. Verificación

- **Ruff** sobre los ficheros tocados → `All checks passed!`
- **Mypy** sobre los módulos de aplicación/API tocados → `Success: no issues found`.
- **Suite application + domain** → **1310 passed**.
- **Enumeración exacta del job `python` del tag** (incluye los tests V2.27/V2.28/V2.29
  que **no estaban** en el workflow) → **139 passed**.
- **PG real** `test_strategy_lifecycle_pg.py` → **5 passed**, incluido el nuevo
  `test_promotion_persists_champion_and_coach_pg`: ciclo real que promociona con el
  campeón persistido (`champion_params` + `executable`) y certifica el dictamen COACH
  persistido, idempotente y legible.

### Un aprendizaje de la verificación

El primer intento del test del SignalEvaluator esperaba `HOLD` en una serie plana. El
contrato real (y correcto) es **delegar en el spine** cuando no hay señal: "sin señal" no
es "sin operación" en este diseño. El test se ajustó al contrato, no al revés.

## 6. Hueco de CI cerrado (auditable desde Git)

El job `python` de `release-tag-ci.yml` enumeraba **archivos individuales** (no
directorios), por lo que los tests de V2.27/V2.28 **no corrían en el tag**. V2.29 los
añade, junto con los nuevos, y también lleva la atribución SIM al job `lifecycle-pg`:

- `python`: `test_orchestrator_universe`, `test_orchestrator_lab_runner`,
  `test_strategy_observed_metrics`, `test_strategy_observed_metrics_provider`,
  `test_strategy_vigilance_observed`, `test_sim_strategy_attribution`,
  `test_strategy_executable_definition`, `test_active_strategy_signal_evaluator`,
  `test_auto_sim_active_strategy_seam`, `test_auto_simulation_worker`.
- `lifecycle-pg`: `test_sim_strategy_attribution` (con `STRATEGY_LIFECYCLE_PG_REQUIRED=1`
  y `AUTO_ORCHESTRATOR_PG_REQUIRED=1` como gates fail-if-skipped).

## 7. Fuera de alcance (P2 que siguen para V2.30)

- **StrategyDiscoveryEngine**: no existe selector sobre los 30+ indicadores; el sistema
  optimiza 3 familias (`SUPPORTED_FAMILIES` en `optimize.py`).
- **Shadow automático**: `AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1` sigue certificando la
  validación shadow sin que el sistema la haya ejecutado. No existe entidad ni store de
  evidencia shadow (`StrategyValidation` solo lleva gates).
- **Atribución tras crash**: los cierres de posiciones readoptadas quedan sin versión
  (la proyección durable no la guarda) — límite documentado en V2.28.

## 8. Barreras (sin cambios)

- AUTO → SIMULATED únicamente. LIVE real intacto.
- Sin LLM en el hot path.
- El motor SIM no cambia su identidad de ejecución ni la semántica de settlement.
- Fail-closed en toda la cadena: sin campeón no hay definición ejecutable; sin snapshot
  se usa el spine; sin evidencia no se promociona; el COACH solo veta o deja pasar, nunca
  eleva un gate cuantitativo.
