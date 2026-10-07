# Evidencia `v2.88.82-beta` — `ESTRATEGIA`: **oleada anti-overfit (campeón OOS-aware + TOP3 cross-asset + gate DSR)**

**Producto:** `V2.88.82-beta` · **Package:** `2.11.82-beta` · **AsOf:** 2026-10-07. **Con migración** `052_top3_opportunities`. **`Δ motor ≠ 0`** (el scoring del simulador consume evidencia LAB por instrumento). **Tag anotado `v2.88.82-beta`** (→ commit `0b907398`).

**Padre de producto:** [`v2.88.80`](../v2.88.80/README.md) (el `v2.88.81-beta` — «telemetría robusta» — quedó con entrada de CHANGELOG pero **sin** bump de `package.json`; este sello avanza de `2.11.80-beta` a `2.11.82-beta`).

## Qué cambia

Cierra la línea anti-overfit de la operativa («más aciertos fuera de muestra, menos overfit»)
en tres piezas encadenadas:

1. **Campeón OOS-aware.** `champion_trial()` unifica qué trial manda: OOS preferido cuando todos
   los trials lo miden, fallback IS **declarado**. La versión ACTIVE promueve el **mismo** trial cuya
   evidencia se validó fuera de muestra (adiós al overfit del IS puro).
2. **TOP3 cross-asset (P3).** Tablero de oportunidades que rankea instrumentos con 7 componentes de
   evidencia (`edge`, `liquidez`, `robust_score` OOS-aware, drawdown, CPCV, régimen, DSR); ruta
   `/top3-opportunities`; persistencia `052_top3_opportunities`.
3. **Gate DSR exigible.** El DSR pasa a ser el **7º gate** del Promotion Gate: `LabThresholds.min_dsr`
   sube de `0.0` (inoperante) a `0.7`, con override por entorno `AUTO_ORCHESTRATOR_LAB_MIN_DSR`.
   Fail-closed: DSR ausente o `< 0.7` veta la promoción.

## Invariantes de honestidad (no negociables)

- El campeón que se promueve es el mismo trial que la evidencia validó (fuente única del campeón).
- Sin DSR medido (`None`) o `< min_dsr`, no hay promoción (fail-closed, nunca un hueco que pase).
- El ranking del TOP3 intra-instrumento sigue admitiendo `in_sample_only` (barrera `backtest`), porque
  la promoción es la que veta después con los 7 gates.

## Hallazgo de esta oleada (no bloqueante, abre trabajo futuro)

Se intentó elevar el default de `select_top3` a `lab_validated` (exigir `backtest`+`oos`+`walk_forward`+
`robustness`) para que el TOP3 no mostrase hipótesis `in_sample_only`. **Se revirtió**: el LAB real
cableado en el orquestador (`RunSmaGridOptimize` en `_default_orchestrator`) solo ejecuta la **rejilla
IS plana** (no pasa `cpcv_groups` ni `walk_forward_folds`), de modo que **nunca produce** evidencia
`oos`/`walk_forward`/`cpcv`. Con el default exigente, el ciclo real emitiría `sin_evidencia_top3`
siempre (certificado por `test_default_orchestrator_real_wiring_end_to_end_pg`). El camino correcto
para «más aciertos» es **cablear CPCV/walk-forward al LAB** (los modos `_run_cpcv`/`_run_walk_forward`
ya existen en `optimize.py`) y, con evidencia real presente, subir el default del TOP3.

## Verificación

- Python (aplicación): `champion_trial` (fuente única OOS-aware), `evaluate_optimize_result` (gate `dsr`
  exigible), `test_strategy_top3_coach_phase.py`, `test_top3_opportunities.py`, `test_auto_orchestrator.py`.
- PG: roundtrips de migración con head `052_top3_opportunities` (`test_discovery_evidence_snapshot_pg.py`,
  `test_auto_v57_auto16_applied_cost_pg.py`, `test_auto_v88_27_durable_facts_idempotent_pg.py`);
  `test_default_orchestrator_real_wiring_end_to_end_pg` verde (el LAB real no cae en `sin_evidencia_top3`).
- Hermeticidad de DB: purga de residuos **antes y después** de la sesión (raíz y `chaos/live_a7`).
- Sello de versión: `test_dia_d_bump_guard.py` (`meta.bump` de los 9 CLIs DÍA-D == `package.json`).

## Qué no cambia

Núcleo financiero (`ExecuteTrade`, ledger, posiciones, settlement) y el criterio de salida DÍA-D.
El tag `v2.88.76-beta` permanece.

## Cita POST-TAG

**Tag anotado `v2.88.82-beta`** (→ commit `0b907398`). `Release tag CI` [`37599997743`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37599997743) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `python` `4587 passed / 45 skipped`; `frontend` `1519 passed`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).
