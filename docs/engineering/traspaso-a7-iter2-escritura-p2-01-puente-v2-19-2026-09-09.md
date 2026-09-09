# Traspaso / relevo — A7 Iter-2 (escritura) · P2-01 + puente financiero · V2.19

Fecha: 2026-09-09 · Ámbito: A7 LIVE Certification / Iter-2 — primera ENTREGA DE
ESCRITURA (V2.19) del marco `plan-a7-iter2-financial-crash-v2-19`. Descongela POR
FIN, de forma **GATED**, la vertiente financiera del crash (P2-01 + cable).

Estado honesto: **implementado y validado** en unidad + migración real-PG + **batería
real-PG C3-C/C3-D**. El commit/push/tag no está ejecutado (acción del operador en el
flujo de elevación, §7).

## 1. Decisión de bridge (registrada, Iter-2 escrita)

El marco Iter-2 (§7 backlog) pidió elegir el puente = **despark real pero GATED**
(go fail-closed OFF). Esta escritura fija el bridge **POR FASES IDEMPOTENTES**:

- El recovery resuelve la FSM (UNKNOWN→FILLED) como en V2.18 (fsm_only intacto en
  ausencia de go).
- Bajo el **go nuevo `LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED` (default OFF)** y
  solo si el broker del recovery **acredita `fill_seq` + `fill_price`**, se captura
  un `ExecutionEvent` durable (identidad `execution_id = venue_order_id#fill_seq`)
  y se materializa Position/Ledger por **fases** con doble idempotencia:
  (a) CAS `CAPTURED→APPLYING→APPLIED/FAILED/RETRY` por `execution_id`;
  (b) `ExecuteTrade` idempotente por `idempotency_key` (M4, no-doble hasta con
  retry/crash multi-worker).
- Ningún precio/plan se INVENTA: si el bridge no devuelve `fill_seq`/`fill_price`,
  `recovery_apply.recovery_financial_decision` → `price_unknown`/`not_fill` y la
  fila queda `fsm_only` (firewall H4/H6, cero dinero sin broker que lo acredite).

## 2. Alcance de código (ruta:línea exacto)

- **Migración**: `packages/py/infrastructure/alembic/versions/024_execution_events_state.py`
  (down_revision `023`) — añade a `execution_events`: `status` (default `'CAPTURED'`,
  NC), `applied_at` (null), `attempt_count` (default 0, NC), `last_error` (null).
  Estilo 022/023 (guards standalone). **No toca** la revisión 023 ni otra tabla.
- **Modelo**: `.../database/models/tables.py` `ExecutionEventRow` (+ las 4 columnas, un
  solo hunk al final de la clase).
- **Dominio/workflow durable**: `packages/py/application/src/bolsa_application/execution_event.py`
  — `ExecutionEventStatus`, `VALID_EXECUTION_EVENT_STATUSES`,
  `can_transition_execution_event` (CAPTURED/APPLYING/APPLIED/FAILED/RETRY);
  `ExecutionEvent` + campos de workflow; store Protocol + `InMemoryExecutionEventStore`
  y `PostgresExecutionEventStore` con `start_apply` (CAS), `mark_applied/failed/retry`;
  orquestador **`apply_execution_financial_once`** (fases con no-doble).
- **Decisión pura del puente**: `packages/py/application/src/bolsa_application/recovery_apply.py`
  (`recovery_financial_decision`, `build_recovery_execution_candidate`,
  `recovery_idempotency_key`) — fail-closed, sin I/O.
- **Query del broker**: `.../live_order_query.py` → `BrokerOrderQueryResult` + campos
  OPCIONALES `fill_seq`, `fill_price` (ausencia = fsm_only, no se fabrica nada).
- **Cable en recovery** (`apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py`):
  `financial_apply_enabled()` (go default OFF, lectura estilo `live_drift`);
  `resolve_one_unknown(..., out_result)` expone el result del fill;
  `_drain_unknowns(..., _fill_results)` recolecta fills resueltos;
  `_drain_once` bajo go llama `_apply_recovery_fills_financially` (ExecuteTrade
  idempotente real + `apply_execution_financial_once`, misma sesión).

## 3. Go nuevo (fail-closed, spec igual al marco)

`LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED` (default OFF). OFF ⇒ el recovery queda
**bit-for-bit** al fsm_only de V2.18 (no toca Position/Ledger; `execution_events`
permanece sin filas financieras que un conductor no escriba). El `a7-gate` real-PG
inyectará `=1` solo con BD dedicada cuando la batería financiera esté lista.

## 4. Migración validada en PG real

`alembic upgrade head` aplicado y comprobado sobre la BD de dev — **head local pasa a
`024_execution_events_state`**; columnas materializadas con los defaults correctos:
`status 'CAPTURED'`, `attempt_count 0`, `applied_at`/`last_error` nullable.
(Additiva; sin efectos sobre la fila `execution_events` existente. La head remota/origin
sigue en 023 hasta la elevación.)

## 5. Verificación (esta entrega)

- Ruff `packages/py + apps/api-python` limpio en los ficheros tocados; chain alembic
  single-head (`024`, sin ramas).
