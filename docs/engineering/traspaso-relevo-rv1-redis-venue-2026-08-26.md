# RELEVO — RV-1 Redis persist broker venue · 2026-08-26

> **Padre:** [`plan-rv1-redis-venue-2026-08-26.md`](./plan-rv1-redis-venue-2026-08-26.md) · ADR-034 · relevo VS-1.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código + tests).**

---

## Qué quedó hecho

| Pieza                                      | Estado          |
| ------------------------------------------ | --------------- |
| Redis key `bolsa:risk:broker_venue`        | **Hecho**       |
| Coalesce `memory ?? redis ?? env ?? paper` | **Hecho**       |
| DI Confirm/FillPending async effective     | **Hecho**       |
| POST memory + Redis best-effort            | **Hecho**       |
| Per-account venue                          | **Parked**      |
| Thaw `PAPER_D_EXECUTE`                     | **Chat aparte** |

## Siguiente chat

1. Per-account venue (opcional).
2. Thaw **estricto** P1–P5 (deuda) — chat aparte.
3. Revisions child / paper_orders DDL (parked).

## Sesión 2026-08-26 (cadena)

- **VS-1** selector mesa Paper \| Live.
- **RV-1** Redis persist venue (este chat).
- **JP-1** · **Thaw stamp** (misma sesión, chats lógicos aparte).

## Docs

- Plan RV-1 · roadmap v1.11 · CURRENT_SYSTEM · ADR-034
- Relevo VS-1: [`traspaso-relevo-vs1-venue-selector-2026-08-26.md`](./traspaso-relevo-vs1-venue-selector-2026-08-26.md)
- Relevo thaw: [`traspaso-relevo-thaw-paper-d-execute-2026-08-26.md`](./traspaso-relevo-thaw-paper-d-execute-2026-08-26.md)
