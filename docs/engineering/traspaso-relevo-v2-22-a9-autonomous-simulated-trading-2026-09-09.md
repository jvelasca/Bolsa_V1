# Traspaso / relevo — V2.22-beta · A9 — Autonomous Simulated Trading (AUTO dual durable + worker SIM-once)

Fecha: 2026-09-09 · Rama: `main` (HEAD `ca98a39e`, tag `v2.21-beta` sin commit) · Ámbito: A9 plan v2.22 —
continuación del trabajo en-curso (M1/M2/M3/M6 ya en árbol) + **M4**, **M5**, **M7** y **Prueba Reina**.

## Resumen del ciclo

A9 añade varios sostenes nuevos al motor AUTO:

1. **M4 — Estado AUTO durable (P2 del audit)**: sustituye la telemetría en-memoria del
   `PaperAutoEngine` por un espejo durable PostgreSQL (`auto_engine_runs`/`auto_engine_ticks`, migración
   **Alembic 027**) vía `auto_engine_state_store` (Protocol + InMemory + Postgres), de modo que un worker
   reiniciado **readopta RUNNING + contadores SIN doblar el tick tras un crash**. Se mantienen los alias
   retrocompat `AUTO_ENGINE_DRY_*` añadiendo los canónicos `AUTO_ENGINE_SIMULATED_*` (worker prefiere SIM).
   AUTO sigue SIM-ONLY (no se toca la doble barrera LIVE).
2. **M5 — Bucle continuo SIM-ONLY**: worker conductor (`AutoSimulationWorker`) por tick: decisión inyectada →
   RiskGate/venue AUTO → settlement **reusando** `submit_simulated_order`/`apply_simulated_order_once`
   (M1/M2, `ExecutionEvent` idempotente por `execution_id`) → posición → journal; **off por defecto**
   (`AUTO_SIMULATION_WORKER_ENABLED`), registrado en `scheduler_worker` env-gated.
3. **M7 — Journal / diario AUTO (puro)**: `build_auto_daily_report` + invariantes del día en
   `packages/py/application` (orders>0, fills>0, positions_created>0, exits>0, ledger balanceado vía
   `assert_equity_invariant` o par numérico, sin duplicar `execution_events`, venues ⊆ {paper, simulated},
   y **no_live_bridge_posts**).
4. **Cierre del gap finance AUTO (ciclo extra)**: seam `simulated_finance.py` (mapper puro + factory
   `build_simulated_execute_trade_applier` → ExecuteTrade idempotente por `simulated_idempotency_key`,
   SIM-ONLY) + knob `finance_applier` en el worker + Reina-modo-finance + gate PG `test_simulated_finance_pg.py`.
   Fills AUTO pueden materializar **dinero real de práctica** sin tocar el núcleo LIVE; fail-closed sin
   contexto/venue no-AUTO, y `None` por defecto mantiene el día hermético sin dinero.

Núcleo financiero LIVE congelado intacto. **Alembic head: `027_auto_engine_state`** (añadida este ciclo;
`026_execution_events_fence` sigue como down_revision inmediato).

## Alcance cerrado (fases y archivos)

### M1/M2/M3/M6 — ya presentes en el árbol (arranque del ciclo; NO revertidos)

- [`packages/py/application/src/bolsa_application/simulated_settlement.py`](../../packages/py/application/src/bolsa_application/simulated_settlement.py) (nuevo): venue AUTO normalizer, candidates y `apply/submit_simulated_order`.
- [`packages/py/application/src/bolsa_application/decision_contract.py`](../../packages/py/application/src/bolsa_application/decision_contract.py) (modificado, M6): `simulation_gate_allows`.
- [`apps/api-python/src/bolsa_api/background/paper_auto_engine_worker.py`](../../apps/api-python/src/bolsa_api/background/paper_auto_engine_worker.py) (modificado, M3 y M4-DI): DecisionProvider al motor, telemetría `pendingPlans`, y **este ciclo** la docstring cabe en durable+decider (SIM-ONLY) + los env canónicos SIM.

