# Relevo — V1.70 LISTA→GRÁFICO→ACCIÓN

> **AsOf:** 2026-09-02 · **Estado:** CERRADA · **Auditor:** [`arranque-auditor-v1-70-lista-grafico-accion-2026-09-02.md`](./arranque-auditor-v1-70-lista-grafico-accion-2026-09-02.md)

## Hecho

- Click fila lista → `focusInstrumentInMercado` (gráfico + DECISIÓN + `/trading`)
- Resolver compartido `resolveInstrumentOperationalFacts` (lista ↔ cockpit)
- POV fail-closed (sin fallback cliente)
- E2E GP-V170 mock + integrado (3 tests)
- CI integrado opt-in: `gp-v170-list` en `release-tag-ci.yml`
- Hardening mock Mercado: layout context hidratación + fixtures `meta`

## Pre-flight

Ver spec §3 y arranque auditor.

## Next candidato

Post-V1.70 aparcado: bump package · HUD chart unification residual · NO LIVE.
