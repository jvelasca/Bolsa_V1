# Plan — ExitPermission (Operational Core)

> **Padre:** [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · ADR-032 §4 · relevo INFRA [`traspaso-relevo-infra-ci-by-tag-2026-08-25.md`](./traspaso-relevo-infra-ci-by-tag-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · batería spine **217**.
> **Método:** veto **puro** de salida / mutación de stop. Simétrico a `check_opening`, **distinto** de él. Sin wire Confirm / EvaluatePositionExits / ExecuteTrade. Sin broker.

---

## 0. Objetivo

Responder «¿podemos **salir / mutar stop ahora**?» con ALLOW/DENY ligado a `ExitPlan` (+ señales), sin ejecutar.

## 1. Decisiones (D1–D8) — OK

| Id     | Decisión                                                                       |
| ------ | ------------------------------------------------------------------------------ |
| **D1** | Objeto nuevo `ExitPermission`. No fusionar con `check_opening`.                |
| **D2** | `checkExitPermission` / `check_exit_permission`; ExecutionPlan opcional.       |
| **D3** | `ALLOW`/`DENY` + reasons + action eco.                                         |
| **D4** | ALLOW solo accionable (`TRIGGERED` exit/reduce o `ARMED` protect).             |
| **D5** | Señales: kill / broker / paper_auto_env / position_closed / execution_blocked. |
| **D6** | SEMI no exige `PAPER_D_EXECUTE`; AUTO solo si `autoExecute`.                   |
| **D7** | Paridad TS+Py; HELP sync.                                                      |
| **D8** | Tests D + stamp + relevo. E1: SEMI · tag `v1.9-beta` · wire fase.              |

## 2. Ficheros

- `packages/shared/src/cognitive/exit-permission.ts` · `exit-permission.test.ts`
- `packages/py/analytics/.../exit_permission.py` · `tests/test_exit_permission.py`
- HELP · stamps · relevo

## 3. Freeze (intactos)

`check_opening` · F1–F4 · INFRA · thin · `PAPER_D_EXECUTE` off · Confirm / Router.
