# Cierre V2.24-beta / A9.1 — Durable Autonomous Simulation Integrity

**Fecha:** 2026-09-10
**Versión:** `1.51.0-beta` (`package.json`)
**Tag:** `v2.24-beta`
**Alcance:** AUTO SIM-ONLY (simulación). **LIVE real intacto y doblemente bloqueado.**
**PR:** [#60](https://github.com/jvelasca/Bolsa_V1/pull/60)

---

## 1. Objetivo

Cerrar los **4 P1 de durabilidad/aislamiento** detectados en la auditoría V2.23 sobre el
AUTO SIM autónomo, endurecer los **6 P2 de integridad**, y elevar la certificación a una
**Reina real por proceso scheduler** (sin `run_tick()` manual) con **invariante de equity
sobre el ledger real**.

Núcleo financiero congelado. Ninguna feature de trading nueva.

---

## 2. Qué cambia (evidencia por invariante)

### P1 — Durabilidad / aislamiento

| ID    | Cambio                                                                                                              | Invariante certificado                                                                                                              |
| ----- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| P1-01 | `sim_auto_positions` pasa a **proyección reconstruible** (no autoridad)                                             | Una proyección no autoriza compra por sí sola; ante divergencia se reconstruye desde el canónico y, si falta, se veta (fail-closed) |
| P1-02 | Migración `029_sim_auto_pos_account_scope`: `account_id` + PK `(account_id, engine_id, symbol)` + scoping en stores | Dos cuentas con el mismo `engine_id`+símbolo **no colisionan**; cada una lee solo la suya                                           |
| P1-03 | `execution_id` con namespace único (`engine/account/logical_order_id`) vía `auto_venue_order_id`                    | Dos cuentas, mismo símbolo/minuto ⇒ `execution_id` **distintos**; aleatoriedad del book desacoplada de la identidad del order       |
| P1-04 | `account_id=None` ⇒ AUTO **BLOQUEADO** (arranque + veto `account_id_required`)                                      | Sin cuenta inequívoca no arranca; `auto_turn` veta antes de cualquier settlement                                                    |

### P2 — Integridad

| ID    | Cambio                                                                               | Invariante certificado                                                                            |
| ----- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| P2-01 | Estado de protección durable (`entry_price`/`high_watermark`/`stop`/`t1`/`trailing`) | Tras crash + readopt, el worker **no olvida** el máximo (trailing correcto)                       |
| P2-02 | `sim_reconciliation.reconcile_sim_position`                                          | Exige `ExecutionEvents == posición canónica == proyección` → `OK / REBUILT / DIVERGENT / UNKNOWN` |
| P2-03 | Batería crash C3-F/G/H/I                                                             | Sin doble ledger, sin doble `ExecutionEvent`, posición reconstruida                               |
| P2-04 | Reina real por **proceso scheduler**                                                 | El proceso, por sí solo, produce ticks/fills/ledger y deja el libro plano                         |
| P2-05 | `assert_equity_invariant` sobre el ledger real                                       | Invariante de equity sobre el estado financiero real (no `net_cash_delta=0`)                      |
| P2-06 | `exit_reason` trailing-before-T1, edad por símbolo, T1 parcial                       | Etiqueta honesta del motivo de salida; `exit_after_ticks` comparable entre watches                |

---

## 3. Tests de certificación (los tests son el certificado)

### Herméticos (sin PG; corren en el job `quality` de `python-ci.yml`)

`apps/api-python/tests/test_a9_1_durability_integrity.py`

- `test_execution_identity_namespaced_by_account` — P1-03
- `test_two_accounts_same_symbol_distinct_execution_ids` — P1-03 (colisión)
- `test_position_store_isolated_by_account` — P1-02
- `test_auto_blocked_without_account_id` — P1-04
- `test_protection_state_survives_restart` — P2-01
- `test_reconcile_ok` / `test_reconcile_divergent_blocks_openings` / `test_reconcile_rebuilds_stale_projection` / `test_reconcile_unknown_without_canonical` — P2-02
- `test_exit_reason_trailing_wins_over_t1` / `test_exit_reason_t1_when_no_retracement` / `test_t1_partial_fraction` — P2-06
- `test_auto_decision_engine_age_is_per_symbol` — P2-06
- `test_t1_partial_leaves_residual_position` — P2-06

`apps/api-python/tests/test_a9_1_crash_battery.py`

- `test_c3f_crash_before_position_no_second_effect` — P2-03 (C3-F)
- `test_c3g_crash_after_position_no_duplicate` — P2-03 (C3-G)
- `test_c3h_crash_during_context_no_money` — P2-03 (C3-H)
- `test_c3i_crash_during_readopt_is_safe` — P2-03 (C3-I)
- `test_reconciliation_blocks_openings_when_divergent` — P2-02

### PG-gated (job `lifecycle-pg` de `release-tag-ci.yml`)

`apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`

- `test_a9_scheduler_process_full_day_pg_zero_human` — P2-04 + P2-05
  Arranca `python -m bolsa_api.workers.scheduler_worker` como **subproceso real** con el
  spine determinista, sin `run_tick()` manual. Cuenta **scoped** a su `engine_id`/`account_id`;
  verifica `ticks>0, events>0, ledger>0`, cero trazas LIVE y — con
  `AUTO_EQUITY_INVARIANT_PG_REQUIRED=1` — `assert_equity_invariant` sobre el ledger real.

`apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py`

- Día AUTO completo con reinicio a mitad de jornada (readopción sin doble BUY/efecto),
  conteos **scoped** por `engine_id`/`account_id`, y `assert_equity_invariant` sobre el
  ledger real.

---

## 4. Gates CI

### `python-ci.yml` → job `quality` (se dispara en PR/push)

1. **Ruff** `ruff check packages/py apps/api-python --config pyproject.toml`
2. **Import-linter** `lint-imports --config packages/py/.importlinter` (4 contratos)
3. **Mypy** full-tree (0 errores; bloqueante)
4. **Pytest** unitarios + API offline (sin Postgres; los PG-gated hacen skip honesto)

### `release-tag-ci.yml` → job `lifecycle-pg` (se dispara con tags `v*`)

| Gate (env)                             | Certifica                                         |
| -------------------------------------- | ------------------------------------------------- |
| `AUTO_M4_PG_REQUIRED=1`                | ticks durables AUTO                               |
| `AUTO_M5_FIN_PG_REQUIRED=1`            | finanzas SIM reales                               |
| `AUTO_SCHEDULER_PG_REQUIRED=1`         | día AUTO por el camino real del scheduler         |
| `AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1` | **P2-04**: proceso scheduler real (no vacuo)      |
| `AUTO_EQUITY_INVARIANT_PG_REQUIRED=1`  | **P2-05**: invariante de equity sobre ledger real |

Un skip silencioso en cualquiera de estos gates es un **fallo duro**.

---

## 5. Barreras de seguridad (no negociables)

- **AUTO → SIMULATED únicamente.** LIVE real doblemente bloqueado
  (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`, false por defecto e independientes).
- **Sin LLM en el hot path de ejecución.**
- **Sin fallback SIM → LIVE.**
- El test de proceso verifica **cero trazas LIVE** en la cuenta AUTO (`venue` distinto de
  `live/broker_live/xtb/real/live_bridge`).

---

## 6. Evidencia de verificación local (comandos exactos de CI)

```
uv run ruff check packages/py apps/api-python --config pyproject.toml
  → All checks passed!

uv run lint-imports --config packages/py/.importlinter
  → Contracts: 4 kept, 0 broken.

uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
  → Success: no issues found in 451 source files

# tests herméticos A9.1
uv run pytest apps/api-python/tests/test_a9_1_durability_integrity.py \
  apps/api-python/tests/test_a9_1_crash_battery.py \
  apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q
  → 20 passed
```

---

## 7. Riesgos conocidos y limitaciones (honestidad de auditoría)

1. **Contaminación de la BD de desarrollo compartida.** `account_migration._load_default_scope`
   usa `scalar_one_or_none()` sobre `investment_accounts.is_default = true`. Los tests de
   aislamiento (p. ej. `test_platform_events_isolation`, `test_lifecycle_*`) dejan cuentas
   `is_default=true` duplicadas (`lc-*`/`user-a`) que rompen ejecuciones posteriores del
   suite completo contra la BD compartida. **Pre-existente y ajeno a A9.1**: se verificó que
   `main` (`v2.23-beta`) falla igual. Recomendación: ejecutar los tests de aislamiento
   contra una BD efímera por sesión. **No se modifica en esta entrega.**
2. **Conteos de la Reina escopados.** Al pasar `sim_auto_positions` a estar escopada por
   cuenta (P1-02), el helper `_counts` de `test_auto_scheduler_real_pg_zero_human_intervention.py`
   pasó a filtrar por `engine_id`/`account_id`; un conteo global ya no es significativo en BD
   compartida.
3. **Fallos locales no reproducibles en CI.** `test_non_auto_venue_requires_attention` y
   `test_queue_poll_worker::test_run_con_arq_es_noop` fallan **solo** en el entorno local
   (resolución de venue/`arq`); el CI de `main` está verde y se confirmó que
   `test_non_auto_venue_requires_attention` también falla en `v2.23-beta`. No bloquean.
4. **Fases 2 y 3 fuera de alcance.** El `Strategy Lifecycle` (V2.25) y el `auto_orchestrator`
   (V2.26) son el siguiente incremento; el orquestador ESTUDIO→LAB→COACH autónomo aún no
   existe en esta entrega (semilla A10).

---

## 8. Archivos clave de la entrega

- `packages/py/infrastructure/alembic/versions/029_sim_auto_pos_account_scope.py` (nueva)
- `packages/py/application/src/bolsa_application/sim_reconciliation.py` (nueva)
- `packages/py/application/src/bolsa_application/sim_durable_store.py`
- `packages/py/application/src/bolsa_application/simulated_settlement.py`
- `packages/py/application/src/bolsa_application/simulated_broker.py`
- `packages/py/application/src/bolsa_application/auto_decision_engine.py`
- `packages/py/application/src/bolsa_application/auto_daily_journal.py`
- `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`
- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
- `apps/api-python/tests/test_a9_1_durability_integrity.py` (nueva)
- `apps/api-python/tests/test_a9_1_crash_battery.py` (nueva)
- `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` (nueva)
- `.github/workflows/release-tag-ci.yml` (gates P2-04/P2-05)
- `package.json`, `CHANGELOG.md`

---

## 9. Cómo auditar esta entrega

1. **Diff del PR:** https://github.com/jvelasca/Bolsa_V1/pull/60 (19 + 5 ficheros, sección
   Commits).
2. **CI del PR:** checks `quality` (ruff/import-linter/mypy/pytest), `battery`,
   `fase2-battery`, `scan`, frontend.
3. **Certificación por release:** tag `v2.24-beta` → run de `release-tag-ci.yml` con los
   5 gates PG (`lifecycle-pg`).
4. **Migración:** `029_sim_auto_pos_account_scope` (up + down reversibles; el down descarta
   filas homónimas de otras cuentas, pérdida documentada e inevitable).
