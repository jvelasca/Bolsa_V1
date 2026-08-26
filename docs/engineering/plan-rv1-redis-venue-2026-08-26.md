# Plan — RV-1 Redis persist broker venue

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · relevo VS-1.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código).** Redis key + coalesce + DI async; per-account parked.
> **Relevo previo:** VS-1 venue selector. · Relevo: [`traspaso-relevo-rv1-redis-venue-2026-08-26.md`](./traspaso-relevo-rv1-redis-venue-2026-08-26.md).

---

## Objetivo

Persistir override **Paper | Live** en Redis (best-effort), mismo patrón que kill-switch. Multi-worker + restart. Default **paper**. **No** per-account. **No** thaw `PAPER_D_EXECUTE`.

## Decisiones

| ID  | Decisión                                                                                      |
| --- | --------------------------------------------------------------------------------------------- |
| D1  | Redis key `bolsa:risk:broker_venue`; values `paper`\|`live`.                                  |
| D2  | Precedence: `runtime_memory ?? redis ?? Settings.BROKER_VENUE ?? paper` (coalesce).           |
| D3  | POST: memory always + Redis best-effort. GET/status expose `redis`.                           |
| D4  | Confirm/FillPending DI await effective async → `resolve_broker_adapter(..., venue=)`.         |
| D5  | **No** per-account · **no** Alembic · **no** AccountSettings · **no** thaw.                   |
| D6  | API response additive `redis: paper\|live\|null`; manual types `api.ts`.                      |
| D7  | Freeze: Confirm firma · LR-1/XL-2/VS-1 intactos · `PAPER_D_EXECUTE` off · mesa default paper. |
| D8  | Tests: Redis mock precedence + write; mesa bar unchanged.                                     |

## Kernel

```text
effective = memory ?? redis ?? env ?? paper
POST → set memory + write redis
DI Confirm/Fill → await effective → resolve_broker_adapter(venue=)
```

## Freeze

VS-1 · XL-2 · LR-1 · Confirm firma · `PAPER_D_EXECUTE` off · per-account parked.

## E1

Parked: per-account venue · thaw **estricto** · default-on `PAPER_D_EXECUTE` (palabra owner). Thaw stamp DEMO opt-in **cerrado** (docs/ops).
