# Plan — V1.82 Fixtures Split (higiene E2E mock)

> **Padre:** [`spec-v182-fixtures-split-2026-09-02.md`](./spec-v182-fixtures-split-2026-09-02.md).  
> **Estado:** **CERRADA** (código + pre-flight) · stamp CI GREEN remoto **PENDING** (`v1.82-beta`).  
> **Partida tip:** V1.81 [`4fcfc9bb`](https://github.com/jvelasca/Bolsa_V1/commit/4fcfc9bb) (tag `v1.81-beta`) · docs [`4d7120cf`](https://github.com/jvelasca/Bolsa_V1/commit/4d7120cf) · handoff [`3fcc8ade`](https://github.com/jvelasca/Bolsa_V1/commit/3fcc8ade) · CI GREEN [run 33648642728](https://github.com/jvelasca/Bolsa_V1/actions/runs/33648642728).

| ID  | Entrega                                                             | Estado   |
| --- | ------------------------------------------------------------------- | -------- |
| D0  | spec GO + plan + arranque auditor                                   | **DONE** |
| P0  | `helpers/e2e-mock-runtime.ts` (enable + flags + workspace override) | **DONE** |
| P0  | `helpers/e2e-mock-routes.ts` (`routeBody` + HTTP helpers)           | **DONE** |
| P0  | `helpers/e2e-mock-installers.ts` (`install*`)                       | **DONE** |
| P0  | `fixtures.ts` → barrel (API pública estable)                        | **DONE** |
| P1  | Pre-flight mismo filtro CI → 33 passed (3 skipped) · `tsc --noEmit` | **DONE** |
| P1  | Cierre docs: relevo · CURRENT_SYSTEM · engineering-index §51        | **DONE** |
| —   | Stamp CI GREEN remoto vía tag `v1.82-beta` / Actions + pre-release  | PENDING  |

## Secuencia (ejecutada)

1. Extraer runtime → `e2e-mock-runtime.ts`.
2. Mover `routeBody` + HTTP → `e2e-mock-routes.ts`.
3. Mover `install*` → `e2e-mock-installers.ts`.
4. `fixtures.ts` barrel.
5. Pre-flight filtro V1.81 → **33 passed** · cierre docs · tag `v1.82-beta` · stamp remoto.

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · `dryRun=false` browser · fills ledger
- Cambiar asserts / stages / filtro CI (`|gp-v182` no obligatorio)
- Playwright en `frontend-ci` · integrated E2E obligatorio
- Commitear `**/logs/`
