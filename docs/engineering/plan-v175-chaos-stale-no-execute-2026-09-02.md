# Plan — V1.75 Chaos & stale → no-execute E2E

> **Padre:** [`spec-v175-chaos-stale-no-execute-2026-09-02.md`](./spec-v175-chaos-stale-no-execute-2026-09-02.md).  
> **Estado:** **CERRADA** — E2E mock GP-01..04 · pytest GP-05..07.

| ID  | Entrega                                                        | Estado |
| --- | -------------------------------------------------------------- | ------ |
| D0  | spec GO + plan                                                 | DONE   |
| P0  | helpers stale/UNKNOWN + `installHoyStaleNoExecuteMocks`        | DONE   |
| P0  | GP-V175-01..04 mock E2E                                        | DONE   |
| P1  | pytest GP-V175-05..07 (stale dryRun · ENTRY_STALE · adv smoke) | DONE   |
| P1  | auditor + relevo + CURRENT_SYSTEM + engineering-index          | DONE   |

## Entregables

1. [`apps/web/e2e/integration.ts`](../../apps/web/e2e/integration.ts) — `staleNoExecute*` helpers
2. [`apps/web/e2e/fixtures.ts`](../../apps/web/e2e/fixtures.ts) — `installHoyStaleNoExecuteMocks` (separado)
3. [`apps/web/e2e/gp-v175-chaos-stale-no-execute-mock.spec.ts`](../../apps/web/e2e/gp-v175-chaos-stale-no-execute-mock.spec.ts)
4. [`packages/py/application/tests/test_v175_chaos_stale_no_execute.py`](../../packages/py/application/tests/test_v175_chaos_stale_no_execute.py)
5. Docs cierre
