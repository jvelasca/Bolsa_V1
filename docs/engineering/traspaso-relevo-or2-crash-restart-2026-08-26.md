# RELEVO — OR-2 Crash/restart recovery · 2026-08-26

> **Padre:** [`plan-or2-crash-restart-2026-08-26.md`](./plan-or2-crash-restart-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.11-beta` → `76d0f951`**. Spine **372 → 382**.
> **Estado:** **CERRADO (código + tests + docs).** Cambiar de chat recomendado para OR-3.
> **Arranque chat nuevo:** este fichero + ADR-035 + roadmap v1.12 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

OR-2 cierra crash/restart Confirm: intento durable **antes** de `adapter.submit`; al reiniciar reconstruye `UNKNOWN` + mapeo `intent ↔ venue_order_id` sin re-POST. El siguiente hueco del auditor es la **state machine de orden** (OR-3): más allá de `CREATED`/`FILLED`. No mezclar veto recon (OR-4) ni suite A–L (OR-5) en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                                 | Estado                                      |
| ----------------------------------------------------- | ------------------------------------------- |
| `DurableSubmitIntent` recorded / venue_bound / filled | **Hecho** — ≠ OR-3 SUBMITTED/ACK/…          |
| Persist **antes** de `adapter.submit`                 | **Hecho** — fail-closed si `put` falla      |
| Recovery sin fill → `UNKNOWN` · 0 re-POST             | **Hecho** — `crashRecovery`                 |
| Mapeo `intent` ↔ `venue_order_id`                     | **Hecho** — live `submitted` retry = 1 send |
| Store sin Alembic                                     | **Hecho** — puerto + InMemory proceso       |
| Spine                                                 | **382**                                     |
| Alembic / Redis multi-worker / OR-3…OR-6              | **No**                                      |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OI-1…OE-1 **no se reabren**.
- Auto-exit **no** es CTA cotidiano. **No** más brokers. **No** AUTO on.
- Store = singleton de **proceso** (retry mismo worker). Tabla PG / Redis cross-PID = parked.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** **OR-3** order state machine — ampliar `CREATED→FILLED` hacia SUBMITTED / ACK / PARTIAL / REJECTED / CANCELLED / EXPIRED / UNKNOWN. Citar ADR-035. **No** broker producción · **no** OCO.
2. **Opción B:** operar SEMI con OR-1+OR-2 (TRIGGERED → Confirm → retry/crash). No reabrir thin. No XTB capital.
3. **No** veto recon (OR-4), **no** suite A–L (OR-5), **no** CTA «EJECUTAR EN LIVE» (OR-6), **no** pack auditor v112 (al tag).

## 4. Docs clave

- [`plan-or2-crash-restart-2026-08-26.md`](./plan-or2-crash-restart-2026-08-26.md)
- [`plan-or1-e2e-idempotency-2026-08-26.md`](./plan-or1-e2e-idempotency-2026-08-26.md)
- [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo OR-1: [`traspaso-relevo-or1-e2e-idempotency-2026-08-26.md`](./traspaso-relevo-or1-e2e-idempotency-2026-08-26.md)
