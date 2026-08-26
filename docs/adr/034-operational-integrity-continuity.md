# ADR-034: Operational Integrity — continuidad post-fill (contrato v1.11 OI-1)

**Estado:** Accepted — **OI-1+OI-2+OI-3+OI-4+OI-5+OI-6 + PaperBroker + BrokerAdapter + PH-1 + XL-1 + LR-1 + XL-2 + VS-1 + RV-1 + JP-1 + thaw stamp + PA-1 + OE-1 CERRADOS**  
**Fecha:** 2026-08-26  
**Contexto:** Auditorías post-`v1.10-beta`: el camino Confirm→fill→PositionState está gobernado, pero OrderDialog, pending SELL, Confirm post-fill, Lab executeTrades y Proteger no alineaban ledger y Position persistida.

**Depende de:** [ADR-033](./033-operational-authority-position-persistence.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · plan [`plan-oi1-continuity-2026-08-26.md`](../engineering/plan-oi1-continuity-2026-08-26.md).

---

## 1. Decisión

**Un post-fill, varios orígenes.** Tras cualquier fill paper que mueva el ledger, el producto actualiza PositionState cuando corresponde. Sin OrderIntent-dios. Sin Alembic nuevo en OI-1.

| Origen                                      | Nacimiento / mutación        | Override       |
| ------------------------------------------- | ---------------------------- | -------------- |
| IA SEMI (TradePlan TRIGGERED)               | `PersistPositionFromFill`    | —              |
| Manual HTTP / pending sin plan              | `PersistPositionFromFill`    | `human_manual` |
| Cierre (SEMI, pending SELL, Lab si ejecuta) | `PersistPositionFromExit`    | —              |
| Proteger (Confirm)                          | `PersistPositionFromProtect` | H2 stop        |

Origen manual en snapshot: `origin: HUMAN_MANUAL`. Stop operativo persistido **≠** orden stop de broker.

---

## 2. Caminos cableados (OI-1)

```text
POST /portfolio/trade  → sync_position_after_ledger_fill
FillPendingOrder       → sync_position_after_ledger_fill
Confirm execute        → fill/exit persist (honest si falla post-fill)
Confirm protect        → apply_position_current_stop (cero ledger)
Lab executeTrades      → PersistPositionFromExit si trade_executed (Lab ≠ mesa)
```

**Confirm no miente:** si `execute_trade` OK y persist/journal falla → `trade.status=executed` + `positionPersist.error`.

**Clasificación D2:** por fila OPEN + lado del fill. Add-on y sell huérfano → ledger sí, PositionState no (OI-1).

---

## 3. OI-2 (cerrado)

**Risk signature honesty.** Apertura SEMI (`recommend_long`/`recommend_short`) exige TradePlan **TRIGGERED** vía `require_triggered_plan`. Sin plan → `blockReason=no_tradeplan`, Confirm no ejecuta. Manual HTTP no usa `risk_signature`.

Implementación: `risk_signature.py` · `risk-signature.ts` · `confirm_recommendation.py` · UI F3.

---

## 4. OI-3 (cerrado)

**ExecutionRecord.** Outcome `not_executed` | `executed` | `error` | `unknown`. Confirm llama a `execute_trade` y revienta → `unknown` (nunca `error`, nunca `intent.status=rejected_by_gate`). ERROR solo si el envío no se intentó. Fill OK + persist falla → `executed` (OI-1). `ExecutionPlan` (F4) = cómo se enviaría; `ExecutionRecord` = qué pasó.

Implementación: `execution_record.py` · `execution-record.ts` · `confirm_recommendation.py`.

## 5. OI-4 (cerrado)

**PaperOrder.** Ciclo paper `CREATED` → `FILLED`. Venue `PAPER`. Confirm/FillPending adjuntan `paperOrder`. Gate/skip → no hay orden. Excepción de `execute_trade` → `CREATED` (fill no confirmado; OI-3 `unknown` intacto). CREATED ≠ FILLED. ≠ Intent ≠ ExecutionPlan ≠ ExecutionRecord ≠ broker. Sin Alembic.

Implementación: `paper_order.py` · `paper-order.ts` · `confirm_recommendation.py` · `fill_pending_order.py`.

## 6. OI-5 (cerrado)

**PositionRevision.** Historia append-only de cambios de `currentStop` y transiciones de status relevantes en `PositionState.revisions[]`. `applyCurrentStop` / `applyReduce` append cuando hay cambio real. Confirm protect / `PersistPositionFromProtect` → `origin=protect`. Exit persist → `origin=reduce`. Mark no revisa. `initialStop` ≠ revisión. Sin Alembic · JSON en snapshot.

Implementación: `position_revision.py` · `position-revision.ts` · `position_state.py` / `position-state.ts` · `persist_position_from_protect.py` · `persist_position_from_exit.py`.

## 7. OI-6 (cerrado)

**PortfolioReconciliation.** Informe ephemeral detect/report: cash ↔ Σ ledger, holdings qty ↔ OPEN `remainingQuantity`, OPEN sin holding, holding sin OPEN (`expected`), `open_transaction_id` link. Add-on OI-1 → `expected`. Top-level `clean` | `drift`. **No** auto-heal · **no** Alembic · **no** broker · ≠ ADR-021.

Implementación: `portfolio_reconciliation.py` · `portfolio-reconciliation.ts` · `reconcile_portfolio_integrity.py`.

## 8. PaperBroker (cerrado)

**PaperBroker.** Capa venue **PAPER** antes de `BrokerAdapter` / live. `PaperBroker.submit` nace `PaperOrder` CREATED → ledger `execute_trade` → FILLED (o CREATED + `unknown` si excepción). Confirm / FillPending adjuntan `paperOrder` + `paperBroker` receipt (`venue: PAPER`, `adapter: paper_broker`). ≠ broker live · ≠ thaw `PAPER_D_EXECUTE`.

Implementación: `paper_broker.py` (analytics receipt + application submit) · `paper-broker.ts`.

## 9. BrokerAdapter (cerrado — mock, no live)

**IBrokerAdapter.** Puerto EXECUTION Paper | Live. Mesa Confirm / FillPending envían por el puerto (default `PaperBrokerAdapter` → PaperBroker). `MockBrokerAdapter` ocupa el slot LIVE de prueba: `fillStatus=not_wired`, **nunca** llama `execute_trade`. **XL-1** `XtbBrokerAdapter` = LIVE vía bridge (`adapter: xtb`); `rejected`/`submitted` ≠ fill ledger. Receipt `brokerAdapter` (`venue: PAPER|LIVE`, `adapter: paper_broker|mock|xtb`). Gate/skip → sin receipt.

Implementación: `broker_adapter.py` (analytics receipt + application Protocol / paper / mock / xtb) · `broker-adapter.ts`.

## 10. PH-1 Confirm protect honesty (cerrado)

**Proteger no miente.** `persist` → `None` (H2 empeora sin override) o excepción → `trade.status=skipped` (`stop_not_applied` | `persist_error`). **No** `protect_applied`. **No** journal `protect_applied`. Intent no `executed`. UI Confirm no saca de cola. Cero ledger: el éxito es persistir el stop.

Implementación: `confirm_recommendation.py` · `protect-persist-honesty.ts`.

## 11. XL-1 Broker live XTB (cerrado — adapter; submitted ≠ fill)

**XtbBrokerAdapter.** `venue: LIVE`, `adapter: xtb`. POST bridge `/orders`. Sin URL → `not_wired`. Mock bridge fail-closed `live_orders_disabled`. `submitted` ≠ fill. Confirm/FillPending: rejected→skipped; submitted→unknown `live_submitted_no_fill`; pending intacta. Mesa default paper. Mock `not_wired` intacto.

Implementación: `broker_adapter.py` (Xtb) · `providers.py` `submit_order` · `xtb-bridge-mock.mjs` POST `/orders`.

## 12. LR-1 Live reconciliation (cerrado — detect/report)

**LiveLedgerReconciliation.** Venue LIVE cash/positions ↔ ledger cash/holdings. Status `clean` \| `drift` \| `unavailable` (sin bridge → fail-closed). Checks: `live_cash_vs_ledger` · `live_qty_vs_holding` · `live_without_holding` · `holding_without_live`. **No** auto-heal · **no** `execute_trade` · **no** `submit_order`. ≠ OI-6 (capas paper internas).

Implementación: `live_ledger_reconciliation.py` · `reconcile_live_ledger.py` · bridge `GET /account/cash` · `/account/positions`.

## 13. XL-2 XTB fill → ledger (cerrado — money path)

Bridge puede devolver `filled` (opt-in `XTB_BRIDGE_FILL_ORDERS=1` + ALLOW). Solo `filled` → `execute_trade` → Confirm/FillPending `executed`. `submitted` sigue ≠ fill. Sin execute wired / boom → `unknown` (OI-3). Mock default fail-closed.

Implementación: `XtbBrokerAdapter(execute_trade=…)` · providers status `filled` · mock FILL flag.

## 14. VS-1 Venue selector (cerrado — Paper | Live)

`BROKER_VENUE` + runtime memory. DI Confirm/FillPending vía `resolve_broker_adapter`. Mesa toggle Paper \| Live. Live → Xtb (sin URL → `not_wired`). Default paper. API `GET/POST /api/risk/broker-venue`. **No** thaw `PAPER_D_EXECUTE`.

## 15. Fuera (parked) / stamps posteriores

- **RV-1** Redis venue global — **CERRADO** (key `bolsa:risk:broker_venue`; coalesce memory ?? redis ?? env ?? paper).
- **PA-1** Per-account venue — **CERRADO** (`settings_json.brokerVenue`; coalesce memory ?? redis ?? account ?? env ?? paper; lazy Confirm/Fill; `GET/PATCH /accounts/{id}/broker-venue`). Mesa/API risk = override **global**. ≠ thaw.
- **JP-1** columnas hot `position_states` (Alembic `012`, dual-write; JSONB SoT) — **CERRADO**.
- **Thaw stamp** `PAPER_D_EXECUTE` — **CERRADO (docs/ops)** · DEMO opt-in autorizado · repo default **OFF** · ≠ thaw estricto P1–P5.
- **OE-1** Ops Autoeval — **CERRADO** (`GET /api/risk/ops-self-eval` + `scripts/ops_operativa_self_eval.mjs` + chip mesa); measure ≠ Accept; OI-6 en informe `not_wired`.
- Parked aún: Redis per-account cache · typed `AccountSettings.brokerVenue` · Accept estricto · default-on (palabra owner) · UI preferencia cuenta · wire OI-6 en ops-self-eval.

---

## 16. Freeze

ADR-033 intacto · Confirm = única firma transaccional de mesa · Lab no fusionado con ExitPlan · H2 factories sin campos extra · I1–I3 + RX1 · `PAPER_D_EXECUTE` off · mesa default paper.

---

## 17. Consecuencias

- Implementación: [`post_fill_position_sync.py`](../../packages/py/application/src/bolsa_application/post_fill_position_sync.py) · [`persist_position_from_protect.py`](../../packages/py/application/src/bolsa_application/persist_position_from_protect.py) · [`execution_record.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/execution_record.py) · [`paper_order.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/paper_order.py) · [`position_revision.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/position_revision.py) · [`portfolio_reconciliation.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_reconciliation.py) · [`live_ledger_reconciliation.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/live_ledger_reconciliation.py) · [`paper_broker.py`](../../packages/py/application/src/bolsa_application/paper_broker.py) · [`broker_adapter.py`](../../packages/py/application/src/bolsa_application/broker_adapter.py) · [`broker_venue_runtime.py`](../../packages/py/application/src/bolsa_application/broker_venue_runtime.py) · [`reconcile_live_ledger.py`](../../packages/py/application/src/bolsa_application/reconcile_live_ledger.py) · [`confirm_recommendation.py`](../../packages/py/application/src/bolsa_application/confirm_recommendation.py).
- Spine: OI-1…OI-6 + PaperBroker + BrokerAdapter + PH-1 + XL-1 + LR-1 + XL-2 + VS-1 + RV-1 + PA-1 + OE-1 (**367** `test:decision-spine`).
- Siguiente: **v1.12 Operational Reliability** (ADR-035 · OR-1…OR-6 **CERRADOS**) · pack + tag `v1.12-beta` (chat aparte) · thaw **estricto** P1–P5 (deuda). Tag **`v1.11-beta` → `76d0f951`** (cerrado).
