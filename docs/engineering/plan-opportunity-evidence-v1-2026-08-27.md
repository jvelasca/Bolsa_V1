# Plan — OpportunityEvidence V1 (primera rebanada)

> **AsOf:** 2026-08-27 · **Baseline:** post `v1.17.1-beta` / HEAD con V1.18 L2a.
> **Padre:** [ADR-039](../adr/039-portfolio-scenario-operational-priority.md) · [RFC-008](../rfc/008-cognitive-decision-architecture.md) §3 Opportunity≠Permission · [CURRENT_SYSTEM.md](../CURRENT_SYSTEM.md).
> **Estado:** contrato + proyección + tests en `@bolsa/shared`.

## Por qué este epic

Operational Priority ya tiene Quality/Suitability/Operability, pero Quality está contaminada (TRIGGERED / hasPlan = Operability). Falta el contrato read-only **OpportunityEvidence** que responde solo _¿hay setup interesante?_ sin ser BUY ni permiso.

## Entrega (slice 1)

| Pieza                                        | Qué                                                                                                             |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `OpportunityEvidenceV1`                      | `symbol`, strength, expectedRR, factors, label, `qualityValue`, `provisional: true` — sin action/BUY/permission |
| `projectOpportunityEvidence`                 | Quality **pura** (strength + R/R); no usa TRIGGERED/hasPlan                                                     |
| `BestNextRProjectionV1` + `projectBestNextR` | Orden por expectedRewardR (`expectedRR × initialRiskR`); `impliesOperable: false`                               |
| Adapter fino                                 | `qualityScoreFromOpportunityEvidence` — bridge futuro; **no** cambia pesos 35/35/30                             |
| Docs                                         | ADR-039 Pending · este plan · CURRENT_SYSTEM una línea                                                          |

## Fuera de slice

- UI Mesa / Primary Action mega-rediseño
- Confirm / DEX / AUTO / `PAPER_D_EXECUTE`
- Renombrar Python `opportunity.py` / `build_opportunity_package`
- Cambiar pesos Priority ni quitar projection legacy
- Actionability v1 · Stress Risk · endpoint backend · `contract:gen`

## Freeze

Ranking ≠ BUY · Confirm = firma · Opportunity ≠ Permission · scenario ≠ permiso · `PAPER_D_EXECUTE` off · AUTO off · no score definitivo · LAB ≠ TRADING.

## DoD

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run opportunity-evidence operational-priority
```

- Evidencia ≠ BUY (sin campos action/permission)
- Quality alta + Suitability baja → Priority sigue `NO_OPERAR`
- Operability bloqueada no baja Opportunity
- Best-next-R no implica operable
