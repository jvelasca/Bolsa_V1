# Plan — V1.39 Position Operating UX

> **Padre:** V1.38 [`plan-v138-entry-operating-ux-2026-08-31.md`](./plan-v138-entry-operating-ux-2026-08-31.md) · auditorías post-V1.38.  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO** (2026-08-31).

## Objetivo

Una sola CTA primaria por posición abierta, alineada a `OperationalTruth.primaryCta` (`decision.action`). Mercado / Hoy / Journal / Operaciones leen la misma etiqueta y kind. Summary = estado; Plan = geometría.

## Entregables

| ID  | Entrega                                                                | Estado          |
| --- | ---------------------------------------------------------------------- | --------------- |
| P0  | `PositionOperatingCtaV1` + `positionOperatingCtaFromDecision` (shared) | CÓDIGO + vitest |
| P0  | `OperationalTruthV1.primaryCta` + snapshot `ctaLabel` / `ctaKind`      | CÓDIGO + vitest |
| P0  | Test coherencia mismas CTA en Mercado/Hoy/Journal/Operaciones          | CÓDIGO          |
| P1  | `PositionOperatingSummary` ← `primaryCta`                              | CÓDIGO          |
| P1  | Cockpit POSICIÓN: `primaryOnly` (una CTA, no banda reduce/salir)       | CÓDIGO          |
| P1  | Operaciones + `MesaPositionRow` ← `truth.primaryCta`                   | CÓDIGO          |

## Freeze intacto

Confirm = firma · backend operativo congelado · EntryOperatingTruth intacto · sin drag entry/exit · AUTO execute off.

## Hoja congelada (no código en este slice)

- **V1.40** Exit Management UX (ruta visual Entrada → Stop / T1 / T2)
- **V1.41** Daily Desk (Hoy quita paneles; inbox por `attention`)

## Criterios de cierre

- vitest `same-operational-truth-across-surfaces` GREEN con `ctaLabel` / `ctaKind`
- cockpit POSICIÓN HOLD → solo «Mantener», sin Reducir/Salir secundarios
- web `tsc` OK
- protect_hint thin no fuerza CTA distinta de `decision.action`
