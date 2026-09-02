# Plan — V1.76 Certification Hardening

> **Padre:** [`spec-v176-certification-hardening-2026-09-02.md`](./spec-v176-certification-hardening-2026-09-02.md).  
> **Estado:** **CERRADA** — E2E mock GP-V175-01/03/04 endurecidos · GP-V176-01.

| ID  | Entrega                                                       | Estado |
| --- | ------------------------------------------------------------- | ------ |
| D0  | spec GO + plan                                                | DONE   |
| P0  | `data-reason-code` DailyDesk + notes stale sin AUTO armado    | DONE   |
| P0  | GP-V175-01 endurecido                                         | DONE   |
| P0  | Fixture `hoyUnknown` / `ord-unknown-001` + GP-V175-04 aislado | DONE   |
| P1  | Echo `data-status.instrumentId` + badge + GP-V175-03          | DONE   |
| P1  | GP-V176-01 causalidad                                         | DONE   |
| P1  | auditor + relevo + CURRENT_SYSTEM + engineering-index         | DONE   |

## Entregables

1. [`packages/shared/src/cognitive/daily-desk.ts`](../../packages/shared/src/cognitive/daily-desk.ts) — `reasonCode?` en ítem
2. [`packages/shared/src/cognitive/daily-desk-auto-projection.ts`](../../packages/shared/src/cognitive/daily-desk-auto-projection.ts) — deny rellena `reasonCode`
3. [`apps/web/src/features/mesa/daily-desk-inbox.tsx`](../../apps/web/src/features/mesa/daily-desk-inbox.tsx) — `data-reason-code`
4. [`apps/web/src/features/charts/chart-data-status-badge.tsx`](../../apps/web/src/features/charts/chart-data-status-badge.tsx) — `chart-data-status`
5. [`apps/web/src/features/trading/operativa-cockpit-card.tsx`](../../apps/web/src/features/trading/operativa-cockpit-card.tsx) — `data-execution-lifecycle`
6. [`apps/web/e2e/integration.ts`](../../apps/web/e2e/integration.ts) / [`fixtures.ts`](../../apps/web/e2e/fixtures.ts)
7. [`apps/web/e2e/gp-v175-chaos-stale-no-execute-mock.spec.ts`](../../apps/web/e2e/gp-v175-chaos-stale-no-execute-mock.spec.ts)
8. [`apps/web/e2e/gp-v176-certification-hardening-mock.spec.ts`](../../apps/web/e2e/gp-v176-certification-hardening-mock.spec.ts)
9. Docs cierre
