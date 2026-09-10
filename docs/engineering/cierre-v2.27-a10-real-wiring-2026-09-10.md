# Cierre V2.27 / A10 — Real Wiring (P1-01 + P1-02)

**Fecha:** 2026-09-10
**Alcance:** AUTO **estrictamente SIMULATED**. **LIVE real intacto y doblemente bloqueado.**
**Motivo:** cerrar los dos P1 de la auditoría de V2.26 — la arquitectura A10 existía,
pero el composition root real no le proporcionaba universo ESTUDIO ni optimizador LAB,
de modo que el ciclo nunca promocionaba.

> Continúa a `cierre-v2.25-v2.26-a10-strategy-lifecycle-auto-orchestrator-2026-09-10.md`.
> No se añade arquitectura nueva: **solo cableado**.

---

## 1. Problema P1-01/P1-02 (verificado en código)

`_default_orchestrator()` construía:

```python
AutoOrchestrator(OrchestratorDeps(store=_SessionScopedStore()))
```

con `resolve_universe=None` y `run_optimize=None`. Consecuencia en el proceso real
(`AUTO_ORCHESTRATOR_ENABLED=1`):

- ESTUDIO omitido ⇒ "candidata directa" (una candidata sintética).
- LAB omitido ⇒ `evaluations == []` ⇒ `status="sin_evidencia_top3"`.
- COACH / FINALISTA / PROMOTION / ACTIVE inalcanzables.

Los tests A10 no lo detectaban porque **inyectaban** `run_optimize` y el resolver
(comportamiento correcto para tests herméticos, pero no certificaba la composición).

## 2. Cambios

**Adaptadores nuevos (application, sin lógica cuantitativa propia)**

- `packages/py/application/src/bolsa_application/orchestrator_lab_runner.py`
  - `LabOptimizeRunner(session_factory, build_use_case)`: adapta
    `StrategyCandidate → RunSmaGridOptimizeAndSave.execute(...)` (firma keyword-only),
    normaliza familia, aplica grid por familia y **desempaqueta** el tuple
    `(OptimizeSmaGridResult, OptimizationRunRecord)`.
  - `LabOptimizeResult`: resultado compatible con `evaluate_optimize_result` que
    expone además `optimization_run_id` y `edge_report_id` (ciclos auditables).
  - Errores de dominio (`ValueError`: instrumento ausente / barras insuficientes) ⇒
    `None` ("sin evidencia"). Nunca se inventa evidencia.
  - `AUTO_LAB_GRID_DEFAULTS`: grids SMA/RSI/MACD en código (familias-first).
- `packages/py/application/src/bolsa_application/orchestrator_universe.py`
  - `make_estudio_universe_resolver(estudio_list)`: reutiliza
    `resolve_estudio_universe`; `None` ⇒ `unavailable` (fail-closed).

**Composition root real**

- `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`
  - `_default_orchestrator()` cablea `resolve_universe` (ESTUDIO vía
    `_SessionScopedEstudioList` + `GetInstrumentList`) y `run_optimize`
    (`LabOptimizeRunner` sobre `RunSmaGridOptimizeAndSave`, con repos de DI).
  - Sesión por operación (no se retiene `AsyncSession`).
  - `candidate_id_factory` determinista y `max_candidates` como tope de universo.
- `packages/py/application/src/bolsa_application/auto_orchestrator.py`
  - Nuevo `resolve_universe()` público y property `deps` (evita que el worker toque
    `_deps` privado).

**ESTUDIO como fuente canónica de instrumentos**

- `auto_orchestrator_loop` resuelve el universo por ciclo (`_instruments_for_cycle`).
  `AUTO_ORCHESTRATOR_INSTRUMENTS` pasa a **allowlist opcional** que filtra el universo.
  Universo `empty`/`unavailable` ⇒ no se inventan candidatas; el bucle no muere.

## 3. Variables de entorno

| Variable                             | Default | Efecto                                                 |
| ------------------------------------ | ------- | ------------------------------------------------------ |
| `AUTO_ORCHESTRATOR_ENABLED`          | OFF     | Arranca el bucle del orquestador (SIM-only)            |
| `AUTO_ORCHESTRATOR_INSTRUMENTS`      | vacío   | **Allowlist opcional** sobre el universo ESTUDIO       |
| `AUTO_ORCHESTRATOR_INTERVAL_SECONDS` | 3600    | Periodo del bucle                                      |
| `AUTO_ORCHESTRATOR_SHADOW_VALIDATED` | OFF     | Permite promocionar (sin shadow NO hay promoción)      |
| `AUTO_ORCHESTRATOR_STRATEGY_FAMILY`  | SMA     | Familia por defecto del ESTUDIO                        |
| `AUTO_ORCHESTRATOR_LAB_PARAMS`       | vacío   | Override JSON del grid del LAB                         |
| `AUTO_ORCHESTRATOR_MAX_CANDIDATES`   | 3       | Tope de candidatas por instrumento/ciclo (TOP3 aparte) |

