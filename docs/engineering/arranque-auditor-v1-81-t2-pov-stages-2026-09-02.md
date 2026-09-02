# Arranque auditor — V1.81 T2 POV Stages (2026-09-02)

> **Padre:** [`spec-v181-t2-pov-stages-2026-09-02.md`](./spec-v181-t2-pov-stages-2026-09-02.md) · partida **V1.80** [`7bd6ed81`](https://github.com/jvelasca/Bolsa_V1/commit/7bd6ed81) (docs tip [`3b5f10a0`](https://github.com/jvelasca/Bolsa_V1/commit/3b5f10a0))  
> **Estado slice:** **ABIERTA** (implementación en paralelo; tip/commit TBD; **sin stamp CI GREEN**).

## Punta de partida

- Producto previo: **V1.80** CI GREEN Tip Honesty — tag `v1.80-beta` → `7bd6ed81` · run 33644966298 GREEN
- Brecha: lifecycle V1.79 certifica hasta T1/TRAIL/EXIT; dominio ya tiene `T2_READY`/`T2_EXECUTED` (V1.57) **sin** stages mock E2E ni GP dedicado
- Regla: **0 COMPRAR** · `primaryAction` MONITOR (UI Mantener) **intencional** · **no** rediseño «GESTIONAR T2» · dryRun honesto

## Qué auditar

| Paso         | Evidencia                                                                                       |
| ------------ | ----------------------------------------------------------------------------------------------- |
| Partida tip  | V1.80 `7bd6ed81` / docs `3b5f10a0` · V1.81 tip/commit **TBD** hasta cierre                      |
| Stages       | `E2eGoldenPositionStage` incluye `t2_ready` \| `t2_executed` en `golden-session.ts`             |
| Overlays     | `fixtures.ts` overlays T2 · **sin** mega-split del archivo                                      |
| T2_READY     | `data-pov-state=T2_READY` · Mantener / mesa MONITOR · IDs AAPL · 0 COMPRAR                      |
| T2_EXECUTED  | `data-pov-state=T2_EXECUTED` · Mantener / MONITOR · evento T2 · remaining coherente · 0 COMPRAR |
| GP-V181-01   | Un test mock `gp-v181-t2-pov-stages-mock.spec.ts`                                               |
| CI filtro    | `release-tag-ci` `playwright-mock` incluye `\|gp-v181`                                          |
| Tip honesty  | `frontend-ci` **sin** Playwright · integrated sigue opt-in                                      |
| Freeze / OUT | NO LIVE · sin bump · sin `dryRun=false` · sin fills · sin EXIT_EXECUTED · sin desk CTA redesign |

## Pre-flight (esperado al cerrar)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v181
# → 1 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179|gp-v181"

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- CI GREEN remoto · LIVE · bump `1.35.0-beta`
- `dryRun=false` browser · scheduler prod · fills ledger
- Enum `EXIT_EXECUTED` · mega-split `fixtures.ts` · «GESTIONAR T2» CTA
