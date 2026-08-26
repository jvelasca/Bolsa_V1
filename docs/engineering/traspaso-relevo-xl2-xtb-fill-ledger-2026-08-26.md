# RELEVO — XL-2 XTB fill → ledger · 2026-08-26

> **Padre:** [`plan-xl2-xtb-fill-ledger-2026-08-26.md`](./plan-xl2-xtb-fill-ledger-2026-08-26.md) · ADR-034.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código + tests).**

---

## Qué quedó hecho

| Pieza                                         | Estado    |
| --------------------------------------------- | --------- |
| Bridge status `filled` (opt-in FILL)          | **Hecho** |
| `XtbBrokerAdapter` filled → `execute_trade`   | **Hecho** |
| `submitted` ≠ fill (XL-1 intacto)             | **Hecho** |
| Confirm/FillPending executed + pending delete | **Hecho** |
| Fail-closed: sin execute → `unknown`          | **Hecho** |
| Tests XL-2                                    | **Hecho** |

## Siguiente

1. **VS-1** venue selector (mismo programa).

**No** thaw `PAPER_D_EXECUTE`.

## Docs

- Plan XL-2 · roadmap · ADR-034 · CURRENT_SYSTEM
- Relevo LR-1: [`traspaso-relevo-lr1-live-reconciliation-2026-08-26.md`](./traspaso-relevo-lr1-live-reconciliation-2026-08-26.md)
