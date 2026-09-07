# V2.14 — Financial Execution & Full Reconciliation (plan + decreto de numeración)

**AsOf:** 2026-09-07 · **Padre:** [engineering-index](./engineering-index-2026-08-03.md) · [vertido auditor V2.13](./audit-ext-v2-13-execution-core-honesty-2026-09-07.md) · [roadmap LIVE core](./roadmap-live-execution-core-2026-09-07.md)
**Rama:** `v2-13-1-rc-honesty-remediation` (base de partida; esta faena puede abrir `v2-14-financial-execution-*`)

> Base real de audit: tip formal V2.13 `da5c4b2a` (package `1.42.0-beta`) → HEAD actual `08cada82`
> (veredicto auditor + adendo N-1..N-4 + deuda P2/P3 ya registrada en `deuda-anotada-audit-v2-13-ampliado`).

---

## 0. Decreto de numeración (corrige colisión V2.14)

El repo tenía DOS etiquetas V2.14 divergentes: `roadmap-live-execution-core` decía **V2.14 = Shadow LIVE**;
`traspaso-relevo-v2-1-operator-journey-...` usaba **V2.14 = Gráfico operativo** (track UI). Se sella:

| Versión   | Significado                                                                                                                  |
| --------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **V2.13** | Fallo tip formal `da5c4b2a` (cerrado, audit sin P0/P1)                                                                       |
| **V2.14** | **Financial Execution & Full Reconciliation** (pipeline del auditor: fill → ExecutionEvent → Position → Ledger → Full Recon) |
| **V2.15** | Shadow LIVE (consultar, no enviar)                                                                                           |
| **V2.16** | LIVE Certification (evidencia Release-tag CI `conclusion=success`)                                                           |

Se actualiza la tabla de `roadmap-live-execution-core` (§2) para reflejar esta numeración y se registra la
colisión en la entrada de índice #89. V2.13 (formal tip `da5c4b2a`) **sigue SIN certificar GREEN** mientras
GitHub no devuelva `statuses: [...] conclusion=success` — deuda honesta de certificación (C1).

---

## 1. Propósito

Convertir V2.13 —excelente máquina de órdenes `LiveOrder`, pero **NO** Financial Execution Engine
(fill → ledger PARKED en la rama LIVE; solo existe completo en PAPER)— en **V2.14 = motor de ejecución
financiera + reconciliación completa**, preservando las defensas honestas de V2.13:

1. Decimal en el **boundary financiero** (hogar único de verdad, DB + dominio) y float solo para DTO/UI.
2. **Idempotencia financiera real por fill** (`execution_id`), no solo un contador `financial_apply_count`.
3. **Reconciliación de la máquina viva** frente a broker truth (orders/fills/cash/positions/exposure),
   con incidencia durable (OperationalIncident) y gate OR-4 de DENY mientras hay drift.
4. Observabilidad del recovery worker (lease configurable + `attempt_count/last_error/claim_expires_at`).
5. Cancelación XTB real round-trip (confirmación broker-side) cuando el venue lo permita; honestamente PARKED si no.
6. **Certificación** contra PostgreSQL real (migración 021→legacy data→022→multi-worker→recon) + Release-tag CI.

> Principio de honestidad mantenido: **no** afirmar CI GREEN sin evidencia observada de GitHub Actions;
> **no** auto-heal de drift financiero (verificar-then-operator/machine-go), nunca síntesis ciega fill→ledger.

---

## 2. Faenas (cada una = rama/commit propio + tests + handover + entrada índice)

Tabla y flujo: ver sección "Dependency flow" del plan aprobado (en `~/.cursor/plans/v2.14_...plan.md`)
y su decantación a `traspaso-relevo-d0-v2-14-foundation` / faenas. Resumen de arquitectura objetivo:

```
            Decision Spine → Authorization → Execution Router → XTB Adapter
                                              submit ──┬── submitted ─────→ UNKNOWN
                                                       └── broker truth     ↓ query broker
                                                  FILL ←────────────────────┘
                                                    ↓
                                            ExecutionEvent  (idempotency/execution_id)
                                                    ↓
                                        ┌────────────┴────────────┐
                                   PositionState              Ledger
                                        └────────────┬────────────┘
                                                     ↓
                                             Operating Truth
                                                     ↓
                                        Full Reconciliation
                                        Account/Position/Order/Fills
                                                     ↓
                                            OperationalIncident (durable)
```

---

## 3. Áreas de código a tocar (localización real HEAD `08cada82`)

- **Dominio/máquina:** `packages/py/analytics/src/bolsa_analytics/cognitive/live_order.py` (Decimal qty,
  FSM, contador `financial_apply_count` → a sustituir por idempotencia por fill). Espejo TS
  `packages/shared/src/cognitive/live-order.ts`.
- **Reconcile máquina (H7):** `packages/py/application/src/bolsa_application/live_order_machine_reconcile.py`
  (`LiveOrderDrift` hoy con `float` qty; a durar a `OperationalIncident`).
- **Boundary float / XTB:** `packages/py/market/src/bolsa_market/providers.py`
  (`XtbBridgeOrderState.filled/remaining`, `XtbBridgeAccountCash.cash`, `XtbBridgePosition.quantity` = float);
  `packages/py/application/src/bolsa_application/live_order_query.py` (`BrokerOrderQueryResult` con
  `.filled/remaining` float); adapter de query `XtbLiveOrderQueryAdapter` en `broker_adapter.py`.
- **Recovery worker / lease:** `apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py`
  (`DEFAULT_CLAIM_STALE_SECONDS=120` hardcoded; `recovery_worker_id/recovery_claimed_at` en 021).
- **Migraciones:** `packages/py/infrastructure/alembic/versions/` head `021_live_orders_fin`
  (quantity → NUMERIC(18,6) + CHECK `filled+remaining=quantity`). Siguiente `022_*` para ExecutionEvent + observabilidad.
- **PAPER path (kernel financiero de referencia):** `packages/py/application/src/bolsa_application/accounts/trade.py`
  (`ExecuteTrade` Decimal → `execute_trade` → `append_trade/append_fee`) y `confirm/position_sync.py`
  (`sync_after_fill`/`sync_position_after_ledger_fill`).
- **Store PG claim:** `packages/py/application/src/bolsa_application/live_order_store.py`
  (intersección `claim_unknown_batch` `FOR UPDATE SKIP LOCKED`, lineas 555-599).
- **Docs/thaw:** la deuda de **certificación CI e idempotencia** queda anotada en `deuda-anotada-v2-14-*`.

---

## 4. Estado

**PARTIAL** · D0 foundation (esta faena) en curso · B1..C1 según ramas listadas al inicio.
Frontera de certificación honesta: **no** afirmar "Release-tag CI = GREEN" para V2.14 sin observarse
`conclusion=success` en GitHub Actions (mismo criterio que ya fijó V2.10.1).
