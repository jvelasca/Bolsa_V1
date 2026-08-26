# RELEVO — DEX-1 PostgreSQL SubmitIntent · apertura DEX-2 · 2026-08-26

> **Padre:** [`plan-dex1-pg-submit-intents-2026-08-26.md`](./plan-dex1-pg-submit-intents-2026-08-26.md) · ADR-035 · roadmap v1.13.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. Spine **433** (partida).
> **Estado:** **DEX-1 CERRADO** (código + tests + docs). Sucesor: [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](./traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md) (**DEX-2 CERRADO** · next DEX-3).
> **Arranque chat nuevo (histórico DEX-2):** este fichero + plan DEX-1. **Apertura DEX-3:** relevo DEX-2.

---

## 0. Por qué cambiar de chat

DEX-1 deja la **persistencia física** (`submit_intents` + `PostgresSubmitIntentStore` + fases `send_attempted`). El siguiente hueco del auditor es demostrar recuperación **cross-PID**: store/cliente **fresco** leyendo PG → `UNKNOWN` · 0 re-POST. No mezclar Incident (DEX-3) ni Confirm split (DEX-4) en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                                                      | Estado                                |
| -------------------------------------------------------------------------- | ------------------------------------- |
| Alembic `013_submit_intents` + `SubmitIntentRow`                           | **Hecho**                             |
| Fases `recorded` / `send_attempted` / bound / filled + `send_attempted_at` | **Hecho** · espejo TS                 |
| `send_attempted_durable` (no solo `intent≠None`)                           | **Hecho**                             |
| Confirm: put recorded → mark send → adapter                                | **Hecho** · fila durable ⇒ no re-POST |
| `PostgresSubmitIntentStore` + DI Confirm                                   | **Hecho** · InMemory en unit tests    |
| Tests kernel / crash OR-2 / store contract                                 | **Hecho**                             |
| DEX-2 kill-process / cliente fresco PG                                     | **No**                                |
| DEX-3 Incident · DEX-4 split · pack v113                                   | **No**                                |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**. AUTO **off**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OR-1/3/4/5/6 **no se reabren** a ciegas.
- Auto-exit **no** es CTA cotidiano. **No** más brokers.
- JSONB PositionState SoT · `position_revisions` parked.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** implementar **DEX-2** — crash/restart real: persist → submit → store/cliente **nuevo** leyendo PG → `UNKNOWN` · 0 re-POST. Citar plan DEX-1 + ADR-035. Cero Incident · cero Confirm split.
2. **Opción B:** operar SEMI con v1.12 + DEX-1 PG (TRIGGERED → Confirm → `Ejecutar en PAPER`). No reabrir thin. No XTB capital.
3. **No** DEX-3 Incident, **no** DEX-4 Confirm split, **no** DEX-5 property suite, **no** pack auditor v113 en el mismo chat que DEX-2.

## 4. Docs clave

- [`plan-dex1-pg-submit-intents-2026-08-26.md`](./plan-dex1-pg-submit-intents-2026-08-26.md)
- [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md)
- [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo: [`traspaso-relevo-audit-ext-v112-apertura-v113-2026-08-26.md`](./traspaso-relevo-audit-ext-v112-apertura-v113-2026-08-26.md)
