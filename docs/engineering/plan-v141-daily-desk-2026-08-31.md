# Plan — V1.41 Daily Desk

> **Padre:** V1.40 [`plan-v140-exit-management-ux-2026-08-31.md`](./plan-v140-exit-management-ux-2026-08-31.md) · auditorías post-V1.40.  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO** (2026-08-31).

## Objetivo

Hoy = inbox único ordenado por `attention` (Daily Desk). Quita paneles de ranking/KPI del chrome. No segundo Mercado. Oportunidades / Libro / Decisiones / Consola detrás de «Ver detalles».

## Entregables

| ID  | Entrega                                                              | Estado          |
| --- | -------------------------------------------------------------------- | --------------- |
| P0  | `DailyDeskInboxV1` + `buildDailyDeskInbox` (shared)                  | CÓDIGO + vitest |
| P0  | Inbox = pending confirm + posiciones por attention + board attention | CÓDIGO          |
| P1  | `DailyDeskInbox` UI — un bloque «Requiere atención»                  | CÓDIGO          |
| P1  | Hoy resumen: sin Oportunidades / Vigilar / Sin acción / KPIs         | CÓDIGO          |
| P1  | Footer compacto + Oportunidades en «Ver detalles»                    | CÓDIGO          |

## Freeze intacto

Confirm = firma · backend operativo congelado · OperationalTruth / EntryOperatingTruth / ExitRoute intactos · sin drag · AUTO execute off.

## Criterios de cierre

- vitest `daily-desk` GREEN
- chrome Hoy sin `MesaOpportunitiesTeaser` / `MesaWatchList` / KPI cobertura
- HOLD limpio → inbox vacío
- web `tsc` OK
- Ningún CTA BUY/COMPRAR en Daily Desk