### Este ciclo (nuevo / modificado)

| Archivo                                                                                         | Descripción                                                                                                                                                                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `packages/py/infrastructure/alembic/versions/027_auto_engine_state.py` (nuevo)                  | Migración idempotente que crea `auto_engine_runs` + `auto_engine_ticks` (PK/índices, `UniqueConstraint(engine_id, seq)` con nombre soporta `ON CONFLICT ON CONSTRAINT`), downgrade simétrico.                                                                                                                                                                  |
| `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` (modificado)    | Modelos `AutoEngineRunRow` y `AutoEngineTickRow`.                                                                                                                                                                                                                                                                                                              |
| `packages/py/application/src/bolsa_application/auto_engine_state_store.py` (nuevo)              | `AutoEngineStore` (Protocol) + `InMemoryAutoEngineStore` (hermético) + `PostgresAutoEngineStore` (upsert idempotente: tick `DO NOTHING`, run `DO UPDATE`) + `next_tick_input`/`crash_restart_readopts`.                                                                                                                                                        |
| `packages/py/application/tests/test_auto_engine_state_store_hermetic.py` (nuevo)                | Crash-restart readopt + no-double del InMemory.                                                                                                                                                                                                                                                                                                                |
| `apps/api-python/tests/test_auto_engine_state_pg.py` (nuevo)                                    | PG real: restart del store no dobla el tick (gate `AUTO_M4_PG_REQUIRED`). **Nota de verificación**: verde sólo con credenciales PG de dev en el entorno; en una re-verificación independiente sin ese usario/credencial, psycopg no autenticó (`no password supplied`) y el test hizo _skip_ honesto, no falló. Corre como gate real-PG del CI `lifecycle-pg`. |
| `packages/py/application/src/bolsa_application/auto_daily_journal.py` (nuevo, M7)               | Resumen diario AUTO puro + invariantes del día (ledger puede delegar en `assert_equity_invariant`).                                                                                                                                                                                                                                                            |
| `packages/py/application/tests/test_auto_daily_journal.py` (nuevo, M7)                          | Celajes del build + predicados por invariante.                                                                                                                                                                                                                                                                                                                 |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (nuevo, M5)                | Bucle determinista SIM-ONLY + settlement sobre `ExecutionEventStore` inyectado + `start_auto_sim_worker` env-gated + loop.                                                                                                                                                                                                                                     |
| `apps/api-python/src/bolsa_api/workers/scheduler_worker.py` (modificado, M5)                    | Registro de `start_auto_sim_worker` en `_event_loop_starters` (gate interno devuelve `None` si OFF).                                                                                                                                                                                                                                                           |
| `apps/api-python/tests/test_auto_simulation_worker.py` (nuevo, M5)                              | Day-dive hermético (InMemory EventStore) con day-journal sano.                                                                                                                                                                                                                                                                                                 |
| `apps/api-python/tests/test_auto_engine_full_day_zero_human_intervention.py` (nuevo, **Reina**) | Conduce el día completo por ticks del worker (sin `POST /paper-desk/cycle` ni `execute_trade()` directo), reloj+price deterministas; comprueba los 8 invariantes.                                                                                                                                                                                              |
| `.github/workflows/release-tag-ci.yml` (modificado)                                             | Añade `test_auto_engine_state_pg.py` (M4) Y `test_simulated_finance_pg.py` (cierre del gap finance AUTO) al pytest real-PG del job `lifecycle-pg` (esquema a head 027).                                                                                                                                                                                        |

### Cierre del gap finance AUTO (ciclo extra) — dinero real SIM-ONLY por fill

Cierra el delta declarado en el relevo (antes el worker liquidaba con `apply_finance=None`, fills `CAPTURED`
sin dinero). Ahora hay un tornillo real, que **reusa** el núcleo canónico (no toca el núcleo LIVE):

