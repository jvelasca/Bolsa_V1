# RELEVO — LR-1 Live reconciliation · 2026-08-26

> **Padre:** [`plan-lr1-live-reconciliation-2026-08-26.md`](./plan-lr1-live-reconciliation-2026-08-26.md) · ADR-034.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código + tests).**

---

## Qué quedó hecho

| Pieza                                                     | Estado    |
| --------------------------------------------------------- | --------- |
| `LiveLedgerReconciliation` (TS + Py)                      | **Hecho** |
| Checks live cash/qty vs ledger; `unavailable` fail-closed | **Hecho** |
| Bridge `GET /account/cash` + `/account/positions`         | **Hecho** |
| `XtbBridgeClient.fetch_cash` / `fetch_positions`          | **Hecho** |
| Use-case `ReconcileLiveLedger` (no heal / no trade)       | **Hecho** |
| Tests LR-1 + spine                                        | **Hecho** |

## Siguiente chat / fase

1. **XL-2** Fill→ledger (`filled` → `execute_trade`).
2. UI venue selector Paper \| Live.

**No** mezclar thaw `PAPER_D_EXECUTE`.

## Docs

- Plan LR-1 · roadmap v1.11 · CURRENT_SYSTEM stamp LR-1
- Relevo XL-1: [`traspaso-relevo-broker-live-xtb-2026-08-26.md`](./traspaso-relevo-broker-live-xtb-2026-08-26.md)
