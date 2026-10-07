# Evidencia `v2.88.83-beta` — `ESTRATEGIA`: **anti-overfit II (CPCV/walk-forward al LAB real + TOP3 `lab_validated`)**

**Producto:** `V2.88.83-beta` · **Package:** `2.11.83-beta` · **AsOf:** 2026-10-07. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor ≠ 0`** (el LAB real cablea CPCV/WF a las familias H0 y el TOP3 eleva su barrera de evidencia). **Tag anotado** por crear.

**Padre de producto:** [`v2.88.82`](../v2.88.82/README.md) (la «oleada anti-overfit» que dejó un **hallazgo no bloqueante**: el default del TOP3 no podía subir a `lab_validated` porque el LAB real solo corría la rejilla IS plana).

## Qué cambia

Cierra la deuda que **abrió el sello anterior** — *«el camino correcto para “más aciertos” es cablear CPCV/walk-forward al LAB y, con evidencia real presente, subir el default del TOP3»* — en tres piezas encadenadas:

1. **CPCV/walk-forward al LAB real (familias H0).** `_STRUCTURAL_LAB_DEFAULTS`
   (`orchestrator_lab_runner.py`) pasa a incluir `cpcv_groups=4` y `walk_forward_folds=3`
   para **todas** las familias (H0 `SMA`/`RSI`/`MACD` **y** declarativas). Se elimina el
   override redundante `_DECLARATIVE_LAB_DEFAULTS`: los modos `_run_cpcv`/`_run_walk_forward`
   (`optimize.py`) ya cubren H0 vía `_run_h0_partial_on_bars` y declarativas vía
   `_run_declarative_partial_on_bars`. El ciclo real deja de correr la «rejilla IS plana»
   y mide evidencia OOS/WF/CPCV, de modo que los gates `oos`/`robustness`/`walk_forward`
   dejan de quedar `NOT_EVALUATED`.
2. **TOP3 por defecto `lab_validated`.** `select_top3` (`strategy_top3_coach_phase.py`)
   sube su `min_gates` por defecto de `("backtest",)` a
   `("backtest", "oos", "walk_forward", "robustness")`. El TOP3 deja de admitir hipótesis
   `in_sample_only` por defecto; el flujo `semifinal`/in_sample_only sigue disponible con el
   override explícito `min_gates=("backtest",)`.
3. **Persistencia certificada.** Se certifica que `cpcv`/`walkForward`/`pbo` viajan en el
   result JSON (`optimize_result_to_dict`) y en los `blocks` de los research trials
   (`_persist_optimize_research_trials`), alimentando los gates `robustness`/`walk_forward`/
   `oos` de `evaluate_optimize_result`.

## Invariantes de honestidad (no negociables)

- El campeón que se promueve sigue siendo el mismo trial que la evidencia validó (fuente única del campeón).
- El TOP3 por defecto solo admite candidatas con los 4 gates `lab_validated` en PASS; sin evidencia OOS/WF/CPCV real no hay TOP3 (fail-closed, `sin_evidencia_top3`).
- El 7º gate DSR (`LabThresholds.min_dsr = 0.7`) permanece fail-closed e independiente del TOP3.

## Verificación

- **Hermético (aplicación):** `test_strategy_top3_coach_phase.py` (nuevo
  `test_top3_default_requires_lab_validated_gates`: el default excluye `in_sample_only` y el
  override `min_gates=("backtest",)` sigue habilitando el flujo semifinal),
  `test_top3_opportunities.py`, `test_auto_orchestrator.py`, `test_optimization_runs.py`
  (nuevos `test_optimize_result_to_dict_persists_anti_overfit_evidence` y
  `test_persist_trials_includes_cpcv_walk_forward_pbo_blocks`).
- **PG end-to-end:** `test_default_orchestrator_real_wiring_end_to_end_pg` certifica ahora que,
  con el LAB real cableado a CPCV/WF y el TOP3 por defecto `lab_validated`, el campeón pasa los
  4 gates (`backtest`+`oos`+`walk_forward`+`robustness` = `pass`) y el ciclo NO cae en
  `sin_evidencia_top3`. Serie sintética calibrada (drift dominante `0.08/día` + sinusoide
  `2.0·sin(2π·día/60)`) para que el campeón OOS-aware conserve `IS > 0` y `OOS > 0` y `WFE > 0`.
- **Suite completa:** `ruff`, `mypy`, `lint-imports` y pytest (paquetes + API) verdes.

## Qué no cambia

Núcleo financiero (`ExecuteTrade`, ledger, posiciones, settlement) y el criterio de salida DÍA-D.
El tag `v2.88.76-beta` permanece (como en `v2.88.82`); el tag anotado de este sello se crea en el paso POST-TAG.

## Cita POST-TAG

Pendiente: tag anotado `v2.88.83-beta` + `Release tag CI` VERDE + `replay-repro` reproducido (⇒ `Δ motor` confirmado por CI).
