# Plan — V1.78 Session Golden MERCADO→EXIT

> **Padre:** [`spec-v178-session-golden-mercado-exit-2026-09-02.md`](./spec-v178-session-golden-mercado-exit-2026-09-02.md).  
> **Estado:** **CERRADA** — E2E mock GP-V178-01..08 · deskMode/positionStage · helpers POV.

| ID  | Entrega                                                                    | Estado   |
| --- | -------------------------------------------------------------------------- | -------- |
| D0  | spec GO + plan                                                             | **DONE** |
| P0  | Runtime flags: `deskMode` · `positionStage` + `installGoldenSessionMocks`  | **DONE** |
| P0  | Helper `assertPovStage` / entry candidato (extender `integration.ts`)      | **DONE** |
| P0  | GP-V178-01 MERCADO candidato NVDA                                          | **DONE** |
| P0  | GP-V178-02 Hoy ENTRY dryRun                                                | **DONE** |
| P0  | GP-V178-03 Hoy stale → recovery                                            | **DONE** |
| P0  | GP-V178-04 POSITION truth                                                  | **DONE** |
| P1  | GP-V178-05 T1_READY                                                        | **DONE** |
| P1  | GP-V178-06 TRAILING                                                        | **DONE** |
| P1  | GP-V178-07 recon → clean                                                   | **DONE** |
| P1  | GP-V178-08 EXIT_REQUIRED                                                   | **DONE** |
| P1  | Spec `gp-v178-session-golden-mercado-exit-mock.spec.ts` + pre-flight local | **DONE** |
| P1  | Cierre: auditor · relevo · CURRENT_SYSTEM · engineering-index              | **DONE** |

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · `dryRun=false` browser
- Rewrite motor / Decision Engine
- Stamp CI GREEN remoto
- T2 obligatorio
