# Plan — V1.42 F4 TradeStory

> **Padre:** [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) §A.6 · [ADR-042](../adr/042-operating-excellence.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (2026-08-31).

## Objetivo

Proyección canónica `TradeStory` (timeline idea→cierre). Journal consume; no segundo diario; no `TradeStoryEngine`.

## Entregables

| ID  | Entrega                                                        | Estado          |
| --- | -------------------------------------------------------------- | --------------- |
| F4  | `trade-story.ts` + golden / same-surfaces                      | CÓDIGO + vitest |
| F4  | Journal ficha «Historia de la operación» + page journalEntries | CÓDIGO          |

## Freeze intacto

Confirm = firma · Spine · `PAPER_D_EXECUTE` off · sin F5–F8 · sin inventar `asOf` · trail hint ≠ applied · Historial técnico intacto.

## Criterios de cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/trade-story.test.ts src/cognitive/trade-story-golden-path.test.ts src/cognitive/same-trade-story-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/decision-journal/decision-ficha-panel.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```
