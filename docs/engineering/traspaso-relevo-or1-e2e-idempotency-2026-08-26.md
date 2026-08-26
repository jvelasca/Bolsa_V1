# RELEVO — OR-1 End-to-end idempotency · 2026-08-26

> **Padre:** [`plan-or1-e2e-idempotency-2026-08-26.md`](./plan-or1-e2e-idempotency-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.11-beta` → `76d0f951`**. Spine **367 → 372**.
> **Estado:** **CERRADO (código + tests + docs).** Cambiar de chat recomendado para OR-2.
> **Arranque chat nuevo:** este fichero + ADR-035 + roadmap v1.12 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

OR-1 cierra el retry Confirm paper (identidad estable + short-circuit pre-`adapter.submit`). El siguiente hueco del auditor es **crash/restart** (OR-2): intento durable y `UNKNOWN` reconstruible. No mezclar state machine (OR-3) ni veto recon (OR-4) en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                         | Estado                                          |
| --------------------------------------------- | ----------------------------------------------- |
| `decision_id` canónico · sin `confirm-{uuid}` | **Hecho** — fail-closed `decision_id_required`  |
| `intent_id` / `order_id` estables             | **Hecho** — `INT-{slug}` / `ORD-{slug}`         |
| Short-circuit pre-`adapter.submit`            | **Hecho** — peek `find_existing_by_idempotency` |
| Journal no duplica `executed` en replay       | **Hecho**                                       |
| Concurrente `test_confirm_double_execute_…`   | **Verde**                                       |
| Spine                                         | **372**                                         |
| Alembic / `contract:gen` / OR-2…OR-4          | **No**                                          |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OI-1…OE-1 **no se reabren**.
- Auto-exit **no** es CTA cotidiano. **No** más brokers. **No** AUTO on.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** **OR-2** crash/restart — submit intent durable; al reiniciar reconstruye `UNKNOWN` + mapeo `intent ↔ venue_order_id`. Citar ADR-035. Sin Alembic solo si el diseño lo permite; si hace falta tabla, plan explícito.
2. **Opción B:** operar SEMI con OR-1 (TRIGGERED → Confirm → retry). No reabrir thin. No XTB capital.
3. **No** OR-3 state machine, **no** veto recon (OR-4), **no** CTA «EJECUTAR EN LIVE», **no** pack auditor v112 (al tag).

## 4. Docs clave

- [`plan-or1-e2e-idempotency-2026-08-26.md`](./plan-or1-e2e-idempotency-2026-08-26.md)
- [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo D0: [`traspaso-relevo-audit-ext-v111-cierre-apertura-v112-2026-08-26.md`](./traspaso-relevo-audit-ext-v111-cierre-apertura-v112-2026-08-26.md)
