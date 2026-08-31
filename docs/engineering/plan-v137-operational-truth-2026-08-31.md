# Plan — V1.37 Operational Truth

> **Padre:** V1.36 [`plan-v136-daily-operating-ui-2026-08-31.md`](./plan-v136-daily-operating-ui-2026-08-31.md) · auditorías post-V1.36.  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO** (2026-08-31).

## Objetivo

Una sola proyección de posición abierta (`OperationalTruth`) para Mercado / Hoy / Journal / Operaciones. Cero divergencia de acción. Summary = estado; Plan = geometría.

## Entregables

| ID  | Entrega                                                                   | Estado          |
| --- | ------------------------------------------------------------------------- | --------------- |
| P0  | `OperationalTruthV1` + `buildOperationalTruth` (shared, no motor nuevo)   | CÓDIGO + vitest |
| P0  | Test coherencia mismas `action` / `protection` / `nextEvent` / `asOf`     | CÓDIGO          |
| P0  | Hoy inbox + fila + Operaciones leen `PositionDecision`, no `protect_hint` | CÓDIGO          |
| P1  | `PositionOperatingSummary` = estado (P&L, acción, recon, asOf)            | CÓDIGO          |
| P1  | `OperationalPlanView` apilado `omitLiveMetrics`                           | CÓDIGO          |

## Freeze intacto

Confirm = firma · Decision Spine · PositionState durable · ExitPlan / ExitPermission · gráfico no autoriza · backend operativo congelado · sin entry/T1/T2 drag · OCO · AUTO execute off.

`mapMesaNextAction` sigue para **candidatos** (sin posición). Posición abierta → `mesaNextActionFromDecision`.

## Hoja congelada (no código en este slice)

- **V1.38** Entry Operating UX (PREPARADA / DISPARADA / PROPUESTA; no BUY)
- **V1.39** Position Operating UX (una CTA primaria)
- **V1.40** Exit Management UX (ruta visual Entrada → Stop / T1 / T2)
- **V1.41** Daily Desk (Hoy quita paneles; inbox por `attention`)

## Criterios de cierre

- vitest `same-operational-truth-across-surfaces` GREEN
- `protect_hint` thin no fuerza PROTEGER si `PositionDecision` es HOLD
- web `tsc` OK
- Plan apilado omite precio actual y R abierto
