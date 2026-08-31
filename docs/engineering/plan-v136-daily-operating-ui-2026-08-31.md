# Plan — V1.36 Daily Operating UI

> **Padre:** V1.35 [`plan-v135-position-operating-hardening-2026-08-31.md`](./plan-v135-position-operating-hardening-2026-08-31.md) · auditorías post-`v1.34.1-beta`.  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO** (2026-08-31).

## Objetivo

UI operativa diaria en Mercado: separar **próximo evento** vs **protección**, frase humana read-only, honestidad semántica stop operativo ≠ broker.

## Entregables

| ID  | Entrega                                                                  | Estado slice 1  |
| --- | ------------------------------------------------------------------------ | --------------- |
| S1  | `positionStateFromPositionDto` + `formatPositionDecisionPhrase` (shared) | CÓDIGO + vitest |
| S1  | `PositionOperatingSummary` en `OperativaCockpitCard` (fase POSICIÓN)     | CÓDIGO          |
| S1  | Label «Stop operativo» en `OperationalPlanView`                          | CÓDIGO          |
| S2  | Acciones MANTENER · PROTEGER · REDUCIR · SALIR alineadas con `action`    | CÓDIGO          |
| S2  | Hoy / Journal mismo resumen operativo                                    | CÓDIGO          |
| S3  | Tests integración cockpit POSICIÓN (vitest)                              | CÓDIGO          |

## Freeze intacto

Confirm = firma · gráfico no autoriza · backend operativo congelado · sin entry/T1/T2 drag · OCO · AUTO execute off.

## Criterios de cierre

- web `tsc` OK
- vitest `position-decision-copy` GREEN
- Cockpit POSICIÓN muestra frase + próximo evento + protección
- Copy stop ≠ «broker colocado» en toda la UI operativa
