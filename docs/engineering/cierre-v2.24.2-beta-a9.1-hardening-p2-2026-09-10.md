# Cierre V2.24.2-beta / A9.1-hardening — P2 residuales cerrados

**Fecha:** 2026-09-10
**Versión:** `1.51.1-beta` (`package.json`)
**Base:** V2.24-beta / A9.1 (`1.51.0-beta`, tag `v2.24-beta` → `b2ee67ed`, certificación
GREEN run `34470214388`).
**Alcance:** AUTO SIM-ONLY. **LIVE real intacto y doblemente bloqueado.**
**Motivo:** cerrar los 4 P2 residuales de la auditoría externa de V2.24 (equity
invariant demasiado sintético, commits independientes, reconciliación solo por símbolo,
restart sin posición protegida).

---

## 1. Qué cambia (por P2)

| ID   | Cambio                                                                                                         | Invariante certificado                                                                                    |
| ---- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| P2-A | `reconstruct_accounting_from_state` reconstruye la contabilidad desde el ledger real (no ceros)                | `total_equity == initial + realized + unrealized` es una afirmación financiera NO tautológica             |
| P2-B | `SimDurableUnitOfWork` + `autocommit=False` en los stores Postgres                                             | Proyección y contexto financiero del mismo fill pueden commitear en UNA transacción; el default no cambia |
| P2-C | `reconcile_sim_account` (global por cuenta) + `reconciliation_blocks_openings` en el worker                    | Un solo símbolo `DIVERGENT`/`UNKNOWN` (o fantasma) bloquea aperturas en TODA la cuenta (fail-closed)      |
| P2-D | Test PG-gated de restart REAL del proceso con posición abierta + retén parametrizable (`..._EXIT_AFTER_TICKS`) | Tras crash+restart, el proceso readopta la posición durable y NO re-compra (BUY no se dobla)              |

## 2. Archivos clave

- `packages/py/application/src/bolsa_application/auto_daily_journal.py`
  (`LedgerCashMovement`, `reconstruct_accounting_from_state`).
- `packages/py/application/src/bolsa_application/sim_durable_store.py`
  (`SimDurableUnitOfWork`, `autocommit` en ambos stores Postgres).
- `packages/py/application/src/bolsa_application/sim_reconciliation.py`
  (`AccountReconciliationReport`, `reconcile_sim_account`).
- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
  (reconciliación global + propiedades de estado + retén por env).
- `apps/api-python/tests/test_a9_1_durability_integrity.py`
  (P2-C global + P2-D hermético con trailing sobre `high_watermark` persistido).
- `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`
  (P2-A real + P2-D restart PG-gated).
- `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py`
  (P2-A real, conservando el check M-2 ledger↔cash).
- `packages/py/application/tests/test_auto_daily_journal.py`,
  `packages/py/application/tests/test_sim_durable_unit_of_work.py` (nuevos tests herméticos).
- `.github/workflows/release-tag-ci.yml` (gate `AUTO_SCHEDULER_RESTART_PG_REQUIRED`).

## 3. Verificación (estado honesto)

Ejecutado en local (Windows, PostgreSQL de desarrollo disponible):

- **Ruff** `uv run ruff check packages/py apps/api-python --config pyproject.toml` → `All checks passed!`
- **Import-linter** `uv run lint-imports --config packages/py/.importlinter` → `4 kept, 0 broken`.
- **Mypy** full-tree (`--follow-imports=silent`) → `Success: no issues found in 451 source files`.
- **Herméticos** (`test_auto_daily_journal`, `test_sim_durable_unit_of_work`,
  `test_a9_1_durability_integrity`, `test_a9_1_crash_battery`, `test_auto_simulation_worker`)
  → **46 passed**.
- **PG real** (`test_a9_scheduler_process_pg_zero_human.py`, incluye P2-A real y P2-D
  restart por proceso): el test de restart **1 passed** (≈96 s) contra la BD de desarrollo;
  el resto del fichero también verde.

**No ejecutado aquí:** la certificación por tag `v2.24.2-beta` en CI `release-tag-ci.yml`
(no se hace push ni tag en este ciclo); el resto de la suite completa del repo.

## 4. Barreras (sin cambios)

- AUTO → SIMULATED únicamente. LIVE real doblemente bloqueado.
- Sin LLM en el hot path. El COACH (A10) será offline/advisory.
- Sin fallback SIM → LIVE.

## 5. Siguiente (A10)

Con los P2 de A9.1 cerrados, el siguiente salto es **V2.25 Strategy Lifecycle**
(ESTUDIO → LAB → TOP3 → COACH → FINALISTA → VALIDACIÓN → PROMOTION → ACTIVE → vigilancia)
reutilizando el LAB/optimización/OOS existente, y después **V2.26 Auto Orchestrator**.
Nota de nomenclatura: "V2.25/V2.26" se usó el 2026-09-04 para polish de UI (docs
`traspaso-relevo-v2-3/v2-4-*`); este plan **recicla** esos números para A10 y así se
documenta para evitar colisión de referencias.
