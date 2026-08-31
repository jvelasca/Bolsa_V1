# Plan — V1.35 Position Operating Hardening

> **Padre:** auditorías externas post-`v1.34.1-beta` · [`traspaso-relevo-tag-v1-34-1-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-34-1-beta-2026-08-31.md).  
> **AsOf:** 2026-08-31.  
> **Estado:** **CERRADO (código + tests + docs).**

## Objetivo

Endurecer contratos operativos sin rediseñar el Decision Spine, antes de V1.36 (Daily Operating UI).

## Entregables

| ID  | Entrega                                                              |
| --- | -------------------------------------------------------------------- |
| P0  | TTL 30s + invalidación `signedStop` prefill B-γ                      |
| A6  | `sourcesShouldContract` alert-only (V1.33.4)                         |
| P1  | `PositionDecision`: `protection` ≠ `nextEvent`; confidence semántica |
| P1  | Journey tests J01–J06 + `pnpm test:operative-journeys`               |
| P1  | Contrato B-γ worsening-stop backend                                  |
| P1  | Esqueleto `OperatingPolicy` (InvestorProfile → políticas)            |
| P2  | Main tip ≠ Certified tip · package `1.35.0-beta`                     |

## Freeze intacto

Confirm = firma · gráfico no autoriza · `PAPER_D_EXECUTE` off · AUTO execute off · nav L1 · sin entry/T1/T2 drag · sin OCO · reversión A6 manual.

## Criterios de cierre

- `pnpm test:operative-journeys` 6/6 GREEN
- `pnpm test:decision-spine` GREEN
- web `tsc` OK
- Backend operativo **congelado** para V1.36
