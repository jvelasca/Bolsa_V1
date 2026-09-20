# Audit-pack v2.43.3-beta — AUTO-3 reliability closure (kill durable, identidad de salida y orden UTC)

**Fecha:** 2026-09-20 · **Versión:** `1.68.3-beta` (bump desde `1.68.2-beta`) · **Migración nueva:**
`043_exit_identity_and_kill_state` (**head de Alembic pasa de `042_portfolio_reservations` a `043`**).

**Alcance declarado.** Este pack cierra los **cinco hallazgos P0/P1** que la auditoría de
`v2.43.2-beta` dejó declarados en su §10/§12 (`Límites declarados`), todos de la misma familia: **un
hecho que pertenecía a la RAM del proceso y que el sistema presentaba como si fuera del sistema**.

| Hallazgo de `v2.43.2-beta`                                                    | Cómo se cierra aquí                                                 | Sección |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------- |
| **P0-1** «la parada dura es en memoria: un reinicio olvida el halt»           | `auto_kill_state` + `KillSwitchStore` + orden de arranque nuevo     | §3.1    |
| **P0-2** «identidad de salida no durable (`_v2_exit_seq` vuelve a 0)»         | `auto_exit_orders` + `exit_order_id` (ULID) + columna en la reserva | §3.2    |
| **P1-4** «si la reserva falla, el SELL se emite igual sin política declarada» | política **B** (intent de emergencia o HALT) + veto del call-site   | §3.3    |
| **P1-5** «`_fold_sort_key` ordena por cadena ISO, no por instante»            | `_applied_instant` (epoch UTC) + sin-fecha degrada medición         | §3.4    |
| **P0-3** «las cuatro ventanas de crash no están cubiertas»                    | matriz C1–C4 + Golden Day ampliado + PG de la 043                   | §3.5    |

**Regla de la casa respetada:** nada de esto cambia el comportamiento con
`AUTO_ENGINE_SIM_V2_GOVERNOR=0` sin parada dura más allá de lo declarado, y **el gobernador no se
toca** — `apps/api-python/scripts/v2_43_governor_evidence.py` sigue **byte a byte igual** y **exit 0**,
con su `"bump"` conservado en `1.68.0-beta` por el motivo ya declarado en `v2.43.1` §8.2.

---

## 1. Estado verificado (lo que había)

- **P0-1.** `AutoSimulationWorker` construía `HardKillSwitch()` por worker; `engage_kill_switch` /
  `release_kill_switch` no tenían **productor** ni **releasor** en producción y nada persistía
  `engaged`/`reason`. Un `WORKER 1 → KILL ON → CRASH → WORKER 2` reabría el motor.
- **P0-2.** `_v2_exit_seq = 0` en el constructor y `exit:{engine_id}:{symbol}:{seq}` como identidad:
  un contador de proceso que **volvía a 0** en cada arranque, así que un reinicio podía **reutilizar**
  una identidad histórica; el retorno de `_v2_reserve_exit` se descartaba en el único call-site.
- **P1-4.** Si `store.save/commit` fallaba, `_v2_reserve_exit` devolvía `None` y **el SELL se emitía
  igual**: salida sin identidad durable.
- **P1-5.** `_fold_sort_key` ordenaba `str(applied_at)` **lexicográficamente**: offsets distintos no se
  comparaban por instante (`09:00:00+02:00` vs `08:00:00Z` son el mismo momento).

## 2. Migración 043 (`043_exit_identity_and_kill_state`)

Aditiva, simétrica e idempotente (guards `_table_exists`/`_column_exists`/`_index_exists`, patrón
028–042, cadena lineal con `down_revision = "042_portfolio_reservations"`).

- **`auto_kill_state`** (PK compuesta `account_id, engine_id`): `engaged BOOLEAN NOT NULL default false`,
  `reason VARCHAR(32)` (32 y no 16: los motivos canónicos son más largos y `String(16)` abortaría la
  activación con `StringDataRightTruncation`), `engaged_at timestamptz`, `engagement_id TEXT`,
  `reengagements INTEGER NOT NULL default 0`, `released_at timestamptz`, `release_actor TEXT`,
  `release_reconciliation_id TEXT`, `updated_at timestamptz`. Índice `(account_id, engaged)`.
- **`auto_exit_orders`** (PK `exit_order_id`): `account_id`, `engine_id`, `instrument_id`,
  `side VARCHAR(16)`, `requested_qty/filled_qty/remaining_qty NUMERIC(18,6)`, `reservation_id`,
  `venue_order_id`, `state VARCHAR(32) default 'INTENT'`, `emergency BOOLEAN NOT NULL default false`,
  `reason`, `created_at`/`updated_at`. Índices `(account_id, state)` y `(account_id, instrument_id)`.
