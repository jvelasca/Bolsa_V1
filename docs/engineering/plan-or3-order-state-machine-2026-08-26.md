# Plan — OR-3 Full order state machine

> **Padre:** [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs). Spine **387**.
> **Relevo:** [`traspaso-relevo-or3-order-state-machine-2026-08-26.md`](./traspaso-relevo-or3-order-state-machine-2026-08-26.md).

---

## Objetivo

Ampliar `PaperOrderStatus` más allá de `CREATED`/`FILLED` hacia el ciclo del auditor:

```text
CREATED → SUBMITTED → ACK → PARTIAL → FILLED
                 ↘ REJECTED | CANCELLED | EXPIRED | UNKNOWN
```

OI-4 **no se reabre**: nacimiento sigue `CREATED`; `CREATED≠FILLED` se conserva. OR-3 añade estados y transiciones legales.

## Decisiones

| ID  | Decisión                                                                                                                                                                            |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Status = `CREATED \| SUBMITTED \| ACK \| PARTIAL \| FILLED \| REJECTED \| CANCELLED \| EXPIRED \| UNKNOWN`. Nacimiento = `CREATED` (OI-4).                                          |
| D2  | Grafo explícito (`ALLOWED_TRANSITIONS`). Terminales: `FILLED`, `REJECTED`, `CANCELLED`, `EXPIRED`. `UNKNOWN` resoluble → `ACK`/`PARTIAL`/`FILLED`/`REJECTED`/`CANCELLED`/`EXPIRED`. |
| D3  | `apply_paper_order_fill` sigue: desde cualquier no-terminal abierto → `FILLED` (idempotente). Atajo paper OK; no fuerza PARTIAL.                                                    |
| D4  | `transition_paper_order(order, to)` aplica el grafo; ilegal → no muta / error de dominio en tests. Campo opcional `filled_quantity` para `PARTIAL`.                                 |
| D5  | **PaperBroker:** `CREATED` → `SUBMITTED` pre-`execute_trade` → fill → `FILLED`; excepción → `UNKNOWN` (no deja `CREATED` como si no se hubiera enviado).                            |
| D6  | **OR-2 crash recovery:** `paperOrder.status = UNKNOWN` (antes `CREATED`). Misma identidad `order_id`/`intent_id`.                                                                   |
| D7  | Copy de mesa por estado. Espejo TS. Sin Alembic · sin `contract:gen` · sin OCO · sin broker producción · sin OR-4/OR-5/OR-6.                                                        |
| D8  | Tests unidad (grafo + PaperBroker + recovery) + spine. Live `submitted≠fill` intacto (XL-1).                                                                                        |

## Kernel

```text
build                    → CREATED
mark submitted           → SUBMITTED
ack                      → ACK
partial(qty)             → PARTIAL (+ filled_quantity)
fill / apply_fill        → FILLED
reject | cancel | expire → terminal
crash / boom post-send   → UNKNOWN
UNKNOWN + verdad         → ACK | PARTIAL | FILLED | REJECTED | CANCELLED | EXPIRED
```

## Ficheros

- [`paper_order.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/paper_order.py) + espejo TS
- [`paper_broker.py`](../../packages/py/application/src/bolsa_application/paper_broker.py)
- [`confirm_recommendation.py`](../../packages/py/application/src/bolsa_application/confirm_recommendation.py) (recovery UNKNOWN)
- Tests: `test_paper_order.py` · `paper-order.test.ts` · `test_paper_broker.py` · `test_confirm_crash_restart.py`
- Spine: `pnpm test:decision-spine`

## DoD

- [x] Literal + grafo + copy PY/TS.
- [x] PaperBroker: SUBMITTED pre-send · FILLED ok · UNKNOWN boom.
- [x] Crash recovery: `paperOrder.status == UNKNOWN`.
- [x] `CREATED→FILLED` direct (OI-4) y FILLED idempotente intactos.
- [x] Sin Alembic · sin `contract:gen` · sin OR-4/5/6 · sin OCO.
- [x] Docs: CURRENT_SYSTEM / ADR-035 / CHANGELOG / roadmap / relevo OR-3.

## Freeze (intactos)

ADR-034 · Confirm = única firma · `PAPER_D_EXECUTE` off · no broker producción · no veto recon (OR-4) · thin 5.x/8.x congelados · Lab ≠ mesa · DurableSubmitIntent fases OR-2 intactas.

## E1

Tras OR-3: **OR-4** recon → opening veto **o** operar SEMI. **No** suite A–L (OR-5) ni CTA LIVE (OR-6) en el mismo chat.
