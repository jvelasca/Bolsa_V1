# Plan — UI Mesa incidente DEX-3 (2026-08-26)

> **Padre:** [ADR-035](../adr/035-operational-reliability.md) · [plan DEX-3](./plan-dex3-operational-incident-2026-08-26.md).
> **AsOf:** 2026-08-26 · tag vivo `v1.13-beta`.
> **Estado:** M0–M4 **CERRADOS**. **No** reabre DEX-1…5 ni Confirm.

## Objetivo

Exponer workflow DEX-3 (OperationalIncident) vía HTTP mínimo + banner Mesa con resolve/clear humano.

## Fases

| ID  | Entrega                                                          |
| --- | ---------------------------------------------------------------- |
| M0  | GET active incidents + DTOs + `contract:gen` + tests API         |
| M1  | `MesaIncidentBanner` read-only en `mesa-operational-bar` + tests |
| M2  | POST resolve + form nota + tests API/UI                          |
| M3  | POST clear con recon gate + UI disabled states + tests           |
| M4  | plan/relevo + help copy + spine **483**                          |

## Fuera de alcance

Auto-heal · mutar libros · historial completo · Operational Console · reabrir Confirm/DEX.

## Verificación

- `test_operational_incident_api.py`
- `test_dex3_operational_incident.py` (regresión)
- web `mesa-incident-banner.test.tsx` + `mesa-operational-bar.test.tsx`
- `pnpm test:decision-spine` **483**