- **`portfolio_reservations.exit_order_id TEXT`** (nullable: las reservas históricas no tienen intent y
  siguen siendo válidas) + índice `(exit_order_id)`.
- **Sin backfill:** la ausencia de fila **es** información (no hay parada, no hay intent), nunca un cero
  inventado.

Paridad 1:1 con los row models `AutoKillStateRow` y `AutoExitOrderRow` de `tables.py`.

## 3. Matriz afirmación → código → test

### 3.1 P0-1 — El HALT es del SISTEMA, no del proceso

| Afirmación                                                              | Código                                                                                | Test                                                                   |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| El latch se persiste por `(account_id, engine_id)` y se lee al arrancar | `kill_switch_store.py` (`load`/`save`/`commit`), `worker._v2_load_kill_state`         | `test_a_durable_halt_survives_the_restart_and_still_blocks_entry`      |
| Un HALT persistido **jamás** se ignora                                  | `_v2_load_kill_state` (adopción unidireccional)                                       | idem (con latch nuevo vacío)                                           |
| Un fallo de escritura **no** levanta la parada                          | `_v2_persist_kill_state` (fail-closed)                                                | — (declarado; cubierto por el veto de arranque)                        |
| Liberar exige `reconciliation_id` y se persiste                         | `release_kill_switch`, `_v2_persist_kill_release`                                     | `test_a_durable_release_requires_a_reconciliation_id_and_is_persisted` |
| Una liberación persistida no revive la parada                           | `_v2_load_kill_state` (engaged=False no levanta halt local)                           | idem (segunda sesión)                                                  |
| Un libro no medible con reservas vivas **hala** el sistema              | `_v2_reconcile_reservations` → `engage_kill_switch_durable("RECONCILIATION_FAILURE")` | `test_auto_v44_exit_governance.py` (regresión de medición)             |
| Un duplicado de ejecución hala el sistema                               | `_reconcile_before_trusting` → `"DUPLICATE_EXECUTION"`                                | `test_a9_1_crash_battery.py`                                           |
| La parada restaurada veta entradas                                      | `_kill_active` / `governor_halted`                                                    | `test_v2_hard_kill_switch_vetoes_entry_with_governor_halted`           |

### 3.2 P0-2 — `exit_order_id`: identidad de salida durable

| Afirmación                                                   | Código                                                                     | Test                                                                         |
| ------------------------------------------------------------ | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| La identidad se mintea (ULID) **antes** de reservar y emitir | `exit_order.py:new_exit_order_id`, `worker._v2_reserve_exit`               | C1/C2 de la matriz de crash                                                  |
| El INTENT se persiste con su estado y su cola                | `exit_order_store.py`, `_v2_save_exit_order`                               | `test_exit_intent_survives_a_restart_and_keeps_its_queue` (PG)               |
| La identidad viaja a la orden (atribución por fill)          | `_next_logical_order_id(exit_order_id=…)`, `_settle(..., exit_order_id=…)` | C1 (`#1..#n` comparten `order_id`)                                           |
| La reserva enlaza con su intent                              | `build_reservation(..., exit_order_id=…)`, `_WRITABLE_COLUMNS`             | `test_reservation_links_to_its_intent_and_partial_fill_updates_it_once` (PG) |
| Un fill parcial deja el INTENT `PARTIAL` con cola viva       | `ExitOrder.apply_fill`, `_v2_apply_exit_fill`                              | C1/C4                                                                        |
| Una reserva muerta sin fill deja el INTENT `ABANDONED`       | `_v2_sync_exit_orders`                                                     | C2                                                                           |
| Un reinicio no re-emite la misma cola                        | reconciliación + reserva viva                                              | C3                                                                           |
| `_v2_exit_seq` **deja** de ser fuente de identidad           | (retirado del constructor)                                                 | mutación M3/M4                                                               |

### 3.3 P1-4 — Política de fallo de reserva (opción B)

| Afirmación                                                              | Código                                                                        | Test                                                                         |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Reserva no durable ⇒ intent de **emergencia** durable y la salida sigue | `_v2_reserve_exit` (`as_emergency`)                                           | `test_p1_4_reservation_failure_persists_an_emergency_intent_and_still_exits` |
| Intent de emergencia tampoco durable ⇒ **HALT** y **no** se emite       | `engage_kill_switch_durable("SYSTEM_ERROR")` + veto `exit_intent_not_durable` | `test_p1_4_when_neither_store_is_durable_the_system_halts_and_does_not_emit` |
| Con el intent de emergencia durable **no** se para el sistema           | idem                                                                          | idem (assert de `kill_state is None`)                                        |

