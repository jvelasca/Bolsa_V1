# Plan — V1.81 T2 POV Stages (mock E2E)

> **Padre:** [`spec-v181-t2-pov-stages-2026-09-02.md`](./spec-v181-t2-pov-stages-2026-09-02.md).  
> **Estado:** **ABIERTA** — tip/commit TBD · **sin stamp CI GREEN**.  
> **Partida tip:** V1.80 [`7bd6ed81`](https://github.com/jvelasca/Bolsa_V1/commit/7bd6ed81) · docs tip [`3b5f10a0`](https://github.com/jvelasca/Bolsa_V1/commit/3b5f10a0).

| ID  | Entrega                                                                               | Estado      |
| --- | ------------------------------------------------------------------------------------- | ----------- |
| D0  | spec GO + plan + arranque auditor                                                     | **DONE**    |
| P0  | `E2eGoldenPositionStage` += `t2_ready` \| `t2_executed` (`golden-session.ts`)         | **IN PROG** |
| P0  | Overlays T2 en `fixtures.ts` (sin mega-split)                                         | **IN PROG** |
| P0  | GP-V181-01 `gp-v181-t2-pov-stages-mock.spec.ts` (AAPL · MONITOR/Mantener · 0 COMPRAR) | **IN PROG** |
| P0  | `release-tag-ci.yml` `playwright-mock` filtro `+= \|gp-v181`                          | **PENDING** |
| P1  | Cierre: relevo · CURRENT_SYSTEM · engineering-index + pre-flight local                | **PENDING** |
| —   | Stamp CI GREEN remoto                                                                 | **OUT**     |

## Secuencia

1. Extender stages golden + `applyGoldenPositionStage` para T2 (post `t1_executed`).
2. Overlays mínimos en `fixtures.ts` — **no** reorganizar el archivo.
3. Un test mock GP-V181-01: T1_EXECUTED → T2_READY → T2_EXECUTED · identidad AAPL.
4. Ampliar filtro `playwright-mock` con `|gp-v181`.
5. Pre-flight local · cierre docs (tip/commit al cerrar).

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · `dryRun=false` browser · fills ledger
- Enum `EXIT_EXECUTED` · desk CTA «GESTIONAR T2» · rewrite motor
- Mega-split `fixtures.ts` (candidato **V1.82**)
- Playwright en cada PR (`frontend-ci`) · integrated E2E obligatorio
- Stamp CI GREEN remoto en esta apertura
