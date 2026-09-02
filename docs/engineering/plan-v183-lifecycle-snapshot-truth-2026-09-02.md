# Plan — V1.83 Lifecycle Snapshot Truth (mock E2E)

> **Padre:** [`spec-v183-lifecycle-snapshot-truth-2026-09-02.md`](./spec-v183-lifecycle-snapshot-truth-2026-09-02.md).  
> **Estado:** **CERRADA (código + E2E mock locales)** · stamp CI GREEN remoto **PENDIENTE** (`v1.83-beta`).  
> **Partida tip:** V1.82 [`d0ccf235`](https://github.com/jvelasca/Bolsa_V1/commit/d0ccf235) (tag `v1.82-beta`) · CI GREEN [run 33651647262](https://github.com/jvelasca/Bolsa_V1/actions/runs/33651647262).

| ID  | Entrega                                                         | Estado                           |
| --- | --------------------------------------------------------------- | -------------------------------- |
| D0  | spec GO + plan + respuesta auditor V1.82 + arranque             | **DONE**                         |
| P0  | `helpers/lifecycle-snapshot.ts` (SoT + lineage + invariantes)   | **DONE**                         |
| P0  | `applyGoldenPositionStage` proyección con prefijo trail/T2      | **DONE**                         |
| P0  | `e2e-mock-routes` lifecycleDesk desde snapshot (equity única)   | **DONE**                         |
| P0  | GP-V183-01/02 + CLOSED lineage en GP-V179/V181                  | **DONE**                         |
| P0  | `release-tag-ci.yml` filtro `+= \|gp-v183`                      | **DONE**                         |
| P1  | Pre-flight filtro CI · `tsc --noEmit` · docs CURRENT_SYSTEM §52 | **DONE** (35 passed · 3 skipped) |
| —   | Stamp CI GREEN remoto vía tag `v1.83-beta`                      | **PENDIENTE**                    |

## Secuencia (ejecutada)

1. Capturar auditoría V1.82 (P1 lineage / invariantes / snapshot).
2. Snapshot canónico + `lineagePath` en runtime.
3. EXIT_REQUIRED/CLOSED heredan prefijo; CLOSED añade `POSITION_CLOSED`.
4. Rutas lifecycle derivan portfolio/summary/desk del snapshot.
5. Recalibrar R a fórmula; GP-V183 + filtro CI.
6. Pre-flight local · cierre docs. Tag remoto = paso posterior.

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · `dryRun=false` browser · fills ledger
- Event-driven POST→persist→GET · integrated E2E obligatorio
- Playwright en `frontend-ci` · `/portfolio` open-only · CTA «GESTIONAR T2»
- Commitear `**/logs/`
