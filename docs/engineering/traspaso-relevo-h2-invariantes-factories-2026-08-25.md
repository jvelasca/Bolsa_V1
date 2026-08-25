# RELEVO — H2 Invariantes factories CERRADO · apertura P1 · 2026-08-25

> **Padre:** [`plan-h2-invariantes-factories-2026-08-25.md`](./plan-h2-invariantes-factories-2026-08-25.md) · roadmap [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO (guards factories TS+Py + HELP).** Cambiar de chat recomendado para P1.
> **Arranque chat nuevo:** este fichero + plan H2 + ADR-033 §2 + `CURRENT_SYSTEM.md` + roadmap v1.10.

---

## 0. Qué quedó hecho

| Pieza                                                             | Estado             |
| ----------------------------------------------------------------- | ------------------ |
| `from_fill` exige TRIGGERED (o override `{ reason }`)             | **Hecho**          |
| `applyCurrentStop` no empeora sin override                        | **Hecho**          |
| T2 subsume T1 → `full_exit` remaining (no half-reduce)            | **Hecho**          |
| ExecutionPlan: cerrar short = `buy`                               | **Hecho**          |
| Kill switch asimétrico (AUTO DENY; SEMI desriesgo ALLOW)          | **Hecho**          |
| HELP Trading + HELP.md + note HELP_CONTENT_AS_OF                  | **Hecho**          |
| Smoke UI Ayuda → Guía → «Hoy en la mesa» (kill switch asimétrico) | **Hecho** (Chrome) |
| Alembic / wire Confirm / Fill / Consola / `stopPrice` / OCO       | **No** (fuera)     |

Spine `pnpm test:decision-spine` **226**. Shared factories H2 **59**.

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- `check_opening` **intacto** (aperturas siguen vetadas por kill switch).
- Pending ≠ stop de posición. OrderIntent = fill (ADR-029). **No** OrderIntent-dios.
- Factories F1–F4 **sin campos extra**. Override no persiste (P1 lo usará).

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **P1 Position durable + wire fill** (Alembic + snapshot TradePlan + `transactionId`; fill SEMI/pending → PositionState).
2. **Opción B:** operar SEMI. No reabrir thin.
3. **No** Consola de Mesa en el mismo chat. **No** `stopPrice` / OCO. **No** P2/P3.

## 3. Docs clave

- [`plan-h2-invariantes-factories-2026-08-25.md`](./plan-h2-invariantes-factories-2026-08-25.md)
- ADR-033 §2 · gap autoridad · `CURRENT_SYSTEM.md` · roadmap v1.10