| Archivo                                                                                          | Descripción                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `packages/py/application/src/bolsa_application/simulated_finance.py` (nuevo)                     | Seam SIM-ONLY: mapper puro `sim_fill_finances`/`resolve_execution_finance` (recupera `ExecutionEvent`→`SimulatedFillFinance` con `instrument/side/qty/price` deterministas y `execution_id`), guardas `guard_sim_only_venue`/`SIM_FINANCE_VENUES`, mini-day puro `sim_roundtrip_accounting`, y la mitad PG-lazy `build_simulated_execute_trade_applier` → `ApplyFinanceCallable` (ExecuteTrade idempotente por `simulated_idempotency_key`; fail-closed → `False` si no hay contexto viable o venue no-AUTO). |
| `packages/py/application/tests/test_simulated_finance.py` (nuevo)                                | 7 herméticos: mapper por fill, fail-closed venue live, idempotencia real `apply_execution_financial_once` (un fill = una `idempotency_key`), invariante de dominio `assert_equity_invariant(LifecycleAccounting)` sobre libro real-money no-degenerado, y replay idempotente.                                                                                                                                                                                                                                 |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (modificado)                | Añade `finance_applier` (constructor + `_settle` lo reenvía como `apply_finance`). `None` (default) = comportamiento hermético actual sin dinero; inyectado = fills SIM materializan dinero SIM-ONLY. Docstring cabecera actualizada.                                                                                                                                                                                                                                                                         |
| `apps/api-python/tests/test_auto_engine_full_day_zero_human_intervention.py` (modificado, Reina) | Añade modo-finance: el mismo día, pero con `finance_applier` conectado a un book real-money SIM-ONLY. El modo estructural original queda byte-igual.                                                                                                                                                                                                                                                                                                                                                          |
| `apps/api-python/tests/test_simulated_finance_pg.py` (nuevo)                                     | Gate PG real del cierre (ExecuteTrade real sobre repos), skip honesto sin credenciales salvo `AUTO_M5_FIN_PG_REQUIRED=1` (entonces falla en CI `lifecycle-pg`).                                                                                                                                                                                                                                                                                                                                               |

## Decisiones registradas

- **Durabilidad M4 en dos tablas** (`auto_engine_runs` singleton + `auto_engine_ticks` ledger append-only) en
  lugar de una sola, para respetar a la vez "estado + contadores + último motivo" y la propiedad
  idempotente por `(engine_id, seq)` (un `ON CONFLICT ON CONSTRAINT` real, no sólo índice único).
- **Fail-closed del store**: sin store (DB off / hermético) `PaperAutoEngine` sigue exactamente en-memoria
  (SAFE/dry) para no romper los tests de M3; el driver durable solo actúa cuando hay store.
- **Env canónico over alias**: se prefieren `AUTO_ENGINE_SIMULATED_*`; los tests existentes siguen fijando
  `AUTO_ENGINE_DRY_*` (alias intactos) → no se rompe ningún test ni el fixture del worker.
- **Real-money SIM-ONLY opt-in (finanzas)**: el seam `simulated_finance` materializa dinero de práctica por
  fill SOLO cuando alguien inyecta un `finance_applier` (ExecuteTrade sobre una cuenta/cartera de práctica).
  Default `None` = trazas `CAPTURED` sin dinero; guardas SIM-ONLY bloquean cualquier venue live/real;
  idempotencia estricta por `simulated_idempotency_key(execution_id)` (el ExecuteTrade se alimenta de la MISMA
  key del `simulated_settlement`, nunca otra); el core LIVE queda intocado.
- **M5 usa la vía de settlement M1/M2** (`submit_simulated_order`), nunca dinero directo ni brida LIVE;
  `AUTO_SIMULATION_WORKER_ENABLED` default OFF ⇒ nada se llena sin flag explícito; logs "SIM only".
- **M5 se registra en `_event_loop_starters`** como worker continuo pero con gate interno OFF (como los demás
  workers que "gestionan su propio gate de configuración").
- **Reina hermética**: el day-drive verde se hace contra `InMemoryExecutionEventStore` (sin ledger vivo de PG
  por tick). En el relevo se declara el **delta** frente a una corrida scheduler-PG que quedó fuera de alcance
  (ver Gaps/notas).

