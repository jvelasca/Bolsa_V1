# Plan — XL-1 Broker live XTB (adapter + bridge; fail-closed)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · relevo [`traspaso-relevo-confirm-protect-honesty-2026-08-26.md`](./traspaso-relevo-confirm-protect-honesty-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** PH-1 cerrado.

---

## Objetivo

Existe **`XtbBrokerAdapter`** en el puerto `IBrokerAdapter` (`venue: LIVE`, `adapter: xtb`). Habla con el bridge XTB (`POST /orders`). **Fail-closed:** mock bridge rechaza por defecto; **nunca** llama `execute_trade` / ledger. `submitted` ≠ fill ≠ `executed`.

≠ thaw `PAPER_D_EXECUTE` · ≠ money path real XTB API · ≠ reconciliación live · mesa default paper · Mock intacto.

`MockBrokerAdapter` = slot not_wired de prueba. `XtbBrokerAdapter` = cable live vía bridge (sin ledger).

## Decisiones

| ID  | Decisión                                                                                                                                      |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | `adapter: xtb` + fillStatus `rejected` \| `submitted` (además de executed/unknown/not_wired).                                                 |
| D2  | Sin URL/cliente → `not_wired` / `xtb_bridge_not_configured`.                                                                                  |
| D3  | Bridge `POST /orders`; mock default **rejected** (`live_orders_disabled`). Opt-in mock `XTB_BRIDGE_ALLOW_ORDERS=1` → `submitted`.             |
| D4  | `XtbBrokerAdapter` **nunca** llama `execute_trade`. Cero ledger en este slice.                                                                |
| D5  | Confirm / FillPending: `rejected`→`skipped`; `submitted`→`unknown` / `live_submitted_no_fill`; pending **no** se borra. Default mesa = paper. |
| D6  | Sin Alembic · sin `contract:gen` · sin thaw · sin wire UI venue selector.                                                                     |
| D7  | Tests receipt + adapter + Confirm/FillPending XTB + spine. HELP honesty.                                                                      |
| D8  | Money path real / reconcile live / thaw **parked**.                                                                                           |

## Kernel

```text
XtbBrokerAdapter.submit
  no bridge → not_wired
  POST /orders → rejected | submitted
  never execute_trade

Confirm/FillPending (LIVE xtb)
  rejected  → skipped (pending intact)
  submitted → unknown live_submitted_no_fill (pending intact)
  paper default unchanged
```

## Ficheros

- `packages/shared/src/cognitive/broker-adapter.ts` · test
- `packages/py/analytics/.../broker_adapter.py` · test
- `packages/py/market/.../providers.py` · `submit_order`
- `packages/py/application/.../broker_adapter.py` · `XtbBrokerAdapter`
- `confirm_recommendation.py` · `fill_pending_order.py`
- `scripts/xtb-bridge-mock.mjs` — `POST /orders`
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP · CHANGELOG · relevo

## Freeze

ADR-033 · Confirm = firma · OI-1…OI-6 · PaperBroker · BrokerAdapter mock · PH-1 · `PAPER_D_EXECUTE` off · Lab ≠ mesa · thin 5.x/8.x · **no** thaw · **no** ledger desde XTB.

## E1

Money path real XTB / reconcile live↔ledger / selector UI venue. **No** mezclar thaw en el mismo chat.
