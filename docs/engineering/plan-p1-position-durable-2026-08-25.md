# Plan — P1 Position durable + wire fill

> **Padre:** [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 §2 · gap [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md) §2.1 · relevo [`traspaso-relevo-h2-invariantes-factories-2026-08-25.md`](./traspaso-relevo-h2-invariantes-factories-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO.** D1–D8 OK · Alembic `011` · wire Confirm/Fill · Operaciones stop/T1/T2 · HELP.
> **Método:** persistir PositionState v1.9 (no objeto hermano). Ledger `positions` intacto. H2 factories **sin campos extra**. Cero Consola. Cero `stopPrice` / OCO. Cero P2/P3. Cero `regen_full`.

---

## 0. Objetivo

Tras un fill de **apertura** (Confirm SEMI execute **o** pending con snapshot de plan), el producto puede responder: qué plan se aprobó, cuál es el stop, T1/T2, estado OPEN. Operaciones enseña ese snapshot. El holding `qty/avg_cost` sigue siendo contabilidad.

### Qué entra vs qué queda fuera

| Incluye (P1)                                                                                | Excluye                                       |
| ------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Alembic `011`: tabla `position_states` + `pending_orders.trade_plan_snapshot`               | Mutar ledger `positions` (qty/avg_cost)       |
| Snapshot TradePlan + PositionState al nacer; `open_transaction_id` único                    | Consola de Mesa · P4                          |
| Wire Confirm execute (apertura) + FillPendingOrder (si hay snapshot)                        | `stopPrice` · OCO · OrderIntent-dios          |
| Operaciones: stop / T1 / T2 / estado cuando hay fila; si no, holding plano (honest)         | P2 firma ticket · P3 cadena ExitPlan          |
| Override `{ reason }` persistido en **columna** `birth_override_reason` (no campo nuevo F2) | Persist mark/reduce/BE (remaining as-of fill) |
| Tests familia C (fill → fila) + E (`transactionId`, no duplicar) + HELP                     | Thin 5.x/8.x · broker · `PAPER_D_EXECUTE`     |

---

## 1. Decisiones (D1–D8)

| Id     | Decisión                                                                                                                                                                                                            |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | Tabla **nueva** `position_states`. Ledger `positions` **intacto**. Agregado = PositionState v1.9 en JSONB + snapshot TradePlan. **No** objeto hermano. **No** Prisma DDL.                                           |
| **D2** | Nacimiento = `build_position_state_from_fill` (H2). WATCH/ARMED sin override → **no** fila (holding sí). Override auditado → columna `birth_override_reason`; factories F1–F4 **sin** campos extra.                 |
| **D3** | Wire **aperturas** con plan: Confirm `execute` + `recommend_long`/`recommend_short`; FillPendingOrder si la fila tiene `trade_plan_snapshot`. `POST /portfolio/trade` **sin** plan → solo ledger.                   |
| **D4** | Idempotencia: `open_transaction_id` UNIQUE. Replay del mismo fill no duplica. Un OPEN por `(account_id, instrument_id)` en P1 (segundo natalicio del mismo símbolo se omite).                                       |
| **D5** | Pending: JSONB `trade_plan_snapshot` nullable. Fill usa ese snapshot. El diálogo de orden P1 **no** lo envía (sin TradePlan en el diálogo / sin `regen_full`). Tests cubren fill **con** snapshot.                  |
| **D6** | Solo **nacimiento** OPEN. Mark/reduce/BE **no** se graban. `remainingQuantity` es as-of fill hasta P3. HELP lo dice.                                                                                                |
| **D7** | Operaciones lee `operational` opcional en `PositionDto` (status, direction, currentStop, target1, target2, tradePlanId). Dominio `Position` **intacto**. Delta mínimo openapi.json + schema.d.ts (no `regen_full`). |
| **D8** | Tests C+E · HELP (fill → plan visible en Operaciones; holding ≠ plan) · stamp CURRENT_SYSTEM / CHANGELOG / ADR-033 / roadmap P1 · relevo. **E1:** P2 firma **o** operar SEMI. **No** P3/P4 en este chat.            |

Si P1 muta `positions.avg_cost`, añade `stopPrice`, Consola, o reabre F1–F4 con campos extra: **parar y replanificar**.

---

## 2. Ficheros

- Alembic `011_position_states.py` · `tables.py` (`PositionStateRow` + pending snapshot)
- `position_state_repository.py` · `persist_position_from_fill.py`
- `confirm_recommendation.py` · `fill_pending_order.py` · `dependencies.py`
- `portfolio.py` DTO + mapper GET `/portfolio` · `operations-panel.tsx` · shared `PositionDto`
- Tests application (persist / confirm / fill) · HELP · stamp

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · `check_opening` · H1 pending honesty · H2 factories · Dedup Hoy por símbolo · broker **no** · **no** OrderIntent-dios · **no** Consola.
