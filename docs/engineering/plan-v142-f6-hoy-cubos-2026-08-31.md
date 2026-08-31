# Plan — V1.42 F6 Hoy 2.0 cuatro cubos

> **Padre:** [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) §B.7 · [ADR-042](../adr/042-operating-excellence.md) · F5 [`plan-v142-f5-mercado-decision-2026-08-31.md`](./plan-v142-f5-mercado-decision-2026-08-31.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (2026-08-31).

## Objetivo

Hoy = command center con **cuatro cubos** §B.7. Misma CTA/frase que Mercado (POT/EOT). No DailyEngine. No segundo Mercado. Cobertura / Ranking / Libro / Decisiones / Consola detrás de «Ver detalles».

## Entregables

| ID  | Entrega                                                       | Estado |
| --- | ------------------------------------------------------------- | ------ |
| F6  | `daily-desk.ts` — proyección a 4 buckets + phrase/CTA         | CÓDIGO |
| F6  | Web: `DailyDeskInbox` / `mesa-hoy-view` / `mesa-hoy-page`     | CÓDIGO |
| F6  | vitest shared + web · `tsc` web                               | CÓDIGO |
| F6  | Docs plan + relevo · stamp CURRENT_SYSTEM / spec §D / ADR-042 | CÓDIGO |

## Freeze intacto

Confirm = firma · Router · `PAPER_D_EXECUTE` off · AUTO execute off · sin LIVE thaw · `protect_hint` ≠ autoridad · Ranking ≠ BUY · sin F7 SEMI productization · sin F8 AUTO · sin OpportunityScore · sin nav L1 · sin segundo Mercado.

## Criterios de cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/daily-desk.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/mesa/daily-desk-inbox.test.tsx src/features/mesa/mesa-hoy-view.test.ts src/features/mesa/mesa-hoy-page.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```
