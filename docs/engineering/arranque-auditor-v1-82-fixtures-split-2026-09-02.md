# Arranque auditor — V1.82 Fixtures Split (2026-09-02)

> **Padre:** [`spec-v182-fixtures-split-2026-09-02.md`](./spec-v182-fixtures-split-2026-09-02.md) · partida **V1.81** [`4fcfc9bb`](https://github.com/jvelasca/Bolsa_V1/commit/4fcfc9bb)  
> **Estado slice:** **CERRADA** (código + pre-flight local) · **stamp CI GREEN remoto** pendiente tras tag `v1.82-beta`.

## Punta de partida

- Producto previo: **V1.81** T2 POV Stages — tag `v1.81-beta` → `4fcfc9bb` · run 33648642728 GREEN · docs `4d7120cf` · handoff `3fcc8ade`
- Cierre V1.82: modularizar `fixtures.ts` → `helpers/e2e-mock-*` + barrel · **misma semántica**
- Gate: filtro `playwright-mock` **intacto** · **no** `gp-v182`
- Freeze: **NO LIVE** · no fills · no `dryRun=false` browser · no bump · no Playwright en `frontend-ci` · no integrated obligatorio

## Qué auditar

| Paso         | Evidencia                                                                                   |
| ------------ | ------------------------------------------------------------------------------------------- | -------- |
| Partida tip  | Tip código partida = `4fcfc9bb` (tag `v1.81-beta`) · docs `4d7120cf` / handoff `3fcc8ade`   |
| Barrel       | `fixtures.ts` ≈ re-exports (como `integration.ts`)                                          |
| Módulos      | `e2e-mock-runtime` · `e2e-mock-routes` · `e2e-mock-installers` bajo `apps/web/e2e/helpers/` |
| API pública  | Specs siguen `from "./fixtures"` · firmas `install*` / setters intactas                     |
| Semántica    | Pre-flight mismo filtro CI → **33 passed** (3 integrated skipped)                           |
| Tip honesty  | `frontend-ci` **sin** Playwright · integrated opt-in                                        |
| Filtro CI    | `release-tag-ci` `playwright-mock` **sin** `                                                | gp-v182` |
| Freeze / OUT | NO LIVE · sin bump · sin `dryRun=false` · sin fills · sin logs en commit                    |
| Remote GREEN | Pendiente — tag `v1.82-beta` → run success                                                  |

## Pre-flight (local 2026-09-02) — = CI

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179|gp-v181"
# → 33 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- LIVE · bump `1.35.0-beta` · `dryRun=false` browser · scheduler prod · fills ledger
- Cambio de semántica mock / asserts / stages
- Playwright en cada PR / integrated E2E obligatorio
- Stamp CI GREEN remoto sin run exitoso
