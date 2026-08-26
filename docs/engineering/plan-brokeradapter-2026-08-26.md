# Plan — BrokerAdapter (puerto Paper | Live; mock)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 §9 · relevo [`traspaso-relevo-paperbroker-2026-08-26.md`](./traspaso-relevo-paperbroker-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** PaperBroker cerrado.

---

## Objetivo

Existe un **puerto `IBrokerAdapter`** (Paper | Live). La mesa Confirm / FillPending envían por el puerto, no por `PaperBroker` a pelo. Implementación **paper** = `PaperBrokerAdapter` (delega en PaperBroker). Implementación **live** en este chat = **mock** (`not_wired`, cero envío).

≠ broker live / XTB · ≠ thaw `PAPER_D_EXECUTE` · ≠ ExecutionPlan wire · PaperBroker intacto.

`PaperOrder` = ciclo. `ExecutionRecord` = honestidad del intento. `PaperBroker` = venue paper. `IBrokerAdapter` = puerto Paper|Live. Mock ≠ live.

## Decisiones

| ID  | Decisión                                                                                                    |
| --- | ----------------------------------------------------------------------------------------------------------- |
| D1  | Objeto `BrokerAdapterReceipt` (TS + Py) + Protocol `IBrokerAdapter.submit`.                                 |
| D2  | `venue`: `PAPER` \| `LIVE`. `adapter`: `paper_broker` \| `mock`. **No** live real.                          |
| D3  | `PaperBrokerAdapter` envuelve `PaperBroker` (CREATED→fill→FILLED / unknown).                                |
| D4  | `MockBrokerAdapter`: `LIVE` + `not_wired`; **nunca** llama `execute_trade`.                                 |
| D5  | Confirm / FillPending inyectan el puerto (default paper). Adjunto `brokerAdapter`. Gate/skip → sin receipt. |
| D6  | Mock en Confirm → `trade.skipped` / `live_not_wired`; sin `paperOrder`. Pending mock → no borra la orden.   |
| D7  | Sin XTB · sin Alembic · sin `contract:gen` · sin thaw.                                                      |
| D8  | Tests kernel + adapter + Confirm mock + FillPending. HELP honesty. Edge protect **parked**.                 |

## Kernel

```text
build_receipt(venue, adapter, fill_status)
  PAPER + paper_broker → executed | unknown
  LIVE  + mock         → not_wired
submit (paper): PaperBroker.submit
submit (mock):  no ledger · not_wired
```

## Ficheros

- `packages/shared/src/cognitive/broker-adapter.ts` · test
- `packages/py/analytics/.../broker_adapter.py` · `tests/test_broker_adapter_receipt.py`
- `packages/py/application/.../broker_adapter.py` · test
- `confirm_recommendation.py` · `fill_pending_order.py`
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP · CHANGELOG · relevo

## Freeze

ADR-033 · Confirm = firma · OI-1…OI-6 · PaperBroker · `PAPER_D_EXECUTE` off · broker live no · Lab ≠ mesa · thin 5.x/8.x congelados.

## E1

Broker live (XTB) **o** edge Confirm protect honesty. **No** live en el mismo chat que este mock.
