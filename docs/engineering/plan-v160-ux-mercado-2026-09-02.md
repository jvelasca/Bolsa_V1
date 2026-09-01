# Plan — V1.60 UX Mercado (tarjeta estrella DECISIÓN)

> **Padre:** [`spec-v160-ux-mercado-2026-09-02.md`](./spec-v160-ux-mercado-2026-09-02.md) · [ADR-042](../adr/042-operating-excellence.md).  
> **AsOf:** 2026-09-02.  
> **Estado:** **PLAN** — partida **`v1.59-beta` → `b5c5c6ab`**. Tag `v1.60-beta` pendiente.

| ID  | Entrega                                           | Estado |
| --- | ------------------------------------------------- | ------ |
| D0  | spec/plan V1.60                                   | DONE   |
| P0a | POV wiring en `operativa-cockpit-card` GP-V160-01 | TODO   |
| P0b | T2 + RECONCILIATION_DRIFT copy/fase GP-V160-02    | TODO   |
| P1a | stopHistory colapsable GP-V160-03                 | TODO   |
| P1b | vitest + testids GP-V160-04                       | TODO   |
| R1  | relevo + arranque auditor + pre-flight            | TODO   |

## Orden de implementación

1. **P0a** — Helper `usePositionOperationalView(instrumentId)` o inline desde context + blob; tarjeta estrella lee POV cuando `phase === "posicion"`.
2. **P0b** — Mapear `operatingState` a label fase/copy (`T2_READY`, `T2_EXECUTED`, `RECONCILIATION_DRIFT`); alinear chip recon existente.
3. **P1a** — Sub-sección stop history (colapsable); reutilizar labels de `buildStopHistory`.
4. **P1b** — Tests componente + testids auditor.
5. **R1** — relevo + arranque al cerrar.

## Criterios de cierre

Bloque pre-flight spec §5 verde · una CTA primaria intacta · Confirm = única firma · V1.59 integration **7/7** sin regresión.

## No hacer

LIVE · bump package · drag gráfico · segundo Mercado · motores nuevos · cambiar Golden Session · Playwright CI job nuevo.
