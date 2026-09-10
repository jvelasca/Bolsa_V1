# Cierre V2.25 + V2.26 / A10 — Strategy Lifecycle + Auto Orchestrator

**Fecha:** 2026-09-10
**Versión:** `1.52.0-beta` (`package.json`)
**Base:** V2.24.2-beta / A9.1-hardening (`1.51.1-beta`).
**Alcance:** AUTO **estrictamente SIMULATED**. **LIVE real intacto y doblemente bloqueado.**
**Motivo:** construir el ciclo de vida autónomo de estrategia (A10), reutilizando el
LAB/optimización/OOS ya existente, y cablearlo al AUTO **solo** por el seam
`DecisionProvider`.

> **Reciclaje de nombres.** Los identificadores **V2.25** y **V2.26** se usaron el
> 4-sep-2026 para _polish_ de UI. Aquí se **reutilizan** con el significado canónico del
> plan A10: **V2.25 = Strategy Lifecycle**, **V2.26 = Auto Orchestrator**. Las
> referencias antiguas de UI quedan superadas por el `CHANGELOG` `1.52.0-beta`.

---

## 1. Invariantes certificados

| Área              | Invariante                                                                                                                          |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Funnel A10        | Solo se avanza de fase si el gate previo PASS; sin evidencia no hay TOP3; sin shadow no hay promoción                               |
| `StrategyVersion` | Inmutable (hash de definición estable); la promoción crea una versión, no muta la candidata                                         |
| COACH             | Advisory: puede **vetar/degrada**, **nunca** aprobar por encima de los gates cuantitativos                                          |
| Promotion Gate    | `backtest ∧ robustness ∧ walk_forward ∧ oos ∧ risk ∧ coach` + coach + **shadow** antes de `ACTIVE`                                  |
| Anti-chasing      | El LAB **no** sustituye la estrategia activa sin Promotion Gate + shadow                                                            |
| Vigilancia        | Degradación de salud ⇒ **re-LAB**, nunca _swap_ directo                                                                             |
| Seam AUTO         | La `ACTIVE` entra al AUTO **solo** por `DecisionProvider` (`active_strategy_decider`); RiskGate/SimulationGate intactos; LIVE nunca |
| Env gates         | Orquestador y seam ACTIVE **default OFF** (fail-closed); sin activa fiable se conserva el spine determinista                        |

## 2. Archivos clave

**Dominio / A10**

- `packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py`
  (entidades + `StrategyLifecycleState`, `next_state`, `evaluate_promotion`, `can_transition`).
- `packages/py/domain/tests/test_strategy_lifecycle.py`.

**Persistencia**

- `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`
  (`StrategyCandidateRow`, `StrategyVersionRow`, `StrategyEvaluationRow`,
  `StrategyPromotionRow`, `StrategyHealthRow`).
- `packages/py/infrastructure/alembic/versions/030_strategy_lifecycle.py` (head `029` → `030`).
- `packages/py/application/src/bolsa_application/strategy_lifecycle_store.py`
  (`InMemory` + `Postgres` stores).

**Fases**

- `packages/py/application/src/bolsa_application/strategy_lab_phase.py` (ESTUDIO/LAB).
- `packages/py/application/src/bolsa_application/strategy_top3_coach_phase.py` (TOP3/COACH).
- `packages/py/application/src/bolsa_application/strategy_promotion_phase.py` (FINALISTA/Gate).
- `packages/py/application/src/bolsa_application/strategy_vigilance_phase.py` (vigilancia).

**V2.26 Auto Orchestrator**

- `packages/py/application/src/bolsa_application/auto_orchestrator.py`
  (`AutoOrchestrator`, `OrchestratorDeps/Result`, `active_strategy_decider`).
- `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`
  (bucle env-gated + starter).
- `apps/api-python/src/bolsa_api/workers/scheduler_worker.py` (registro en `_event_loop_starters`).
- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
  (`active_strategy_enabled`, `load_active_strategy_decider`, `AutoSimRuntime.set_decider`,
  `decider_refresher` en `auto_sim_loop`).