## 4. Fuera de alcance (P2 explícitos para V2.28)

- **COACH comparativo**: sigue evaluando solo `selection.top.candidate_ids[0]`, no los 3.
- **Vigilancia real**: `watch_active(metrics={})` sigue sin métricas cuantitativas
  (edge/WFE/drawdown/Sharpe); `evaluate_active_health` no puede degradar de verdad.
- **StrategyDiscoveryEngine**: no existe selector sobre los 30+ indicadores ya
  implementados en `bolsa_analytics.indicators.compute` (SMA, EMA, RSI, MACD, ADX,
  ATR, Bollinger, Stochastic, CCI, Donchian, Supertrend, Ichimoku…). Hoy se optimizan
  familias (SMA/RSI/MACD), no se descubre el mejor indicador por activo.
- **SignalEvaluator real**: `active_strategy_decider` sigue delegando la decisión a
  `fallback(symbol)` (spine determinista); la ACTIVE solo aporta lote/watch.
- **Shadow automático**: `AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1` certifica shadow sin
  que el sistema lo haya ejecutado; debe pasar a evidencia generada (ShadowValidation).

## 5. Verificación

- **Ruff** sobre los ficheros tocados → sin errores.
- **Mypy** sobre `orchestrator_lab_runner.py`, `orchestrator_universe.py`,
  `auto_orchestrator.py`, `strategy_lab_phase.py`, `auto_orchestrator_worker.py`
  → `Success: no issues found`.
- **Herméticos A10** (application tests de fases + orchestrator + los nuevos
  `test_orchestrator_lab_runner.py` / `test_orchestrator_universe.py`, dominio
  `test_strategy_lifecycle.py`, worker + seam) → **106 passed**.
- **PG real** `test_strategy_lifecycle_pg.py` → **3 passed** (modo default), incluye:

  - `test_default_orchestrator_real_wiring_end_to_end_pg` (nuevo): usa
    `_default_orchestrator(session_factory)` **sin inyectar** `resolve_universe` ni
    `run_optimize`. Siembra instrumento + pertenencia a la lista `estudio` + 420 barras
    OHLCV y certifica que el ciclo resuelve el universo real, ejecuta el LAB real,
    persiste la evaluación con `optimization_run_id` y ya **no** cae en
    `sin_evidencia_top3`.

**Hallazgos de la verificación end-to-end (dos bugs reales de cableado, corregidos):**

1. **Truncado de universo (`max_candidates`).** `build_estudio_candidates` recortaba
   `instrument_ids[:max_candidates]` **antes** de que `run_cycle` filtrara por
   instrumento, dejando inalcanzables todos los instrumentos posteriores al tope.
   Fix: nuevo parámetro `instrument_id` en `build_estudio_candidates`, aplicado antes
   del tope; `run_cycle` lo usa. Detectado solo al ejecutar el composition root real.
2. **Grid del LAB incompatible con la ventana de barras.** El grid SMA por defecto
   (`slow_periods=[50,100,200]`) superaba el warm-up disponible; `assert_grid_warmup`
   abortaba la búsqueda, el LAB devolvía "sin trials" y el gate `backtest` quedaba
   NOT_EVALUATED → nunca promocionaba pese a haber evidencia posible. Fix:
   `_prune_grid_to_window` recorta periodos que no caben (`bar_limit`), y el grid por
   defecto usa `slow_periods` realistas con `bar_limit=400`.

**No ejecutado aquí:** certificación por tag en CI `release-tag-ci.yml`; job
`lifecycle-pg` con `AUTO_ORCHESTRATOR_PG_REQUIRED=1`; suite completa del repo.

## 6. Criterio de éxito

Con `AUTO_ORCHESTRATOR_ENABLED=1` y OHLCV suficiente, un ciclo debe producir
`status != "sin_evidencia_top3"` con `evaluated >= 1`; con `shadow_validated=true` y
gates PASS ⇒ `promoted=True`, ACTIVE en `strategy_promotions` y `optimization_run_id`
persistido. Sin datos o universo `unavailable` ⇒ fail-closed (`evaluated=0`, sin
promoción).

Matiz honesto tras la verificación real: entrar en el TOP3 exige gate `backtest` PASS
(score IS > 0). Con series/mercados donde ningún campeón del grid tiene score positivo,
el ciclo **correctamente** no promociona aunque `evaluated >= 1`. Es fail-closed, no un
fallo de cableado: la promoción sigue dependiendo de evidencia real y no del mero hecho
de que el LAB se haya ejecutado.

## 7. Barreras (sin cambios)

- AUTO → SIMULATED únicamente. LIVE real doblemente bloqueado.
- Sin LLM en el hot path. El COACH sigue offline/advisory.
- Sin fallback SIM → LIVE. El LAB nunca cambia la activa directamente.

## 8. Siguiente

- V2.28: métricas reales de vigilancia, COACH comparativo sobre el TOP3, discovery de
  indicadores y SignalEvaluator que ejecute la definición optimizada (no el fallback).
