# Plan — OR-1 End-to-end idempotency (retry Confirm paper)

> **Padre:** [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs). Spine **372**.
> **Relevo:** [`traspaso-relevo-or1-e2e-idempotency-2026-08-26.md`](./traspaso-relevo-or1-e2e-idempotency-2026-08-26.md).

---

## Objetivo

El escenario de reintento del auditor, en **paper**:

```text
Confirm → PaperBroker ejecuta → timeout de red → cliente reintenta Confirm
→ 1 order identity + 1 execution + 1 position
nunca 2 fills
```

Hoy el ledger **ya** es idempotente por `decision_id` (`ExecuteTrade` UNIQUE + `find_transaction_by_idempotency`). El agujero era la **identidad de intento**: Confirm reentraba `adapter.submit`, `intent_id` era `uuid4` por llamada, fallback `confirm-{uuid4}` si faltaba `decision_id`, PaperOrder nacía con un `ORD-…` nuevo, ExecutionRecord era efímero.

## Decisiones

| ID  | Decisión                                                                                                                                                                                              |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Clave canónica de intento = `decision_id` (ya es `idempotency_key` del ledger). **Sin** fallback `confirm-{uuid4}`. Sin `decision_id` → fail-closed (`error` / `decision_id_required`).               |
| D2  | `intent_id` **estable** derivado de `decision_id` (`INT-{slug}`).                                                                                                                                     |
| D3  | `PaperOrder.order_id` **estable** derivado de la misma clave (`ORD-{slug}`).                                                                                                                          |
| D4  | **Short-circuit Confirm** _antes_ de `adapter.submit`: si `find_existing_by_idempotency` ya tiene fill → devolver el mismo trade / posición / ExecutionRecord `executed` **sin** reenviar al adapter. |
| D5  | Confirm concurrente existente (`test_confirm_double_execute_concurrent_single_logical_fill`) se **mantiene**. Ampliar a retry **secuencial** post-fill.                                               |
| D6  | LIVE en OR-1: short-circuit solo con fill local. Sin fill → `unknown` (OI-3). Mapeo durable `intent ↔ venue_order_id` = **OR-2**. **No** Alembic.                                                     |
| D7  | Tests en spine: retry post-fill; missing `decision_id`; identidad estable; journal no duplica fill. Sin `contract:gen`.                                                                               |

## Kernel

```text
decision_id ausente              → error pre-send (no orden)
fill ya existe para decision_id  → replay (no adapter.submit)
primer envío paper               → adapter.submit como hoy
retry mismo decision_id          → mismos intent_id + order_id + transaction_id
LIVE sin fill local              → unknown (OI-3); mapeo durable = OR-2
```

## Ficheros

- [`confirm_recommendation.py`](../../packages/py/application/src/bolsa_application/confirm_recommendation.py) — clave sin uuid4; short-circuit pre-submit
- [`accounts/trade.py`](../../packages/py/application/src/bolsa_application/accounts/trade.py) — `find_existing_by_idempotency`
- [`order_intent.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/order_intent.py) + espejo TS — `intent_id` estable
- [`paper_order.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/paper_order.py) + espejo TS — `order_id` estable
- Tests: [`test_execute_trade_idempotency.py`](../../packages/py/application/tests/test_execute_trade_idempotency.py) (OR-1 + concurrente)
- Spine: `pnpm test:decision-spine` **372**

## DoD

- [x] Retry Confirm paper post-fill → 1 transacción, mismos `intent_id` y `order_id`.
- [x] Confirm **no** llama `adapter.submit` / `execute_trade` en el replay.
- [x] Sin `decision_id` → no se envía (fail-closed).
- [x] Concurrente existente sigue verde.
- [x] Journal no duplica el fill en retry.
- [x] LIVE: short-circuit solo con fill local; `unknown` si no hay fill (OI-3 intacto).
- [x] Sin Alembic · sin `contract:gen` · OI-3/OI-4 outcomes intactos.
- [x] Docs: stamp CURRENT_SYSTEM / ADR-035 / CHANGELOG Unreleased · relevo OR-1.

## Freeze (intactos)

ADR-034 · Confirm = única firma · `PAPER_D_EXECUTE` off · no broker producción · no OR-3 machine · no veto recon (OR-4) · thin 5.x/8.x congelados · Lab ≠ mesa.

## E1

Tras OR-1: **OR-2** crash/restart **o** operar SEMI (TRIGGERED → Confirm → retry). **No** OR-3/OR-4 en el mismo chat.
