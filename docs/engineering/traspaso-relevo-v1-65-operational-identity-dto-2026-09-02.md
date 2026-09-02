# RELEVO — V1.65 Operational Identity & Canonical DTO (2026-09-02)

> **Padre:** [`spec-v165-operational-identity-dto-2026-09-02.md`](./spec-v165-operational-identity-dto-2026-09-02.md) · [`plan-v165-operational-identity-dto-2026-09-02.md`](./plan-v165-operational-identity-dto-2026-09-02.md) · partida **V1.64** (`cbe89c8`).  
> **Estado:** **CERRADA** (pre-flight local).  
> **Arranque auditor:** [`arranque-auditor-v1-65-operational-identity-dto-2026-09-02.md`](./arranque-auditor-v1-65-operational-identity-dto-2026-09-02.md).

---

## 0. Qué cierra

| Pieza                                                                     | Estado |
| ------------------------------------------------------------------------- | ------ |
| GP-V165-01 — `PositionState.decisionId` TS+Python                         | DONE   |
| GP-V165-02 — POV sin alias `tradePlanId→decisionId`                       | DONE   |
| GP-V165-03 — tests lineage DEC≠TP (POV · POT · revision · aggregate)      | DONE   |
| GP-V165-03b — alias fixes (propose-exit · mesa-hoy · Python persist/auto) | DONE   |
| GP-V165-04 — port Python `buildPositionOperationalView`                   | DONE   |
| GP-V165-05 — `OperationalPositionDto.decisionId` + `operationalView`      | DONE   |
| GP-V165-06 — hook prefer-wire                                             | DONE   |
| GP-V165-07 — GP-V162-04 test real                                         | DONE   |
| GP-V165-08 — CURRENT_SYSTEM V1.64 + V1.65                                 | DONE   |

V1.58–V1.64 intactos salvo identidad + DTO + test GP-V162-04 + docs.

## 1. Pre-flight (local, 2026-09-02)

| Suite                                    | Resultado      |
| ---------------------------------------- | -------------- |
| shared vitest GP-V165 block              | **102** passed |
| web vitest (hook · entry · propose-exit) | **28** passed  |
| pytest analytics + origin                | **28** passed  |
| pytest V1.59 integration                 | **7** passed   |
| tsc `@bolsa/shared` + `@bolsa/web`       | OK             |

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 3. Next

1. **V1.66** Why / Decision Explainability (determinista).
2. **V1.67** Browser E2E Mercado real + aislamiento DB.
3. **V1.68** Paper Autonomous Desk.
4. **NO LIVE** · LISTA→GRÁFICO→ACCIÓN (parked).
