# Plan — Mesa · Hoy V1.15 (Operational UX)

> **ADR:** [`037-mesa-hoy-operational-ux.md`](../adr/037-mesa-hoy-operational-ux.md)  
> **AsOf:** 2026-08-26  
> **Estado:** Implementado

---

## Objetivo

Unificar la UX operativa diaria en `/mesa` componiendo Decision Board, portfolio, studies e incidentes — sin endpoints nuevos ni cambios al core.

## Entregables

| ID  | Entrega                                  | Archivos clave                                             |
| --- | ---------------------------------------- | ---------------------------------------------------------- |
| P1  | Shell Mesa + nav                         | `mesa-hoy-page.tsx`, `daily-nav.ts`, `app.tsx`             |
| P2  | Posiciones comprimidas                   | `mesa-position-row.tsx`, `mesa-positions-summary.tsx`      |
| P3  | Candidatos enriquecidos                  | `mesa-candidates-panel.tsx`, `mesa-hoy-model.ts`           |
| P4  | Deep-links Journal                       | `mesa-nav-links.ts`, `decision-journal-page.tsx`           |
| UX  | Tabla Journal simplificada               | `journal-studies-table.tsx`, `SIMPLE_JOURNAL_STUDY_LAYOUT` |
| Nav | Consola → Herramientas; Hoy strip → Mesa | `app-top-bar.tsx`, `hoy-command-strip.tsx`                 |

## Tests

- `packages/shared/src/cognitive/mesa-hoy-model.test.ts`
- `packages/shared/src/cognitive/mesa-status-dimensions.test.ts`
- `apps/web/src/features/confirm/daily-nav.test.ts`
- `apps/web/src/features/mesa/mesa-hoy-page.test.ts`

## Freeze V1.15

DecisionPackage · TradePlan · Position · Confirm · SubmitIntent · incident lifecycle · `mapJournalStudyStatus` enum.
