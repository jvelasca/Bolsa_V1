# Plan — V1.61 Market Decision Surface (posición)

> **Padre:** [`spec-v161-market-decision-surface-2026-09-02.md`](./spec-v161-market-decision-surface-2026-09-02.md) · [ADR-042](../adr/042-operating-excellence.md).  
> **AsOf:** 2026-09-02.  
> **Estado:** **CERRADA** — partida **`v1.60-beta` → `7ac8ad9b`**.

| ID  | Entrega                                         | Estado |
| --- | ----------------------------------------------- | ------ |
| D0  | spec/plan V1.61                                 | DONE   |
| P0a | recon fail-closed shared + GP-V161-01           | DONE   |
| P0b | Decision Surface 3 niveles + tono GP-V161-02/03 | DONE   |
| P1a | hook source canonical/fallback                  | DONE   |
| P1b | GP-V161-04..06 honesty + cross-surface          | DONE   |
| R1  | relevo + arranque auditor + pre-flight          | DONE   |

## Orden de implementación

1. **P0a** — `mapPortfolioReconToPovRecon` en `@bolsa/shared`; coerce en `buildPositionOperationalView`.
2. **P0b** — Evolucionar `position-operational-star-card` → Decision Surface; cockpit sin Summary/Plan en posición.
3. **P1a** — `{ view, source }` en hook; chip DEV fallback.
4. **P1b** — Tests GP-V161-04..06; actualizar GP-V160 compat.
5. **R1** — pre-flight + relevo.

## Criterios de cierre

Pre-flight spec §4 verde · GP-V160-01..04 intactos · una CTA primaria · Confirm = única firma · V1.59 integration **7/7** sin regresión.

## No hacer

LIVE · bump package · EntryOperationalView · Playwright CI · DTO Python POV · segundo Mercado.
