# RELEVO — VS-1 Venue selector Paper | Live · 2026-08-26

> **Padre:** [`plan-vs1-venue-selector-2026-08-26.md`](./plan-vs1-venue-selector-2026-08-26.md) · ADR-034.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código + tests).**

---

## Qué quedó hecho

| Pieza                                           | Estado    |
| ----------------------------------------------- | --------- |
| `BROKER_VENUE` Settings + runtime memory        | **Hecho** |
| `resolve_broker_adapter` DI Confirm/FillPending | **Hecho** |
| API `GET/POST /api/risk/broker-venue`           | **Hecho** |
| Mesa toggle Paper \| Live                       | **Hecho** |
| Default paper; live sin bridge → `not_wired`    | **Hecho** |
| Spine **362**                                   | **Hecho** |

## Siguiente chat

1. Redis persist venue / per-account venue (opcional).
2. Columnas JSONB promovidas.
3. Thaw `PAPER_D_EXECUTE` — **chat aparte, no mezclar**.

## Sesión 2026-08-26 (cadena)

- **LR-1** LiveLedgerReconciliation detect/report.
- **XL-2** filled → ledger.
- **VS-1** selector mesa Paper \| Live.

## Docs

- Planes LR-1 · XL-2 · VS-1 · roadmap v1.11 · CURRENT_SYSTEM · HELP
- Relevo XL-2: [`traspaso-relevo-xl2-xtb-fill-ledger-2026-08-26.md`](./traspaso-relevo-xl2-xtb-fill-ledger-2026-08-26.md)
