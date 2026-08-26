# Plan — LR-1 Live reconciliation (live↔ledger; detect/report)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · relevo [`traspaso-relevo-broker-live-xtb-2026-08-26.md`](./traspaso-relevo-broker-live-xtb-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** XL-1 cerrado.

---

## Objetivo

Responder **«¿cuadra el venue LIVE (XTB bridge) con el ledger paper?»** — cash y qty holdings. Informe ephemeral `LiveLedgerReconciliation`. Detect/report. **No** auto-heal. **No** `execute_trade`. **No** `submit_order`.

≠ OI-6 (capas paper internas) · ≠ XL-2 fill→ledger · ≠ thaw `PAPER_D_EXECUTE` · ≠ UI venue selector.

## Decisiones

| ID  | Decisión                                                                                                                                                   |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Objeto nuevo `LiveLedgerReconciliation` (TS + Py). No sobrecargar OI-6.                                                                                    |
| D2  | Status: `clean` \| `drift` \| `unavailable` (sin bridge / error → fail-closed, nunca `clean` falso).                                                       |
| D3  | Checks: `live_cash_vs_ledger` · `live_qty_vs_holding` · `live_without_holding` · `holding_without_live`. Outcomes `ok`\|`mismatch`\|`expected`\|`unknown`. |
| D4  | Bridge read-only: `GET /account/cash` · `GET /account/positions`. Mock deterministic.                                                                      |
| D5  | `instrumentId` del bridge = id interno (mismo string). Sin mapa símbolo extra.                                                                             |
| D6  | Solo detect/report — **no** muta cash/holdings/PositionState/ledger.                                                                                       |
| D7  | Kernel + use-case + spine tests. Sin Alembic · sin `contract:gen` · sin wire Confirm.                                                                      |
| D8  | XL-2 fill→ledger y UI venue **parked** (mismo programa, chats/fases siguientes).                                                                           |

## Kernel

```text
no bridge / boom → status unavailable (checks empty or unknown)
GET cash + positions → snaps
live_cash_vs_ledger: |liveCash − portfolioCash| < ε → ok else mismatch
live_qty_vs_holding: qty match → ok; else mismatch
live sin holding>0: mismatch
holding>0 sin live: expected (ledger-only / paper residual)
status: unavailable | any mismatch → drift | else clean
```

## Ficheros

- `packages/shared/src/cognitive/live-ledger-reconciliation.ts` · test
- `packages/py/analytics/.../live_ledger_reconciliation.py` · test
- `packages/py/application/.../reconcile_live_ledger.py` · test
- `packages/py/market/.../providers.py` — `fetch_cash` / `fetch_positions`
- `scripts/xtb-bridge-mock.mjs` — GET account cash/positions
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP · CHANGELOG · relevo

## Freeze

ADR-033 · Confirm = firma · OI-1…OI-6 · PaperBroker · BrokerAdapter · PH-1 · XL-1 · `PAPER_D_EXECUTE` off · sin money path fill · sin UI venue.

## E1

**XL-2** Fill→ledger (`filled` → `execute_trade`). Luego UI venue selector. **No** thaw en el mismo chat.
