# Spec — V1.68 Paper Autonomous Desk (Hoy wire + E2E)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v167-browser-e2e-mercado-integrated-2026-09-02.md`](./spec-v167-browser-e2e-mercado-integrated-2026-09-02.md) · partida **V1.67** (`fbce4999`). **No** LIVE.

Cierra el wire **PaperDeskCycle → autoDesk → Hoy inbox** en runtime y certifica el journey en navegador. Complementa V1.54 (proyección shared + vitest) y V1.59 (pytest HTTP cycle).

```text
P0  GP-V168-01 — Hoy /mesa carga daily-desk-inbox con autoDesk real
P0  GP-V168-02 — Sin CTA COMPRAR indebido
P0  GP-V168-03 — Cinco cubos Daily Desk visibles
P0  GP-V168-04 — AUTO posture honesta (arm ≠ execute) cuando hay candidatos
P1  GP-V168-05 — pytest seed harness daily-report + cycle dry-run
P1  GP-V168-06 — api.getPaperDeskDailyReport + mesa-hoy-page wire
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package · V1.67 intacto · no execute dryRun=false · no scheduler.

## 1. IN

| ID         | Comportamiento                                                                                      |
| ---------- | --------------------------------------------------------------------------------------------------- |
| GP-V168-01 | Playwright `/mesa` sin mocks · `mesa-hoy-page` + `daily-desk-inbox` + `daily-desk-buckets`          |
| GP-V168-02 | Sin botón primario `COMPRAR` en Hoy                                                                 |
| GP-V168-03 | Cubos `requiere_accion` · `proteger` · `posiciones` · `oportunidades` · `no_operar`                 |
| GP-V168-04 | `autoDesk` presente · badge `AUTO armado · ejecución off` si hay proposed · sin execute CTA         |
| GP-V168-05 | pytest GET `/paper-desk/daily-report` + POST cycle dryRun                                           |
| GP-V168-06 | `mesa-hoy-page` usa `getPaperDeskDailyReport` (dry-run evaluate) en lugar de daily-ops sin autoDesk |

## 2. OUT

`dryRun=false` execute · LIVE · scheduler · redesign Daily Desk · CI Playwright Release-tag obligatorio · LISTA→GRÁFICO→ACCIÓN.

## 3. Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/daily-desk-auto-projection.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/mesa/daily-desk-inbox.test.tsx src/features/mesa/mesa-hoy-page.test.ts
python -m pytest apps/api-python/tests/integration/test_v168_hoy_e2e_seed.py -m integration -q
E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v168-hoy
pnpm --filter @bolsa/web exec tsc --noEmit
```
