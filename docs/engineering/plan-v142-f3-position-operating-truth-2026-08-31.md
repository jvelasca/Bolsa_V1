# Plan — V1.42 F3 PositionOperatingTruth + §A.8

> **Padre:** [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) §A.5 · §A.8 · [ADR-042](../adr/042-operating-excellence.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (2026-08-31).

## Objetivo

Proyección canónica `PositionOperatingTruth` (compone `OperationalTruth` + `ExecutionState` + protect/route). CTA: `full_exit`/`reduce` ganan a `protectionDiscrepancy` (§A.8); discrepancia = secundaria.

## Entregables

| ID  | Entrega                                                     | Estado          |
| --- | ----------------------------------------------------------- | --------------- |
| F3  | `mapMesaNextAction` §A.8 priority flip                      | CÓDIGO + vitest |
| F3  | `position-operating-truth.ts` + golden / same-surfaces      | CÓDIGO + vitest |
| F3  | Thin wire: summary · Mesa · Operaciones · cockpit · Journal | CÓDIGO          |

## Freeze intacto

Confirm = firma · Spine · `PAPER_D_EXECUTE` off · AUTO execute off · sin TradeStory / Mercado 2.0 / Hoy cubos · hint trail ≠ `currentStop`.

## Criterios de cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/mesa-next-action.test.ts src/cognitive/position-operating-truth.test.ts src/cognitive/position-operating-truth-golden-path.test.ts src/cognitive/same-position-operating-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/decision-journal/decision-ficha-panel.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```
