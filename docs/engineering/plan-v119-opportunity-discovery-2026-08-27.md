# Plan — V1.19 Opportunity Discovery + Mesa unificada

> **AsOf:** 2026-08-27 · **Baseline:** tag `v1.18-beta`.
> **Padre:** [ADR-039](../adr/039-portfolio-scenario-operational-priority.md) · [ADR-037](../adr/037-mesa-hoy-operational-ux.md) · [RFC-008](../rfc/008-cognitive-decision-architecture.md) · auditorías externas V1.18.
> **Estado:** implementado (contrato + Mesa L3 + scan opt-in + redirects Zona 1).

## Por qué

Mesa proyectaba `buildActionQueue(Decision Board)` — atención operativa, no ranking del universo. Los “3 candidatos” eran el subconjunto ya materializado en sesiones/F3, no las mejores oportunidades de HOY.

## Entrega

| Pieza                                          | Qué                                                                                                                                       |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `OpportunityFunnelV1` + `OpportunityRankingV1` | Funnel honesto (universo→screening→hits→analizadas→setup→encaje→operables) + categorías TOP / WATCH / NOT_FOR_PORTFOLIO / STALE / BLOCKED |
| Quality 0–100                                  | strength≤60 + R/R≤40; bandas Excelente…No atractiva; cableada a Priority Quality (sin TRIGGERED/hasPlan)                                  |
| Mesa L3                                        | «Mejores oportunidades para mi cartera» · TOP 5 · embudo · CTA Señales · umbral 75                                                        |
| Scan diario opt-in                             | `OPPORTUNITY_DAILY_SCAN_ENABLED=false` · list `ibex35` · propose cap 15 · cero execute                                                    |
| Zona 1                                         | `/operations` → `/mesa?focus=libro` · `/decision-board` → `/mesa?focus=spine`                                                             |

## Freeze

Ranking ≠ BUY · Confirm = firma · Opportunity ≠ Permission · Decision Board ≠ screener · `PAPER_D_EXECUTE` off · AUTO off · pesos Priority 35/35/30 · no `contract:gen`.

## Fuera de slice (V1.20+)

- OpportunityScore multiplicativo (expectancy histórica, régimen, correlación…)
- Motor TA+FA sobre 400+ nombres
- Endpoint Opportunity persistido / Alembic
- Rediseño Zonas 2–4

## DoD

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run opportunity-evidence opportunity-ranking operational-priority
pnpm --filter @bolsa/web test -- mesa-candidates mesa-hoy daily-nav decision-board
# Python
pytest packages/py/application/tests/test_opportunity_daily_discovery.py -q
```