**API**

- `apps/api-python/src/bolsa_api/schemas/research.py`
  (`StrategyHealthSnapshotDto/StrategyHealthDto/StrategyHealthResponseDto`).
- `apps/api-python/src/bolsa_api/api/v1/routes/research.py`
  (`GET /research/strategy/{version_id}/health`).

**Tests**

- `packages/py/application/tests/test_strategy_{lab,top3_coach,promotion,vigilance}_phase.py`.
- `packages/py/application/tests/test_auto_orchestrator.py`.
- `apps/api-python/tests/test_auto_orchestrator_worker.py`.
- `apps/api-python/tests/test_auto_sim_active_strategy_seam.py`.
- `apps/api-python/tests/test_strategy_lifecycle_pg.py`
  (`test_auto_orchestrator_full_cycle_pg` sobre PG real).

**CI**

- `.github/workflows/{python-ci,release-tag-ci}.yml` (tests herméticos A10/V2.26 al pytest offline).
- `.github/workflows/release-tag-ci.yml` (`lifecycle-pg` con `AUTO_ORCHESTRATOR_PG_REQUIRED=1`
  además de `STRATEGY_LIFECYCLE_PG_REQUIRED=1`).

## 3. Variables de entorno

| Variable                             | Default | Efecto                                            |
| ------------------------------------ | ------- | ------------------------------------------------- |
| `AUTO_ORCHESTRATOR_ENABLED`          | OFF     | Arranca el bucle del orquestador (SIM-only)       |
| `AUTO_ORCHESTRATOR_INSTRUMENTS`      | vacío   | CSV de instrumentos a orquestar                   |
| `AUTO_ORCHESTRATOR_INTERVAL_SECONDS` | 3600    | Periodo del bucle                                 |
| `AUTO_ORCHESTRATOR_SHADOW_VALIDATED` | OFF     | Permite promocionar (sin shadow NO hay promoción) |
| `AUTO_ENGINE_SIM_ACTIVE_STRATEGY`    | OFF     | Cablea la `ACTIVE` al AUTO vía `DecisionProvider` |
| `STRATEGY_LIFECYCLE_PG_REQUIRED`     | —       | Gate CI: skip de los tests PG de A10 ⇒ fallo duro |
| `AUTO_ORCHESTRATOR_PG_REQUIRED`      | —       | Gate CI: skip del ciclo completo PG ⇒ fallo duro  |

## 4. Verificación (estado honesto)

Ejecutado en local (Windows, PostgreSQL de desarrollo disponible):

- **Ruff** sobre los ficheros tocados → `All checks passed!`.
- **Mypy** (`--follow-imports=silent`) sobre `auto_orchestrator.py`,
  `auto_orchestrator_worker.py`, `auto_simulation_worker.py`, `scheduler_worker.py`
  → `Success: no issues found`.
- **Herméticos** (`packages/py/application/tests` + `packages/py/domain/tests`
  - los dos nuevos ficheros de worker/seam) → **1256 passed**.
- **PG real** `apps/api-python/tests/test_strategy_lifecycle_pg.py` → **2 passed**
  (incluye `test_auto_orchestrator_full_cycle_pg`: ciclo completo, promoción con shadow y
  degradación → re-LAB).

**No ejecutado aquí:** la certificación por tag `v2.25/v2.26` en CI `release-tag-ci.yml`
(no se hace push ni tag en este ciclo); el resto de la suite completa del repo.

## 5. Barreras (sin cambios)

- AUTO → SIMULATED únicamente. LIVE real doblemente bloqueado.
- Sin LLM en el hot path de ejecución. El COACH es offline/advisory.
- Sin fallback SIM → LIVE.
- El LAB nunca cambia una estrategia activa directamente.

## 6. Siguiente

- **Orquestador real:** cablear `run_optimize` al LAB real (`RunSmaGridOptimize`) en el
  proceso API; hasta entonces el worker crea candidatas sin evidencia y **no promociona**
  (comportamiento fail-closed correcto).
- Validación shadow/paper automática como paso previo a habilitar
  `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`.
