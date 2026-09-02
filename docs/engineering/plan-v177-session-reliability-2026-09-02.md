# Plan — V1.77 Session Reliability / Operational Truth

> **Padre:** [`spec-v177-session-reliability-2026-09-02.md`](./spec-v177-session-reliability-2026-09-02.md).  
> **Estado:** **CERRADA** — E2E mock GP-V177-01..07 · helper truth · flags mutables.

| ID  | Entrega                                                                               | Estado   |
| --- | ------------------------------------------------------------------------------------- | -------- |
| D0  | spec GO + plan                                                                        | **DONE** |
| P0  | Helpers assert operational truth (IDs · phase · levels · primaryAction · WHY · recon) | **DONE** |
| P0  | Fixture/mocks journey: multi + stale inject/recovery + UNKNOWN + recon drift → clean  | **DONE** |
| P0  | GP-V177-01 A→B→C→A identidad + verdad operativa                                       | **DONE** |
| P0  | GP-V177-02 refresh integrity + verdad operativa                                       | **DONE** |
| P0  | GP-V177-03 stale transition · 0 COMPRAR · IDs                                         | **DONE** |
| P1  | GP-V177-04 recovery post-stale sin inventar COMPRAR                                   | **DONE** |
| P1  | GP-V177-05 UNKNOWN aislado en journey                                                 | **DONE** |
| P1  | GP-V177-06 recon drift · REVISAR · 0 COMPRAR                                          | **DONE** |
| P1  | GP-V177-07 back to clean                                                              | **DONE** |
| P2  | GP-V177-08 (opt) nits V1.76                                                           | SKIP     |
| P1  | Spec mock `gp-v177-session-reliability-mock.spec.ts` + pre-flight verde local         | **DONE** |
| P1  | Cierre: auditor · relevo · CURRENT_SYSTEM · engineering-index                         | **DONE** |

## Orden de implementación recomendado

1. **Assert helper** reutilizable (extender patrón `assertPositionIdentity` de GP-V173): identidad + `data-phase` + stop/T1/T2 + `data-trade-plan-id`/`data-decision-id` + `primaryAction`/CTA + recon + WHY-si-presente + **0 COMPRAR**.
2. **GP-V177-01** sobre `installMercadoMultiApiMocks` / slices V1.73 (baseline identity → truth).
3. **GP-V177-02** refresh (mismo helper post-reload).
4. **GP-V177-03 + 04**: inyectar/recuperar stale en Mercado (y/o puente Hoy) sin contaminar multi; reusar `installHoyStaleNoExecuteMocks` / data-status echo V1.76 donde encaje.
5. **GP-V177-05**: cablear tramo UNKNOWN aislado (`hoyUnknown` / lifecycle) **después** de recovery, sin mezclar con stale.
6. **GP-V177-06 + 07**: mock recon drift → clean; asertar `data-recon` y ausencia de COMPRAR.
7. **GP-V177-08** solo si sobra capacidad post-P1.
8. Regresión `gp-v173` · `gp-v174` · `gp-v175` · `gp-v176` · `tsc --noEmit`.

## Entregables (implementación)

1. [`apps/web/e2e/integration.ts`](../../apps/web/e2e/integration.ts) — helpers journey / assert truth (**extender**, no mega-split)
2. [`apps/web/e2e/fixtures.ts`](../../apps/web/e2e/fixtures.ts) — mocks staged (stale ↔ current · UNKNOWN · recon drift)
3. [`apps/web/e2e/gp-v177-session-reliability-mock.spec.ts`](../../apps/web/e2e/gp-v177-session-reliability-mock.spec.ts) — GP-V177-01..07 (+08 opt)
4. Docs cierre (auditor · relevo · CURRENT_SYSTEM · engineering-index) — **no** en esta apertura

## OUT (plan)

- Golden MERCADO→EXIT completo → **V1.78+**
- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump package · `dryRun=false` browser
- Rewrite motor / Decision Engine
- Split masivo `integration.ts` (salvo necesidad P2 posterior)
- Stamp CI GREEN remoto

## Pre-flight (cuando exista código)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v177
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v173
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v175
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v176
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v174
pnpm --filter @bolsa/web exec tsc --noEmit
```