## Verificación (estado honesto)

Tasks/edición de código de este ciclo con resultado ejecutado en local:

- Ruff (`check` + `format --check`, config raíz): **limpio** sobre los ficheros nuevos/modificados (simulated_finance,
  auto_engine_state_store, auto_daily_journal, worker M5 + verified seam finance, paper_auto_engine_worker, scheduler,
  migración 027 + tests). Mypy (strict) sobre módulos src nuevos/modificados: `simulated_finance.py`,
  `auto_engine_state_store.py`, `auto_daily_journal.py`, `auto_simulation_worker.py`, `paper_auto_engine_worker.py`,
  `scheduler_worker.py` → **Success, 0 issues**.
- pytest (verde, ejecutado local):
  - M4 durable hermético: `test_auto_engine_state_store_hermetic.py` → **6 passed**.
  - M4 durable PG real (PostgreSQL localhost:5432, `ensure_migrated`→head 027): `test_auto_engine_state_pg.py`
    → **1 passed en el entorno dev con credenciales PG** / **skip honesto** en re-verificación independiente sin
    credencial: `PostgreSQL no disponible: no password supplied`. El test hace skip salvo `AUTO_M4_PG_REQUIRED=1`
    (entonces falla), pensado para correr en el job CI `lifecycle-pg` con la BD del esquema a head 027.
  - M7: `test_auto_daily_journal.py` → **8 passed**.
  - M5: `test_auto_simulation_worker.py` → **1 passed**.
  - Reina: `test_auto_engine_full_day_zero_human_intervention.py` → **2 passed** (estructural con los 8
    invariantes + modo finance: mismo día, pero con el semillero de `finance_applier` real-money SIM-ONLY).
  - Directamente afectados / M3 ya en árbol: `test_paper_auto_engine_worker.py` → **8 passed**.
  - Basamentos M1/M2/M6/suite aplicación: `test_simulated_broker.py + test_simulated_settlement.py +
test_decision_contract_barricade.py` → **20 passed**.
  - **Hermético verificado en local (este ciclo + basamentos): 52 passed** en los ficheros citados
    (de ellos: finance SIM-ONLY nuevo `test_simulated_finance.py` = 7; Reina = 2 con su modo finance;
    M4-herm = 6; M7 = 8; worker M5 = 1; M3-preexistentes `paper_auto_engine_worker` = 8; basamentos
    M1/M2/M6 `simulated_broker+simulated_settlement+decision_contract_barricade` = 20).
  - **PG real (2 cels) — condicionales a credenciales dev PG**: `test_auto_engine_state_pg.py` (M4 durable,
    gate `AUTO_M4_PG_REQUIRED`) y el NUEVO `test_simulated_finance_pg.py` (cierre del gap finance AUTO,
    gate `AUTO_M5_FIN_PG_REQUIRED`). En la re-verificación independiente SIN credencial hicieron **skip
    honesto**: `PostgreSQL no disponible: no password supplied`. Están cableados al job CI `lifecycle-pg`
    (esquema Alembic a head 027) donde la BD SÍ está; allí son gates de verificación real-PG, no se dan por
    corridos-en-verde en un entorno sin esas credenciales.
- **NO ejecutado / no verificado aquí (marcados con honestidad):**
  - **Not run**: suite completa del repo (rincones muy amplios/no relacionados) — no se lanzó; sólo los ficheros
    citados.
  - **Not run**: el job **Release-tag CI** (no se hace push ni tag en este ciclo).
  - **Not run (delta PG en vivo)** : una corrida _scheduler + PG_ de un "día AUTO" con cierre de libro contable
    real (positions/ledger vivos y `assert_equity_invariant` del dominio sobre un ledger PG normal, POR cada
    fill materializado vía `ExecuteTrade` idempotente por `simulated_idempotency_key`). El código de ese camino
    (seam `simulated_finance` + `finance_applier` + Reina-modo-finance) está cerrado y su lógica hermética es
    verde; el **gate PG en vivo** `test_simulated_finance_pg.py` (CI `lifecycle-pg`) lo valida contra la BD real
    cuando hay credenciales. En este entorno sin credenciales dev hace skip honesto, así que esa corrida PG en
    vivo NO se reporta como verde-aquí.

