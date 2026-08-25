# RELEVO — P1 Position durable CERRADO · apertura P2 · 2026-08-25

> **Padre:** [`plan-p1-position-durable-2026-08-25.md`](./plan-p1-position-durable-2026-08-25.md) · roadmap [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO (Alembic 011 + wire Confirm/Fill + Operaciones + HELP).** Cambiar de chat recomendado para P2.
> **Arranque chat nuevo:** este fichero + plan P1 + ADR-033 §6 + `CURRENT_SYSTEM.md` + roadmap v1.10.

---

## 0. Qué quedó hecho

| Pieza                                                          | Estado         |
| -------------------------------------------------------------- | -------------- |
| Tabla `position_states` + `pending_orders.trade_plan_snapshot` | **Hecho**      |
| `from_fill` al nacer (H2 TRIGGERED o override en columna)      | **Hecho**      |
| Wire Confirm apertura + FillPendingOrder con snapshot          | **Hecho**      |
| Operaciones: stop / T1 / T2 / estado; si no hay plan → honest  | **Hecho**      |
| HELP Trading + HELP.md + note HELP_CONTENT_AS_OF               | **Hecho**      |
| Consola / `stopPrice` / OCO / P2 firma / persist reduce-BE     | **No** (fuera) |

Spine `pnpm test:decision-spine` **233** (P1 persist +7).

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- `check_opening` **intacto**. H1 pending honesty **intacta**. H2 factories **sin campos extra**.
- Pending ≠ stop de posición. OrderIntent = fill. **No** OrderIntent-dios.
- Diálogo de orden **no** envía snapshot (pending sin plan = solo ledger). Tests cubren fill **con** snapshot.

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **P2 Riesgo al firmar** (ADR-033 §6). Ticket vs TradePlan. **No** consola.
2. **Opción B:** operar SEMI. No reabrir thin.
3. **No** Consola de Mesa en el mismo chat. **No** `stopPrice` / OCO. **No** P3/P4.

## 3. Docs clave

- [`plan-p1-position-durable-2026-08-25.md`](./plan-p1-position-durable-2026-08-25.md)
- ADR-033 §6 · gap autoridad · `CURRENT_SYSTEM.md` · roadmap v1.10
