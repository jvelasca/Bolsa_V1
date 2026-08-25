# Plan — F2 PositionState v1 (Operational Core)

> **Padre:** [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · ADR-032 §3 · gap [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §2 · relevo [`traspaso-relevo-f1-tradeplan-v1-2026-08-25.md`](./traspaso-relevo-f1-tradeplan-v1-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · batería spine **172**.
> **Método:** objeto **nuevo** de autoridad post-entrada. **No** promover thin 5.x/8.x. Sin ExitPlan / ExecutionPlan. Sin `contract:gen`. Sin Alembic.

---

## 0. Objetivo

Modelar «qué ocurre **tras** entrar»: identidad ligada a TradePlan F1 + ciclo de vida mínimo + geometry plan-vs-fill.

## 1. Decisiones (D1–D8) — OK

| Id  | Decisión                                                      |
| --- | ------------------------------------------------------------- |
| D1  | Objeto nuevo PositionState; thin no copiados                  |
| D2  | `positionId` + `tradePlanId` (= decisionId)                   |
| D3  | Status `OPEN`/`PARTIAL`/`PROTECTED`/`CLOSED`; F2 emite `OPEN` |
| D4  | Geometry plan-vs-fill; stops foto al nacer                    |
| D5  | realizedR=0; MFE/MAE source none                              |
| D6  | thesis/protect/trail/exit stubs                               |
| D7  | Factory pura; sin Alembic/contract:gen/opening                |
| D8  | Tests + stamp + relevo                                        |

## 2. Ficheros

- `packages/shared/src/cognitive/position-state.ts` · `position-state.test.ts`
- `packages/py/analytics/.../position_state.py` · `tests/test_position_state.py`
- HELP · CURRENT_SYSTEM · CHANGELOG · relevo F2
