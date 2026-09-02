# Plan — V1.79 Stateful Position Lifecycle Certification

> **Padre:** [`spec-v179-stateful-position-lifecycle-2026-09-02.md`](./spec-v179-stateful-position-lifecycle-2026-09-02.md).  
> **Estado:** **CERRADA** — split helpers · stages stateful · GP-V179-01.

| ID  | Entrega                                                                              | Estado   |
| --- | ------------------------------------------------------------------------------------ | -------- |
| D0  | spec GO + plan + arranque auditor                                                    | **DONE** |
| P0  | Split `integration.ts` → `e2e/helpers/*` + barrel                                    | **DONE** |
| P0  | Stages `t1_executed` / `closed` + identidad AAPL + installer lifecycle               | **DONE** |
| P0  | Capas `assertIdentityTruth` / `assertFinancialTruth` / `assertPositionCertification` | **DONE** |
| P0  | GP-V179-01 un test stateful (~120s timeout)                                          | **DONE** |
| P1  | Recovery: deny stale ausente                                                         | **DONE** |
| P1  | CLOSED: portfolio + Journal + 0 COMPRAR                                              | **DONE** |
| P1  | Cierre: relevo · CURRENT_SYSTEM · engineering-index + pre-flight local               | **DONE** |

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · `dryRun=false` browser
- Enum `EXIT_EXECUTED` · T2 obligatorio · rewrite motor
- Stamp CI GREEN remoto
- Cambiar `hasOpenPositionQuantity`
