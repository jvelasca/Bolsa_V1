# Plan — OI-4 Order lifecycle paper (CREATED→FILLED)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** [`traspaso-relevo-oi3-execution-record-2026-08-26.md`](./traspaso-relevo-oi3-execution-record-2026-08-26.md).

---

## Objetivo

La ejecución paper no salta de Intent a ledger. Existe un **PaperOrder** con ciclo **CREATED → FILLED** antes de broker. CREATED ≠ FILLED: orden creada no es fill.

`OrderIntent` = voluntad. `ExecutionPlan` (F4) = cómo se enviaría. `ExecutionRecord` (OI-3) = qué pasó al intentar. `PaperOrder` = la orden paper en ciclo. `pending_orders` = cola a precio (no se promociona a tabla OMS).

## Decisiones

| ID  | Decisión                                                                                                                  |
| --- | ------------------------------------------------------------------------------------------------------------------------- |
| D1  | Objeto nuevo `PaperOrder` (TS + Py). ≠ Intent ≠ ExecutionPlan ≠ ExecutionRecord ≠ broker.                                 |
| D2  | `status`: `CREATED` \| `FILLED`. Sin PARTIAL / ACKED / CANCELLED / broker SUBMITTED.                                      |
| D3  | `venue` siempre `PAPER` en OI-4.                                                                                          |
| D4  | Gate/skip **antes** de enviar → no hay `paperOrder` (no se creó).                                                         |
| D5  | `execute_trade` lanza → `CREATED` (fill no confirmado). Nunca `FILLED`. OI-3 `unknown` intacto.                           |
| D6  | Fill OK → `FILLED` (OI-1: persist fail no pisa el fill).                                                                  |
| D7  | Confirm y FillPending adjuntan `paperOrder`. Sin Alembic · sin `contract:gen`. HTTP gated no cambia el DTO `TradeResult`. |
| D8  | Tests factory + Confirm + FillPending. **No** broker · **No** OI-5/OI-6 · **No** reconciliación.                          |

## Kernel

```text
build                         → CREATED (transactionId null)
apply_fill(CREATED, tx)       → FILLED
FILLED no vuelve a CREATED
gate/skip                     → sin PaperOrder
send + excepción              → CREATED
```

## Ficheros

- `packages/shared/src/cognitive/paper-order.ts` · `paper-order.test.ts`
- `packages/py/analytics/.../paper_order.py` · `tests/test_paper_order.py`
- `confirm_recommendation.py` — crear CREATED al enviar; FILLED si fill
- `fill_pending_order.py` — fill → FILLED (`orderId` = pending id)
- `supervised-f3-panel.tsx` · HELP Hoy CREATED ≠ FILLED
- Tests: `test_confirm_paper_order.py` · FillPending · spine battery

## Freeze (intactos)

ADR-033 · Confirm = única firma · OI-1/OI-2/OI-3 · `PAPER_D_EXECUTE` off · broker no · Lab ≠ mesa · thin 5.x/8.x congelados · pending ≠ stop (H1).

## E1

OI-5 Position revisions **o** operar SEMI (TRIGGERED → Confirm → protect). **No** broker en el mismo chat.
