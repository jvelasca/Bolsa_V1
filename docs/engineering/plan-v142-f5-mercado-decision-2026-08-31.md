# Plan — V1.42 F5 Mercado 2.0 panel DECISIÓN

> **Padre:** [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) §B · [ADR-042](../adr/042-operating-excellence.md) · [diseño](./diseno-mercado-2-0-cockpit-2026-08-27.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CÓDIGO** (2026-08-31).

## Objetivo

Chrome de producto **DECISIÓN** (no Operativa). Panel CONTEXTO → ESTADO → ACCIÓN consumiendo truths existentes. Una CTA primaria. Confirm = firma. Sin motores nuevos. Sin F6/F7/F8.

## Entregables

| ID  | Entrega                                                               | Estado |
| --- | --------------------------------------------------------------------- | ------ |
| F5  | Chrome DECISIÓN (layout · top-bar · panel aria · HELP · queue origin) | CÓDIGO |
| F5  | Cockpit CONTEXTO→ESTADO→ACCIÓN + 1 CTA + ¿Por qué? colapsado          | CÓDIGO |
| F5  | POT `primaryCtaKind` en PositionExitDrawerActions (paridad Hoy)       | CÓDIGO |
| F5  | Copy B.4 vigilar «Esperando disparador»                               | CÓDIGO |

## Freeze intacto

Confirm = firma · Router · `PAPER_D_EXECUTE` off · AUTO execute off · sin LIVE thaw · `protect_hint` ≠ autoridad · sin F6 cubos · sin F7 SEMI productization · sin F8 AUTO · sin OpportunityEngine / DailyEngine · sin segundo Mercado · sin nav L1.

## Criterios de cierre

```bash
pnpm --filter @bolsa/web exec vitest run src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/operativa-cockpit-phase.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```
