# Plan — Ciclo C3 ActionQueue (v1.8.1)

> **Padre:** [`roadmap-v181-operational-consolidation-2026-08-25.md`](./roadmap-v181-operational-consolidation-2026-08-25.md) · C1 [`traspaso-relevo-ciclo-c1-hoy-honesty-help-2026-08-25.md`](./traspaso-relevo-ciclo-c1-hoy-honesty-help-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **ABIERTA**.
> **Método:** proyección Hoy; Ranking ≠ BUY; C1 intacto (nunca BUY sin plan); sin backend HTTP; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Separar cola completa ordenada (`buildActionQueue`) del slice visual Hoy (`limit=8`). Prioridad determinista, no orden de llegada del backend.

### Qué entra vs qué queda fuera

| Incluye (C3)                                       | Excluye                    |
| -------------------------------------------------- | -------------------------- |
| `buildActionQueue(board)` lista completa ordenada  | ActionQueue HTTP / backend |
| `mapDecisionBoardToHoyQueue(board, limit=8)` slice | Inventar freshness/age     |
| Prioridad D2 + dedup post-sort                     | C2 Alembic · C5 métricas   |
| Tests orden / slice / C1 no BUY                    | Módulos thin nuevos        |

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                      |
| --- | ------------------------------------------------------------------------------------------------------------- |
| D1  | `buildActionQueue` = full sorted. `mapDecisionBoardToHoyQueue(board, limit=8)` = slice. C1 intacto.           |
| D2  | Prioridad: exit_hint → REVIEW → BUY(TRIGGERED vivo) → ARMED → protect_hint → thesis review → WATCH → BLOCKED. |
| D3  | Desempate: `actionability` del plan vivo; si no, orden estable. No inventar freshness/age.                    |
| D4  | Dedup por símbolo **después** de ordenar (queda banda más alta).                                              |
| D5  | UI Hoy sigue top-8. Copy vacío intacto.                                                                       |
| D6  | Tests `hoy-queue.test.ts`.                                                                                    |
| D7  | Sin backend nuevo.                                                                                            |
| D8  | Relevo C3. E1 = C5.                                                                                           |

Si D1 vuelve a emitir BUY sin plan o D7 crea endpoint: **parar**.

---

## 2. Ficheros

- `packages/shared/src/cognitive/hoy-queue.ts`
- `packages/shared/src/hoy-queue.test.ts`
- `apps/web/src/features/trading/hoy-command-strip.tsx` (sigue llamando el mapper con default 8)
- Stamp CURRENT_SYSTEM · CHANGELOG Unreleased · relevo

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · C1 WATCH-sin-plan · 5.x/8.x parked · `PAPER_D_EXECUTE` off.
