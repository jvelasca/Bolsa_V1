# Plan — V1.40 Exit Management UX

> **Padre:** V1.39 [`plan-v139-position-operating-ux-2026-08-31.md`](./plan-v139-position-operating-ux-2026-08-31.md) · auditorías post-V1.39.  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO** (2026-08-31).

## Objetivo

Una sola ruta visual de salida (`ExitRouteView`) para posición abierta: Entrada → Stop (proteger) / T1 / T2 (trailing). Mercado / Hoy / Journal / Operaciones leen los mismos nodos y roles.

## Entregables

| ID  | Entrega                                                              | Estado          |
| --- | -------------------------------------------------------------------- | --------------- |
| P0  | `ExitRouteViewV1` + `buildExitRouteView` (shared)                    | CÓDIGO + vitest |
| P0  | Test coherencia mismas labels / roles / values en cuatro superficies | CÓDIGO          |
| P1  | Componente `ExitRouteView` (web)                                     | CÓDIGO          |
| P1  | Cockpit POSICIÓN + Journal ficha + `PositionRoutePanel`              | CÓDIGO          |
| P1  | T1 tocado ≠ gestionado · T2 trailing cuando `plan.trailingActive`    | CÓDIGO          |

## Freeze intacto

Confirm = firma · backend operativo congelado · OperationalTruth / EntryOperatingTruth intactos · sin drag exit · AUTO execute off.

## Hoja congelada (no código en este slice)

- **V1.41** Daily Desk (Hoy quita paneles; inbox por `attention`)

## Criterios de cierre

- vitest `same-exit-route-across-surfaces` GREEN
- Stop roleLabel = «Proteger» · T2 trailing cuando MFE ≥ umbral
- web `tsc` OK
- T1 touched no muestra «✓ gestionado» sin sello
