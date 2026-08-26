# Plan — OI-3 ExecutionRecord (UNKNOWN ≠ ERROR)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** [`traspaso-relevo-oi2-risk-signature-2026-08-26.md`](./traspaso-relevo-oi2-risk-signature-2026-08-26.md).

---

## Objetivo

Nunca confundir **excepción** con **no-ejecutado**. Si Confirm llama a `execute_trade` y revienta, el resultado es **UNKNOWN** (el ledger puede haberse escrito). **ERROR** solo si el envío no se intentó.

`ExecutionPlan` (F4) = cómo se enviaría. `ExecutionRecord` = qué pasó al intentar.

## Decisiones

| ID  | Decisión                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------ |
| D1  | Objeto nuevo `ExecutionRecord` (TS + Py). ≠ ExecutionPlan ≠ ExecuteTrade ≠ broker.                     |
| D2  | `outcome`: `not_executed` \| `executed` \| `error` \| `unknown`.                                       |
| D3  | `execute_trade` lanza → `unknown`. Nunca `error`. Nunca `intent.status=rejected_by_gate`.              |
| D4  | Gate/skip **antes** de enviar → `not_executed` (`rejected_by_gate` / `skipped` intactos).              |
| D5  | Fill OK + persist/journal falla → `executed` (OI-1 intacto). `filled` gana a `exception`.              |
| D6  | ERROR = fallo **pre-send** (no se llamó a `execute_trade`).                                            |
| D7  | Confirm adjunta `executionRecord`. UI copy explícita para `unknown`. Sin Alembic · sin `contract:gen`. |
| D8  | Tests factory + Confirm. **No** broker · **No** OI-4 · **No** reconciliación.                          |

## Kernel de honestidad

```text
filled                 → executed
send_attempted + !fill → unknown     (excepción o silencio)
!send + exception      → error
!send + gate/skip      → not_executed
```

## Ficheros

- `packages/shared/src/cognitive/execution-record.ts` · `execution-record.test.ts`
- `packages/py/analytics/.../execution_record.py` · `tests/test_execution_record.py`
- `confirm_recommendation.py` — split try; `trade.status=unknown`
- `supervised-f3-panel.tsx` · HELP Hoy
- Tests: `test_confirm_execution_record.py` · spine battery

## Freeze (intactos)

ADR-033 · Confirm = única firma · OI-1/OI-2 · `PAPER_D_EXECUTE` off · broker no · Lab ≠ mesa · thin 5.x/8.x congelados.

## E1

OI-4 Order lifecycle paper **o** operar SEMI (TRIGGERED → Confirm → protect).
