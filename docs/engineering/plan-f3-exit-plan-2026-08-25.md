# Plan — F3 ExitPlan (Operational Core)

> **Padre:** [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · ADR-032 §4 · gap [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §3 · relevo F2.1 [`traspaso-relevo-f2-1-position-state-transitions-2026-08-25.md`](./traspaso-relevo-f2-1-position-state-transitions-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · batería spine **192**.
> **Método:** objeto **nuevo** de autoridad post-entrada (simétrico a TradePlan). Razones canónicas. **ExitPlan ≠ execution ≠ ExitPermission.** Sin promocionar thin 5.2/8.1. Sin wire Confirm / Hoy CTA. Sin `contract:gen`. Sin Alembic.

---

## 0. Objetivo

Responder «si ocurre Y, ¿cómo salimos / protegemos?» con un **plan condicional** ligado a `PositionState`, sin enviar órdenes ni abrir permiso de salida.

### Qué entra vs qué queda fuera

| Incluye (F3)                                            | Excluye                                                                    |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| Objeto `ExitPlan` (shared TS + Py)                      | `ExitPermission` · `ExecutionPlan`                                         |
| Razones canónicas gap §3 (enum cerrado)                 | Mapper thin `map_exit_plan` / copiar `exitRadar`/`trailPlan`/`protectPlan` |
| Factory pura desde `PositionState` + señales explícitas | Wire Confirm / opening / Hoy CTA «Salida»                                  |
| Status propio del plan (`IDLE`…`DONE`)                  | Mutar `PositionState` / `applyReduce` / `applyCurrentStop`                 |
| `suggestedAction` advisory (≠ orden)                    | Auto-exit · `EvaluatePositionExits` producto · broker                      |
| Tests familia **C** (lifecycle exit) + HELP + stamp     | `contract:gen` · Alembic · ActionabilityScore · F4                         |

---

## 1. Decisiones (D1–D8) — OK

| Id     | Decisión                                                                                                                                                                                                                                                                                     |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | Objeto **nuevo** `ExitPlan` (como F2 PositionState). **No** crece solo dentro de PositionState. **No** `map_*` hermano thin. Thin 5.x/8.x **congelados**. ExitPermission / ExecutionPlan **fuera** de esta rebanada.                                                                         |
| **D2** | Identidad: `exitPlanId` + `positionId` + `tradePlanId` (+ `instrumentId` / `direction` eco). Factory: `buildExitPlanFromPosition(position, signals?)` / `build_exit_plan_from_position`.                                                                                                     |
| **D3** | Razones **cerradas** (gap §3): `STRUCTURAL_STOP` · `THESIS_INVALIDATION` · `TARGET_1` · `TARGET_2` · `TRAIL` · `TIME_STOP` · `PORTFOLIO_RISK` · `MANUAL`. Campos: `reasons[]` + `primaryReason` (prioridad fija abajo). Sin razones inventadas.                                              |
| **D4** | Status ExitPlan: `IDLE` \| `HINT` \| `ARMED` \| `TRIGGERED` \| `DONE`. **No** muta `PositionState.exitStatus` en F3 (sigue `none`→`done` solo vía reduce F2.1). CLOSED position → ExitPlan `DONE` (lectura, no write-back).                                                                  |
| **D5** | Evaluación **pura y honesta** (solo lo que hay inputs para): precio/mark vs `currentStop` / T1 / T2; `expiresAt` señal → `TIME_STOP`; `thesisInvalid` / `portfolioRisk` / `manual` / `trailHint` solo si la señal llega explícita — **no** leer mappers thin. Sin señal → no inventar razón. |
| **D6** | `suggestedAction`: `hold` \| `protect` \| `reduce` \| `full_exit` — **advisory**. Puede llevar `suggestedQty` / `suggestedStop` informativos. **≠** orden · **≠** mutar stop · **≠** `applyReduce`. ExitPlan **≠** permiso de salida.                                                        |
| **D7** | Paridad **shared TS + Python**. Sin Alembic · sin `contract:gen` · sin HTTP · sin Confirm/Hoy CTA · sin `EvaluatePositionExits` wire · `PAPER_D_EXECUTE` off. HELP: ExitPlan = razones canónicas; mark/reduce PositionState ≠ orden; thin «Salida» ≠ ExitPlan.                               |
| **D8** | Tests invariante familia **C** (exit lifecycle) en shared + py · stamp `CURRENT_SYSTEM` / CHANGELOG / roadmap / ADR-032 §4 nota · relevo F3. **E1** siguiente: **F4 ExecutionPlan→PAPER** **o** INFRA CI-by-tag. **No** broker.                                                              |

### Precedencia de `primaryReason` (si varias)

```text
MANUAL >
STRUCTURAL_STOP >
THESIS_INVALIDATION >
PORTFOLIO_RISK >
TARGET_1 >
TARGET_2 >
TRAIL >
TIME_STOP
```

### Status (resumen)

```text
position CLOSED     → DONE
else primary dispara condición dura (stop/thesis/portfolio/manual/targets tocados) → TRIGGERED
else señal trail/time o hint débil → HINT o ARMED (ARMED = protect/trail tip con geometría; HINT = advisory flojo)
else                → IDLE
```

---

## 2. Ficheros

- `packages/shared/src/cognitive/exit-plan.ts` · `exit-plan.test.ts`
- `packages/py/analytics/.../cognitive/exit_plan.py` · `tests/test_exit_plan.py`
- HELP (`hoy-en-la-mesa` / as-of)
- Stamp: `CURRENT_SYSTEM.md` · CHANGELOG · roadmap v1.9 · ADR-032 · relevo F3

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · PositionState ≠ permiso de salida · ExitPlan ≠ permiso · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · C1 Hoy honesty · dedup Hoy por símbolo · F1 / F2 / F2.1 factory+transitions **intactos** · opening / Confirm **intactos**.
