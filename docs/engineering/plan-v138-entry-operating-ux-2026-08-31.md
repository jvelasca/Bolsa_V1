# Plan — V1.38 Entry Operating UX

> **Padre:** V1.37 [`plan-v137-operational-truth-2026-08-31.md`](./plan-v137-operational-truth-2026-08-31.md) · auditorías post-V1.37.  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO** (2026-08-31).

## Objetivo

Una sola proyección pre-posición (`EntryOperatingTruth`) para Mercado / Hoy / Journal en fases PREPARADA → CONFIRMADA. Summary = estado de entrada; Plan = geometría. Ranking ≠ BUY.

## Entregables

| ID  | Entrega                                                           | Estado          |
| --- | ----------------------------------------------------------------- | --------------- |
| P0  | `EntryOperatingTruthV1` + `buildEntryOperatingTruth` (shared)     | CÓDIGO + vitest |
| P0  | `mercado-cockpit-phase.ts` en shared (fuente única de fase)       | CÓDIGO          |
| P0  | Test coherencia mismas `phase` / `ctaLabel` / niveles / frase     | CÓDIGO          |
| P0  | CTAs unificados: Preparar · Revisar y confirmar · Ver operaciones | CÓDIGO          |
| P1  | `EntryOperatingSummary` en cockpit + Journal ficha                | CÓDIGO          |
| P1  | Hoy candidatos vía `mapCandidateNextAction` → entry truth         | CÓDIGO          |

## Freeze intacto

Confirm = firma · backend operativo congelado · sin drag entry · AUTO execute off · OperationalTruth para posición abierta intacto.

## Hoja congelada (no código en este slice)

- **V1.39** Position Operating UX (una CTA primaria)
- **V1.40** Exit Management UX (ruta visual Stop/T1/T2)
- **V1.41** Daily Desk (Hoy quita paneles)

## Criterios de cierre

- vitest `same-entry-operating-truth-across-surfaces` GREEN
- disparada ≠ «Confirmar» suelto — «Revisar y confirmar»
- web `tsc` OK
- Ningún label BUY/COMPRAR en CTAs de entrada
