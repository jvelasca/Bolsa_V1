# Plan V1.18 L1 — Position lineage (decisionId)

> **AsOf:** 2026-08-27 · **Baseline:** tag `v1.17.1-beta`.
> **Padre:** [ADR-038](../adr/038-position-operational-memory.md) · [CURRENT_SYSTEM.md](../CURRENT_SYSTEM.md).
> **Estado:** implementación L1 (proyección) — sin Alembic / sin Confirm/DEX.

## Por qué este epic (vs Mesa residual / Stress / Opportunity)

Soft-join Journal por `instrumentId` puede atribuir **otra** tesis a la posición. Es mentira de memoria operativa (peor que copy UX). Stress MVP ≈ open risk; Opportunity arriesga BUY/score. Mesa residual sin origen correcto queda cosmética.

## Entrega L1

| Pieza                          | Qué                                                                       |
| ------------------------------ | ------------------------------------------------------------------------- |
| `resolvePositionOriginLineage` | Origen = `tradePlanId`/`decisionId`; orphan fail-closed                   |
| Aggregate                      | `originDecisionId` + `lineage`; `thesisSnapshot` solo si packageAvailable |
| `pickPositionStudies`          | origin por decisionId · evolution por instrumento                         |
| Mesa wire                      | Hoy / PositionsSummary / Route usan el pair                               |
| Docs                           | ADR-038 + CURRENT_SYSTEM                                                  |

## Freeze

Confirm · DEX-1…5 · `PAPER_D_EXECUTE` off · AUTO off · Stress stub · Opportunity · thaw · `contract:gen`.

## DoD

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run position-lineage investment-position-aggregate mesa-hoy-model
pnpm --filter @bolsa/web test -- mesa-hoy mesa-position
```

- Match por id → `packageAvailable`
- Study otro decisionId mismo instrumento → no thesisSnapshot
- Orphan ≠ inventar acción BUY
- `originalPlan` intacto (regresión H2)