## Gaps / notas

- El `finance_applier` del worker es **opt-in**: sin él (`None`, default) las trazas `ExecutionEvent` quedan
  `CAPTURED`/fail-closed sin dinero (correcto y seguro por defecto). Con el seam **cerrado**:
  `bolsa_application/simulated_finance.py` (factory `build_simulated_execute_trade_applier` → ExecuteTrade
  idempotente por `simulated_idempotency_key`, SIM-ONLY) + knob `finance_applier` en `AutoSimulationWorker` +
  Reina-modo-finance. El **applied real sobre PG** del cierre contable del día es el gate PG en vivo
  (`test_simulated_finance_pg.py`, CI `lifecycle-pg`).
- La **vertiente de protect/trail/T1/T2/exit** con `decide_position_policy`/`check_exit_permission`/
  `ExecutePositionPolicyAuto` del área analytics/cognitive no se volvió a implementar en el worker M5 (se dejó el
  conductor de settlement/posición con sus costuras). Hombre asumir esa política por-tick como siguiente paso
  (ver _Next steps_).
- El seed del settlement SIM usa `minute*… + sum(ord(symbol))` (determinista en proceso). Estable de correr a
  correr en el mismo proceso; no fue necesario para la reina (que usa varios símbolos/minutos) aunque es una
  superficie a no olvidar si se quiere una semilla reproducible entre procesos.

## Next steps (siguiente ciclo propuesto)

1. Disparar el **gate PG en vivo del cierre contable del día AUTO** (`test_simulated_finance_pg.py` junto a
   `test_auto_engine_state_pg.py`) en el job CI `lifecycle-pg` con credenciales reales, y exigir el
   `assert_equity_invariant` del dominio sobre un ledger PG normal por cada fill materializado.
2. Hacer que `AutoSimulationWorker` consuma la política existente del área **analytics/cognitive**
   (protect/trail/T1/T2/exit) reusando `ExecutePositionPolicyAuto` y reconciliando por tick.
3. Re-evaluar seed del settlement SIM para reproducibilidad entre procesos (fuera de la semilla por proceso).
4. Vigilar que los workers env-gated (M5 y M4 durable) no degraden el arranque del scheduler en dev sin PG (se
   verificó fail-closed en hermético).

## Estado de la rama / head

- Alembic head tras este ciclo: **`027_auto_engine_state`** (añadida). Sin migraciones para deshacer por encima;
  base `026_execution_events_fence` sin cambio. El resto de migraciones (`023`–`026`) intactas.
- No se hizo commit ni tag (instrucción del ciclo); el árbol de trabajo recoge M1/M2/M3/M6 (ya presentes) +
  M4/M5/M7 + Prueba Reina + **cierre del gap finance AUTO** (`simulated_finance.py` + knob `finance_applier` +
  `test_simulated_finance.py` + PG gate `test_simulated_finance_pg.py`) + toque de CI sobre `release-tag-ci.yml`
  (los dos gates real-PG M4/finance en el job `lifecycle-pg`).

FIN DEL RELEVO — V2.22-beta · A9 (M4 durable + M5 loop SIM-ONLY + M7 journal + Prueba Reina + cierre del gap
finance AUTO SIM-ONLY real-money) documentado con verificación honesta: **52 tests herméticos verdes
reproducidos en local** (incl. `test_simulated_finance.py`=7 y Reina=2 con modo finance) + los 2 gates PG
(M4 durable y finance AUTO) cableados a CI `lifecycle-pg`, reportados como **skip honesto** cuando no hay
credenciales dev PG (no se reclamó verde en ese entorno); Alembic head `027_auto_engine_state`; gap pendiente
restante: política protect/trail/T1/T2/exit del worker M5 + corrida PG en vivo a validar en el job dedicado;
archivo de plan intacto.
