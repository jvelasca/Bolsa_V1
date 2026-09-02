# Plan — V1.80 CI GREEN Tip Honesty (mock certification gate)

> **Padre:** [`spec-v180-ci-green-tip-honesty-2026-09-02.md`](./spec-v180-ci-green-tip-honesty-2026-09-02.md).  
> **Estado:** **CERRADA** · **stamp CI GREEN remoto DONE** — [`v1.80-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.80-beta) → [`7bd6ed81`](https://github.com/jvelasca/Bolsa_V1/commit/7bd6ed81) · [run 33644966298](https://github.com/jvelasca/Bolsa_V1/actions/runs/33644966298) **success**.  
> **Partida tip:** V1.79 [`8228d1c3`](https://github.com/jvelasca/Bolsa_V1/commit/8228d1c3).

| ID  | Entrega                                                                                 | Estado                           |
| --- | --------------------------------------------------------------------------------------- | -------------------------------- |
| D0  | spec GO + plan + arranque auditor                                                       | **DONE**                         |
| P0  | Expandir `release-tag-ci.yml` job `playwright-mock`: `gp-e2e` + `gp-v173\|…\|gp-v179`   | **DONE**                         |
| P0  | Verificar `certify` sigue needing `playwright-mock` (sin ampliar required a integrated) | **DONE**                         |
| P0  | Pre-flight local: un filtro `gp-e2e\|gp-v173\|…\|gp-v179` (mismo que CI)                | **DONE** (32 passed · 3 skipped) |
| P1  | Confirmar `frontend-ci.yml` sin Playwright (by design; sin diff salvo docs)             | **DONE**                         |
| P1  | Cierre: relevo · CURRENT_SYSTEM · engineering-index                                     | **DONE**                         |
| —   | Stamp CI GREEN remoto vía tag `v1.80-beta` / Actions                                    | **DONE** (run 33644966298)       |

## Secuencia (ejecutada)

1. Pre-flight local (mismo curado que CI) — un solo filtro.
2. Diff mínimo en `playwright-mock`: `pnpm e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179"`.
3. No tocar `frontend-ci.yml` · no forzar `playwright-integrated`.
4. Cierre docs + stamp remoto GREEN (`v1.80-beta` → `7bd6ed81`; 1ª tag falló ruff → fix + retag; playwright-mock ya GREEN).

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · `dryRun=false` browser · fills ledger
- T2 POV stages · split `fixtures.ts` · rewrite motor
- Playwright en cada PR (`frontend-ci`)
- Integrated E2E / PG obligatorio en cada certify
