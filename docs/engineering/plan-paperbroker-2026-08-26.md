# Plan — PaperBroker (venue paper antes de BrokerAdapter)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 §8 · relevo [`traspaso-relevo-oi6-reconciliation-2026-08-26.md`](./traspaso-relevo-oi6-reconciliation-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** OI-6 cerrado.

---

## Objetivo

Existe una **capa PaperBroker** que envía a venue **PAPER**: nace `PaperOrder` CREATED → ledger fill → FILLED (o CREATED si excepción). Confirm / FillPending no llaman `execute_trade` a pelo; pasan por PaperBroker.

≠ `IBrokerAdapter` / BrokerAdapter live · ≠ thaw `PAPER_D_EXECUTE` · ≠ broker live.

`PaperOrder` = ciclo. `ExecutionRecord` = honestidad del intento. `PaperBroker` = venue paper que orquesta ambos alrededor del ledger. `ExecutionPlan` (F4) = cómo se enviaría (sigue sin wire).

## Decisiones

| ID  | Decisión                                                                                                                     |
| --- | ---------------------------------------------------------------------------------------------------------------------------- |
| D1  | Objeto `PaperBrokerReceipt` (TS + Py) + use-case `PaperBroker.submit` (application).                                         |
| D2  | `venue` siempre `PAPER`; `adapter` = `paper_broker`. **No** live.                                                            |
| D3  | `submit` crea CREATED → llama `execute_trade` → FILLED si fill; excepción → CREATED + status `unknown` (OI-3/OI-4 intactos). |
| D4  | Confirm y FillPending usan `PaperBroker`; adjuntan `paperOrder` + `paperBroker` receipt.                                     |
| D5  | Gate/skip **antes** de submit → sin `paperOrder` / sin `paperBroker` (igual OI-4).                                           |
| D6  | Sin `IBrokerAdapter` · sin live · sin Alembic · sin `contract:gen`.                                                          |
| D7  | Tests kernel + Confirm + FillPending + spine. HELP honesty.                                                                  |
| D8  | Edge Confirm `protect_applied` si persist→None **parked**. **No** broker live en este chat.                                  |

## Kernel

```text
build_receipt(order, fill_status) → { venue:PAPER, adapter:paper_broker, paperOrder, fillStatus }
submit:
  CREATED → execute_trade
  OK      → FILLED + executed
  boom    → CREATED + unknown
```

## Ficheros

- `packages/shared/src/cognitive/paper-broker.ts` · test
- `packages/py/analytics/.../paper_broker.py` · `tests/test_paper_broker_receipt.py`
- `packages/py/application/.../paper_broker.py` · test
- `confirm_recommendation.py` · `fill_pending_order.py`
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP · CHANGELOG · relevo

## Freeze

ADR-033 · Confirm = firma · OI-1…OI-6 · `PAPER_D_EXECUTE` off · broker live no · Lab ≠ mesa · thin 5.x/8.x congelados.

## E1

BrokerAdapter (interfaz Paper\|Live) **o** edge Confirm protect honesty. **No** broker live en el mismo chat que PaperBroker (ya cerrado aquí).