- Unit:
  - `test_execution_event.py` → **16 passed** (9 previos + 7 durable incl. reclaim
    crash de APPLYING y no-doble).
  - `test_recovery_apply.py` (nuevo) → **10 passed** (decisiones fail-closed, candidato
    identity estable, idempotency_key).
  - worker `test_live_order_recovery_worker.py` → intacto (go OFF = comportamiento
    congelado idéntico).
- Regresión amplia `packages/py/application/tests` → **1031 passed / 0 fail**.
  En su día afloraron 2 fallas **pre-existentes** (verificadas en blanco vía git stash,
  ajenas a V2.19): el fake `_FakeAccountRepo.list_accounts` sin firmar
  `owner_user_id` (drift de protocolo) y el `fetchedAt` fijo de
  `test_run_fundamental_screener_f4` que caducaba con el reloj (> maxAgeDays). Se
  cerraron con **fix de test único** (data/fixture únicamente, cero lógica de
  producto): el fake acepta e ignora `owner_user_id`; el fixture del screener usa un
  `fetchedAt` reciente (relativo a `now`) para no volver a enmohecerse.

## 6. Batería real-PG C3-C/C3-D (construida tras cerrar esta escritura)

- **SÍ hay batería real-PG `chaos/live_a7` de crash-financiero end-to-end** ya construida
  y verde: `apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py`
  (+ modos de probe en `_crash_recovery_probe.py`). Siembra una cuenta+portfolio+cash
  simulados reales en la BD A7 dedicada y ejecuta `ExecuteTrade` real.
  - C3-C → `test_c3c_crash_financial_apply_reexecuted_exact_once`: proceso A entra al
    apply durable (event `APPLYING` ya COMMITteado, ExecuteTrade en vuelo en tx no
    committeada) → **SIGKILL** (PG hace ROLLBACK de cash/position/ledger dejando el
    event durable `APPLYING`) → proceso B reaparece y re-ejecuta el mismo primitivo
    idempotente → termina `APPLIED/attempt≥1`, position==100 (nunca 200), cash por
    UNA notional+fee, **1** ledger effect.
  - C3-D → `test_c3d_reclaim_applying_or_terminal_no_double`: re-delivery en terminal no
    re-materializa (byte-idéntico tras APPLIED).
  - Live real-PG dedicado: **`4 passed`** (C3-A + C3-B intactos; re-verificado 3×).
- **Bug real de PG detectado y arreglado (mínimo):** `PostgresExecutionEventStore.capture`
  usaba el `insert` genérico de SQLAlchemy (sin `on_conflict_do_nothing` → `AttributeError`
  en el camino real). Fix: dialecto PostgreSQL `pg_insert` (idempotente igual que
  `live_order_store`). Solo apareció al ejecutar la batería PG (los unit son InMemory).
- **Caveat honesto:** el loop de recovery `_drain` solo alimenta finanzas para fills que
  él resuelve ese tick desde UNKNOWN; **no hay aún auto-re-scan prod de un event `APPLYING`
  huérfano por stale** (C3-D lo cubre con dos actores, no con self-healing del worker).
  Ese re-scan auto-heal es un puente de wiring prod a backlogear aparte, no esta entrega.
- El `scheduler_worker` completo sigue sin arrancar los apply (C3-S no cubierto). Igual
  que tras V2.18.

## 7. Para la elevación (realizada en esta iteración de cierre)

1. ✅ CERRADO: los **2 tests pre-existentes rojos** quedan con fix de test único
   (arriba). Offline reproducible GREEN: `application/tests` **1031 passed**.
2. ✅ HECHO: la **batería real-PG `chaos/live_a7`** C3-C/C3-D del crash financiero
   (cuenta simulada sembrada + ExecuteTrade idempotente + SIGKILL en distintas fases)
   está construida y verde.
3. Offline CI pasos ajenos al pytest verificados verdes: `ruff check` (config repo,
   alcance completo) `All checks passed`; import-linter `4 kept / 0 broken`; mypy
   `Success (438 files)`. Tipados del código V2.19 nuevos corregidos para
   dejar el pipeline sin deuda (incl. `pg_insert` dialecto PG en `capture`
   descubierto por la batería real; quitar `type: ignore` huérfanos; annotar
   `_fill_results: list[tuple[Any, Any]]`, `_to_event_qty -> Decimal`).
4. Commit local → push a `origin/main` (trae también `eb777544`, marco documental
   ya committeado y pendiente de push) → tag `v2.19-beta` → **Release-tag CI**
   (`python` offline + `certify` + `a7-gate` real-PG con la batería C3-C/D).

FIN DEL TRASPASO — A7 Iter-2 · escritura P2-01 + puente financiero por-fases (go OFF
por defecto, cable recovery) implementado y validado en unidad + migración real-PG;
**batería real-PG C3-C/C3-D verde**; **árbol listo para commit/push/tag V2.19** con el
pipeline offline/online en verde; núcleo congelado elevado solo en la columna additiva
autorizada (BBDD local a head 024). Home/gate de continuidad: `chaos/live_a7` + job
`a7-gate` real-PG.