### 3.4 P1-5 — Orden temporal por instante UTC

| Afirmación                                            | Código                                                   | Test                                                           |
| ----------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------- |
| El fold ordena por epoch UTC                          | `position_ledger.py:_applied_instant` + `_fold_sort_key` | `test_facts_are_ordered_by_utc_instant_not_by_string`          |
| ISO con offset y sufijo `Z` se parsean; naive = UTC   | `_applied_instant`                                       | idem                                                           |
| Un hecho sin fecha **degrada** la medición            | `build_position_ledger` (`undated` → `unvalued`)         | `test_a_fact_without_a_readable_date_degrades_the_measurement` |
| Los hechos sin fecha van al final, de forma declarada | `_fold_sort_key` → `(1, 0.0, execution_id)`              | regresión de H6 (`v2.43.2`)                                    |

### 3.5 P0-3 — Matriz de crash, Golden Day y PG

`apps/api-python/tests/test_auto_v44_exit_crash_matrix.py` (8 tests):

| Ventana | Escenario                                           | Convergencia que se exige                                                |
| ------- | --------------------------------------------------- | ------------------------------------------------------------------------ |
| **C1**  | decisión tomada → crash **antes** de reservar       | un único INTENT `FILLED`, una sola orden, posición plana                 |
| **C2**  | reserva persistida → crash **antes** de emitir      | reserva muerta `RELEASED_BY_RESTART`, INTENT `ABANDONED`, cierre exacto  |
| **C3**  | orden emitida → crash **antes** de `APPLIED`        | la reserva en vuelo **no se libera** y **no se re-emite**                |
| **C4**  | fill **parcial** aplicado                           | INTENT `PARTIAL` (80/120), total vendido = posición (no 280)             |
| P1-4a/b | reserva caída / ambos stores caídos                 | intent de emergencia sin halt / HALT persistido sin emisión              |
| HALT    | parada durable + liberación con `reconciliation_id` | el reinicio no olvida la parada y una liberación persistida no la revive |

El **Golden Day** dinámico y el **reinicio RISK_EXIT** (`test_auto_v44_exit_governance.py`, 9 tests) se
amplían con la ventana **crash-antes-de-reservar** (solo posición durable: ni reserva ni intent) y
verifican el `exit_order_id` del día completo.

`apps/api-python/tests/test_auto_v44_exit_identity_pg.py` (4 tests, gate `AUTO_RESERVATION_PG_REQUIRED=1`):
roundtrip de la **043** (tablas + índices + columna; `downgrade` a 042 y `upgrade head`), INTENT y HALT
que **sobreviven a un reinicio real por segunda sesión**, y el enlace reserva→intent con fill parcial.

## 4. Matriz de mutaciones (MEDIDA, no esperada)

Sonda: `apps/api-python/scripts/v2_43_3_mutation_audit.py` (patrón de `v2_43_2_mutation_audit.py`:
restauración **desde memoria**, nunca `git checkout --`, y verificación de **huella del árbol**
`git status --porcelain` de los ficheros tocados antes/después).

| #      | Mutación                                             | Dirección del error                    | Rojos medidos                                                          |
| ------ | ---------------------------------------------------- | -------------------------------------- | ---------------------------------------------------------------------- |
| **M1** | `_v2_load_kill_state` no restaura el HALT persistido | el reinicio reabre el motor            | `test_a_durable_halt_survives_the_restart_and_still_blocks_entry`      |
| **M2** | liberar sin `reconciliation_id`                      | el levantamiento deja de ser auditable | `test_a_durable_release_requires_a_reconciliation_id_and_is_persisted` |
| **M3** | la reconciliación no casa el INTENT con su reserva   | la identidad durable queda decorativa  | C2, C4                                                                 |
| **M4** | el fill no localiza el INTENT de salida              | idem, por el camino caliente           | C1, C2                                                                 |
| **M5** | sin intent de emergencia ni parada (fail-open)       | salida emitida sin rastro              | los dos tests de P1-4                                                  |
| **M6** | el fold vuelve a ordenar por cadena ISO              | orden y P&L por texto, no por instante | `test_facts_are_ordered_by_utc_instant_not_by_string`                  |

**Resultado: 6 de 6 muerden**, y la sonda deja la huella del árbol **intacta**.

## 5. Verificación medida (2026-09-20, máquina del autor)

