# Plan — F4 ExecutionPlan → PAPER (Operational Core)

> **Padre:** [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · ADR-032 §4 · gap [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §4 · relevo F3 [`traspaso-relevo-f3-exit-plan-2026-08-25.md`](./traspaso-relevo-f3-exit-plan-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · batería spine **203**.
> **Método:** objeto **nuevo** de envío. Cadena **PAPER → Journal → Replay → Validation**. **No** broker. **No** ExitPermission. **No** `PAPER_D_EXECUTE` on. **No** OCO. Sin wire Confirm / ExecuteTrade / Router.

---

## 0. Objetivo

Responder «¿cómo se **enviaría**?» con un plan de envío ligado a `ExitPlan`, destino **solo PAPER**, sin tocar ledger ni broker.

### Qué entra vs qué queda fuera

| Incluye (F4)                                              | Excluye                                             |
| --------------------------------------------------------- | --------------------------------------------------- |
| Objeto `ExecutionPlan` (shared TS + Py)                   | Broker adapter · OCO · live                         |
| Factory desde `ExitPlan` (acciones order-like)            | `ExitPermission` producto                           |
| `venue: PAPER` fijo en F4                                 | `PAPER_D_EXECUTE` on · `ExecuteTrade` · Router AUTO |
| Status pipeline PAPER→Journal→Replay→Validation           | Wire Confirm / Hoy CTA / HTTP journal               |
| Transiciones puras de stage (+ bloqueo broker)            | Mutar PositionState / ExitPlan                      |
| Tests familia **C/D** (lifecycle + safety) + HELP + stamp | `contract:gen` · Alembic · ActionabilityScore       |

---

## 1. Decisiones (D1–D8) — OK

| Id     | Decisión                                                                                                                                                       |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | Objeto **nuevo** `ExecutionPlan`. **No** mapper thin. **No** reutilizar `OrderIntent` como SoT. Thin 5.x/8.x **congelados**. ExitPermission **fuera**.         |
| **D2** | Identidad: `executionPlanId` + `exitPlanId` + `positionId` + `tradePlanId`. Factory: `buildExecutionPlanFromExitPlan` / `build_execution_plan_from_exit_plan`. |
| **D3** | `venue` **solo** `PAPER` en F4. Intento `BROKER` → `BLOCKED` (`broker_not_allowed`).                                                                           |
| **D4** | Status: `DRAFT` \| `PAPER_READY` \| `JOURNALED` \| `REPLAYED` \| `VALIDATED` \| `BLOCKED`. Stages puros sin I/O.                                               |
| **D5** | `TRIGGERED` exit/reduce → `PAPER_READY`; `ARMED` protect → `DRAFT` stop_amend; else **null**.                                                                  |
| **D6** | `intentKind` + `paperProjection` opcional ≠ fill ledger. ExecutionPlan ≠ permiso ≠ ExecuteTrade.                                                               |
| **D7** | Paridad TS+Py. Sin Alembic/contract:gen/HTTP/Confirm/Router. `PAPER_D_EXECUTE` off. HELP sync.                                                                 |
| **D8** | Tests C+D · stamp · relevo F4. **E1**: INFRA CI-by-tag · ExitPermission · SEMI. **No** broker.                                                                 |

---

## 2. Ficheros

- `packages/shared/src/cognitive/execution-plan.ts` · `execution-plan.test.ts`
- `packages/py/analytics/.../cognitive/execution_plan.py` · `tests/test_execution_plan.py`
- HELP · CURRENT_SYSTEM · CHANGELOG · roadmap · ADR-032 · relevo F4

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · PositionState ≠ permiso · ExitPlan ≠ permiso · ExecutionPlan ≠ ExecuteTrade · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · C1 Hoy honesty · F1–F3 **intactos** · opening / Confirm / Router **intactos**.
