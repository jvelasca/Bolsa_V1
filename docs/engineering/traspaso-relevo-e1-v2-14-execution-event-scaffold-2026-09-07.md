# Traspaso de relevo — E1 V2.14 (ExecutionEvent scaffold idempotente GATED)

Fecha: 2026-09-07 · Rama `v2-14-financial-execution` · Repo `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`.

> Sigue a B2. Texto para el agente que continúe V2.14 (E1 resta que el apply-position se conecte al
> kernel Decimal cuando una capa autorizante dé go).

---

## RESULTADO E1 — audit P1-01 (scaffold GATED; decisión de usuario `scaffold_gated`)

1. **RFE/design choice (implícito en código+decreto):** idempotencia financiera por **`execution_id`**
   (= `venue_order_id` + `fill_seq`), NO por el contador `financial_apply_count`. Un fill → una sola
   clave; dos events del mismo fill → el segundo es `duplicate_skipped` (no materializa 2×).
2. **Migración** `packages/py/infrastructure/alembic/versions/022_live_orders_exec.py`
   (down `021_live_orders_fin`, head nuevo idempotente): añade a `live_orders` las columnas de
   observabilidad `attempt_count/last_error/claim_expires_at` (deuda B2) y crea tabla
   `execution_events` (`execution_id` PK + `order_id`/`venue`/`account_id`/`venue_order_id`/`fill_seq`/
   `qty NUMERIC(18,6)`/`captured_at`) con índices por `order_id` y `venue_order_id`.
3. **ORM** `tables.py`: `LiveOrderRow` + 3 columnas ops opcionales; nueva `ExecutionEventRow`.
4. **Store/dominio** `packages/py/application/src/bolsa_application/execution_event.py`:
   - `ExecutionEvent` (identity + qty Decimal) · `ExecutionEventStore` protocol.
   - `InMemoryExecutionEventStore` (refleja la idempotencia).
   - `PostgresExecutionEventStore` con **`ON CONFLICT (execution_id) DO NOTHING ... RETURNING`** =
     inserted vs duplicate SIN carrera entre workers.
   - `apply_fill_idempotent(...)` = captura idempotente y, solo si `permit=True` y hay `apply_finance`
     efectivo, aplica. **Default `permit=False`**: la captura persiste pero **NO materializa**
     Position/Ledger (honestidad H4: no hay auto-heal; se requiere go autorizante).
5. **Tests** `packages/py/application/tests/test_execution_event.py` (5) — duplicate no re-aplica ·
   permit=False nunca materializa (aunque haya applier) · applier False devuelve captured_not_applied ·
   sin applier fail-closed · exige execution_id. + guard offline en `test_live_order_store_pg.py` del 022.

## Verificación E1

- ruff 0 (módulos+tests+022). mypy execution_event 0.
- pytest `test_execution_event`+`test_live_order_store_pg` → **32 passed** (5 nuevos).
- NOTA honesta (DB real): el upgrade `alembic upgrade head` (aplica 022) **NO** se ejecutó sobre el PG
  compartido del dev en esta faena (mutación de estado requería go explícito). La DB local permanece en
  `021_live_orders_fin`; `PostgresExecutionEventStore` queda DDL-list o y su aplicación real+MigrApp para
  rows legacy se certifica en **C1** (protocolo del repo: real-PG en C1). InMemory cubre la semántica hoy.

## Archivos E1

MOD (4): `022_live_orders_exec.py` (nuevo), `tables.py`, `test_live_order_store_pg.py`,
`test_lifecycle_event_store_pg.py` (guards head). NUEVO (3): `execution_event.py`, `test_execution_event.py`,
este traspaso. ÍNDICE: #94.

## Remanente E1 honesto

- Conectar `apply_finance` al kernel Decimal (`ExecuteTrade`/`append_*`/`sync_position_after_ledger_fill`)
  **SOLO tras** evidence de migration 022 + un caper go/incidente (C1 + Shadow). No cableado abierto.
- `execution_id` derivado de venue_order_id+fill_seq → aún no hay columna fill_seq real en `XtbBridgeOrderState`
  (el venue no la envía; hoy seq = ordinal del poll). Documentado: seq por-orden en una capa posterior o,
  si el venue indica `fills[]`, identity exacta del fill.

FIN DE TRASPASO E1