```text
ruff check packages/py apps/api-python --config pyproject.toml     → All checks passed (0)
mypy <5 paquetes + apps/api-python/src> --follow-imports=silent    → Success: 489 ficheros, 0 issues
lint-imports --config packages/py/.importlinter                    → 4 kept, 0 broken (605 ficheros)
offline_ci_run_yaml.py ... python-ci.yml quality --with-pg-ignores → 2042 passed, 0 skipped, 0 failed
offline_ci_run_yaml.py ... release-tag-ci.yml python --with-pg-ignores
                                                                   → 2053 passed, 0 skipped, 0 failed
las 6 suites del cierre (crash matrix + governance + ledger + kill switch +
reserva ledgers + position manager)                                → 110 passed
v2_43_3_mutation_audit.py                                          → 6/6 muerden, huella intacta
```

**Límite declarado (honestidad):** los **tests PG de la 043 no se midieron en la máquina del autor**
(sin PostgreSQL alcanzable: el `connect` del DSN se cuelga). La certificación de la migración y del
reinicio real es la del **CI**, con gate **fail-if-skipped** (`AUTO_RESERVATION_PG_REQUIRED=1`) en el job
`auto-v2-durable-pg` de `python-ci.yml` y en `lifecycle-pg` de `release-tag-ci.yml`; el fichero queda en
`--ignore` del job hermético (si no, skipearía en mudo).

## 6. Comandos exactos de CI

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el gobernador NO se movió: esto debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

# bloques offline extraídos del YAML (medida por JUnit XML, no copia a mano)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

# suites del cierre
uv run pytest apps/api-python/tests/test_auto_v44_exit_crash_matrix.py \
              apps/api-python/tests/test_auto_v44_exit_governance.py \
              packages/py/analytics/tests/test_position_ledger.py \
              packages/py/analytics/tests/test_hard_kill_switch.py \
              packages/py/analytics/tests/test_portfolio_reservation_ledger.py \
              packages/py/application/tests/test_position_manager.py -q

# PG real (necesita PostgreSQL 16; el gate convierte un skip en fallo duro)
AUTO_RESERVATION_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v44_exit_identity_pg.py -q

# matriz de mutaciones
uv run --no-sync python apps/api-python/scripts/v2_43_3_mutation_audit.py
```

## 7. Límites declarados y deuda diferida

**Límites (declarados, no hallazgos):**

- Los tests PG **no** se midieron en local (arriba).
- `force_protective_exits` sigue existiendo y el camino de salida lo consulta; su productor automático
  sigue sin existir (deuda heredada de `AUTO-2`), igual que el emisor de `RECONCILED`.
- La identidad de salida **no** cubre todavía la atribución de P&L por intent (el ledger sigue siendo
  read-model sin tabla propia).
- El gobernador sigue **default OFF** y sus umbrales **sin calibrar** (fuera de alcance aquí).

**Deuda diferida (fuera de esta versión):** API de ledger por `(account_id, instrument_id)`; separación
`pending_entry`/`pending_exit` en `committed_positions`; renombrado de `EXIT_ONLY`; frescura de quote
como condición de ejecución; hysteresis/calibración del gobernador; gobernador ON por defecto; tags
firmados / CI attestation; **`AUTO-4` Portfolio Optimizer** (`V2.44` / `1.69.0-beta`).

## 8. Reproducibilidad e inventario

- **Ficheros nuevos:** migración `043_exit_identity_and_kill_state`, `exit_order.py` (modelo puro),
  `kill_switch_store.py`, `exit_order_store.py`, `test_auto_v44_exit_crash_matrix.py`,
  `test_auto_v44_exit_identity_pg.py`, `v2_43_3_mutation_audit.py`, este pack y el arranque del auditor.
- **Ficheros modificados:** `tables.py` (2 row models + columna e índice), `portfolio_reservation.py`,
  `reservation_store.py`, `hard_kill_switch.py`, `position_ledger.py`, `auto_simulation_worker.py`
  (composición por tick, kill durable, identidad de salida, política B, veto del call-site),
  `test_position_ledger.py`, `test_auto_v44_exit_governance.py`,
  `test_discovery_evidence_snapshot_pg.py` (head de Alembic), `python-ci.yml`, `release-tag-ci.yml`,
  `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index`, `package.json`.
- **Versionado:** bump `1.68.2-beta` → `1.68.3-beta`; **Alembic head `043`**.

## 9. Sello

**PENDIENTE al publicar este pack** (el documento se publica antes de sellar y **no afirma CI de un tag
que aún no existe**). Aquí irán el commit de fase, el `+N/−M` real del diff, el tag anotado
`v2.43.3-beta` y las URLs de los runs reales (`Python CI` en `main` y en la ref del tag, `Gitleaks` y
`Release tag CI` con `certify`).
