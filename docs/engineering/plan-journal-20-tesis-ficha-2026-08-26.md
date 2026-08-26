# Plan — Decision Journal 2.0 Tesis + ficha (2026-08-26)

> **Padre:** [ADR-036](../adr/036-decision-journal-study-view.md) · [ADR-029](../adr/029-order-proposal-decision-journal.md).
> **AsOf:** 2026-08-26 · tag vivo `v1.13-beta`.
> **Estado:** J0–J4 **CERRADOS**. **No** reabre DEX-1…DEX-5.

## Objetivo

Capa de presentación del Decision Spine para un usuario básico: pestaña **Tesis** (filtros + tabla + ficha) y pestaña **Historial técnico** (timeline actual). Sin nueva SoT.

## Fases

| ID  | Entrega                                                                    |
| --- | -------------------------------------------------------------------------- |
| J0  | Contrato `DecisionJournalStudyViewV1` + mapper + tests de honestidad WATCH |
| J1  | `GET /api/accounts/{id}/decision-studies` + UI tabla/filtros/tabs          |
| J2  | Ficha de decisión (split)                                                  |
| J3  | Mini gráfico de decisión (priceLines solo si geometría válida)             |
| J4  | Docs CURRENT_SYSTEM + relevo + contract:gen + regresión spine              |

## Fuera de alcance

UI Mesa incidente · Operational Console · Evolución de tesis · property DEX-5 · Confirm freeze.
